from functools import lru_cache

from core.settings import settings
from core.telegram.field_adapter import FieldAdapter


@lru_cache
def get_field_adapter() -> FieldAdapter:
    if settings.mock_telegram:
        from core.telegram.mock_field_adapter import MockFieldAdapter

        return MockFieldAdapter()
    from core.telegram.telethon_field_adapter import TelethonFieldAdapter

    return TelethonFieldAdapter()
