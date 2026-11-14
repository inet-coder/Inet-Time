"""user bots (menu builder): user_bots, bot_subscribers, bot_broadcasts; bot plan limits

Revision ID: d6e7f8a9b0c1
Revises: c5d6e7f8a9b0
Create Date: 2026-11-14 12:00:00.000000

"""
import json
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "d6e7f8a9b0c1"
down_revision: Union[str, None] = "c5d6e7f8a9b0"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# Mavjud tariflarga boshlang'ich limitlar (admin paneldan o'zgartiriladi). Kalit allaqachon bo'lsa tegilmaydi.
PLAN_DEFAULTS = {
    "free": {"bot_limit": 1, "bot_pages_limit": 10},
    "starter": {"bot_limit": 2, "bot_pages_limit": 40},
    "pro": {"bot_limit": 5, "bot_pages_limit": 150},
}


def upgrade() -> None:
    op.create_table(
        "user_bots",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("bot_telegram_id", sa.BigInteger(), nullable=False),
        sa.Column("username", sa.String(length=64), nullable=False),
        sa.Column("name", sa.String(length=128), nullable=False),
        sa.Column("token_encrypted", sa.LargeBinary(), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False, server_default="active"),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("menu", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("bot_telegram_id"),
    )
    op.create_index(op.f("ix_user_bots_user_id"), "user_bots", ["user_id"], unique=False)
    op.create_index(op.f("ix_user_bots_status"), "user_bots", ["status"], unique=False)

    op.create_table(
        "bot_subscribers",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("bot_id", sa.Integer(), nullable=False),
        sa.Column("tg_user_id", sa.BigInteger(), nullable=False),
        sa.Column("first_name", sa.String(length=128), nullable=True),
        sa.Column("username", sa.String(length=64), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("last_active_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("blocked", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.ForeignKeyConstraint(["bot_id"], ["user_bots.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("bot_id", "tg_user_id", name="uq_bot_subscriber"),
    )
    op.create_index(op.f("ix_bot_subscribers_bot_id"), "bot_subscribers", ["bot_id"], unique=False)

    op.create_table(
        "bot_broadcasts",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("bot_id", sa.Integer(), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("media_id", sa.Integer(), nullable=True),
        sa.Column("status", sa.String(length=16), nullable=False, server_default="sending"),
        sa.Column("total", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("sent", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("failed", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["bot_id"], ["user_bots.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["media_id"], ["media_files.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_bot_broadcasts_bot_id"), "bot_broadcasts", ["bot_id"], unique=False)

    conn = op.get_bind()
    for code, flags in PLAN_DEFAULTS.items():
        # Mavjud qiymatlar ustun: (defaults || flags) — admin qo'ygan limit o'zgarmaydi.
        conn.execute(
            sa.text("UPDATE plans SET flags = (CAST(:flags AS jsonb) || flags::jsonb)::json WHERE code = :code"),
            {"flags": json.dumps(flags), "code": code},
        )


def downgrade() -> None:
    op.drop_index(op.f("ix_bot_broadcasts_bot_id"), table_name="bot_broadcasts")
    op.drop_table("bot_broadcasts")
    op.drop_index(op.f("ix_bot_subscribers_bot_id"), table_name="bot_subscribers")
    op.drop_table("bot_subscribers")
    op.drop_index(op.f("ix_user_bots_status"), table_name="user_bots")
    op.drop_index(op.f("ix_user_bots_user_id"), table_name="user_bots")
    op.drop_table("user_bots")
