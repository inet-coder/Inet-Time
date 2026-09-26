import datetime

from sqlalchemy import Boolean, DateTime, Enum, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from core.db.base import Base
from core.db.enums import AutomationPriority, AutomationStatus, ProfileField, SelectionStrategy, TriggerType
from core.db.mixins import TimestampMixin


class Automation(TimestampMixin, Base):
    """Trigger + Actions[] engine ustidagi ishlaydigan instans (bitta akkauntdagi bitta preset)."""

    __tablename__ = "automations"

    id: Mapped[int] = mapped_column(primary_key=True)
    telegram_account_id: Mapped[int] = mapped_column(
        ForeignKey("telegram_accounts.id", ondelete="CASCADE"), index=True
    )
    service_id: Mapped[int] = mapped_column(ForeignKey("services.id"), index=True)
    status: Mapped[AutomationStatus] = mapped_column(
        Enum(AutomationStatus, native_enum=False, length=24),
        default=AutomationStatus.DRAFT,
        index=True,
    )
    priority: Mapped[AutomationPriority] = mapped_column(
        Enum(AutomationPriority, native_enum=False, length=16), default=AutomationPriority.NORMAL
    )
    restore_on_stop: Mapped[bool] = mapped_column(Boolean, default=True)
    selection_strategy: Mapped[SelectionStrategy] = mapped_column(
        Enum(SelectionStrategy, native_enum=False, length=16), default=SelectionStrategy.NONE
    )
    last_playlist_index: Mapped[int] = mapped_column(Integer, default=0)
    started_at: Mapped[datetime.datetime | None] = mapped_column(DateTime(timezone=True))
    expires_at: Mapped[datetime.datetime | None] = mapped_column(DateTime(timezone=True))
    error_message: Mapped[str | None] = mapped_column(Text)


class AutomationAction(TimestampMixin, Base):
    """Field ← template. Bir automation bir nechta field'ga ta'sir qilishi mumkin (Combo)."""

    __tablename__ = "automation_actions"

    id: Mapped[int] = mapped_column(primary_key=True)
    automation_id: Mapped[int] = mapped_column(ForeignKey("automations.id", ondelete="CASCADE"), index=True)
    field: Mapped[ProfileField] = mapped_column(
        Enum(ProfileField, native_enum=False, length=16, values_callable=lambda e: [m.value for m in e]),
        index=True,
    )
    template: Mapped[str] = mapped_column(Text)
    order_index: Mapped[int] = mapped_column(Integer, default=0)


class Schedule(TimestampMixin, Base):
    """Automation'ning trigger konfiguratsiyasi: interval | schedule(cron) | window(start..end)."""

    __tablename__ = "schedules"

    id: Mapped[int] = mapped_column(primary_key=True)
    automation_id: Mapped[int] = mapped_column(ForeignKey("automations.id", ondelete="CASCADE"), unique=True)
    trigger_type: Mapped[TriggerType] = mapped_column(Enum(TriggerType, native_enum=False, length=16))
    interval_seconds: Mapped[int | None] = mapped_column(Integer)
    cron_expr: Mapped[str | None] = mapped_column(String(64))
    window_start_at: Mapped[datetime.datetime | None] = mapped_column(DateTime(timezone=True))
    window_end_at: Mapped[datetime.datetime | None] = mapped_column(DateTime(timezone=True))
    timezone: Mapped[str] = mapped_column(String(64), default="UTC")
    next_run_at: Mapped[datetime.datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    last_run_at: Mapped[datetime.datetime | None] = mapped_column(DateTime(timezone=True))


class ProfileSnapshot(TimestampMixin, Base):
    """Service boshlanishidagi field qiymati — to'xtaganda Restore/Keep uchun."""

    __tablename__ = "profile_snapshots"

    id: Mapped[int] = mapped_column(primary_key=True)
    telegram_account_id: Mapped[int] = mapped_column(
        ForeignKey("telegram_accounts.id", ondelete="CASCADE"), index=True
    )
    automation_id: Mapped[int | None] = mapped_column(ForeignKey("automations.id", ondelete="SET NULL"))
    field: Mapped[ProfileField] = mapped_column(
        Enum(ProfileField, native_enum=False, length=16, values_callable=lambda e: [m.value for m in e])
    )
    value: Mapped[str | None] = mapped_column(Text)
    captured_at: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True))
    restored: Mapped[bool] = mapped_column(Boolean, default=False)
