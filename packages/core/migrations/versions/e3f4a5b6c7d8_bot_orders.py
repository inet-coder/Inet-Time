"""bot_orders: bot do'koni buyurtmalari

Revision ID: e3f4a5b6c7d8
Revises: d2e3f4a5b6c7
Create Date: 2026-11-20 10:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "e3f4a5b6c7d8"
down_revision: Union[str, None] = "d2e3f4a5b6c7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "bot_orders",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("bot_id", sa.Integer(), nullable=False),
        sa.Column("number", sa.Integer(), nullable=False),
        sa.Column("tg_user_id", sa.BigInteger(), nullable=False),
        sa.Column("items", postgresql.JSONB(), nullable=False),
        sa.Column("total", sa.BigInteger(), nullable=False),
        sa.Column("delivery", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("data", postgresql.JSONB(), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False, server_default="new"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["bot_id"], ["user_bots.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("bot_id", "number", name="uq_bot_order_number"),
    )
    op.create_index("ix_bot_orders_user", "bot_orders", ["bot_id", "tg_user_id"])
    op.create_index("ix_bot_orders_status", "bot_orders", ["status"])


def downgrade() -> None:
    op.drop_index("ix_bot_orders_status", table_name="bot_orders")
    op.drop_index("ix_bot_orders_user", table_name="bot_orders")
    op.drop_table("bot_orders")
