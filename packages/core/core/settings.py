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
    # Ichki API (bot -> api) kaliti: /webapp va /health'dan boshqa barcha yo'llar shu sarlavhani talab qiladi.
    internal_api_token: str = ""
    # development | production — production'da maxfiy kalitlarsiz ishga tushmaydi, /docs yopiq.
    environment: str = "development"
    admin_telegram_ids: str = ""
    # Balans to'ldirishda foydalanuvchiga ko'rsatiladi (masalan: karta raqami va egasi).
    payment_instructions: str = ""
    default_timezone: str = "Asia/Tashkent"
    # Mini App manzili. Bo'sh bo'lsa bot uni cloudflared quick tunnel'dan o'zi aniqlaydi.
    webapp_url: str = ""
    tunnel_metrics_url: str = "http://tunnel:2000/quicktunnel"

    @property
    def is_production(self) -> bool:
        return self.environment.lower() == "production"

    def missing_production_secrets(self) -> list[str]:
        required = {
            "BOT_TOKEN": self.bot_token,
            "TELEGRAM_API_ID": self.telegram_api_id,
            "TELEGRAM_API_HASH": self.telegram_api_hash,
            "SESSION_ENCRYPTION_KEY": self.session_encryption_key,
            "JWT_SECRET": self.jwt_secret,
            "ADMIN_SECRET": self.admin_secret,
            "INTERNAL_API_TOKEN": self.internal_api_token,
            "WEBAPP_URL": self.webapp_url,
        }
        missing = [name for name, value in required.items() if not value]
        if self.mock_telegram:
            missing.append("MOCK_TELEGRAM=false")
        return missing

    @property
    def admin_telegram_id_set(self) -> set[int]:
        return {int(x) for x in self.admin_telegram_ids.split(",") if x.strip()}

    mock_telegram: bool = False

    api_base_url: str = "http://api:8000"


settings = Settings()
