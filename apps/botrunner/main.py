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
import datetime
import logging
import uuid
from dataclasses import dataclass, field

import httpx
from redis.asyncio import Redis
from sqlalchemy import select, update
from sqlalchemy.dialects.postgresql import insert

from core import crypto
from core.botapi import BotApiError, call
from core.botbuilder import page_by_id, render_text
from core.db.base import async_session
from core.db.models import BotSubscriber, MediaFile, User, UserBot
from core.entitlements import get_entitlement
from core.notify import send_telegram
from core.settings import settings

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
OWNER_START_HINT = "Xabarlarni olish uchun o'z botingizga kirib /start bosing"


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
    task: asyncio.Task | None = None
    conflict_reported: bool = False
    pending: set = field(default_factory=set)


def _k(bot_id: int, kind: str, key) -> str:
    return f"ub:{bot_id}:{kind}:{key}"


def _keyboard(page: dict) -> dict | None:
    rows = page.get("buttons") or []
    if not rows:
        return None
    if page.get("keyboard") == "reply":
        return {"keyboard": [[{"text": b["text"]} for b in row] for row in rows], "resize_keyboard": True, "is_persistent": True}
    inline = []
    for row in rows:
        line = []
        for b in row:
            if b["action"] == "url":
                line.append({"text": b["text"], "url": b["url"]})
            elif b["action"] == "page":
                line.append({"text": b["text"], "callback_data": f"p:{b['target']}"})
            else:
                line.append({"text": b["text"], "callback_data": {"back": "b", "home": "h", "feedback": "f"}[b["action"]]})
        inline.append(line)
    return {"inline_keyboard": inline}


