"""Foydalanuvchi botlarini ishga tushiruvchi servis (bot konstruktori).

Har bir faol bot uchun alohida long-polling sikli (getUpdates) — webhook/ochiq port kerak emas.
Menyu user_bots.menu'dan olinadi (core/botbuilder.py). API o'zgarish qilsa redis'dagi
`userbots:sync` hisoblagichini oshiradi — runner bir-ikki soniyada yangi menyuni oladi.

Holat redis'da (bot qayta ishga tushsa ham saqlanadi):
    ub:{bot}:cur:{chat}   — foydalanuvchi turgan sahifa (reply-tugmalarni topish uchun)
    ub:{bot}:nav:{chat}   — «Orqaga» uchun sahifalar tarixi
    ub:{bot}:st:{chat}    — "fb": keyingi xabar egasiga yuboriladi
    ub:{bot}:fb:{msg_id}  — egasiga yuborilgan xabar -> kimdan kelgani (egasi «reply» qilsa javob qaytadi)
    ub:{bot}:file:{media} — yuklangan rasmning file_id'si
"""

import asyncio
import dataclasses
import datetime
import html
import json
import logging
import random
import re
import uuid
from dataclasses import dataclass, field
from urllib.parse import quote

import httpx
from arq import create_pool
from arq.connections import RedisSettings
from redis.asyncio import Redis
from sqlalchemy import func, literal, select, update
from sqlalchemy.dialects.postgresql import JSONB, insert

from core import crypto
from core.botapi import BotApiError, call
from core.botbuilder import (
    CAPTIONLESS,
    OWNER_START_HINT,
    apply_op,
    check_cond,
    fill,
    form_by_id,
    html_to_plain,
    now_values,
    page_by_id,
    render_text,
)
from core.db.base import async_session
from core.db.models import BotFormAnswer, BotSubscriber, MediaFile, User, UserBot, WebApp
from core.entitlements import get_entitlement
from core.notify import send_telegram
from core.settings import settings
from core.webapp_url import discover_webapp_url

import admin
import ai_chat
import auto
import booking
import editor
import games
import home
import shop
import stats
import tickets

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logging.getLogger("httpx").setLevel(logging.WARNING)  # URL ichida token bor
logger = logging.getLogger("botrunner")

SYNC_KEY = "userbots:sync"
LEADER_KEY = "leader:botrunner"
LEADER_TTL = 30
CHECK_SECONDS = 2
FULL_SYNC_SECONDS = 30
POLL_TIMEOUT = 25
STATE_TTL = 30 * 24 * 3600
SEEN_THROTTLE = 600
NAV_DEPTH = 20
CANCEL_TEXT = "❌ Bekor qilish"
NAV_BACK = "⬅️ Orqaga"
NAV_HOME = "🏠 Bosh menyu"


def json_param(value: dict):
    return literal(value, type_=JSONB)


@dataclass
class RunningBot:
    bot_id: int
    user_id: int
    owner_chat_id: int | None
    token: str
    username: str
    name: str
    menu: dict
    branding: str | None
    # E'lon qilingan Web App manzili va bot menyu tugmasi (None — ilova yo'q yoki menyu tugmasi o'chiq)
    webapp_url: str | None = None
    menu_button: tuple | None = None
    menu_button_applied: tuple | None = field(default=None)
    # Bot darajasidagi (global) o'zgaruvchilar
    globals: dict = field(default_factory=dict)
    commands_applied: tuple | None = None
    # 🧪 Sinov rejimi: egasi AI taklifini sinayotganda ishlatiladigan nusxa (saqlash taqiqlangan)
    sandbox: bool = False
    origin: object = None
    task: asyncio.Task | None = None
    conflict_reported: bool = False
    pending: set = field(default_factory=set)


SHOP_CALLBACKS = {"sl", "si", "sa", "sk", "sz", "sx", "sm", "so"}


def _k(bot_id: int, kind: str, key) -> str:
    return f"ub:{bot_id}:{kind}:{key}"


