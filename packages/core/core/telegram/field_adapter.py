from abc import ABC, abstractmethod

from core.db.enums import ProfileField


class FieldAdapter(ABC):
    """Bitta profil maydonini o'qish/yangilash. Session hech qachon qaytarilmaydi/loglanmaydi.

    PHOTO alohida metodlar orqali (baytlar kerak); BIRTHDAY hozircha implement qilinmagan.
    """

    @abstractmethod
    async def get_current_value(self, session_string: str, field: ProfileField) -> str | None: ...

    @abstractmethod
    async def apply(self, session_string: str, field: ProfileField, value: str) -> None: ...

    @abstractmethod
    async def upload_photo(self, session_string: str, data: bytes) -> dict:
        """Yangi profil rasmi qo'yadi; keyin o'chirish uchun rasm ma'lumotini qaytaradi."""

    @abstractmethod
    async def delete_photo(self, session_string: str, ref: dict) -> None:
        """Biz qo'ygan rasmni o'chiradi — foydalanuvchining oldingi (asl) rasmi yana ko'rinadi."""
