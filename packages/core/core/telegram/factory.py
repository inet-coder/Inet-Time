from functools import lru_cache

from core.settings import settings
from core.telegram.base import TelegramAdapter


@lru_cache
def get_adapter() -> TelegramAdapter:
    """Bitta process ichida bitta adapter instansi (login holatlarini xotirada ushlab turadi)."""
    if settings.mock_telegram:
        from core.telegram.mock_adapter import MockAdapter

        return MockAdapter()
    from core.telegram.telethon_adapter import TelethonAdapter

    return TelethonAdapter()
