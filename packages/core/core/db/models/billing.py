import datetime
import decimal

from sqlalchemy import JSON, Boolean, DateTime, Enum, ForeignKey, Integer, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from core.db.base import Base
from core.db.enums import PaymentMethod, PaymentStatus, SubscriptionStatus, TransactionType
from core.db.mixins import TimestampMixin


class Plan(TimestampMixin, Base):
    __tablename__ = "plans"

    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(String(32), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(128))
    price: Mapped[decimal.Decimal] = mapped_column(Numeric(14, 2))
    duration_days: Mapped[int] = mapped_column(Integer)
    # tarif flag'lari: account_limit, max_bio_items, scheduler_limit, online_service, emoji_service, ...
    flags: Mapped[dict] = mapped_column(JSON, default=dict)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


class Subscription(TimestampMixin, Base):
    __tablename__ = "subscriptions"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    plan_id: Mapped[int] = mapped_column(ForeignKey("plans.id"), index=True)
    status: Mapped[SubscriptionStatus] = mapped_column(
        Enum(SubscriptionStatus, native_enum=False, length=16),
        default=SubscriptionStatus.ACTIVE,
        index=True,
    )
    started_at: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True))
    expires_at: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True), index=True)
    auto_renew: Mapped[bool] = mapped_column(Boolean, default=False)


class Service(TimestampMixin, Base):
    """SKU/preset katalogi: Clock Name, Auto Bio, Playlist, Scheduler, Scenario, Combo, ..."""

    __tablename__ = "services"

    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(String(32), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(128))
    description: Mapped[str | None] = mapped_column(Text)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


class Payment(TimestampMixin, Base):
    __tablename__ = "payments"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    plan_id: Mapped[int | None] = mapped_column(ForeignKey("plans.id"))
    subscription_id: Mapped[int | None] = mapped_column(ForeignKey("subscriptions.id"))
    amount: Mapped[decimal.Decimal] = mapped_column(Numeric(14, 2))
    currency: Mapped[str] = mapped_column(String(8), default="UZS")
    method: Mapped[PaymentMethod] = mapped_column(Enum(PaymentMethod, native_enum=False, length=16))
    status: Mapped[PaymentStatus] = mapped_column(
        Enum(PaymentStatus, native_enum=False, length=16),
        default=PaymentStatus.PENDING,
        index=True,
    )
    external_ref: Mapped[str | None] = mapped_column(String(128))
    confirmed_at: Mapped[datetime.datetime | None] = mapped_column(DateTime(timezone=True))
    confirmed_by_admin_id: Mapped[int | None] = mapped_column(ForeignKey("admin_users.id"))


class Transaction(TimestampMixin, Base):
    """Balans ledger (double-entry): har yozuv balansdagi bitta o'zgarishni bildiradi."""

    __tablename__ = "transactions"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    type: Mapped[TransactionType] = mapped_column(
        Enum(TransactionType, native_enum=False, length=24), index=True
    )
    amount: Mapped[decimal.Decimal] = mapped_column(Numeric(14, 2))
    balance_after: Mapped[decimal.Decimal] = mapped_column(Numeric(14, 2))
    reference_payment_id: Mapped[int | None] = mapped_column(ForeignKey("payments.id"))
    reference_subscription_id: Mapped[int | None] = mapped_column(ForeignKey("subscriptions.id"))


class Referral(TimestampMixin, Base):
    __tablename__ = "referrals"

    id: Mapped[int] = mapped_column(primary_key=True)
    referrer_user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    referred_user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), unique=True)
    code: Mapped[str] = mapped_column(String(16), index=True)


class ReferralTransaction(TimestampMixin, Base):
    __tablename__ = "referral_transactions"

    id: Mapped[int] = mapped_column(primary_key=True)
    referral_id: Mapped[int] = mapped_column(ForeignKey("referrals.id", ondelete="CASCADE"), index=True)
    transaction_id: Mapped[int] = mapped_column(ForeignKey("transactions.id", ondelete="CASCADE"))
    amount: Mapped[decimal.Decimal] = mapped_column(Numeric(14, 2))