class Runner:
    def __init__(self) -> None:
        self.redis = Redis.from_url(settings.redis_url or "redis://redis:6379")
        self.http = httpx.AsyncClient(timeout=POLL_TIMEOUT + 15, limits=httpx.Limits(max_connections=None, max_keepalive_connections=200))
        self.bots: dict[int, RunningBot] = {}
        self.instance_id = uuid.uuid4().hex
        self.platform_username: str | None = None

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
        result: dict[int, RunningBot] = {}
        async with async_session() as db:
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
                result[bot.id] = RunningBot(
                    bot_id=bot.id, user_id=bot.user_id, owner_chat_id=owner_chat, token=token,
                    username=bot.username, name=bot.name, menu=bot.menu, branding=branding,
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
                if running.task is not None and running.task.done():
                    self.bots.pop(bot_id, None)
                    self.start(wanted)

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

    async def _touch(self, bot: RunningBot, user: dict, force: bool = False) -> None:
        if not force and not await self.redis.set(_k(bot.bot_id, "seen", user["id"]), "1", nx=True, ex=SEEN_THROTTLE):
            return
        now = datetime.datetime.now(datetime.timezone.utc)
        async with async_session() as db:
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

    async def _set_blocked(self, bot: RunningBot, chat_id: int, blocked: bool) -> None:
        async with async_session() as db:
            await db.execute(
                update(BotSubscriber).where(BotSubscriber.bot_id == bot.bot_id, BotSubscriber.tg_user_id == chat_id).values(blocked=blocked)
            )
            await db.commit()

    def _text(self, bot: RunningBot, page: dict, user: dict, with_branding: bool) -> str:
        text = render_text(page["text"], name=user.get("first_name"), username=user.get("username"), bot=bot.name)
        limit = 1024 if page.get("media_id") else 4096
        if with_branding and bot.branding:
            text = f"{text[: limit - len(bot.branding) - 2]}\n\n{bot.branding}"
        return text[:limit]

    async def _photo_arg(self, bot: RunningBot, media_id: int) -> tuple[dict, dict | None]:
        cached = await self.redis.get(_k(bot.bot_id, "file", media_id))
        if cached:
            return {"photo": cached.decode()}, None
        async with async_session() as db:
            media = await db.get(MediaFile, media_id)
        if media is None:
            return {}, None
        return {}, {"photo": ("photo.jpg", media.data, media.mime)}

    async def send_page(self, bot: RunningBot, chat_id: int, page: dict, user: dict, *, with_branding: bool = False) -> None:
        markup = _keyboard(page)
        text = self._text(bot, page, user, with_branding)
        media_id = page.get("media_id")
        if media_id:
            photo, files = await self._photo_arg(bot, media_id)
            if photo or files:
                result = await self.api(bot, "sendPhoto", {"chat_id": chat_id, "caption": text, "reply_markup": markup, **photo}, files)
                if files:
                    await self.redis.set(_k(bot.bot_id, "file", media_id), result["photo"][-1]["file_id"], ex=STATE_TTL)
                return
        await self.api(bot, "sendMessage", {"chat_id": chat_id, "text": text, "reply_markup": markup, "disable_web_page_preview": True})

    async def open_page(self, bot: RunningBot, chat_id: int, page_id: str, user: dict, *, message: dict | None = None, push: bool = True) -> None:
        page = page_by_id(bot.menu, page_id) or page_by_id(bot.menu, bot.menu.get("start"))
        if page is None:
            return
        cur_key, nav_key = _k(bot.bot_id, "cur", chat_id), _k(bot.bot_id, "nav", chat_id)
        current = await self.redis.get(cur_key)
        current = current.decode() if current else None
        if push and current and current != page["id"]:
            await self.redis.rpush(nav_key, current)
            await self.redis.ltrim(nav_key, -NAV_DEPTH, -1)
            await self.redis.expire(nav_key, STATE_TTL)
        await self.redis.set(cur_key, page["id"], ex=STATE_TTL)

        # Inline menyuda xabar o'rnida tahrirlanadi (chat to'lib ketmaydi) — rasmsiz sahifalar uchun.
        if (
            message is not None
            and page.get("keyboard") != "reply"
            and not page.get("media_id")
            and "photo" not in message
        ):
            try:
                await self.api(
                    bot,
                    "editMessageText",
                    {
                        "chat_id": chat_id,
                        "message_id": message["message_id"],
                        "text": self._text(bot, page, user, False),
                        "reply_markup": _keyboard(page) or {"inline_keyboard": []},
                        "disable_web_page_preview": True,
                    },
                )
                return
            except BotApiError as exc:
                if "not modified" in exc.description:
                    return
        await self.send_page(bot, chat_id, page, user)

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

    async def run_action(self, bot: RunningBot, chat_id: int, button: dict, user: dict, message: dict | None) -> None:
        action = button["action"]
        if action == "page":
            await self.open_page(bot, chat_id, button["target"], user, message=message)
        elif action == "back":
            await self.go_back(bot, chat_id, user, message)
        elif action == "home":
            await self.go_home(bot, chat_id, user, message)
        elif action == "feedback":
            await self.ask_feedback(bot, chat_id)

    # --- Updatelar ---

    async def handle(self, bot: RunningBot, upd: dict) -> None:
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
        try:
            await self.api(bot, "answerCallbackQuery", {"callback_query_id": query["id"]})
        except BotApiError:
            pass
        if message is None:
            return
        chat_id = message["chat"]["id"]
        await self._touch(bot, user)
        if data.startswith("p:"):
            await self.open_page(bot, chat_id, data[2:], user, message=message)
        elif data == "b":
            await self.go_back(bot, chat_id, user, message)
        elif data == "h":
            await self.go_home(bot, chat_id, user, message)
        elif data == "f":
            await self.ask_feedback(bot, chat_id)

    async def on_message(self, bot: RunningBot, message: dict) -> None:
        chat = message.get("chat", {})
        if chat.get("type") != "private" or "from" not in message:
            return
        chat_id = chat["id"]
        user = message["from"]
        text = (message.get("text") or "").strip()

        # Egasi kelgan xabarga «reply» qildi — javob o'sha odamga qaytadi.
        if chat_id == bot.owner_chat_id and message.get("reply_to_message"):
            target = await self.redis.get(_k(bot.bot_id, "fb", message["reply_to_message"]["message_id"]))
            if target:
                try:
                    await self.api(bot, "copyMessage", {"chat_id": int(target), "from_chat_id": chat_id, "message_id": message["message_id"]})
                    await self.api(bot, "sendMessage", {"chat_id": chat_id, "text": "✅ Javob yuborildi", "reply_to_message_id": message["message_id"]})
                except BotApiError as exc:
                    reason = "foydalanuvchi botni bloklagan" if exc.user_blocked else exc.description
                    await self.api(bot, "sendMessage", {"chat_id": chat_id, "text": f"⚠️ Yuborilmadi: {reason}"})
                return

        if text.startswith("/start"):
            await self._touch(bot, user, force=True)
            if chat_id == bot.owner_chat_id:
                # Egasi botiga kirdi — endi xabarlarni qabul qila oladi.
                async with async_session() as db:
                    await db.execute(
                        update(UserBot).where(UserBot.id == bot.bot_id, UserBot.error_message == OWNER_START_HINT).values(error_message=None)
                    )
                    await db.commit()
            await self.redis.delete(_k(bot.bot_id, "st", chat_id), _k(bot.bot_id, "nav", chat_id), _k(bot.bot_id, "cur", chat_id))
            start = page_by_id(bot.menu, bot.menu.get("start"))
            if start is not None:
                await self.redis.set(_k(bot.bot_id, "cur", chat_id), start["id"], ex=STATE_TTL)
                await self.send_page(bot, chat_id, start, user, with_branding=True)
            return

        await self._touch(bot, user)

        if await self.redis.get(_k(bot.bot_id, "st", chat_id)) == b"fb" and text != "/cancel":
            await self.redis.delete(_k(bot.bot_id, "st", chat_id))
            await self.forward_feedback(bot, message, user)
            return
        if text == "/cancel":
            await self.redis.delete(_k(bot.bot_id, "st", chat_id))

        button = await self._find_reply_button(bot, chat_id, text) if text else None
        if button is not None:
            await self.run_action(bot, chat_id, button, user, None)
            return
        await self.api(bot, "sendMessage", {"chat_id": chat_id, "text": bot.menu.get("fallback") or "Menyudan tanlang 👇"})

    async def _find_reply_button(self, bot: RunningBot, chat_id: int, text: str) -> dict | None:
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
                    if button["text"] == text:
                        return button
        return None

    async def forward_feedback(self, bot: RunningBot, message: dict, user: dict) -> None:
        chat_id = message["chat"]["id"]
        if not bot.owner_chat_id:
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
        try:
            head = await self.api(bot, "sendMessage", {"chat_id": bot.owner_chat_id, "text": header})
            copied = await self.api(bot, "copyMessage", {"chat_id": bot.owner_chat_id, "from_chat_id": chat_id, "message_id": message["message_id"]})
        except BotApiError as exc:
            logger.info("bot %s: egasiga yetkazilmadi: %s", bot.bot_id, exc.description)
            # Egasi botga hali /start bosmagan.
            await self._set_error(bot, OWNER_START_HINT, stop=False)
            await self.api(bot, "sendMessage", {"chat_id": chat_id, "text": "⚠️ Xabar yetkazilmadi, keyinroq urinib ko'ring."})
            return
        for msg_id in (head["message_id"], copied["message_id"]):
            await self.redis.set(_k(bot.bot_id, "fb", msg_id), chat_id, ex=STATE_TTL)
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
            await asyncio.sleep(CHECK_SECONDS)


if __name__ == "__main__":
    asyncio.run(Runner().run())
