"""bot_bookings: bot yozilishlari

Revision ID: f4a5b6c7d8e9
Revises: e3f4a5b6c7d8
Create Date: 2026-11-21 10:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "f4a5b6c7d8e9"
down_revision: Union[str, None] = "e3f4a5b6c7d8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "bot_bookings",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("bot_id", sa.Integer(), nullable=False),
        sa.Column("number", sa.Integer(), nullable=False),
        sa.Column("tg_user_id", sa.BigInteger(), nullable=False),
        sa.Column("service_id", sa.String(length=32), nullable=False),
        sa.Column("service_title", sa.String(length=64), nullable=False),
        sa.Column("staff_id", sa.String(length=32), nullable=False, server_default="main"),
        sa.Column("staff_title", sa.String(length=64), nullable=False, server_default=""),
        sa.Column("starts_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("minutes", sa.Integer(), nullable=False),
        sa.Column("price", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("data", postgresql.JSONB(), nullable=False),
        sa.Column("status", sa.String(length=12), nullable=False, server_default="pending"),
        sa.Column("reminded", postgresql.JSONB(), nullable=False, server_default="[]"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["bot_id"], ["user_bots.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_bot_bookings_time", "bot_bookings", ["bot_id", "starts_at"])
    op.create_index("ix_bot_bookings_user", "bot_bookings", ["bot_id", "tg_user_id"])
    op.create_index("ix_bot_bookings_status", "bot_bookings", ["status"])


def downgrade() -> None:
    op.drop_index("ix_bot_bookings_status", table_name="bot_bookings")
    op.drop_index("ix_bot_bookings_user", table_name="bot_bookings")
    op.drop_index("ix_bot_bookings_time", table_name="bot_bookings")
    op.drop_table("bot_bookings")
