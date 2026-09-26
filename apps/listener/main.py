"""AI avto-javob tinglovchisi.

AI yoqilgan har bir akkaunt uchun doimiy Telegram ulanishi saqlanadi va faqat SHAXSIY chatlardagi
kiruvchi matnli xabarlarga javob beriladi (guruh, kanal, botlar va «Saqlangan xabarlar» — yo'q).

Xarajatni tejash:
- ketma-ket kelgan xabarlar DEBOUNCE soniya kutib, bitta javobga birlashtiriladi;
- bir chatga COOLDOWN soniyada ko'pi bilan bitta javob;
- egasi shu chatda yaqinda yozgan bo'lsa (only_when_away) — AI jim;
- tarif bo'yicha kunlik limit (Redis), har chaqiruv ai_usage'ga yoziladi."""

import asyncio
import logging
import time
import uuid
from dataclasses import dataclass, field

from redis.asyncio import Redis
from sqlalchemy import select
from telethon import TelegramClient, events
from telethon.errors import RPCError
from telethon.sessions import StringSession

from core import ai, crypto
from core.db.base import async_session
from core.db.models import AccountAI, EncryptedSession, TelegramAccount, User
from core.entitlements import LIVE_ACCOUNT_STATUSES, get_entitlement
from core.notify import send_telegram
from core.settings import settings

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger("listener")

SYNC_SECONDS = 20
CATCH_UP_SECONDS = 15
DEBOUNCE_SECONDS = 4
COOLDOWN_SECONDS = 20
AWAY_SECONDS = 600
LEADER_KEY = "leader:listener"
LEADER_TTL = 30
MAX_TRACKED_OWN_MESSAGES = 500


@dataclass
class Config:
    user_id: int
    owner_name: str
    preset: str
    style: str | None
    only_when_away: bool
    signature: bool
    daily_limit: int


@dataclass
class AccountListener:
    account_id: int
    session_hash: int
    config: Config
    client: TelegramClient
    me_id: int = 0
    owner_last_write: dict[int, float] = field(default_factory=dict)
    last_reply: dict[int, float] = field(default_factory=dict)
    pending: dict[int, asyncio.Task] = field(default_factory=dict)
    our_messages: set[int] = field(default_factory=set)


