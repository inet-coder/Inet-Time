import itertools
import uuid

from core.telegram.base import TelegramAdapter
from core.telegram.enums import LoginStatus
from core.telegram.types import LoginState

MOCK_CODE = "00000"
"""Faqat MOCK_TELEGRAM=true rejimida ishlaydigan qat'iy kod — real Telegram bilan aloqasi yo'q."""

_fake_telegram_id = itertools.count(900000000)


class MockAdapter(TelegramAdapter):
    """Real MTProto'siz test uchun. Ekranga QR ko'rsatish o'rniga
    /accounts/mock/{login_id}/simulate-scan endpointi orqali qo'lda tasdiqlanadi."""

    def __init__(self) -> None:
        self._states: dict[str, LoginState] = {}
        self._phones: dict[str, str] = {}

    async def start_qr_login(self) -> LoginState:
        login_id = uuid.uuid4().hex
        state = LoginState(
            login_id=login_id,
            status=LoginStatus.WAITING_SCAN,
            qr_url=f"tg://login?token=mock-{login_id}",
        )
        self._states[login_id] = state
        return state

    async def get_login_state(self, login_id: str) -> LoginState:
        return self._states.get(login_id) or LoginState(
            login_id=login_id, status=LoginStatus.ERROR, error="login_id topilmadi"
        )

    async def start_phone_login(self, phone: str) -> LoginState:
        login_id = uuid.uuid4().hex
        self._phones[login_id] = phone
        state = LoginState(login_id=login_id, status=LoginStatus.CODE_SENT)
        self._states[login_id] = state
        return state

    async def submit_code(self, login_id: str, code: str) -> LoginState:
        state = self._states[login_id]
        if code != MOCK_CODE:
            state.status = LoginStatus.ERROR
            state.error = "Noto'g'ri kod (mock rejimda kod har doim 00000)"
            return state
        self._simulate_success(state)
        return state

    async def submit_password(self, login_id: str, password: str) -> LoginState:
        state = self._states[login_id]
        self._simulate_success(state)
        return state

    async def simulate_scan(
        self,
        login_id: str,
        need_password: bool = False,
        telegram_user_id: int | None = None,
        username: str | None = None,
        first_name: str = "Mock",
        last_name: str | None = None,
        is_premium: bool = False,
    ) -> LoginState:
        """Faqat mock rejimda: real telefon bilan QR skan qilishni simulyatsiya qiladi."""
        state = self._states[login_id]
        if need_password:
            state.status = LoginStatus.NEED_PASSWORD
            return state
        self._simulate_success(
            state,
            telegram_user_id=telegram_user_id,
            username=username,
            first_name=first_name,
            last_name=last_name,
            is_premium=is_premium,
        )
        return state

    def _simulate_success(
        self,
        state: LoginState,
        telegram_user_id: int | None = None,
        username: str | None = None,
        first_name: str = "Mock",
        last_name: str | None = None,
        is_premium: bool = False,
    ) -> None:
        state.telegram_user_id = telegram_user_id or next(_fake_telegram_id)
        state.username = username
        state.first_name = first_name
        state.last_name = last_name
        state.is_premium = is_premium
        state.session_string = f"mock-session-{state.login_id}"
        state.status = LoginStatus.SUCCESS

    async def revoke(self, session_string: str) -> None:
        return None

    async def cleanup(self, login_id: str) -> None:
        self._states.pop(login_id, None)
        self._phones.pop(login_id, None)
