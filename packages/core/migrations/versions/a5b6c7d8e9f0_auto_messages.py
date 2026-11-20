"""avtomatik xabarlar: bot_auto_log va tarqatish segmenti

Revision ID: a5b6c7d8e9f0
Revises: f4a5b6c7d8e9
Create Date: 2026-11-22 10:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "a5b6c7d8e9f0"
down_revision: Union[str, None] = "f4a5b6c7d8e9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "bot_auto_log",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("bot_id", sa.Integer(), nullable=False),
        sa.Column("rule_id", sa.String(length=32), nullable=False),
        sa.Column("tg_user_id", sa.BigInteger(), nullable=False),
        sa.Column("period", sa.String(length=32), nullable=False),
        sa.Column("sent_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["bot_id"], ["user_bots.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("bot_id", "rule_id", "tg_user_id", "period", name="uq_bot_auto_log"),
    )
    op.create_index("ix_bot_auto_log_bot_id", "bot_auto_log", ["bot_id"])
    op.add_column("bot_broadcasts", sa.Column("segment", sa.String(length=16), nullable=False, server_default="all"))


def downgrade() -> None:
    op.drop_column("bot_broadcasts", "segment")
    op.drop_index("ix_bot_auto_log_bot_id", table_name="bot_auto_log")
    op.drop_table("bot_auto_log")
