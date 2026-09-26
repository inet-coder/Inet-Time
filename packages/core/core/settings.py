from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = ""
    redis_url: str = ""

    bot_token: str = ""
    telegram_api_id: int = 0
    telegram_api_hash: str = ""

    @field_validator("telegram_api_id", mode="before")
    @classmethod
    def _empty_str_to_zero(cls, v):
        return 0 if v == "" else v

    session_encryption_key: str = ""
    jwt_secret: str = ""
    admin_secret: str = ""
    admin_telegram_ids: str = ""
    # Balans to'ldirishda foydalanuvchiga ko'rsatiladi (masalan: karta raqami va egasi).
    payment_instructions: str = ""
    default_timezone: str = "Asia/Tashkent"

    @property
    def admin_telegram_id_set(self) -> set[int]:
        return {int(x) for x in self.admin_telegram_ids.split(",") if x.strip()}

    mock_telegram: bool = False

    api_base_url: str = "http://api:8000"


settings = Settings()
