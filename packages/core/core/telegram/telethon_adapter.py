import asyncio
import uuid

from telethon import TelegramClient
from telethon.errors import PhoneCodeExpiredError, PhoneCodeInvalidError, SessionPasswordNeededError
from telethon.sessions import StringSession

from core.settings import settings
from core.telegram.base import TelegramAdapter
from core.telegram.enums import LoginStatus
from core.telegram.types import LoginState

QR_LOGIN_TIMEOUT_SECONDS = 60


class _Session:
    __slots__ = ("client", "qr_login", "phone", "phone_code_hash", "state")

    def __init__(self) -> None:
        self.client: TelegramClient | None = None
        self.qr_login = None
        self.phone: str | None = None
        self.phone_code_hash: str | None = None
        self.state: LoginState | None = None


class TelethonAdapter(TelegramAdapter):
    """Real MTProto ulanish (Telethon). Hozircha api konteynerida ishlaydi;
    PHASE 6'da worker/lease tizimiga ko'chiriladi (shifrlash kaliti ham)."""

    def __init__(self) -> None:
        self._sessions: dict[str, _Session] = {}

    def _new_client(self) -> TelegramClient:
        return TelegramClient(StringSession(), settings.telegram_api_id, settings.telegram_api_hash)

    async def start_qr_login(self) -> LoginState:
        login_id = uuid.uuid4().hex
        sess = _Session()
        sess.client = self._new_client()
        await sess.client.connect()
        sess.qr_login = await sess.client.qr_login()
        sess.state = LoginState(login_id=login_id, status=LoginStatus.WAITING_SCAN, qr_url=sess.qr_login.url)
        self._sessions[login_id] = sess
        asyncio.create_task(self._watch_qr(login_id))
        return sess.state

    async def _watch_qr(self, login_id: str) -> None:
        sess = self._sessions.get(login_id)
        if sess is None:
            return
        try:
            await sess.qr_login.wait(timeout=QR_LOGIN_TIMEOUT_SECONDS)
            await self._finalize_success(login_id)
        except SessionPasswordNeededError:
            sess.state.status = LoginStatus.NEED_PASSWORD
        except TimeoutError:
            sess.state.status = LoginStatus.EXPIRED
        except Exception as exc:  # noqa: BLE001 — real Telegram xatosini holatga aniq chiqarish uchun
            sess.state.status = LoginStatus.ERROR
            sess.state.error = str(exc)

    async def _finalize_success(self, login_id: str) -> None:
        sess = self._sessions[login_id]
        me = await sess.client.get_me()
        sess.state.telegram_user_id = me.id
        sess.state.username = me.username
        sess.state.first_name = me.first_name
        sess.state.last_name = me.last_name
        sess.state.is_premium = bool(getattr(me, "premium", False))
        sess.state.session_string = sess.client.session.save()
        sess.state.status = LoginStatus.SUCCESS

    async def get_login_state(self, login_id: str) -> LoginState:
        sess = self._sessions.get(login_id)
        if sess is None:
            return LoginState(login_id=login_id, status=LoginStatus.ERROR, error="login_id topilmadi")
        return sess.state

    async def start_phone_login(self, phone: str) -> LoginState:
        login_id = uuid.uuid4().hex
        sess = _Session()
        sess.client = self._new_client()
        await sess.client.connect()
        sent = await sess.client.send_code_request(phone)
        sess.phone = phone
        sess.phone_code_hash = sent.phone_code_hash
        sess.state = LoginState(login_id=login_id, status=LoginStatus.CODE_SENT)
        self._sessions[login_id] = sess
        return sess.state

    async def submit_code(self, login_id: str, code: str) -> LoginState:
        sess = self._sessions[login_id]
        try:
            await sess.client.sign_in(phone=sess.phone, code=code, phone_code_hash=sess.phone_code_hash)
            await self._finalize_success(login_id)
        except SessionPasswordNeededError:
            sess.state.status = LoginStatus.NEED_PASSWORD
        except (PhoneCodeInvalidError, PhoneCodeExpiredError) as exc:
            sess.state.status = LoginStatus.ERROR
            sess.state.error = str(exc)
        return sess.state

    async def submit_password(self, login_id: str, password: str) -> LoginState:
        sess = self._sessions[login_id]
        try:
            await sess.client.sign_in(password=password)
            await self._finalize_success(login_id)
        except Exception as exc:  # noqa: BLE001
            sess.state.status = LoginStatus.ERROR
            sess.state.error = str(exc)
        return sess.state

    async def revoke(self, session_string: str) -> None:
        client = TelegramClient(StringSession(session_string), settings.telegram_api_id, settings.telegram_api_hash)
        await client.connect()
        try:
            await client.log_out()
        finally:
            if client.is_connected():
                await client.disconnect()

    async def cleanup(self, login_id: str) -> None:
        sess = self._sessions.pop(login_id, None)
        if sess and sess.client and sess.client.is_connected():
            await sess.client.disconnect()
