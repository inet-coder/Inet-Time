"""AI auto-reply settings, AI usage log, ai/stories plan flags

Revision ID: a3b4c5d6e7f8
Revises: f2a3b4c5d6e7
Create Date: 2026-09-26 20:00:00.000000

"""
import json
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "a3b4c5d6e7f8"
down_revision: Union[str, None] = "f2a3b4c5d6e7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# Admin paneldan o'zgartiriladi. AI — Pro; Stories — Starter va Pro.
PLAN_FLAGS = {
    "free": {"ai_service": False, "ai_daily_limit": 0, "stories_service": False},
    "starter": {"ai_service": False, "ai_daily_limit": 0, "stories_service": True},
    "pro": {"ai_service": True, "ai_daily_limit": 200, "stories_service": True},
}
NEW_FLAGS = ("ai_service", "ai_daily_limit", "stories_service")


def upgrade() -> None:
    op.create_table(
        "account_ai_settings",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("telegram_account_id", sa.Integer(), nullable=False),
        sa.Column("enabled", sa.Boolean(), server_default=sa.false(), nullable=False),
        sa.Column("preset", sa.String(length=32), server_default="busy", nullable=False),
        sa.Column("style", sa.Text(), nullable=True),
        sa.Column("only_when_away", sa.Boolean(), server_default=sa.true(), nullable=False),
        sa.Column("signature", sa.Boolean(), server_default=sa.true(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["telegram_account_id"], ["telegram_accounts.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_account_ai_settings_telegram_account_id"), "account_ai_settings", ["telegram_account_id"], unique=True)

    op.create_table(
        "ai_usage",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("kind", sa.String(length=16), nullable=False),
        sa.Column("model", sa.String(length=64), nullable=False),
        sa.Column("input_tokens", sa.Integer(), server_default="0", nullable=False),
        sa.Column("output_tokens", sa.Integer(), server_default="0", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_ai_usage_user_id"), "ai_usage", ["user_id"], unique=False)
    op.create_index("ix_ai_usage_created_at", "ai_usage", ["created_at"], unique=False)

    conn = op.get_bind()
    for code, flags in PLAN_FLAGS.items():
        # Mavjud qiymatlar (admin allaqachon o'zgartirgan bo'lsa) ustidan yozilmaydi: yangi flag'lar faqat qo'shiladi.
        conn.execute(
            sa.text("UPDATE plans SET flags = (CAST(:flags AS jsonb) || flags::jsonb)::json WHERE code = :code"),
            {"flags": json.dumps(flags), "code": code},
        )


def downgrade() -> None:
    for flag in NEW_FLAGS:
        op.execute(f"UPDATE plans SET flags = (flags::jsonb - '{flag}')::json")
    op.drop_index("ix_ai_usage_created_at", table_name="ai_usage")
    op.drop_index(op.f("ix_ai_usage_user_id"), table_name="ai_usage")
    op.drop_table("ai_usage")
    op.drop_index(op.f("ix_account_ai_settings_telegram_account_id"), table_name="account_ai_settings")
    op.drop_table("account_ai_settings")
