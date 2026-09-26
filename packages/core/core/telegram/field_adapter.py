from abc import ABC, abstractmethod

from core.db.enums import ProfileField


class FieldAdapter(ABC):
    """Bitta profil maydonini o'qish/yangilash. Session hech qachon qaytarilmaydi/loglanmaydi.

    PHOTO va BIRTHDAY hozircha implement qilinmagan ("Kelajakka tayyor" — BUILD.md).
    """

    @abstractmethod
    async def get_current_value(self, session_string: str, field: ProfileField) -> str | None: ...

    @abstractmethod
    async def apply(self, session_string: str, field: ProfileField, value: str) -> None: ...
