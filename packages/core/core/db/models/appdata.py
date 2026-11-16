import datetime

from sqlalchemy import JSON, BigInteger, Boolean, DateTime, ForeignKey, Integer, String, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from core.db.base import Base
from core.db.mixins import TimestampMixin


class AppCollection(TimestampMixin, Base):
    """Web App ma'lumotlar to'plami (egasining o'z jadvali): mahsulotlar, xizmatlar, arizalar...

    fields — [{key, label, type, required, private, options}] (core/appdata.py).
    read:   public — ilovaning hamma foydalanuvchisi ko'radi; own — har kim faqat o'zi qo'shganini; none — faqat egasi.
    create: true — foydalanuvchilar ilovadagi forma orqali yozuv qo'sha oladi."""

    __tablename__ = "app_collections"
    __table_args__ = (UniqueConstraint("app_id", "key", name="uq_app_collection_key"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    app_id: Mapped[int] = mapped_column(ForeignKey("web_apps.id", ondelete="CASCADE"), index=True)
    key: Mapped[str] = mapped_column(String(32))
    name: Mapped[str] = mapped_column(String(64))
    fields: Mapped[list] = mapped_column(JSON)
    read: Mapped[str] = mapped_column(String(8), default="public")
    create: Mapped[bool] = mapped_column(Boolean, default=False)


class AppRecord(Base):
    __tablename__ = "app_records"

    id: Mapped[int] = mapped_column(primary_key=True)
    collection_id: Mapped[int] = mapped_column(ForeignKey("app_collections.id", ondelete="CASCADE"), index=True)
    data: Mapped[dict] = mapped_column(JSONB)
    position: Mapped[int] = mapped_column(Integer, default=0)
    created_by_tg: Mapped[int | None] = mapped_column(BigInteger, index=True)
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
