from pydantic import BaseModel, ConfigDict


class UserCreate(BaseModel):
    telegram_user_id: int | None = None
    username: str | None = None
    first_name: str | None = None


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    telegram_user_id: int | None
    username: str | None
    first_name: str | None
    referral_code: str


class QrLoginStart(BaseModel):
    user_id: int


class PhoneLoginStart(BaseModel):
    user_id: int
    phone: str


class CodeSubmit(BaseModel):
    code: str


class PasswordSubmit(BaseModel):
    password: str


class MockSimulateScan(BaseModel):
    need_password: bool = False
    telegram_user_id: int | None = None
    username: str | None = None
    first_name: str = "Mock"
    last_name: str | None = None
    is_premium: bool = False


class LoginStatusOut(BaseModel):
    login_id: str
    status: str
    qr_url: str | None = None
    error: str | None = None
    account_id: int | None = None
    telegram_user_id: int | None = None
    username: str | None = None


class AccountOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: int
    telegram_user_id: int | None
    username: str | None
    first_name: str | None
    last_name: str | None
    is_premium: bool
    status: str
