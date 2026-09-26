import datetime

from sqlalchemy import JSON, Boolean, DateTime, Enum, ForeignKey, Integer, LargeBinary, String
from sqlalchemy.orm import Mapped, mapped_column

from core.db.base import Base
from core.db.enums import ActorType
from core.db.mixins import CreatedAtMixin, TimestampMixin


class AdminRole(TimestampMixin, Base):
    """SUPER_ADMIN / ADMIN / SUPPORT / FINANCE / OPERATOR + permissionlar."""

    __tablename__ = "admin_roles"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(32), unique=True)
    permissions: Mapped[dict] = mapped_column(JSON, default=dict)


class AdminUser(TimestampMixin, Base):
    __tablename__ = "admin_users"

    id: Mapped[int] = mapped_column(primary_key=True)
    username: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    role_id: Mapped[int] = mapped_column(ForeignKey("admin_roles.id"))
    totp_secret_encrypted: Mapped[bytes | None] = mapped_column(LargeBinary)
    is_2fa_enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    last_login_at: Mapped[datetime.datetime | None] = mapped_column(DateTime(timezone=True))


class AuditLog(CreatedAtMixin, Base):
    __tablename__ = "audit_logs"

    id: Mapped[int] = mapped_column(primary_key=True)
    actor_type: Mapped[ActorType] = mapped_column(Enum(ActorType, native_enum=False, length=16), index=True)
    actor_id: Mapped[int | None] = mapped_column(Integer, index=True)
    action: Mapped[str] = mapped_column(String(64), index=True)
    entity_type: Mapped[str | None] = mapped_column(String(64))
    entity_id: Mapped[int | None] = mapped_column(Integer)
    meta: Mapped[dict] = mapped_column(JSON, default=dict)
