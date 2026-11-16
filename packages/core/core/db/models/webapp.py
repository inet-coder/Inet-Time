import datetime
import decimal

from sqlalchemy import JSON, BigInteger, Boolean, DateTime, ForeignKey, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column

from core.db.base import Base
from core.db.mixins import CreatedAtMixin, TimestampMixin


class WebApp(TimestampMixin, Base):
    """Bot uchun kodsiz Web App (Telegram Mini App). Hujjat formati — core/webapp_builder.py.

    draft — konstruktorda tahrirlanadi; published — foydalanuvchilar ko'radigan nusxa («E'lon qilish»da
    draft tekshirilib ko'chiriladi). Shu tufayli tahrirlash jarayoni ishlab turgan ilovani buzmaydi."""

    __tablename__ = "web_apps"

    id: Mapped[int] = mapped_column(primary_key=True)
    bot_id: Mapped[int] = mapped_column(ForeignKey("user_bots.id", ondelete="CASCADE"), unique=True)
    draft: Mapped[dict] = mapped_column(JSON)
    published: Mapped[dict | None] = mapped_column(JSON)
    published_at: Mapped[datetime.datetime | None] = mapped_column(DateTime(timezone=True))
    # Botning chap pastdagi menyu tugmasi ilovani ochsin
    menu_button: Mapped[bool] = mapped_column(Boolean, default=True)
    menu_button_text: Mapped[str] = mapped_column(String(32), default="Ochish")


class WebAppSubmission(CreatedAtMixin, Base):
    """Web App'dan kelgan forma yoki buyurtma."""

    __tablename__ = "webapp_submissions"

    id: Mapped[int] = mapped_column(primary_key=True)
    app_id: Mapped[int] = mapped_column(ForeignKey("web_apps.id", ondelete="CASCADE"), index=True)
    tg_user_id: Mapped[int] = mapped_column(BigInteger)
    tg_name: Mapped[str | None] = mapped_column(String(128))
    tg_username: Mapped[str | None] = mapped_column(String(64))
    # form | order
    kind: Mapped[str] = mapped_column(String(16))
    title: Mapped[str] = mapped_column(String(128))
    data: Mapped[dict] = mapped_column(JSON)
    total: Mapped[decimal.Decimal | None] = mapped_column(Numeric(14, 2))
    # new | done
    status: Mapped[str] = mapped_column(String(16), default="new", index=True)


class WebAppVersion(CreatedAtMixin, Base):
    """Har bir «E'lon qilish» — alohida versiya. Istalgan vaqtda qoralamaga qaytarish mumkin."""

    __tablename__ = "web_app_versions"

    id: Mapped[int] = mapped_column(primary_key=True)
    app_id: Mapped[int] = mapped_column(ForeignKey("web_apps.id", ondelete="CASCADE"), index=True)
    doc: Mapped[dict] = mapped_column(JSON)
