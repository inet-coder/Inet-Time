import datetime

from sqlalchemy import Boolean, DateTime, Enum, ForeignKey, Integer, LargeBinary, String
from sqlalchemy.orm import Mapped, mapped_column

from core.db.base import Base
from core.db.enums import TelegramAccountStatus
from core.db.mixins import TimestampMixin


class TelegramAccount(TimestampMixin, Base):
    __tablename__ = "telegram_accounts"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    telegram_user_id: Mapped[int | None] = mapped_column(unique=True, index=True)
    phone_last4: Mapped[str | None] = mapped_column(String(4))
    phone_encrypted: Mapped[bytes | None] = mapped_column(LargeBinary)
    username: Mapped[str | None] = mapped_column(String(64))
    first_name: Mapped[str | None] = mapped_column(String(128))
    last_name: Mapped[str | None] = mapped_column(String(128))
    is_premium: Mapped[bool] = mapped_column(Boolean, default=False)
    status: Mapped[TelegramAccountStatus] = mapped_column(
        Enum(TelegramAccountStatus, native_enum=False, length=16),
        default=TelegramAccountStatus.CONNECTED,
        index=True,
    )
    last_connected_at: Mapped[datetime.datetime | None] = mapped_column(DateTime(timezone=True))


class EncryptedSession(TimestampMixin, Base):
    __tablename__ = "encrypted_sessions"

    id: Mapped[int] = mapped_column(primary_key=True)
    telegram_account_id: Mapped[int] = mapped_column(
        ForeignKey("telegram_accounts.id", ondelete="CASCADE"), unique=True
    )
    ciphertext: Mapped[bytes] = mapped_column(LargeBinary)
    nonce: Mapped[bytes] = mapped_column(LargeBinary)
    key_version: Mapped[int] = mapped_column(Integer, default=1)
    revoked_at: Mapped[datetime.datetime | None] = mapped_column(DateTime(timezone=True))