class Listener:
    def __init__(self) -> None:
        self.redis = Redis.from_url(settings.redis_url or "redis://redis:6379")
        self.accounts: dict[int, AccountListener] = {}
        self.limit_notified: set[tuple[int, str]] = set()
        self.instance_id = uuid.uuid4().hex

    # --- Sozlamalarni bazadan sinxronlash ---

    async def _desired(self) -> dict[int, tuple[str, Config]]:
        """AI yoqilgan, tarifi ruxsat bergan va sessiyasi bor akkauntlar."""
        result: dict[int, tuple[str, Config]] = {}
        async with async_session() as db:
            rows = (
                await db.execute(
                    select(AccountAI, TelegramAccount, EncryptedSession)
                    .join(TelegramAccount, TelegramAccount.id == AccountAI.telegram_account_id)
                    .join(EncryptedSession, EncryptedSession.telegram_account_id == TelegramAccount.id)
                    .where(
                        AccountAI.enabled == True,  # noqa: E712
                        TelegramAccount.status.in_(LIVE_ACCOUNT_STATUSES),
                        EncryptedSession.revoked_at.is_(None),
                    )
                )
            ).all()
            config = await ai.get_config(db)
            if not config["configured"] or not config["enabled"]:
                return {}
            for settings_row, account, session_row in rows:
                ent = await get_entitlement(db, account.user_id)
                if not ent.flags.get("ai_service"):
                    continue
                session_string = crypto.decrypt(session_row.ciphertext, session_row.nonce, session_row.key_version)
                result[account.id] = (
                    session_string,
                    Config(
                        user_id=account.user_id,
                        owner_name=account.first_name or account.username or "",
                        preset=settings_row.preset,
                        style=settings_row.style,
                        only_when_away=settings_row.only_when_away,
                        signature=settings_row.signature,
                        daily_limit=int(ent.flags.get("ai_daily_limit", 0)),
                    ),
                )
        return result

    async def sync(self) -> None:
        desired = await self._desired()
        for account_id in list(self.accounts):
            if account_id not in desired or hash(desired[account_id][0]) != self.accounts[account_id].session_hash:
                await self.stop(account_id)
        for account_id, (session_string, config) in desired.items():
            if account_id in self.accounts:
                self.accounts[account_id].config = config  # uslub/limit o'zgarishi darhol kuchga kiradi
            else:
                await self.start(account_id, session_string, config)

    async def start(self, account_id: int, session_string: str, config: Config) -> None:
        client = TelegramClient(StringSession(session_string), settings.telegram_api_id, settings.telegram_api_hash)
        state = AccountListener(account_id=account_id, session_hash=hash(session_string), config=config, client=client)
        try:
            await client.connect()
            me = await client.get_me() if await client.is_user_authorized() else None
        except (RPCError, OSError) as exc:
            logger.warning("akkaunt %s ulanmadi: %s", account_id, exc)
            await client.disconnect()
            return
        if me is None:
            logger.warning("akkaunt %s sessiyasi yaroqsiz", account_id)
            await client.disconnect()
            return
        state.me_id = me.id

        @client.on(events.NewMessage(outgoing=True, func=lambda e: e.is_private))
        async def on_outgoing(event):
            if event.id in state.our_messages:
                state.our_messages.discard(event.id)
                return
            state.owner_last_write[event.chat_id] = time.monotonic()
            # Egasi o'zi javob berdi — navbatdagi AI javobi bekor.
            task = state.pending.pop(event.chat_id, None)
            if task:
                task.cancel()

        @client.on(events.NewMessage(incoming=True, func=lambda e: e.is_private))
        async def on_incoming(event):
            logger.info("akkaunt %s: shaxsiy xabar keldi (chat %s)", account_id, event.chat_id)
            await self._schedule(state, event)

        self.accounts[account_id] = state
        logger.info("AI avto-javob yoqildi: akkaunt %s", account_id)

    async def catch_up(self) -> None:
        """Zaxira: biror sabab bilan kelmay qolgan yangilanishlarni Telegram'dan o'zimiz so'rab olamiz."""
        for state in list(self.accounts.values()):
            try:
                await state.client.catch_up()
            except (RPCError, OSError) as exc:
                logger.warning("catch_up xatosi (akkaunt %s): %s", state.account_id, exc)

    async def stop(self, account_id: int) -> None:
        state = self.accounts.pop(account_id, None)
        if state is None:
            return
        for task in state.pending.values():
            task.cancel()
        await state.client.disconnect()
        logger.info("AI avto-javob o'chirildi: akkaunt %s", account_id)

    # --- Xabarlarni qayta ishlash ---

    async def _schedule(self, state: AccountListener, event) -> None:
        chat_id = event.chat_id
        if chat_id == state.me_id or not (event.raw_text or "").strip():
            return
        sender = await event.get_sender()
        if sender is None or getattr(sender, "bot", False) or getattr(sender, "is_self", False):
            return
        # Debounce: ketma-ket xabarlar bitta javobga birlashadi.
        previous = state.pending.pop(chat_id, None)
        if previous:
            previous.cancel()
        state.pending[chat_id] = asyncio.create_task(self._reply_later(state, chat_id))

    async def _reply_later(self, state: AccountListener, chat_id: int) -> None:
        try:
            await asyncio.sleep(DEBOUNCE_SECONDS)
        except asyncio.CancelledError:
            return
        state.pending.pop(chat_id, None)
        cfg = state.config
        now = time.monotonic()
        if cfg.only_when_away and now - state.owner_last_write.get(chat_id, -1e9) < AWAY_SECONDS:
            return
        if now - state.last_reply.get(chat_id, -1e9) < COOLDOWN_SECONDS:
            return
        if not await ai.take_quota(self.redis, cfg.user_id, cfg.daily_limit):
            await self._notify_limit(cfg)
            return
        try:
            history = await self._history(state, chat_id)
            async with async_session() as db:
                model = (await ai.get_config(db))["model"]
            result = await ai.reply(model, cfg.owner_name, cfg.preset, cfg.style, history)
            if not result.text:
                await ai.refund_quota(self.redis, cfg.user_id)
                return
            text = f"🤖 {result.text}" if cfg.signature else result.text
            sent = await state.client.send_message(chat_id, text)
            if len(state.our_messages) > MAX_TRACKED_OWN_MESSAGES:
                state.our_messages.clear()
            state.our_messages.add(sent.id)
            state.last_reply[chat_id] = time.monotonic()
            async with async_session() as db:
                await ai.log_usage(db, cfg.user_id, "reply", result)
        except ai.AIError as exc:
            await ai.refund_quota(self.redis, cfg.user_id)
            logger.warning("AI javob bermadi (akkaunt %s): %s", state.account_id, exc)
        except RPCError as exc:
            await ai.refund_quota(self.redis, cfg.user_id)
            logger.warning("xabar yuborilmadi (akkaunt %s): %s", state.account_id, exc)

    async def _history(self, state: AccountListener, chat_id: int) -> list[tuple[bool, str]]:
        messages = await state.client.get_messages(chat_id, limit=ai.MAX_CONTEXT_MESSAGES)
        history = []
        for message in reversed(messages):
            text = (message.raw_text or "").strip()
            if text:
                history.append((bool(message.out), text))
        return history

    async def _notify_limit(self, cfg: Config) -> None:
        """Limit tugaganini egasiga kuniga bir marta aytamiz."""
        today = time.strftime("%Y%m%d")
        if (cfg.user_id, today) in self.limit_notified:
            return
        self.limit_notified.add((cfg.user_id, today))
        async with async_session() as db:
            user = await db.get(User, cfg.user_id)
        if user and user.telegram_user_id:
            await send_telegram(
                user.telegram_user_id,
                f"🤖 Bugungi AI limiti tugadi ({cfg.daily_limit} ta). Ertaga yana ishlaydi — ko'proq kerak bo'lsa tarifni yangilang.",
            )

    # --- Asosiy sikl ---

    async def is_leader(self) -> bool:
        """Bir vaqtda faqat bitta listener ishlasin — aks holda javoblar ikki marta ketadi."""
        if await self.redis.set(LEADER_KEY, self.instance_id, nx=True, ex=LEADER_TTL):
            return True
        current = await self.redis.get(LEADER_KEY)
        if current and current.decode() == self.instance_id:
            await self.redis.expire(LEADER_KEY, LEADER_TTL)
            return True
        return False

    async def catch_up_loop(self) -> None:
        while True:
            await asyncio.sleep(CATCH_UP_SECONDS)
            try:
                await self.catch_up()
            except Exception:  # noqa: BLE001
                logger.exception("catch_up siklida xato")

    async def run(self) -> None:
        logger.info("listener ishga tushdi")
        asyncio.create_task(self.catch_up_loop())
        while True:
            try:
                if await self.is_leader():
                    await self.sync()
                elif self.accounts:
                    for account_id in list(self.accounts):
                        await self.stop(account_id)
            except Exception:  # noqa: BLE001 — sikl to'xtamasin
                logger.exception("sinxronlashda xato")
            await asyncio.sleep(SYNC_SECONDS)


if __name__ == "__main__":
    if not settings.bot_token or not settings.telegram_api_id:
        logger.warning("Telegram sozlanmagan — listener kutish rejimida")
    asyncio.run(Listener().run())
