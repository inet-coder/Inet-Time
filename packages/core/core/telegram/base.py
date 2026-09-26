from abc import ABC, abstractmethod

from core.telegram.types import LoginState


class TelegramAdapter(ABC):
    """QR va telefon+kod login oqimlari uchun umumiy interfeys.

    Field update (name/bio/emoji_status/online/photo) PHASE 5'da
    FieldAdapter orqali qo'shiladi — bu yerda emas.
    """

    @abstractmethod
    async def start_qr_login(self) -> LoginState: ...

    @abstractmethod
    async def get_login_state(self, login_id: str) -> LoginState: ...

    @abstractmethod
    async def start_phone_login(self, phone: str) -> LoginState: ...

    @abstractmethod
    async def submit_code(self, login_id: str, code: str) -> LoginState: ...

    @abstractmethod
    async def submit_password(self, login_id: str, password: str) -> LoginState: ...

    @abstractmethod
    async def revoke(self, session_string: str) -> None: ...

    @abstractmethod
    async def cleanup(self, login_id: str) -> None: ...
