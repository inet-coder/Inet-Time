"""bot_tickets: murojaatlar (tiketlar)

Revision ID: c7d8e9f0a1b2
Revises: b6c7d8e9f0a1
Create Date: 2026-11-24 10:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "c7d8e9f0a1b2"
down_revision: Union[str, None] = "b6c7d8e9f0a1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "bot_tickets",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("bot_id", sa.Integer(), nullable=False),
        sa.Column("number", sa.Integer(), nullable=False),
        sa.Column("tg_user_id", sa.BigInteger(), nullable=False),
        sa.Column("status", sa.String(length=8), nullable=False, server_default="open"),
        sa.Column("assignee", sa.BigInteger(), nullable=True),
        sa.Column("preview", sa.String(length=200), nullable=False, server_default=""),
        sa.Column("messages", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("rating", sa.Integer(), nullable=True),
        sa.Column("first_reply_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("closed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["bot_id"], ["user_bots.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_bot_tickets_status", "bot_tickets", ["bot_id", "status"])
    op.create_index("ix_bot_tickets_user", "bot_tickets", ["bot_id", "tg_user_id"])


def downgrade() -> None:
    op.drop_index("ix_bot_tickets_user", table_name="bot_tickets")
    op.drop_index("ix_bot_tickets_status", table_name="bot_tickets")
    op.drop_table("bot_tickets")
