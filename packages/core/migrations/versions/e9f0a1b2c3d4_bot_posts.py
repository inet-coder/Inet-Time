"""bot_posts: kanalga rejalashtirilgan postlar

Revision ID: e9f0a1b2c3d4
Revises: d8e9f0a1b2c3
Create Date: 2026-11-26 10:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "e9f0a1b2c3d4"
down_revision: Union[str, None] = "d8e9f0a1b2c3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "bot_posts",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("bot_id", sa.Integer(), nullable=False),
        sa.Column("channel_id", sa.BigInteger(), nullable=False),
        sa.Column("channel_title", sa.String(length=64), nullable=False, server_default=""),
        sa.Column("from_chat_id", sa.BigInteger(), nullable=False),
        sa.Column("message_id", sa.Integer(), nullable=False),
        sa.Column("buttons", postgresql.JSONB(), nullable=False, server_default="[]"),
        sa.Column("publish_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("status", sa.String(length=10), nullable=False, server_default="scheduled"),
        sa.Column("error", sa.String(length=200), nullable=False, server_default=""),
        sa.Column("sent_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["bot_id"], ["user_bots.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_bot_posts_bot_id", "bot_posts", ["bot_id"])
    op.create_index("ix_bot_posts_due", "bot_posts", ["status", "publish_at"])


def downgrade() -> None:
    op.drop_index("ix_bot_posts_due", table_name="bot_posts")
    op.drop_index("ix_bot_posts_bot_id", table_name="bot_posts")
    op.drop_table("bot_posts")