class Runner:
    def __init__(self) -> None:
        self.redis = Redis.from_url(settings.redis_url or "redis://redis:6379")
        self.http = httpx.AsyncClient(timeout=POLL_TIMEOUT + 15, limits=httpx.Limits(max_connections=None, max_keepalive_connections=200))
        self.bots: dict[int, RunningBot] = {}
        self.instance_id = uuid.uuid4().hex
        self.platform_username: str | None = None
        self._arq = None

    async def arq(self):
        if self._arq is None:
            self._arq = await create_pool(RedisSettings.from_dsn(settings.redis_url or "redis://redis:6379"))
        return self._arq

    # --- Sinxronlash ---

    async def _platform_username(self) -> str | None:
        if self.platform_username is None and settings.bot_token:
            try:
                me = await call(self.http, settings.bot_token, "getMe")
                self.platform_username = me.get("username")
            except BotApiError:
                return None
        return self.platform_username

    async def _desired(self) -> dict[int, RunningBot]:
        platform = await self._platform_username()
        base = await discover_webapp_url()
        base = base.split("?")[0].rstrip("/") if base else None
        result: dict[int, RunningBot] = {}
        async with async_session() as db:
            apps = {
                a.bot_id: a
                for a in await db.scalars(select(WebApp).where(WebApp.published.is_not(None)))
            }
            rows = (
                await db.execute(
                    select(UserBot, User.telegram_user_id)
                    .join(User, User.id == UserBot.user_id)
                    .where(UserBot.status == "active", User.is_banned == False)  # noqa: E712
                    .order_by(UserBot.id)
                )
            ).all()
            per_user: dict[int, int] = {}
            ents: dict[int, object] = {}
            for bot, owner_chat in rows:
                if bot.user_id not in ents:
                    ents[bot.user_id] = await get_entitlement(db, bot.user_id)
                ent = ents[bot.user_id]
                per_user[bot.user_id] = per_user.get(bot.user_id, 0) + 1
                if per_user[bot.user_id] > ent.bot_limit:
                    continue  # tarif tushgan — eng eski botlar ishlayveradi
                try:
                    token = crypto.decrypt_packed(bot.token_encrypted)
                except Exception:  # noqa: BLE001
                    logger.exception("bot %s tokeni ochilmadi", bot.id)
                    continue
                branding = None if ent.flags.get("bot_no_branding") or not platform else f"🤖 @{platform} orqali yaratilgan"
                app = apps.get(bot.id)
                webapp_url = f"{base}/app/{app.id}" if app is not None and base else None
                result[bot.id] = RunningBot(
                    bot_id=bot.id, user_id=bot.user_id, owner_chat_id=owner_chat, token=token,
                    username=bot.username, name=bot.name, menu=bot.menu, branding=branding, globals=dict(bot.vars or {}),
                    webapp_url=webapp_url,
                    menu_button=(app.menu_button_text, webapp_url) if webapp_url and app.menu_button else None,
                )
        return result

    async def sync(self) -> None:
        desired = await self._desired()
        for bot_id in list(self.bots):
            if bot_id not in desired or desired[bot_id].token != self.bots[bot_id].token:
                await self.stop(bot_id)
        for bot_id, wanted in desired.items():
            running = self.bots.get(bot_id)
            if running is None:
                self.start(wanted)
            else:
                # Menyu/sozlamalar darhol yangilanadi, polling uzilmaydi.
                running.menu, running.branding, running.owner_chat_id = wanted.menu, wanted.branding, wanted.owner_chat_id
                running.username, running.name = wanted.username, wanted.name
                running.webapp_url, running.menu_button = wanted.webapp_url, wanted.menu_button
                running.globals = wanted.globals
                await self.apply_menu_button(running)
                await self.apply_commands(running)
                if running.task is not None and running.task.done():
                    self.bots.pop(bot_id, None)
                    self.start(wanted)

    async def apply_menu_button(self, bot: RunningBot) -> None:
        """Bot chatidagi menyu tugmasi: Web App e'lon qilingan bo'lsa — ilovani ochadi, aks holda buyruqlar ro'yxati."""
        if bot.menu_button_applied == (bot.menu_button,):
            return
        if bot.menu_button:
            text, url = bot.menu_button
            button = {"type": "web_app", "text": text, "web_app": {"url": url}}
        else:
            button = {"type": "commands"}
        try:
            await call(self.http, bot.token, "setChatMenuButton", {"menu_button": button})
            bot.menu_button_applied = (bot.menu_button,)
        except BotApiError as exc:
            logger.info("bot %s: menyu tugmasi o'rnatilmadi: %s", bot.bot_id, exc.description)

    async def apply_commands(self, bot: RunningBot) -> None:
        """Foydalanuvchilar uchun buyruqlar menyusi (/start + bot hujjatidagi buyruqlar)."""
        commands = [{"command": "start", "description": "Bosh menyu"}] + [
            {"command": c["command"], "description": (c.get("description") or c["command"])[:256]} for c in bot.menu.get("commands") or []
        ]
        sig = tuple((c["command"], c["description"]) for c in commands)
        if bot.commands_applied == sig:
            return
        try:
            await call(self.http, bot.token, "setMyCommands", {"commands": commands})
            bot.commands_applied = sig
            await admin.set_owner_commands(self, bot)
        except BotApiError as exc:
            logger.info("bot %s: buyruqlar o'rnatilmadi: %s", bot.bot_id, exc.description)

    def start(self, bot: RunningBot) -> None:
        bot.task = asyncio.create_task(self._poll(bot))
        self.bots[bot.bot_id] = bot
        logger.info("bot %s (@%s) ishga tushdi", bot.bot_id, bot.username)

    async def stop(self, bot_id: int) -> None:
        bot = self.bots.pop(bot_id, None)
        if bot is None:
            return
        if bot.task is not None:
            bot.task.cancel()
            try:
                await bot.task
            except (asyncio.CancelledError, Exception):  # noqa: BLE001
                pass
        logger.info("bot %s to'xtadi", bot_id)

    async def stop_all(self) -> None:
        for bot_id in list(self.bots):
            await self.stop(bot_id)

    # --- Polling ---

    async def _set_error(self, bot: RunningBot, message: str, *, stop: bool) -> None:
        async with async_session() as db:
            values = {"error_message": message}
            if stop:
                values["status"] = "error"
            await db.execute(update(UserBot).where(UserBot.id == bot.bot_id).values(**values))
            await db.commit()

    async def _poll(self, bot: RunningBot) -> None:
        offset: int | None = None
        delay = 2
        try:
            await call(self.http, bot.token, "deleteWebhook", {"drop_pending_updates": False})
        except BotApiError:
            pass
        await self.apply_commands(bot)
        await self.apply_menu_button(bot)
        while True:
            try:
                updates = await call(
                    self.http,
                    bot.token,
                    "getUpdates",
                    {"offset": offset, "timeout": POLL_TIMEOUT, "allowed_updates": ["message", "callback_query", "my_chat_member"]},
                )
                delay = 2
                if bot.conflict_reported:
                    bot.conflict_reported = False
                    await self._set_error(bot, None, stop=False)
            except asyncio.CancelledError:
                raise
            except BotApiError as exc:
                if exc.token_revoked:
                    logger.warning("bot %s: token bekor qilingan", bot.bot_id)
                    await self._set_error(bot, "Token bekor qilingan — @BotFather'dan yangi token olib, qayta ulang", stop=True)
                    if bot.owner_chat_id:
                        await send_telegram(
                            bot.owner_chat_id,
                            f"⚠️ @{bot.username} botingiz to'xtadi: token bekor qilingan.\n"
                            "@BotFather'dan yangi token olib, Studiya → Botlarim orqali qayta ulang.",
                        )
                    return
                if exc.code == 409:
                    # Token boshqa joyda ham ishlatilmoqda (boshqa dastur yoki webhook).
                    if not bot.conflict_reported:
                        bot.conflict_reported = True
                        await self._set_error(bot, "Bu bot boshqa dasturda ham ishga tushirilgan — uni o'chiring", stop=False)
                    try:
                        await call(self.http, bot.token, "deleteWebhook", {"drop_pending_updates": False})
                    except BotApiError:
                        pass
                wait = exc.retry_after or delay
                delay = min(delay * 2, 60)
                await asyncio.sleep(wait)
                continue
            except Exception:  # noqa: BLE001
                logger.exception("bot %s: getUpdates xatosi", bot.bot_id)
                await asyncio.sleep(delay)
                delay = min(delay * 2, 60)
                continue

            for upd in updates:
                offset = upd["update_id"] + 1
                try:
                    await self.handle(bot, upd)
                except asyncio.CancelledError:
                    raise
                except BotApiError as exc:
                    if not exc.user_blocked:
                        logger.warning("bot %s: update %s: %s", bot.bot_id, upd["update_id"], exc.description)
                except Exception:  # noqa: BLE001 — bitta update butun botni to'xtatmasin
                    logger.exception("bot %s: update %s qayta ishlanmadi", bot.bot_id, upd["update_id"])

    # --- Yordamchi ---

    async def api(self, bot: RunningBot, method: str, data: dict | None = None, files: dict | None = None):
        return await call(self.http, bot.token, method, data, files, timeout=30)

    def is_admin(self, bot: RunningBot, chat_id: int) -> bool:
        return chat_id == bot.owner_chat_id or chat_id in (bot.menu.get("admins") or [])

    def admin_chats(self, bot: RunningBot) -> list[int]:
        chats = [bot.owner_chat_id] if bot.owner_chat_id else []
        return chats + [a for a in bot.menu.get("admins") or [] if a not in chats]

    async def _touch(self, bot: RunningBot, user: dict, force: bool = False) -> bool:
        """Obunachini yozib qo'yadi. Yangi obunachi bo'lsa True qaytaradi."""
        if not force and not await self.redis.set(_k(bot.bot_id, "seen", user["id"]), "1", nx=True, ex=SEEN_THROTTLE):
            return False
        now = datetime.datetime.now(datetime.timezone.utc)
        async with async_session() as db:
            existed = await db.scalar(
                select(BotSubscriber.id).where(BotSubscriber.bot_id == bot.bot_id, BotSubscriber.tg_user_id == user["id"])
            )
            stmt = insert(BotSubscriber).values(
                bot_id=bot.bot_id, tg_user_id=user["id"], first_name=(user.get("first_name") or "")[:128],
                username=(user.get("username") or None), started_at=now, last_active_at=now, blocked=False,
            )
            stmt = stmt.on_conflict_do_update(
                constraint="uq_bot_subscriber",
                set_={"last_active_at": now, "blocked": False, "first_name": stmt.excluded.first_name, "username": stmt.excluded.username},
            )
            await db.execute(stmt)
            await db.commit()
        return existed is None

    async def _set_blocked(self, bot: RunningBot, chat_id: int, blocked: bool) -> None:
        async with async_session() as db:
            await db.execute(
                update(BotSubscriber).where(BotSubscriber.bot_id == bot.bot_id, BotSubscriber.tg_user_id == chat_id).values(blocked=blocked)
            )
            await db.commit()

    # --- O'zgaruvchilar ---

    async def subscriber(self, bot: RunningBot, user_id: int) -> dict:
        async with async_session() as db:
            row = (
                await db.execute(
                    select(BotSubscriber.data, BotSubscriber.ref_count, BotSubscriber.banned, BotSubscriber.referred_by).where(
                        BotSubscriber.bot_id == bot.bot_id, BotSubscriber.tg_user_id == user_id
                    )
                )
            ).first()
        if row is None:
            return {"data": {}, "ref_count": 0, "banned": False, "referred_by": None}
        return {"data": dict(row.data or {}), "ref_count": row.ref_count or 0, "banned": bool(row.banned), "referred_by": row.referred_by}

    def _scope(self, bot: RunningBot, key: str) -> str:
        for v in bot.menu.get("variables") or []:
            if v["key"] == key:
                return v.get("scope", "user")
        return "user"

    async def set_vars(self, bot: RunningBot, user_id: int, changes: dict[str, str]) -> None:
        """O'zgaruvchilarni saqlaydi: foydalanuvchiniki — obunachi yozuviga, globallari — botga."""
        user_vars = {k: v for k, v in changes.items() if self._scope(bot, k) == "user"}
        global_vars = {k: v for k, v in changes.items() if self._scope(bot, k) == "global"}
        async with async_session() as db:
            if user_vars:
                await db.execute(
                    update(BotSubscriber)
                    .where(BotSubscriber.bot_id == bot.bot_id, BotSubscriber.tg_user_id == user_id)
                    .values(data=BotSubscriber.data.op("||")(json_param(user_vars)))
                )
            if global_vars:
                await db.execute(update(UserBot).where(UserBot.id == bot.bot_id).values(vars=UserBot.vars.op("||")(json_param(global_vars))))
                bot.globals.update(global_vars)
            await db.commit()

    async def apply_ops(self, bot: RunningBot, user_id: int, ops: list[dict], vals: dict | None = None) -> dict[str, str]:
        if not ops:
            return {}
        vals = vals if vals is not None else await self.values(bot, {"id": user_id})
        changes: dict[str, str] = {}
        for op in ops:
            key = op["var"]
            cur = changes.get(key, vals.get(key))
            changes[key] = apply_op(cur, op.get("op", "set"), fill(op.get("value", ""), vals, escape=False))
        await self.set_vars(bot, user_id, changes)
        if vals is not None:
            vals.update(changes)
        return changes

    async def _subscribers_count(self, bot: RunningBot) -> int:
        cached = await self.redis.get(_k(bot.bot_id, "subs", "n"))
        if cached:
            return int(cached)
        async with async_session() as db:
            n = await db.scalar(select(func.count(BotSubscriber.id)).where(BotSubscriber.bot_id == bot.bot_id, BotSubscriber.blocked == False))  # noqa: E712
        await self.redis.set(_k(bot.bot_id, "subs", "n"), n or 0, ex=300)
        return n or 0

    async def values(self, bot: RunningBot, user: dict, sub: dict | None = None, *, need_subs: bool = False) -> dict[str, str]:
        sub = sub if sub is not None else await self.subscriber(bot, user["id"])
        name = user.get("first_name") or "do'stim"
        vals: dict[str, str] = {}
        for v in bot.menu.get("variables") or []:
            vals[v["key"]] = v.get("default", "")
        vals.update({k: str(v) for k, v in (bot.globals or {}).items()})
        vals.update({k: str(v) for k, v in sub["data"].items()})
        vals.update(now_values())
        vals.update(
            {
                "name": name,
                "first_name": name,
                "last_name": user.get("last_name") or "",
                "username": f"@{user['username']}" if user.get("username") else name,
                "user_id": str(user["id"]),
                "mention": f'<a href="tg://user?id={int(user["id"])}">{html.escape(name, quote=False)}</a>',
                "bot": bot.name,
                "bot_username": f"@{bot.username}",
                "ref_link": f"https://t.me/{bot.username}?start=r{user['id']}",
                "ref_count": str(sub["ref_count"]),
            }
        )
        if need_subs:
            vals["subscribers"] = str(await self._subscribers_count(bot))
        if (bot.menu.get("shop") or {}).get("items"):
            vals.update(await shop.cart_values(self, bot, user["id"]))
        return vals

    # --- Sahifani yuborish ---
    #
    # MenuBuilder modeli: «menyu» — klaviatura tugmalari bor sahifa (reply). Tugmasi yo'q sahifa — «barg»:
    # bosilganda faqat postlari yuboriladi, klaviatura o'zgarmaydi. Har bir postning o'z inline tugmalari bo'lishi
    # mumkin. «Savol» posti foydalanuvchidan javob kutadi va o'zgaruvchiga saqlaydi. Eski «inline» sahifalar
    # (keyboard="inline") avvalgidek ishlaydi.

    @staticmethod
    def is_menu(page: dict) -> bool:
        return page.get("keyboard") == "reply" and bool(page.get("buttons"))

    def _visible(self, bot: RunningBot, page: dict, vals: dict, admin: bool, rows_src: list | None = None, *, editing: bool = False) -> list[list[tuple[int, int, dict]]]:
        rows = []
        for r, row in enumerate(page.get("buttons") or [] if rows_src is None else rows_src):
            line = []
            for c, b in enumerate(row):
                if not editing:
                    if b.get("action") == "webapp" and not bot.webapp_url:
                        continue
                    if b.get("hidden"):
                        continue
                    if b.get("admin_only") and not admin:
                        continue
                    if not check_cond(b.get("cond"), vals):
                        continue
                line.append((r, c, b))
            if line:
                rows.append(line)
        return rows

    @staticmethod
    def label(b: dict, vals: dict) -> str:
        return fill(b["text"], vals, escape=False)[:64]

    def inline_rows(self, bot: RunningBot, page: dict, vals: dict, admin: bool, rows_src: list, prefix: str) -> list:
        out = []
        for row in self._visible(bot, page, vals, admin, rows_src):
            line = []
            for r, c, b in row:
                a, t = b["action"], self.label(b, vals)
                if a == "url":
                    line.append({"text": t, "url": fill(b["url"], vals, escape=False)})
                elif a == "webapp":
                    line.append({"text": t, "web_app": {"url": bot.webapp_url}})
                elif a == "share":
                    text = fill(b.get("share_text") or "{ref_link}", vals, escape=False)
                    link = vals.get("ref_link", "")
                    line.append({"text": t, "url": f"https://t.me/share/url?url={quote(link)}&text={quote(text.replace(link, '').strip())}"})
                elif a == "page" and not b.get("need_sub"):
                    line.append({"text": t, "callback_data": f"p:{b['target']}"})
                elif a in ("back", "home", "feedback") and not b.get("need_sub"):
                    line.append({"text": t, "callback_data": {"back": "b", "home": "h", "feedback": "f"}[a]})
                else:
                    line.append({"text": t, "callback_data": f"{prefix}:{r}:{c}"})
            out.append(line)
        return out

    def reply_rows(self, bot: RunningBot, page: dict, vals: dict, admin: bool, *, editing: bool = False, selected: tuple | None = None) -> list:
        rows = []
        if page.get("keyboard") != "reply":
            # inline bo'lim: tugmalari xabar ostida; muharrirda — faqat navigatsiya
            if editing and page["id"] != bot.menu.get("start"):
                rows.append([{"text": NAV_BACK}, {"text": NAV_HOME}])
            return rows
        for row in self._visible(bot, page, vals, admin, editing=editing):
            line = []
            for r, c, b in row:
                t = self.label(b, vals)
                if editing:
                    line.append({"text": f"[ {t} ]"[:64] if selected == (page["id"], r, c) else t})
                    continue
                item: dict = {"text": t}
                if b["action"] == "webapp":
                    item["web_app"] = {"url": bot.webapp_url}
                elif b["action"] == "contact":
                    item["request_contact"] = True
                elif b["action"] == "location":
                    item["request_location"] = True
                line.append(item)
            rows.append(line)
        if page["id"] != bot.menu.get("start") and (page.get("nav") or editing):
            rows.append([{"text": NAV_BACK}, {"text": NAV_HOME}])
        return rows

    async def menu_markup(self, bot: RunningBot, chat_id: int, page: dict, vals: dict) -> dict | None:
        """Menyu sahifasining klaviaturasi (adminlarga — muharrir tugmalari bilan)."""
        admin = self.is_admin(bot, chat_id)
        mode = await editor.mode(self, bot, chat_id) if admin else None
        selected = await editor.selected(self, bot, chat_id) if mode == "buttons" else None
        rows = self.reply_rows(bot, page, vals, admin, editing=mode is not None, selected=selected)
        if admin:
            rows += await editor.admin_rows(self, bot, chat_id, mode)
        if not rows:
            return {"remove_keyboard": True} if page["id"] == bot.menu.get("start") else None
        markup = {"keyboard": rows, "resize_keyboard": True, "is_persistent": True}
        if page.get("placeholder") and not mode:
            markup["input_field_placeholder"] = fill(page["placeholder"], vals, escape=False)[:64]
        return markup

    def keyboard(self, bot: RunningBot, page: dict, vals: dict, admin: bool = False) -> dict | None:
        """Oddiy (adminsiz) klaviatura — sinov va eski kod uchun."""
        if page.get("keyboard") == "reply":
            rows = self.reply_rows(bot, page, vals, admin)
            return {"keyboard": rows, "resize_keyboard": True, "is_persistent": True} if rows else None
        rows = self.inline_rows(bot, page, vals, admin, page.get("buttons") or [], f"x:{page['id']}")
        return {"inline_keyboard": rows} if rows else None

    async def _photo_arg(self, bot: RunningBot, media_id: int) -> tuple[dict, dict | None]:
        cached = await self.redis.get(_k(bot.bot_id, "file", media_id))
        if cached:
            return {"photo": cached.decode()}, None
        async with async_session() as db:
            media = await db.get(MediaFile, media_id)
        if media is None:
            return {}, None
        return {}, {"photo": ("photo.jpg", media.data, media.mime)}

    def page_msgs(self, bot: RunningBot, page: dict, vals: dict, user: dict, *, with_branding: bool = False, start: int = 0) -> list[dict]:
        """Sahifaning postlari (start — savoldan keyin davom ettirish uchun)."""
        if page.get("messages"):
            msgs = [dict(m, text=fill(m.get("text") or "", vals, escape=True), html=True, idx=i) for i, m in enumerate(page["messages"])][start:]
            if page.get("random_post") and start == 0:
                plain = [m for m in msgs if m["type"] != "question"]
                if len(plain) > 1:
                    msgs = [random.choice(plain)]
            brand = html.escape(bot.branding, quote=False) if with_branding and bot.branding else None
        else:
            text = render_text(page["text"], name=user.get("first_name"), username=user.get("username"), bot=bot.name)
            text = fill(text, vals, escape=False)
            msgs = [{"type": "photo" if page.get("media_id") else "text", "text": text, "media_id": page.get("media_id"), "file_id": None, "html": False, "idx": None}]
            brand = bot.branding if with_branding and bot.branding else None
        if brand and msgs and msgs[-1]["type"] != "question":
            last = msgs[-1]
            if last["type"] in CAPTIONLESS:
                msgs.append({"type": "text", "text": brand, "html": last.get("html", False), "file_id": None, "media_id": None, "idx": None})
            else:
                limit = 4096 if last["type"] == "text" else 1024
                last["text"] = f"{last['text'][: limit - len(brand) - 2]}\n\n{brand}"
        return msgs

    async def send_one(self, bot: RunningBot, chat_id: int, m: dict, markup: dict | None, *, protect: bool = False, edit: dict | None = None) -> dict | None:
        base: dict = {"chat_id": chat_id}
        if markup:
            base["reply_markup"] = markup
        if protect:
            base["protect_content"] = True
        parse = {"parse_mode": "HTML"} if m.get("html") else {}
        kind = m["type"]
        if kind == "text":
            if edit is not None and (markup is None or "inline_keyboard" in markup):
                try:
                    return await self.api(
                        bot,
                        "editMessageText",
                        {"chat_id": chat_id, "message_id": edit["message_id"], "text": m["text"][:4096] or "…", "disable_web_page_preview": True,
                         "reply_markup": markup or {"inline_keyboard": []}, **parse},
                    )
                except BotApiError as exc:
                    if "not modified" in exc.description:
                        return None
            return await self.api(bot, "sendMessage", {**base, "text": m["text"][:4096] or "…", "disable_web_page_preview": True, **parse})
        caption = {"caption": m["text"][:1024], **parse} if kind not in CAPTIONLESS and m.get("text") else {}
        if kind == "photo" and not m.get("file_id"):
            photo, files = await self._photo_arg(bot, m["media_id"]) if m.get("media_id") else ({}, None)
            if not photo and not files:
                return await self.api(bot, "sendMessage", {**base, "text": m.get("text") or "…", **parse})
            result = await self.api(bot, "sendPhoto", {**base, **caption, **photo}, files)
            if files:
                await self.redis.set(_k(bot.bot_id, "file", m["media_id"]), result["photo"][-1]["file_id"], ex=STATE_TTL)
            return result
        method = "send" + {"video_note": "VideoNote"}.get(kind, kind.capitalize())
        return await self.api(bot, method, {**base, kind: m["file_id"], **caption})

    async def deliver(
        self, bot: RunningBot, chat_id: int, page: dict, user: dict, vals: dict, *,
        message: dict | None = None, with_branding: bool = False, start: int = 0, restore: bool = False,
    ) -> None:
        """Sahifa postlarini ketma-ket yuboradi; menyu bo'lsa — klaviaturasi bilan."""
        admin = self.is_admin(bot, chat_id)
        if admin and start == 0 and await editor.mode(self, bot, chat_id) == "posts":
            await editor.show_posts(self, bot, chat_id, page, user)
            return
        if page.get("module") and start == 0 and (
            await shop.render_module(self, bot, chat_id, page, vals, message=message)
            or await booking.render_module(self, bot, chat_id, page, vals, message=message)
            or await games.render_module(self, bot, chat_id, page, vals, message=message)
        ):
            return
        msgs = self.page_msgs(bot, page, vals, user, with_branding=with_branding, start=start)
        legacy_inline = page.get("keyboard") != "reply"
        reply = None
        if not legacy_inline or (admin and page["id"] == bot.menu.get("start")):
            if self.is_menu(page) or page["id"] == bot.menu.get("start"):
                reply = await self.menu_markup(bot, chat_id, page, vals)
            elif restore:
                cur = await self.current_page(bot, chat_id)
                reply = await self.menu_markup(bot, chat_id, cur, vals) if cur else None
        reply_sent = False
        protect = bool(page.get("protect"))
        edit = message if message is not None and len(msgs) == 1 and "text" in message else None
        for k, m in enumerate(msgs):
            if m["type"] == "question":
                await self.ask_question(bot, chat_id, page, m)
                return
            last = k == len(msgs) - 1
            inline = self.inline_rows(bot, page, vals, admin, m.get("buttons") or [], f"y:{page['id']}:{m['idx']}") if m.get("buttons") else []
            if last and legacy_inline:
                inline = inline + self.inline_rows(bot, page, vals, admin, page.get("buttons") or [], f"x:{page['id']}")
            markup = {"inline_keyboard": inline} if inline else None
            if last and reply and not inline:
                markup, reply_sent = reply, True
            await self.send_one(bot, chat_id, m, markup, protect=protect, edit=edit if markup is None or "inline_keyboard" in markup else None)
        if reply and not reply_sent:
            await self.api(bot, "sendMessage", {"chat_id": chat_id, "text": f"📂 {page['title']}" if msgs else "✅", "reply_markup": reply})

    async def send_page(self, bot: RunningBot, chat_id: int, page: dict, user: dict, *, with_branding: bool = False, vals: dict | None = None) -> None:
        vals = vals if vals is not None else await self.values(bot, user, need_subs=self._needs_subs(page))
        await self.deliver(bot, chat_id, page, user, vals, with_branding=with_branding)

    @staticmethod
    def _needs_subs(page: dict) -> bool:
        return "{subscribers}" in page.get("text", "") or any("{subscribers}" in (m.get("text") or "") for m in page.get("messages") or [])

    async def _on_open(self, bot: RunningBot, chat_id: int, page: dict, user: dict, vals: dict) -> None:
        if page.get("ops"):
            await self.apply_ops(bot, user["id"], page["ops"], vals)
        if page.get("notify") and not self.is_admin(bot, chat_id):
            who = user.get("first_name") or "Foydalanuvchi"
            if user.get("username"):
                who += f" (@{user['username']})"
            for admin_chat in self.admin_chats(bot):
                try:
                    await self.api(bot, "sendMessage", {"chat_id": admin_chat, "text": f"👁 {who} [{user['id']}] «{page['title']}» bo'limini ochdi"})
                except BotApiError:
                    pass

    async def enter(self, bot: RunningBot, chat_id: int, page: dict, *, push: bool = True) -> None:
        """Joriy menyuni o'zgartiradi (Orqaga uchun tarix bilan)."""
        cur_key, nav_key = _k(bot.bot_id, "cur", chat_id), _k(bot.bot_id, "nav", chat_id)
        current = await self.redis.get(cur_key)
        current = current.decode() if current else None
        if push and current and current != page["id"]:
            await self.redis.rpush(nav_key, current)
            await self.redis.ltrim(nav_key, -NAV_DEPTH, -1)
            await self.redis.expire(nav_key, STATE_TTL)
        await self.redis.set(cur_key, page["id"], ex=STATE_TTL)

    async def open_page(self, bot: RunningBot, chat_id: int, page_id: str, user: dict, *, message: dict | None = None, push: bool = True) -> None:
        page = page_by_id(bot.menu, page_id) or page_by_id(bot.menu, bot.menu.get("start"))
        if page is None:
            return
        # Menyu (yoki eski inline sahifa) — joriy joy o'zgaradi; «barg» — faqat postlari chiqadi
        inav, leaf = _k(bot.bot_id, "inav", chat_id), _k(bot.bot_id, "leaf", chat_id)
        if self.is_menu(page) or page["id"] == bot.menu.get("start"):
            await self.enter(bot, chat_id, page, push=push)
            await self.redis.delete(inav, leaf)
        else:
            # Post ostidagi tugmalar orqali yurish tarixi (inline «⬅️ Orqaga» uchun)
            if message is not None and push:
                prev = await self.redis.get(leaf)
                if prev and prev.decode() != page["id"]:
                    await self.redis.rpush(inav, prev)
                    await self.redis.ltrim(inav, -NAV_DEPTH, -1)
                    await self.redis.expire(inav, STATE_TTL)
            await self.redis.set(leaf, page["id"], ex=STATE_TTL)
        vals = await self.values(bot, user, need_subs=self._needs_subs(page))
        await self._on_open(bot, chat_id, page, user, vals)
        await stats.track(self, bot, f"page:{page['id']}")
        await self.deliver(bot, chat_id, page, user, vals, message=message)

    async def show_page(self, bot: RunningBot, chat_id: int, page: dict, user: dict, vals: dict, *, message: dict | None = None) -> None:
        await self.deliver(bot, chat_id, page, user, vals, message=message)

    # --- Postdagi savol ---

    async def ask_question(self, bot: RunningBot, chat_id: int, page: dict, m: dict) -> None:
        await self.redis.set(_k(bot.bot_id, "q", chat_id), json.dumps({"p": page["id"], "i": m["idx"]}), ex=STATE_TTL)
        rows: list[list[dict]] = []
        kind = m.get("input", "text")
        if kind == "choice":
            opts = m.get("options") or []
            rows = [[{"text": o} for o in opts[i : i + 2]] for i in range(0, len(opts), 2)]
        elif kind == "phone":
            rows = [[{"text": "📱 Raqamni yuborish", "request_contact": True}]]
        elif kind == "location":
            rows = [[{"text": "📍 Joylashuvni yuborish", "request_location": True}]]
        rows.append([{"text": CANCEL_TEXT}])
        await self.api(
            bot,
            "sendMessage",
            {"chat_id": chat_id, "text": m["text"] or "❓", "parse_mode": "HTML", "reply_markup": {"keyboard": rows, "resize_keyboard": True}},
        )

    async def on_question(self, bot: RunningBot, chat_id: int, message: dict, user: dict, state: dict) -> None:
        page = page_by_id(bot.menu, state.get("p"))
        msgs = (page or {}).get("messages") or []
        i = state.get("i")
        if page is None or i is None or i >= len(msgs) or msgs[i].get("type") != "question":
            await self.redis.delete(_k(bot.bot_id, "q", chat_id))
            return
        q = msgs[i]
        vals = await self.values(bot, user)
        if (message.get("text") or "").strip() in (CANCEL_TEXT, "/cancel"):
            await self.redis.delete(_k(bot.bot_id, "q", chat_id))
            cur = await self.current_page(bot, chat_id)
            markup = await self.menu_markup(bot, chat_id, cur, vals) if cur else None
            await self.api(bot, "sendMessage", {"chat_id": chat_id, "text": "❌ Bekor qilindi.", "reply_markup": markup or {"remove_keyboard": True}})
            return
        value, error = self._form_answer({"type": q.get("input", "text"), "options": q.get("options") or []}, message)
        if value is None:
            await self.api(bot, "sendMessage", {"chat_id": chat_id, "text": error})
            return
        await self.redis.delete(_k(bot.bot_id, "q", chat_id))
        await self.set_vars(bot, user["id"], {q["var"]: value})
        vals[q["var"]] = value
        if i + 1 >= len(msgs):
            cur = page if self.is_menu(page) else await self.current_page(bot, chat_id)
            markup = await self.menu_markup(bot, chat_id, cur, vals) if cur else None
            await self.api(bot, "sendMessage", {"chat_id": chat_id, "text": "✅ Qabul qilindi", "reply_markup": markup or {"remove_keyboard": True}})
            return
        await self.deliver(bot, chat_id, page, user, vals, start=i + 1, restore=True)

    async def current_page(self, bot: RunningBot, chat_id: int) -> dict | None:
        current = await self.redis.get(_k(bot.bot_id, "cur", chat_id))
        return page_by_id(bot.menu, current.decode() if current else None) or page_by_id(bot.menu, bot.menu.get("start"))

    async def go_back(self, bot: RunningBot, chat_id: int, user: dict, message: dict | None) -> None:
        previous = await self.redis.rpop(_k(bot.bot_id, "nav", chat_id))
        target = previous.decode() if previous else bot.menu.get("start")
        await self.open_page(bot, chat_id, target, user, message=message, push=False)

    async def go_home(self, bot: RunningBot, chat_id: int, user: dict, message: dict | None) -> None:
        await self.redis.delete(_k(bot.bot_id, "nav", chat_id))
        await self.open_page(bot, chat_id, bot.menu.get("start"), user, message=message, push=False)

    async def ask_feedback(self, bot: RunningBot, chat_id: int) -> None:
        await self.redis.set(_k(bot.bot_id, "st", chat_id), "fb", ex=3600)
        await self.api(bot, "sendMessage", {"chat_id": chat_id, "text": bot.menu.get("feedback_prompt") or "✍️ Xabaringizni yozing."})

    async def answer(self, bot: RunningBot, query_id: str | None, text: str = "", alert: bool = False) -> None:
        if not query_id:
            return
        try:
            await self.api(bot, "answerCallbackQuery", {"callback_query_id": query_id, "text": text[:200] or None, "show_alert": alert or None})
        except BotApiError:
            pass

    # --- Tugma amallari ---

    async def run_action(
        self, bot: RunningBot, chat_id: int, button: dict, user: dict, message: dict | None, *, query_id: str | None = None
    ) -> None:
        action = button["action"]
        target = button.get("target")
        if button.get("need_sub") and not self.is_admin(bot, chat_id):
            missing = await self.missing_channels(bot, user["id"], fresh=True)
            if missing:
                await self.answer(bot, query_id, "❗ Avval kanallarga obuna bo'ling", alert=True)
                await self.ask_subscribe(bot, chat_id, missing)
                return
        if action == "page":
            await self.answer(bot, query_id)
            await self.open_page(bot, chat_id, target, user, message=message)
        elif action == "back":
            await self.answer(bot, query_id)
            await self.go_back(bot, chat_id, user, message)
        elif action == "home":
            await self.answer(bot, query_id)
            await self.go_home(bot, chat_id, user, message)
        elif action == "feedback":
            await self.answer(bot, query_id)
            await self.ask_feedback(bot, chat_id)
        elif action == "alert":
            vals = await self.values(bot, user)
            await self.answer(bot, query_id, html_to_plain(fill(button["alert"], vals, escape=False)), alert=True)
        elif action == "form":
            await self.answer(bot, query_id)
            await self.start_form(bot, chat_id, button["form"], user)
        elif action == "set":
            vals = await self.values(bot, user)
            await self.apply_ops(bot, user["id"], [{"var": button["var"], "op": button.get("op", "set"), "value": button.get("value", "")}], vals)
            if button.get("alert"):
                await self.answer(bot, query_id, html_to_plain(fill(button["alert"], vals, escape=False)), alert=False)
            else:
                await self.answer(bot, query_id, "✅")
            if target:
                await self.open_page(bot, chat_id, target, user, message=message)
            else:
                page = await self.current_page(bot, chat_id)
                if page is not None:
                    await self.show_page(bot, chat_id, page, user, vals, message=message)
        elif action == "share":
            await self.answer(bot, query_id)
            vals = await self.values(bot, user)
            text = fill(button.get("share_text") or "{ref_link}", vals, escape=False)
            link = vals["ref_link"]
            await self.api(
                bot,
                "sendMessage",
                {
                    "chat_id": chat_id,
                    "text": text if link in text else f"{text}\n{link}",
                    "reply_markup": {"inline_keyboard": [[{"text": "📤 Ulashish", "url": f"https://t.me/share/url?url={quote(link)}"}]]},
                },
            )
        elif action == "check_sub":
            missing = await self.missing_channels(bot, user["id"], fresh=True)
            if missing:
                await self.answer(bot, query_id, "❗ Avval kanallarga obuna bo'ling", alert=True)
                await self.ask_subscribe(bot, chat_id, missing)
            else:
                await self.answer(bot, query_id, "✅ Rahmat!")
                await self.open_page(bot, chat_id, target or bot.menu.get("start"), user, message=message)
        elif action in ("contact", "location"):
            await self.answer(bot, query_id)
            await self.redis.set(_k(bot.bot_id, "ask", chat_id), json.dumps({"var": button["var"], "kind": action, "target": target}), ex=3600)
            request = {"request_contact": True} if action == "contact" else {"request_location": True}
            await self.api(
                bot,
                "sendMessage",
                {
                    "chat_id": chat_id,
                    "text": "📱 Telefon raqamingizni yuborish uchun pastdagi tugmani bosing." if action == "contact" else "📍 Joylashuvingizni yuborish uchun pastdagi tugmani bosing.",
                    "reply_markup": {
                        "keyboard": [[{"text": button["text"] if len(button["text"]) > 2 else "📱 Yuborish", **request}], [{"text": CANCEL_TEXT}]],
                        "resize_keyboard": True,
                        "one_time_keyboard": True,
                    },
                },
            )
        elif action == "notify":
            vals = await self.values(bot, user)
            note = fill(button.get("alert") or "", vals, escape=False)
            who = user.get("first_name") or "Foydalanuvchi"
            if user.get("username"):
                who += f" (@{user['username']})"
            for admin_chat in self.admin_chats(bot):
                try:
                    await self.api(bot, "sendMessage", {"chat_id": admin_chat, "text": f"🔔 {who} [{user['id']}] «{button['text']}» tugmasini bosdi" + (f"\n\n{note}" if note else "")})
                except BotApiError:
                    pass
            await self.answer(bot, query_id, "✅ Yuborildi")
            if target:
                await self.open_page(bot, chat_id, target, user, message=message)
            elif not query_id:
                await self.api(bot, "sendMessage", {"chat_id": chat_id, "text": "✅ Yuborildi"})
        elif action == "random":
            await self.answer(bot, query_id)
            await self.open_page(bot, chat_id, random.choice(button["targets"]), user, message=message)
        else:
            await self.answer(bot, query_id)

    def _button_at(self, bot: RunningBot, page_id: str, r: int, c: int) -> dict | None:
        page = page_by_id(bot.menu, page_id)
        try:
            return page["buttons"][r][c] if page else None
        except (IndexError, KeyError):
            return None

    # --- Majburiy obuna ---

    async def missing_channels(self, bot: RunningBot, user_id: int, *, fresh: bool = False) -> list[dict]:
        channels = bot.menu.get("channels") or []
        if not channels:
            return []
        ok_key = _k(bot.bot_id, "subok", user_id)
        if not fresh and await self.redis.get(ok_key):
            return []
        missing = []
        for ch in channels:
            try:
                member = await self.api(bot, "getChatMember", {"chat_id": ch["chat"], "user_id": user_id})
                status = member.get("status")
                if status in ("left", "kicked") or (status == "restricted" and not member.get("is_member")):
                    missing.append(ch)
            except BotApiError as exc:
                # Bot kanalda admin emas — foydalanuvchini bloklab qo'ymaymiz, egasini ogohlantiramiz (kuniga bir marta)
                if await self.redis.set(_k(bot.bot_id, "subwarn", ch["chat"]), "1", nx=True, ex=86400):
                    for admin_chat in self.admin_chats(bot):
                        try:
                            await self.api(
                                bot,
                                "sendMessage",
                                {"chat_id": admin_chat, "text": f"⚠️ {ch['chat']} kanalida obunani tekshirib bo'lmadi: botni kanalga admin qiling.\n({exc.description})"},
                            )
                        except BotApiError:
                            pass
        if not missing:
            await self.redis.set(ok_key, "1", ex=600)
        return missing

    async def ask_subscribe(self, bot: RunningBot, chat_id: int, missing: list[dict]) -> None:
        rows = [[{"text": f"➕ {ch.get('title') or ch['chat']}", "url": ch["url"]}] for ch in missing if ch.get("url")]
        rows.append([{"text": "✅ Tekshirish", "callback_data": "sub"}])
        await self.api(bot, "sendMessage", {"chat_id": chat_id, "text": bot.menu.get("sub_text") or "📢 Kanallarga obuna bo'ling", "reply_markup": {"inline_keyboard": rows}})

    # --- Formalar ---

    @staticmethod
    def form(bot: RunningBot, form_id: str) -> dict | None:
        if form_id == shop.CHECKOUT_ID:
            return shop.checkout_form(bot)
        if form_id == booking.BOOKING_ID:
            return booking.booking_form(bot)
        return form_by_id(bot.menu, form_id)

    async def start_form(self, bot: RunningBot, chat_id: int, form_id: str, user: dict) -> None:
        form = self.form(bot, form_id)
        if form is None:
            return
        await self.redis.set(_k(bot.bot_id, "form", chat_id), json.dumps({"form": form_id, "step": 0, "data": {}}), ex=STATE_TTL)
        await self.ask_step(bot, chat_id, form, 0, user)

    async def ask_step(self, bot: RunningBot, chat_id: int, form: dict, index: int, user: dict) -> None:
        step = form["steps"][index]
        vals = await self.values(bot, user)
        rows: list[list[dict]] = []
        if step["type"] == "choice":
            opts = step.get("options") or []
            rows = [opts[i : i + 2] for i in range(0, len(opts), 2)]
            rows = [[{"text": o} for o in row] for row in rows]
        elif step["type"] in ("phone", "contact"):
            rows = [[{"text": "📱 Raqamni yuborish", "request_contact": True}]]
        elif step["type"] == "location":
            rows = [[{"text": "📍 Joylashuvni yuborish", "request_location": True}]]
        rows.append([{"text": CANCEL_TEXT}])
        progress = f"<i>{index + 1}/{len(form['steps'])}</i>\n" if len(form["steps"]) > 1 else ""
        await self.api(
            bot,
            "sendMessage",
            {
                "chat_id": chat_id,
                "text": progress + fill(step["question"], vals, escape=True),
                "parse_mode": "HTML",
                "reply_markup": {"keyboard": rows, "resize_keyboard": True, "one_time_keyboard": step["type"] == "choice"},
            },
        )

    def _form_answer(self, step: dict, message: dict) -> tuple[str | None, str | None]:
        """(qiymat, xato). Qiymat None bo'lsa — xato matni qaytariladi."""
        text = (message.get("text") or "").strip()
        kind = step["type"]
        if kind in ("phone", "contact"):
            if message.get("contact"):
                return message["contact"].get("phone_number", ""), None
            if kind == "phone" and re.match(r"^\+?[0-9 ()-]{7,20}$", text):
                return text, None
            return None, "📱 Telefon raqamini to'g'ri kiriting yoki tugmani bosing"
        if kind == "location":
            loc = message.get("location")
            if loc:
                return f"{loc['latitude']:.6f},{loc['longitude']:.6f}", None
            return None, "📍 Joylashuvni tugma orqali yuboring"
        if kind == "photo":
            if message.get("photo"):
                return message["photo"][-1]["file_id"], None
            return None, "🖼 Rasm yuboring"
        if not text:
            return None, "✍️ Javobni matn ko'rinishida yozing"
        if kind == "number":
            try:
                float(text.replace(",", ".").replace(" ", ""))
            except ValueError:
                return None, "🔢 Son kiriting"
        if kind == "email" and not re.match(r"^[^@\s]+@[^@\s]+\.[A-Za-z]{2,}$", text):
            return None, "📧 Email manzilini to'g'ri kiriting"
        if kind == "choice" and text not in (step.get("options") or []):
            return None, "👇 Variantlardan birini tanlang"
        return text[:1000], None

    async def on_form_message(self, bot: RunningBot, chat_id: int, message: dict, user: dict, state: dict) -> None:
        form = self.form(bot, state["form"])
        if form is None or state["step"] >= len(form["steps"]):
            await self.redis.delete(_k(bot.bot_id, "form", chat_id))
            return
        if (message.get("text") or "").strip() in (CANCEL_TEXT, "/cancel"):
            await self.redis.delete(_k(bot.bot_id, "form", chat_id))
            await self.api(bot, "sendMessage", {"chat_id": chat_id, "text": "❌ Bekor qilindi.", "reply_markup": {"remove_keyboard": True}})
            page = await self.current_page(bot, chat_id)
            if page is not None:
                await self.send_page(bot, chat_id, page, user)
            return
        step = form["steps"][state["step"]]
        value, error = self._form_answer(step, message)
        if value is None:
            await self.api(bot, "sendMessage", {"chat_id": chat_id, "text": error})
            return
        state["data"][step["key"]] = value
        state["step"] += 1
        if state["step"] < len(form["steps"]):
            await self.redis.set(_k(bot.bot_id, "form", chat_id), json.dumps(state), ex=STATE_TTL)
            await self.ask_step(bot, chat_id, form, state["step"], user)
            return
        await self.redis.delete(_k(bot.bot_id, "form", chat_id))
        await self.finish_form(bot, chat_id, form, state["data"], user)

    async def finish_form(self, bot: RunningBot, chat_id: int, form: dict, data: dict, user: dict) -> None:
        if form["id"] == shop.CHECKOUT_ID:
            await shop.create_order(self, bot, chat_id, user, data)
            return
        if form["id"] == booking.BOOKING_ID:
            await booking.finish(self, bot, chat_id, user, data)
            return
        await self.set_vars(bot, user["id"], data)
        await stats.track(self, bot, f"form:{form['id']}")
        async with async_session() as db:
            db.add(BotFormAnswer(bot_id=bot.bot_id, tg_user_id=user["id"], form_id=form["id"], data=data))
            await db.commit()
        vals = await self.values(bot, user)
        await self.api(
            bot,
            "sendMessage",
            {"chat_id": chat_id, "text": fill(form.get("done_text") or "✅ Qabul qilindi", vals, escape=True), "parse_mode": "HTML", "reply_markup": {"remove_keyboard": True}},
        )
        if form.get("notify", True):
            who = html.escape(user.get("first_name") or "Foydalanuvchi", quote=False)
            if user.get("username"):
                who += f" (@{user['username']})"
            lines = [f"📝 <b>{html.escape(form['title'], quote=False)}</b>", f"👤 {who} · <code>{user['id']}</code>", ""]
            photos = []
            for step in form["steps"]:
                value = data.get(step["key"], "")
                if step["type"] == "photo":
                    photos.append(value)
                    value = "🖼 (rasm pastda)"
                elif step["type"] == "location" and value:
                    value = f'<a href="https://maps.google.com/?q={value}">📍 xaritada</a>'
                else:
                    value = html.escape(str(value), quote=False)
                lines.append(f"<b>{html.escape(html_to_plain(step['question'])[:60], quote=False)}</b>\n{value}")
            for admin_chat in self.admin_chats(bot):
                try:
                    head = await self.api(bot, "sendMessage", {"chat_id": admin_chat, "text": "\n".join(lines)[:4096], "parse_mode": "HTML", "disable_web_page_preview": True})
                    await self.redis.set(_k(bot.bot_id, "fb", f"{admin_chat}:{head['message_id']}"), chat_id, ex=STATE_TTL)
                    for file_id in photos:
                        await self.api(bot, "sendPhoto", {"chat_id": admin_chat, "photo": file_id})
                except BotApiError:
                    pass
        target = form.get("target")
        page = page_by_id(bot.menu, target) if target else await self.current_page(bot, chat_id)
        if page is not None:
            await self.open_page(bot, chat_id, page["id"], user, push=bool(target))

    # --- Updatelar ---

    def sandbox_copy(self, bot: RunningBot, menu: dict) -> RunningBot:
        return dataclasses.replace(bot, menu=menu, sandbox=True, origin=bot)

    async def _sandboxed(self, bot: RunningBot, upd: dict) -> RunningBot:
        """Admin sinov rejimida bo'lsa — uning updatelari taklif qilingan (hali qo'llanmagan) bot bilan ishlanadi."""
        if "callback_query" in upd:
            chat = ((upd["callback_query"].get("message") or {}).get("chat") or {}).get("id")
        else:
            chat = ((upd.get("message") or {}).get("chat") or {}).get("id")
        if not chat or not self.is_admin(bot, chat):
            return bot
        if await editor.mode(self, bot, chat) != "sandbox":
            return bot
        raw = await self.redis.get(_k(bot.bot_id, "aiprop", chat))
        if not raw:
            await editor.set_mode(self, bot, chat, "ai")
            return bot
        return self.sandbox_copy(bot, json.loads(raw))

    async def _captcha_gate(self, bot: RunningBot, upd: dict) -> bool:
        """Kapcha yoqilgan bo'lsa: tasdiqlanmagan foydalanuvchi faqat «men robot emasman» savoliga javob beradi. True — to'xtatildi."""
        q = upd.get("callback_query")
        msg = upd.get("message")
        src = (q or {}).get("from") or (msg or {}).get("from")
        chat = ((q or {}).get("message") or msg or {}).get("chat", {})
        if not src or chat.get("type") != "private" or self.is_admin(bot, chat["id"]) or getattr(bot, "sandbox", False):
            return False
        chat_id = chat["id"]
        if q and (q.get("data") or "").startswith("cap:"):
            await self._touch(bot, src)
            if await games.captcha_callback(self, bot, chat_id, q["data"], q["message"], src, q["id"]):
                await self.on_start(bot, chat_id, src, "/start")
            return True
        if await games.is_verified(self, bot, src["id"]):
            return False
        await self._touch(bot, src)
        if q:
            await self.answer(bot, q["id"])
        await games.challenge(self, bot, chat_id)
        return True

    async def handle(self, bot: RunningBot, upd: dict) -> None:
        bot = await self._sandboxed(bot, upd)
        if bot.menu.get("captcha") and await self._captcha_gate(bot, upd):
            return
        if "callback_query" in upd:
            await self.on_callback(bot, upd["callback_query"])
        elif "message" in upd:
            await self.on_message(bot, upd["message"])
        elif "my_chat_member" in upd:
            member = upd["my_chat_member"]
            if member.get("chat", {}).get("type") == "private":
                status = member.get("new_chat_member", {}).get("status")
                await self._set_blocked(bot, member["chat"]["id"], status == "kicked")

    async def on_callback(self, bot: RunningBot, query: dict) -> None:
        data = query.get("data") or ""
        message = query.get("message")
        user = query["from"]
        if message is None:
            await self.answer(bot, query["id"])
            return
        chat_id = message["chat"]["id"]
        if data.startswith("tk:"):
            await self.answer(bot, query["id"])
            if tickets.is_staff(self, bot, chat_id):
                await tickets.callback(self, bot, chat_id, data, message, user)
            return
        if data.startswith("tr:"):
            await tickets.rate(self, bot, chat_id, data, message, query["id"])
            return
        if data.startswith(("adm:", "e:", "ai:", "sh:", "bm:", "au:", "gm:")):
            await self.answer(bot, query["id"])
            if self.is_admin(bot, chat_id):
                if data.startswith("sh:"):
                    await shop.admin_callback(self, bot, chat_id, data, message, user)
                elif data.startswith("au:"):
                    await auto.admin_callback(self, bot, chat_id, data, message, user)
                elif data.startswith("gm:"):
                    await games.admin_callback(self, bot, chat_id, data, message, user)
                elif data.startswith("bm:"):
                    await booking.admin_callback(self, bot, chat_id, data, message, user)
                elif data.startswith("adm:"):
                    await admin.on_callback(self, bot, chat_id, data, message, user)
                elif data.startswith("ai:"):
                    await ai_chat.on_callback(self, bot, chat_id, data, message, user)
                else:
                    await editor.on_callback(self, bot, chat_id, data, message, user)
            return
        await self._touch(bot, user)
        sub = await self.subscriber(bot, user["id"])
        if sub["banned"]:
            await self.answer(bot, query["id"])
            return
        if data == "sub":
            missing = await self.missing_channels(bot, user["id"], fresh=True)
            if missing:
                await self.answer(bot, query["id"], "❗ Hali hamma kanallarga obuna bo'lmadingiz", alert=True)
                return
            await self.answer(bot, query["id"], "✅ Rahmat!")
            try:
                await self.api(bot, "deleteMessage", {"chat_id": chat_id, "message_id": message["message_id"]})
            except BotApiError:
                pass
            await self.go_home(bot, chat_id, user, None)
            return
        if not self.is_admin(bot, chat_id):
            missing = await self.missing_channels(bot, user["id"])
            if missing:
                await self.answer(bot, query["id"], "❗ Avval kanallarga obuna bo'ling", alert=True)
                await self.ask_subscribe(bot, chat_id, missing)
                return
        if data.startswith("bk:"):
            await booking.on_callback(self, bot, chat_id, data, message, user, query["id"])
        elif data.startswith(("qz:", "bn:", "cn:")):
            await games.callback(self, bot, chat_id, data, message, user, query["id"])
        elif data.split(":")[0] in SHOP_CALLBACKS:
            await shop.on_callback(self, bot, chat_id, data, message, user, query["id"])
        elif data.startswith("p:"):
            await self.answer(bot, query["id"])
            await self.open_page(bot, chat_id, data[2:], user, message=message)
        elif data == "b":
            await self.answer(bot, query["id"])
            prev = await self.redis.rpop(_k(bot.bot_id, "inav", chat_id))
            if prev:
                await self.open_page(bot, chat_id, prev.decode(), user, message=message, push=False)
            else:
                # inline tarix tugadi — foydalanuvchi turgan menyuga qaytamiz
                cur = await self.current_page(bot, chat_id)
                await self.open_page(bot, chat_id, (cur or {}).get("id") or bot.menu.get("start"), user, message=message, push=False)
        elif data == "h":
            await self.answer(bot, query["id"])
            await self.go_home(bot, chat_id, user, message)
        elif data == "f":
            await self.answer(bot, query["id"])
            await self.ask_feedback(bot, chat_id)
        elif data.startswith("y:"):
            try:
                _, page_id, i, r, c = data.split(":")
                page = page_by_id(bot.menu, page_id)
                button = page["messages"][int(i)]["buttons"][int(r)][int(c)] if page else None
            except (ValueError, IndexError, KeyError):
                button = None
            if button is None:
                await self.answer(bot, query["id"], "Bu tugma eskirgan — /start")
                return
            await self.run_action(bot, chat_id, button, user, message, query_id=query["id"])
        elif data.startswith("x:"):
            try:
                _, page_id, r, c = data.split(":")
                button = self._button_at(bot, page_id, int(r), int(c))
            except ValueError:
                button = None
            if button is None:
                await self.answer(bot, query["id"], "Bu tugma eskirgan — /start", alert=False)
                return
            await self.redis.set(_k(bot.bot_id, "cur", chat_id), page_id, ex=STATE_TTL)
            await self.run_action(bot, chat_id, button, user, message, query_id=query["id"])
        else:
            await self.answer(bot, query["id"])

    async def on_message(self, bot: RunningBot, message: dict) -> None:
        chat = message.get("chat", {})
        if chat.get("type") != "private" or "from" not in message:
            return
        chat_id = chat["id"]
        user = message["from"]
        text = (message.get("text") or "").strip()
        is_admin = self.is_admin(bot, chat_id)

        staff = is_admin or chat_id in (bot.menu.get("operators") or [])
        if staff and text == "/tickets":
            await tickets.staff_command(self, bot, chat_id, user)
            return
        # Xodim (admin yoki operator) kelgan xabarga «reply» qildi — javob o'sha odamga qaytadi.
        if staff and message.get("reply_to_message"):
            reply_id = message["reply_to_message"]["message_id"]
            target = await self.redis.get(_k(bot.bot_id, "fb", f"{chat_id}:{reply_id}")) or (
                await self.redis.get(_k(bot.bot_id, "fb", reply_id)) if chat_id == bot.owner_chat_id else None
            )
            if target:
                try:
                    await self.api(bot, "copyMessage", {"chat_id": int(target), "from_chat_id": chat_id, "message_id": message["message_id"]})
                    await self.api(bot, "sendMessage", {"chat_id": chat_id, "text": "✅ Javob yuborildi", "reply_to_message_id": message["message_id"]})
                    await tickets.on_staff_reply(self, bot, chat_id, reply_id, user)
                except BotApiError as exc:
                    reason = "foydalanuvchi botni bloklagan" if exc.user_blocked else exc.description
                    await self.api(bot, "sendMessage", {"chat_id": chat_id, "text": f"⚠️ Yuborilmadi: {reason}"})
                return

        if chat_id == bot.owner_chat_id and text.startswith("/start"):
            # Egasi botiga kirdi — endi murojaatlarni qabul qila oladi.
            async with async_session() as db:
                await db.execute(
                    update(UserBot).where(UserBot.id == bot.bot_id, UserBot.error_message == OWNER_START_HINT).values(error_message=None)
                )
                await db.commit()
        if is_admin:
            if await editor.on_message(self, bot, message):
                return
            if await admin.on_message(self, bot, message):
                await self._touch(bot, user)
                return

        if text.startswith("/start"):
            await self.on_start(bot, chat_id, user, text)
            return

        await self._touch(bot, user)
        sub = await self.subscriber(bot, user["id"])
        if sub["banned"]:
            return

        # Postdagi savolga javob kutilmoqda
        q_state = await self.redis.get(_k(bot.bot_id, "q", chat_id))
        if q_state:
            await self.on_question(bot, chat_id, message, user, json.loads(q_state))
            return

        # Forma to'ldirilmoqda
        form_state = await self.redis.get(_k(bot.bot_id, "form", chat_id))
        if form_state:
            await self.on_form_message(bot, chat_id, message, user, json.loads(form_state))
            return

        if not is_admin:
            missing = await self.missing_channels(bot, user["id"])
            if missing:
                await self.ask_subscribe(bot, chat_id, missing)
                return

        # Telefon / joylashuv so'ralgan edi
        ask = await self.redis.get(_k(bot.bot_id, "ask", chat_id))
        if ask:
            ask = json.loads(ask)
            value = None
            if ask["kind"] == "contact" and message.get("contact"):
                value = message["contact"].get("phone_number")
            elif ask["kind"] == "location" and message.get("location"):
                value = f"{message['location']['latitude']:.6f},{message['location']['longitude']:.6f}"
            if value is not None or text in (CANCEL_TEXT, "/cancel"):
                await self.redis.delete(_k(bot.bot_id, "ask", chat_id))
                if value is not None:
                    await self.set_vars(bot, user["id"], {ask["var"]: value})
                await self.api(bot, "sendMessage", {"chat_id": chat_id, "text": "✅ Qabul qilindi" if value else "❌ Bekor qilindi", "reply_markup": {"remove_keyboard": True}})
                target = ask.get("target") if value is not None else None
                page = page_by_id(bot.menu, target) if target else await self.current_page(bot, chat_id)
                if page is not None:
                    await self.open_page(bot, chat_id, page["id"], user, push=bool(target))
                return

        if await self.redis.get(_k(bot.bot_id, "st", chat_id)) == b"fb" and text != "/cancel":
            await self.redis.delete(_k(bot.bot_id, "st", chat_id))
            await self.forward_feedback(bot, message, user)
            return
        if text == "/cancel":
            await self.redis.delete(_k(bot.bot_id, "st", chat_id))

        if text.startswith("/"):
            cmd = text[1:].split()[0].split("@")[0].lower()
            for c in bot.menu.get("commands") or []:
                if c["command"] == cmd:
                    await self.open_page(bot, chat_id, c["target"], user)
                    return

        if text:
            vals = await self.values(bot, user, sub)
            button, page_id = await self._find_reply_button(bot, chat_id, text, vals)
            if button is not None:
                await self.redis.set(_k(bot.bot_id, "cur", chat_id), page_id, ex=STATE_TTL)
                await self.run_action(bot, chat_id, button, user, None)
                return
            if text == NAV_BACK:
                await self.go_back(bot, chat_id, user, None)
                return
            if text == NAV_HOME:
                await self.go_home(bot, chat_id, user, None)
                return
            if await self.on_keyword(bot, chat_id, text, user, vals):
                return
        # Qayta aloqa rejimi: menyuda yo'q har qanday xabar (matn, rasm, ovoz...) egasiga boradi.
        if bot.menu.get("forward_all") and not staff and not text.startswith("/"):
            await self.forward_feedback(bot, message, user)
            return
        await self.api(bot, "sendMessage", {"chat_id": chat_id, "text": bot.menu.get("fallback") or "Menyudan tanlang 👇"})

    async def on_start(self, bot: RunningBot, chat_id: int, user: dict, text: str) -> None:
        payload = text.split(maxsplit=1)[1].strip() if " " in text else ""
        is_new = await self._touch(bot, user, force=True)
        sub = await self.subscriber(bot, user["id"])
        if sub["banned"]:
            return
        await self.redis.delete(*(_k(bot.bot_id, kind, chat_id) for kind in ("st", "nav", "cur", "form", "ask", "q")))
        if is_new and payload.startswith("r") and payload[1:].isdigit():
            await self.on_referral(bot, user, int(payload[1:]))
        await stats.track(self, bot, "start")
        if chat_id in (bot.menu.get("operators") or []):
            await self.api(bot, "sendMessage", {"chat_id": chat_id, "text": "🎫 Siz operatorsiz — murojaatlar shu yerga keladi. Ro'yxat: /tickets"})
        if chat_id == bot.owner_chat_id:
            await admin.owner_started(self, bot, chat_id)
        if not self.is_admin(bot, chat_id):
            missing = await self.missing_channels(bot, user["id"], fresh=True)
            if missing:
                await self.ask_subscribe(bot, chat_id, missing)
                return
        target = bot.menu.get("start")
        if payload.startswith("p_") and page_by_id(bot.menu, payload[2:]):
            target = payload[2:]
        elif is_new and bot.menu.get("first_start"):
            target = bot.menu["first_start"]
        page = page_by_id(bot.menu, target)
        if page is None:
            return
        await self.redis.set(_k(bot.bot_id, "cur", chat_id), page["id"], ex=STATE_TTL)
        vals = await self.values(bot, user, sub, need_subs=self._needs_subs(page))
        await self._on_open(bot, chat_id, page, user, vals)
        await self.send_page(bot, chat_id, page, user, with_branding=True, vals=vals)
        if chat_id == bot.owner_chat_id:
            await home.maybe_start_wizard(self, bot, chat_id)

    async def on_referral(self, bot: RunningBot, user: dict, referrer: int) -> None:
        ref = bot.menu.get("referral") or {}
        if not ref.get("enabled") or referrer == user["id"]:
            return
        async with async_session() as db:
            row = await db.scalar(select(BotSubscriber).where(BotSubscriber.bot_id == bot.bot_id, BotSubscriber.tg_user_id == referrer))
            if row is None:
                return
            await db.execute(
                update(BotSubscriber).where(BotSubscriber.bot_id == bot.bot_id, BotSubscriber.tg_user_id == user["id"]).values(referred_by=referrer)
            )
            row.ref_count = (row.ref_count or 0) + 1
            reward = int(ref.get("reward") or 0)
            if reward:
                key = ref.get("var") or "balance"
                data = dict(row.data or {})
                data[key] = apply_op(str(data.get(key, "0")), "add", str(reward))
                row.data = data
            await db.commit()
        if ref.get("notify", True):
            text = fill(ref.get("text") or "", {"name": user.get("first_name") or "Do'stingiz", "reward": str(ref.get("reward") or 0)}, escape=False)
            try:
                await self.api(bot, "sendMessage", {"chat_id": referrer, "text": text})
            except BotApiError:
                pass

    async def on_keyword(self, bot: RunningBot, chat_id: int, text: str, user: dict, vals: dict) -> bool:
        low = text.lower()
        for kw in bot.menu.get("keywords") or []:
            match = kw.get("match", "exact")
            hit = any(
                (low == w) if match == "exact" else (low.startswith(w) if match == "start" else w in low) for w in kw.get("words") or []
            )
            if not hit:
                continue
            if kw.get("reply"):
                await self.api(bot, "sendMessage", {"chat_id": chat_id, "text": fill(kw["reply"], vals, escape=True), "parse_mode": "HTML", "disable_web_page_preview": True})
            if kw.get("target"):
                await self.open_page(bot, chat_id, kw["target"], user)
            return True
        return False

    async def _find_reply_button(self, bot: RunningBot, chat_id: int, text: str, vals: dict) -> tuple[dict | None, str | None]:
        current = await self.redis.get(_k(bot.bot_id, "cur", chat_id))
        current_id = current.decode() if current else bot.menu.get("start")
        # Avval joriy sahifa, keyin bosh sahifa, keyin qolgan reply-sahifalar (doimiy klaviatura eski bo'lishi mumkin).
        pages = sorted(
            (p for p in bot.menu.get("pages", []) if p.get("keyboard") == "reply"),
            key=lambda p: (p["id"] != current_id, p["id"] != bot.menu.get("start")),
        )
        for page in pages:
            for row in page.get("buttons", []):
                for button in row:
                    if button["text"] == text or fill(button["text"], vals, escape=False)[:64] == text:
                        return button, page["id"]
        return None, None

    async def forward_feedback(self, bot: RunningBot, message: dict, user: dict) -> None:
        if tickets.enabled(bot):
            await tickets.intake(self, bot, message, user)
            return
        chat_id = message["chat"]["id"]
        admins = self.admin_chats(bot)
        if not admins:
            await self.api(bot, "sendMessage", {"chat_id": chat_id, "text": "⚠️ Hozircha xabar qabul qilinmayapti."})
            return
        if bot.menu.get("feedback_anonymous"):
            header = "📨 Yangi anonim xabar"
        else:
            who = user.get("first_name") or "Foydalanuvchi"
            if user.get("username"):
                who += f" (@{user['username']})"
            header = f"📨 Yangi xabar: {who}\n🆔 {user['id']}"
        header += "\n\n↩️ Javob berish uchun pastdagi xabarga «Reply» qiling."
        delivered = False
        for admin_chat in admins:
            try:
                head = await self.api(bot, "sendMessage", {"chat_id": admin_chat, "text": header})
                copied = await self.api(bot, "copyMessage", {"chat_id": admin_chat, "from_chat_id": chat_id, "message_id": message["message_id"]})
            except BotApiError as exc:
                logger.info("bot %s: %s ga yetkazilmadi: %s", bot.bot_id, admin_chat, exc.description)
                if admin_chat == bot.owner_chat_id:
                    await self._set_error(bot, OWNER_START_HINT, stop=False)
                continue
            delivered = True
            for msg_id in (head["message_id"], copied["message_id"]):
                await self.redis.set(_k(bot.bot_id, "fb", f"{admin_chat}:{msg_id}"), chat_id, ex=STATE_TTL)
        if not delivered:
            await self.api(bot, "sendMessage", {"chat_id": chat_id, "text": "⚠️ Xabar yetkazilmadi, keyinroq urinib ko'ring."})
            return
        await self.api(bot, "sendMessage", {"chat_id": chat_id, "text": bot.menu.get("feedback_done") or "✅ Yuborildi."})

    # --- Asosiy sikl ---

    async def is_leader(self) -> bool:
        if await self.redis.set(LEADER_KEY, self.instance_id, nx=True, ex=LEADER_TTL):
            return True
        current = await self.redis.get(LEADER_KEY)
        if current and current.decode() == self.instance_id:
            await self.redis.expire(LEADER_KEY, LEADER_TTL)
            return True
        return False

    async def run(self) -> None:
        logger.info("botrunner ishga tushdi")
        last_marker = None
        last_full = 0.0
        last_remind = 0.0
        loop = asyncio.get_running_loop()
        while True:
            try:
                if await self.is_leader():
                    marker = await self.redis.get(SYNC_KEY)
                    if marker != last_marker or loop.time() - last_full >= FULL_SYNC_SECONDS:
                        await self.sync()
                        last_marker, last_full = marker, loop.time()
                elif self.bots:
                    await self.stop_all()
            except Exception:  # noqa: BLE001 — sikl to'xtamasin
                logger.exception("sinxronlashda xato")
            try:
                if loop.time() - last_remind >= 60 and await self.is_leader():
                    last_remind = loop.time()
                    await booking.reminder_tick(self)
                    await auto.tick(self)
            except Exception:  # noqa: BLE001
                logger.exception("eslatmalarda xato")
            await asyncio.sleep(CHECK_SECONDS)


if __name__ == "__main__":
    asyncio.run(Runner().run())
