import datetime

from sqlalchemy import JSON, Boolean, DateTime, Enum, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from core.db.base import Base
from core.db.enums import WorkerJobStatus
from core.db.mixins import CreatedAtMixin, TimestampMixin


class SystemSetting(TimestampMixin, Base):
    __tablename__ = "system_settings"

    id: Mapped[int] = mapped_column(primary_key=True)
    key: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    value: Mapped[dict] = mapped_column(JSON, default=dict)


class Notification(CreatedAtMixin, Base):
    __tablename__ = "notifications"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    type: Mapped[str] = mapped_column(String(64), index=True)
    title: Mapped[str] = mapped_column(String(255))
    message: Mapped[str] = mapped_column(Text)
    is_read: Mapped[bool] = mapped_column(Boolean, default=False)


class WorkerJob(TimestampMixin, Base):
    """Idempotency: har job unique job_id, ikki marta bajarilmaydi."""

    __tablename__ = "worker_jobs"

    id: Mapped[int] = mapped_column(primary_key=True)
    job_id: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    telegram_account_id: Mapped[int] = mapped_column(
        ForeignKey("telegram_accounts.id", ondelete="CASCADE"), index=True
    )
    automation_id: Mapped[int | None] = mapped_column(ForeignKey("automations.id", ondelete="SET NULL"))
    status: Mapped[WorkerJobStatus] = mapped_column(
        Enum(WorkerJobStatus, native_enum=False, length=16),
        default=WorkerJobStatus.PENDING,
        index=True,
    )
    payload: Mapped[dict] = mapped_column(JSON, default=dict)
    error: Mapped[str | None] = mapped_column(Text)
    started_at: Mapped[datetime.datetime | None] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime.datetime | None] = mapped_column(DateTime(timezone=True))
