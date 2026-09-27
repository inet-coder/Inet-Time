"""referral status + rewards, broadcasts

Revision ID: c5d6e7f8a9b0
Revises: b4c5d6e7f8a9
Create Date: 2026-09-27 10:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "c5d6e7f8a9b0"
down_revision: Union[str, None] = "b4c5d6e7f8a9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("referrals", sa.Column("status", sa.String(length=16), server_default="pending", nullable=False))
    op.add_column("referrals", sa.Column("qualified_at", sa.DateTime(timezone=True), nullable=True))
    op.create_index(op.f("ix_referrals_status"), "referrals", ["status"], unique=False)
    # Mavjud referallar: taklif qilingan odam akkaunt ulagan bo'lsa — hisoblangan.
    op.execute(
        "UPDATE referrals SET status = 'qualified', qualified_at = now() "
        "WHERE referred_user_id IN (SELECT DISTINCT user_id FROM telegram_accounts)"
    )

    op.create_table(
        "referral_rewards",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("milestone", sa.Integer(), nullable=False),
        sa.Column("plan_code", sa.String(length=32), nullable=False),
        sa.Column("days", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "milestone", name="uq_referral_reward_milestone"),
    )
    op.create_index(op.f("ix_referral_rewards_user_id"), "referral_rewards", ["user_id"], unique=False)

    op.create_table(
        "broadcasts",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("created_by", sa.BigInteger(), nullable=True),
        sa.Column("status", sa.String(length=16), server_default="draft", nullable=False),
        sa.Column("segment", sa.JSON(), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("media_id", sa.Integer(), nullable=True),
        sa.Column("buttons", sa.JSON(), nullable=False),
        sa.Column("total", sa.Integer(), server_default="0", nullable=False),
        sa.Column("sent", sa.Integer(), server_default="0", nullable=False),
        sa.Column("failed", sa.Integer(), server_default="0", nullable=False),
        sa.Column("blocked", sa.Integer(), server_default="0", nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["media_id"], ["media_files.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_broadcasts_status"), "broadcasts", ["status"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_broadcasts_status"), table_name="broadcasts")
    op.drop_table("broadcasts")
    op.drop_index(op.f("ix_referral_rewards_user_id"), table_name="referral_rewards")
    op.drop_table("referral_rewards")
    op.drop_index(op.f("ix_referrals_status"), table_name="referrals")
    op.drop_column("referrals", "qualified_at")
    op.drop_column("referrals", "status")
