import datetime

from pydantic import BaseModel, ConfigDict


class UserCreate(BaseModel):
    telegram_user_id: int | None = None
    username: str | None = None
    first_name: str | None = None


class UserGetOrCreate(BaseModel):
    telegram_user_id: int
    username: str | None = None
    first_name: str | None = None
    last_name: str | None = None
    language_code: str | None = None
    referral_code: str | None = None


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


class ActionIn(BaseModel):
    field: str
    template: str
    order_index: int = 0


class ScheduleIn(BaseModel):
    trigger_type: str = "INTERVAL"
    interval_seconds: int | None = None
    cron_expr: str | None = None
    window_start_at: datetime.datetime | None = None
    window_end_at: datetime.datetime | None = None
    timezone: str = "UTC"


class AutomationCreate(BaseModel):
    telegram_account_id: int
    service_code: str
    priority: str = "NORMAL"
    restore_on_stop: bool = True
    selection_strategy: str = "NONE"
    actions: list[ActionIn]
    schedule: ScheduleIn


class AutomationOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    telegram_account_id: int
    service_id: int
    status: str
    priority: str
    selection_strategy: str
    restore_on_stop: bool
    started_at: datetime.datetime | None
    error_message: str | None


class ActivateRequest(BaseModel):
    resolution: str | None = None


class StopRequest(BaseModel):
    restore: bool | None = None


class AppliedAction(BaseModel):
    field: str
    value: str


class RunResult(BaseModel):
    applied: list[AppliedAction]
