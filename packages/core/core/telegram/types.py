from dataclasses import dataclass

from core.telegram.enums import LoginStatus


@dataclass
class LoginState:
    login_id: str
    status: LoginStatus
    qr_url: str | None = None
    error: str | None = None
    telegram_user_id: int | None = None
    username: str | None = None
    first_name: str | None = None
    last_name: str | None = None
    is_premium: bool = False
    session_string: str | None = None
