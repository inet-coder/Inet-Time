"""pro services: playlist, schedule, emoji, photo

Revision ID: e1f2a3b4c5d6
Revises: d7e8f9a0b1c2
Create Date: 2026-09-26 12:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "e1f2a3b4c5d6"
down_revision: Union[str, None] = "d7e8f9a0b1c2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

services_table = sa.table(
    "services",
    sa.column("code", sa.String),
    sa.column("name", sa.String),
    sa.column("description", sa.Text),
    sa.column("is_active", sa.Boolean),
)

NEW_SERVICES = [
    ("schedule", "Jadval", "Bio/ism belgilangan vaqtlarda o'zgaradi"),
    ("emoji", "Emoji status", "Premium emoji status avtomatik o'rnatiladi/aylanadi"),
    ("photo", "Rasm almashtirish", "Profil rasmi navbat bilan almashadi"),
]

PRO_ONLY_FLAGS = ("playlist_service", "schedule_service", "photo_service")


def upgrade() -> None:
    op.add_column("automation_actions", sa.Column("at_time", sa.String(length=5), nullable=True))

    op.create_table(
        "media_files",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("mime", sa.String(length=32), nullable=False),
        sa.Column("data", sa.LargeBinary(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_media_files_user_id"), "media_files", ["user_id"], unique=False)

    op.bulk_insert(
        services_table,
        [{"code": c, "name": n, "description": d, "is_active": True} for c, n, d in NEW_SERVICES],
    )

    pro = "{" + ", ".join(f'"{f}": true' for f in PRO_ONLY_FLAGS) + "}"
    starter = "{" + ", ".join(f'"{f}": false' for f in PRO_ONLY_FLAGS) + "}"
    op.execute(f"UPDATE plans SET flags = (flags::jsonb || '{pro}'::jsonb)::json WHERE code = 'pro'")
    op.execute(f"UPDATE plans SET flags = (flags::jsonb || '{starter}'::jsonb)::json WHERE code = 'starter'")


def downgrade() -> None:
    for flag in PRO_ONLY_FLAGS:
        op.execute(f"UPDATE plans SET flags = (flags::jsonb - '{flag}')::json")
    op.execute(services_table.delete().where(services_table.c.code.in_([c for c, _, _ in NEW_SERVICES])))
    op.drop_index(op.f("ix_media_files_user_id"), table_name="media_files")
    op.drop_table("media_files")
    op.drop_column("automation_actions", "at_time")
