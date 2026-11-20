import datetime

from sqlalchemy import JSON, BigInteger, Boolean, DateTime, ForeignKey, Index, Integer, LargeBinary, String, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from core.db.base import Base
from core.db.mixins import CreatedAtMixin, TimestampMixin


class UserBot(TimestampMixin, Base):
    """Foydalanuvchi o'z tokeni bilan ulagan bot (konstruktor). Menyu — bitta JSON hujjat (core/botbuilder.py)."""

    __tablename__ = "user_bots"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    bot_telegram_id: Mapped[int] = mapped_column(BigInteger, unique=True)
    username: Mapped[str] = mapped_column(String(64))
    name: Mapped[str] = mapped_column(String(128))
    # AES-256-GCM (core.crypto.encrypt_packed) — token hech qachon ochiq saqlanmaydi.
    token_encrypted: Mapped[bytes] = mapped_column(LargeBinary)
    # active | paused | error
    status: Mapped[str] = mapped_column(String(16), default="active", index=True)
    error_message: Mapped[str | None] = mapped_column(Text)
    menu: Mapped[dict] = mapped_column(JSON)
    # Bot darajasidagi (global) o'zgaruvchilar: {kalit: qiymat}
    vars: Mapped[dict] = mapped_column(JSONB, default=dict, server_default="{}")


class BotSubscriber(Base):
    __tablename__ = "bot_subscribers"
    __table_args__ = (UniqueConstraint("bot_id", "tg_user_id", name="uq_bot_subscriber"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    bot_id: Mapped[int] = mapped_column(ForeignKey("user_bots.id", ondelete="CASCADE"), index=True)
    tg_user_id: Mapped[int] = mapped_column(BigInteger)
    first_name: Mapped[str | None] = mapped_column(String(128))
    username: Mapped[str | None] = mapped_column(String(64))
    started_at: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    last_active_at: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    blocked: Mapped[bool] = mapped_column(Boolean, default=False)
    # Foydalanuvchi o'zgaruvchilari (forma javoblari, ball, telefon...) — ID bo'yicha eslab qolinadi
    data: Mapped[dict] = mapped_column(JSONB, default=dict, server_default="{}")
    referred_by: Mapped[int | None] = mapped_column(BigInteger)
    ref_count: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    # Egasi bloklagan — bot javob bermaydi
    banned: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")


class BotBroadcast(CreatedAtMixin, Base):
    __tablename__ = "bot_broadcasts"

    id: Mapped[int] = mapped_column(primary_key=True)
    bot_id: Mapped[int] = mapped_column(ForeignKey("user_bots.id", ondelete="CASCADE"), index=True)
    text: Mapped[str] = mapped_column(Text)
    media_id: Mapped[int | None] = mapped_column(ForeignKey("media_files.id", ondelete="SET NULL"))
    # Egasi o'z botida yuborgan xabar (istalgan turi) — copyMessage bilan tarqatiladi; bo'lsa text/media ishlatilmaydi.
    from_chat_id: Mapped[int | None] = mapped_column(BigInteger)
    message_id: Mapped[int | None] = mapped_column(Integer)
    # sending | done
    status: Mapped[str] = mapped_column(String(16), default="sending")
    total: Mapped[int] = mapped_column(Integer, default=0)
    sent: Mapped[int] = mapped_column(Integer, default=0)
    failed: Mapped[int] = mapped_column(Integer, default=0)
    finished_at: Mapped[datetime.datetime | None] = mapped_column(DateTime(timezone=True))


class BotFormAnswer(CreatedAtMixin, Base):
    """Bot formasiga berilgan javoblar (egasi ko'radi va CSV yuklab oladi)."""

    __tablename__ = "bot_form_answers"
    __table_args__ = (Index("ix_bot_form_answers_bot_form", "bot_id", "form_id"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    bot_id: Mapped[int] = mapped_column(ForeignKey("user_bots.id", ondelete="CASCADE"))
    tg_user_id: Mapped[int] = mapped_column(BigInteger)
    form_id: Mapped[str] = mapped_column(String(24))
    data: Mapped[dict] = mapped_column(JSONB)


class BotOrder(TimestampMixin, Base):
    """Bot do'konidagi buyurtma. Raqam — har bir bot uchun alohida ketma-ketlik (#1, #2...)."""

    __tablename__ = "bot_orders"
    __table_args__ = (UniqueConstraint("bot_id", "number", name="uq_bot_order_number"), Index("ix_bot_orders_user", "bot_id", "tg_user_id"))

    id: Mapped[int] = mapped_column(primary_key=True)
    bot_id: Mapped[int] = mapped_column(ForeignKey("user_bots.id", ondelete="CASCADE"))
    number: Mapped[int] = mapped_column(Integer)
    tg_user_id: Mapped[int] = mapped_column(BigInteger)
    items: Mapped[list] = mapped_column(JSONB)  # [{id, title, price, qty}]
    total: Mapped[int] = mapped_column(BigInteger)
    delivery: Mapped[int] = mapped_column(BigInteger, default=0)
    data: Mapped[dict] = mapped_column(JSONB)  # rasmiylashtirish javoblari
    # new | accepted | delivering | done | cancelled
    status: Mapped[str] = mapped_column(String(16), default="new", index=True)
