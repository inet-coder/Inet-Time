from sqlalchemy import Boolean, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from core.db.base import Base
from core.db.mixins import CreatedAtMixin, TimestampMixin


class AccountAI(TimestampMixin, Base):
    """Akkaunt uchun AI avto-javob sozlamalari (faqat shaxsiy chatlarda ishlaydi)."""

    __tablename__ = "account_ai_settings"

    id: Mapped[int] = mapped_column(primary_key=True)
    telegram_account_id: Mapped[int] = mapped_column(
        ForeignKey("telegram_accounts.id", ondelete="CASCADE"), unique=True, index=True
    )
    enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    preset: Mapped[str] = mapped_column(String(32), default="busy")
    # O'z uslubi (preset="custom" bo'lganda) — qisqa, token tejash uchun cheklangan.
    style: Mapped[str | None] = mapped_column(Text)
    # Egasi shu chatda yaqinda yozgan bo'lsa AI jim turadi.
    only_when_away: Mapped[bool] = mapped_column(Boolean, default=True)
    # Javob boshida 🤖 — suhbatdosh avto-javob ekanini bilsin.
    signature: Mapped[bool] = mapped_column(Boolean, default=True)


class AIUsage(CreatedAtMixin, Base):
    """Har bir AI chaqiruvi — xarajatni kuzatish uchun."""

    __tablename__ = "ai_usage"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    kind: Mapped[str] = mapped_column(String(16))  # reply | suggest | test
    model: Mapped[str] = mapped_column(String(64))
    input_tokens: Mapped[int] = mapped_column(Integer, default=0)
    output_tokens: Mapped[int] = mapped_column(Integer, default=0)
