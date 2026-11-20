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
    # Telegram Payments provayder tokeni (sir — menyu hujjatiga yozilmaydi, AI ko'rmaydi)
    pay_token_encrypted: Mapped[bytes | None] = mapped_column(LargeBinary)
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
    segment: Mapped[str] = mapped_column(String(16), default="all", server_default="all")
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
    # awaiting | new | accepted | delivering | done | cancelled
    status: Mapped[str] = mapped_column(String(16), default="new", index=True)
    paid: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")
    payment: Mapped[str] = mapped_column(String(8), default="", server_default="")  # "" | cash | card
    discount: Mapped[int] = mapped_column(BigInteger, default=0, server_default="0")
    promo: Mapped[str] = mapped_column(String(16), default="", server_default="")


class BotBooking(TimestampMixin, Base):
    """Yozilish (booking). starts_at — UTC; xizmat/xodim nomlari yozilish paytidagi nusxa (keyin o'zgarsa ham tarix saqlanadi)."""

    __tablename__ = "bot_bookings"
    __table_args__ = (Index("ix_bot_bookings_time", "bot_id", "starts_at"), Index("ix_bot_bookings_user", "bot_id", "tg_user_id"))

    id: Mapped[int] = mapped_column(primary_key=True)
    bot_id: Mapped[int] = mapped_column(ForeignKey("user_bots.id", ondelete="CASCADE"))
    number: Mapped[int] = mapped_column(Integer)
    tg_user_id: Mapped[int] = mapped_column(BigInteger)
    service_id: Mapped[str] = mapped_column(String(32))
    service_title: Mapped[str] = mapped_column(String(64))
    staff_id: Mapped[str] = mapped_column(String(32), default="main")
    staff_title: Mapped[str] = mapped_column(String(64), default="")
    starts_at: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True))
    minutes: Mapped[int] = mapped_column(Integer)
    price: Mapped[int] = mapped_column(BigInteger, default=0)
    data: Mapped[dict] = mapped_column(JSONB)  # mijoz javoblari (ism, telefon...)
    # pending | confirmed | cancelled | done
    status: Mapped[str] = mapped_column(String(12), default="pending", index=True)
    reminded: Mapped[list] = mapped_column(JSONB, default=list)  # yuborilgan eslatmalar (soat oldin)


class BotAutoLog(Base):
    """Avtomatik xabar yuborilganlik yozuvi — bir foydalanuvchiga bir qoida bir davrda (period) faqat bir marta."""

    __tablename__ = "bot_auto_log"
    __table_args__ = (UniqueConstraint("bot_id", "rule_id", "tg_user_id", "period", name="uq_bot_auto_log"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    bot_id: Mapped[int] = mapped_column(ForeignKey("user_bots.id", ondelete="CASCADE"), index=True)
    rule_id: Mapped[str] = mapped_column(String(32))
    tg_user_id: Mapped[int] = mapped_column(BigInteger)  # 0 — qoida darajasidagi belgi (jadval bo'yicha tarqatish)
    period: Mapped[str] = mapped_column(String(32))
    sent_at: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class BotContestEntry(Base):
    """Konkursda qatnashuvchi (har kim bir konkursda bir marta)."""

    __tablename__ = "bot_contest_entries"
    __table_args__ = (UniqueConstraint("bot_id", "contest_id", "tg_user_id", name="uq_bot_contest_entry"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    bot_id: Mapped[int] = mapped_column(ForeignKey("user_bots.id", ondelete="CASCADE"), index=True)
    contest_id: Mapped[str] = mapped_column(String(32))
    tg_user_id: Mapped[int] = mapped_column(BigInteger)
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class BotTicket(TimestampMixin, Base):
    """Murojaat (tiket): foydalanuvchining ochiq suhbati. Xabarlarning o'zi Telegramda; bu yerda holat va mas'ul."""

    __tablename__ = "bot_tickets"
    __table_args__ = (Index("ix_bot_tickets_status", "bot_id", "status"), Index("ix_bot_tickets_user", "bot_id", "tg_user_id"))

    id: Mapped[int] = mapped_column(primary_key=True)
    bot_id: Mapped[int] = mapped_column(ForeignKey("user_bots.id", ondelete="CASCADE"))
    number: Mapped[int] = mapped_column(Integer)
    tg_user_id: Mapped[int] = mapped_column(BigInteger)
    status: Mapped[str] = mapped_column(String(8), default="open")  # open | closed
    assignee: Mapped[int | None] = mapped_column(BigInteger)  # mas'ul xodim (Telegram ID)
    preview: Mapped[str] = mapped_column(String(200), default="")
    messages: Mapped[int] = mapped_column(Integer, default=1)
    rating: Mapped[int | None] = mapped_column(Integer)
    first_reply_at: Mapped[datetime.datetime | None] = mapped_column(DateTime(timezone=True))
    closed_at: Mapped[datetime.datetime | None] = mapped_column(DateTime(timezone=True))


class BotPost(Base):
    """Kanalga rejalashtirilgan / yuborilgan post: egasining xabari nusxalanadi (copyMessage)."""

    __tablename__ = "bot_posts"
    __table_args__ = (Index("ix_bot_posts_due", "status", "publish_at"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    bot_id: Mapped[int] = mapped_column(ForeignKey("user_bots.id", ondelete="CASCADE"), index=True)
    channel_id: Mapped[int] = mapped_column(BigInteger)
    channel_title: Mapped[str] = mapped_column(String(64), default="")
    from_chat_id: Mapped[int] = mapped_column(BigInteger)
    message_id: Mapped[int] = mapped_column(Integer)
    buttons: Mapped[list] = mapped_column(JSONB, default=list)  # [[{text, url}]]
    publish_at: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True))
    status: Mapped[str] = mapped_column(String(10), default="scheduled")  # scheduled | sent | failed | cancelled
    error: Mapped[str] = mapped_column(String(200), default="")
    sent_at: Mapped[datetime.datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
