"""24/7 Online: har bir akkaunt uchun DOIMIY ulanishda «online» holatini ushlab turish.

Avval worker har daqiqada yangi ulanish ochib UpdateStatus(offline=False) yuborar va darhol uzilardi.
Ulanish uzilishi bilan Telegram akkauntni tez orada «offline» qiladi, bitta tik kechiksa yoki xato bo'lsa —
online ko'rinish o'chib qolardi. Endi ulanish ochiq turadi va holat har PING_SECONDS'da yangilanadi;
uzilsa — avtomatik qayta ulanadi. Sessiya Telegram'da tugatilgan bo'lsa — akkaunt EXPIRED, egasiga xabar.

Worker esa redis'dagi online_keeper:{id} kaliti tirik bo'lsa, shu akkaunt uchun online'ni o'zi yubormaydi
(listener ishlamay qolsa, worker avtomatik zaxira bo'lib qoladi)."""

import asyncio
import logging
import random
from dataclasses import dataclass

from sqlalchemy import select
from telethon import TelegramClient, functions
from telethon.sessions import StringSession

from core import crypto
from core.db.base import async_session
from core.db.enums import AutomationStatus, ProfileField
from core.db.models import Automation, AutomationAction, EncryptedSession, TelegramAccount
from core.entitlements import LIVE_ACCOUNT_STATUSES
from core.session_health import handle_session_dead
from core.settings import settings
from core.telegram.errors import ErrorKind, classify
from core.telegram.presence import ONLINE_KEEPER_TTL_SECONDS, online_keeper_key

logger = logging.getLogger("listener.online")

# Telegram'da online holat qisqa muddat amal qiladi — tez-tez yangilab turamiz.
PING_SECONDS = 30
RECONNECT_MAX_DELAY = 60


@dataclass
class KeptAccount:
    account_id: int
    session_hash: int
    client: TelegramClient
    task: asyncio.Task | None = None


class OnlineKeeper:
    def __init__(self, redis) -> None:
        self.redis = redis
        self.accounts: dict[int, KeptAccount] = {}

    async def _desired(self) -> dict[int, str]:
        """ACTIVE «online» xizmati bor, tirik va sessiyasi bekor qilinmagan akkauntlar."""
        async with async_session() as db:
            rows = (
                await db.execute(
                    select(TelegramAccount.id, EncryptedSession)
                    .join(Automation, Automation.telegram_account_id == TelegramAccount.id)
                    .join(AutomationAction, AutomationAction.automation_id == Automation.id)
                    .join(EncryptedSession, EncryptedSession.telegram_account_id == TelegramAccount.id)
                    .where(
                        Automation.status == AutomationStatus.ACTIVE,
                        AutomationAction.field == ProfileField.ONLINE,
                        TelegramAccount.status.in_(LIVE_ACCOUNT_STATUSES),
                        EncryptedSession.revoked_at.is_(None),
                    )
                )
            ).all()
        result: dict[int, str] = {}
        for account_id, session_row in rows:
            if account_id not in result:
                result[account_id] = crypto.decrypt(session_row.ciphertext, session_row.nonce, session_row.key_version)
        return result

    async def sync(self) -> None:
        desired = await self._desired()
        for account_id in list(self.accounts):
            if account_id not in desired or hash(desired[account_id]) != self.accounts[account_id].session_hash:
                await self.stop(account_id, go_offline=account_id not in desired)
        for account_id, session_string in desired.items():
            try:
                kept = self.accounts.get(account_id)
                if kept is None:
                    self.start(account_id, session_string)
                elif kept.task is not None and kept.task.done():
                    # Sikl tugagan (sessiya o'lgan bo'lsa keyingi sync'da desired'dan chiqadi) — qayta ishga tushiramiz.
                    await self.stop(account_id, go_offline=False)
                    self.start(account_id, session_string)
            except Exception:  # noqa: BLE001 — bitta buzuq sessiya boshqa akkauntlarga xalaqit bermasin
                logger.exception("akkaunt %s uchun online ishga tushmadi", account_id)

    def start(self, account_id: int, session_string: str) -> None:
        client = TelegramClient(
            StringSession(session_string),
            settings.telegram_api_id,
            settings.telegram_api_hash,
            receive_updates=False,  # AI listener'ning yangilanishlarini tortib olmasin
            auto_reconnect=True,
            connection_retries=None,  # tarmoq uzilsa cheksiz qayta ulanadi
            retry_delay=5,
        )
        kept = KeptAccount(account_id=account_id, session_hash=hash(session_string), client=client)
        kept.task = asyncio.create_task(self._run(kept))
        self.accounts[account_id] = kept
        logger.info("24/7 online yoqildi: akkaunt %s", account_id)

    async def _run(self, kept: KeptAccount) -> None:
        delay = 5
        # Bir vaqtda ko'p akkaunt bo'lsa ping'lar bir lahzaga to'planmasin.
        await asyncio.sleep(random.uniform(0, 3))
        while True:
            try:
                if not kept.client.is_connected():
                    await kept.client.connect()
                await kept.client(functions.account.UpdateStatusRequest(offline=False))
                await self.redis.set(online_keeper_key(kept.account_id), "1", ex=ONLINE_KEEPER_TTL_SECONDS)
                delay = 5
                await asyncio.sleep(PING_SECONDS)
            except asyncio.CancelledError:
                raise
            except Exception as exc:  # noqa: BLE001
                if classify(exc) == ErrorKind.SESSION_DEAD:
                    logger.warning("akkaunt %s: sessiya tugatilgan (%s)", kept.account_id, type(exc).__name__)
                    await self.redis.delete(online_keeper_key(kept.account_id))
                    async with async_session() as db:
                        await handle_session_dead(db, kept.account_id, type(exc).__name__)
                    return
                wait = getattr(exc, "seconds", None)  # FloodWait
                if not isinstance(wait, int):
                    wait = delay
                    delay = min(delay * 2, RECONNECT_MAX_DELAY)
                logger.warning("akkaunt %s: online yangilanmadi (%s: %s), %ss dan keyin", kept.account_id, type(exc).__name__, exc, wait)
                await asyncio.sleep(wait)

    async def stop(self, account_id: int, go_offline: bool = True) -> None:
        kept = self.accounts.pop(account_id, None)
        if kept is None:
            return
        if kept.task is not None:
            kept.task.cancel()
            try:
                await kept.task
            except (asyncio.CancelledError, Exception):  # noqa: BLE001
                pass
        await self.redis.delete(online_keeper_key(account_id))
        try:
            if go_offline and kept.client.is_connected():
                await asyncio.wait_for(kept.client(functions.account.UpdateStatusRequest(offline=True)), 10)
        except Exception:  # noqa: BLE001 — offline'ga o'tkazish best-effort
            pass
        try:
            await kept.client.disconnect()
        except Exception:  # noqa: BLE001
            pass
        logger.info("24/7 online o'chirildi: akkaunt %s", account_id)

    async def stop_all(self) -> None:
        for account_id in list(self.accounts):
            await self.stop(account_id, go_offline=False)
