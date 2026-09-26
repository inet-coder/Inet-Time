from sqlalchemy import ForeignKey, LargeBinary, String
from sqlalchemy.orm import Mapped, mapped_column

from core.db.base import Base
from core.db.mixins import CreatedAtMixin


class MediaFile(CreatedAtMixin, Base):
    """Foydalanuvchi yuklagan rasm (profil rasmi aylantirish uchun). Worker bu baytlarni o'zi yuklaydi —
    bot file_id'si userbot sessiyasi uchun yaroqsiz."""

    __tablename__ = "media_files"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    mime: Mapped[str] = mapped_column(String(32), default="image/jpeg")
    data: Mapped[bytes] = mapped_column(LargeBinary)
