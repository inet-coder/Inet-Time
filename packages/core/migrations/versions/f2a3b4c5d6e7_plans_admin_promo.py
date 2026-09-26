"""plans admin: free plan row, plan discounts, promo codes

Revision ID: f2a3b4c5d6e7
Revises: e1f2a3b4c5d6
Create Date: 2026-09-26 15:00:00.000000

"""
import json
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "f2a3b4c5d6e7"
down_revision: Union[str, None] = "e1f2a3b4c5d6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# Bepul tarif endi bazada — admin paneldan sozlanadi. Standart holatda ham foydali bo'lsin:
# asosiy 3 xizmat bir vaqtda + Jadval.
FREE_FLAGS = {
    "account_limit": 1,
    "scheduler_limit": 3,
    "online_service": False,
    "playlist_service": False,
    "schedule_service": True,
    "emoji_service": False,
    "photo_service": False,
}
# Starter Bepul'dan aniq ustun bo'lishi kerak.
STARTER_FLAGS = {
    "account_limit": 2,
    "scheduler_limit": 6,
    "online_service": True,
    "playlist_service": True,
    "schedule_service": True,
}


def upgrade() -> None:
    op.add_column("plans", sa.Column("description", sa.Text(), nullable=True))
    op.add_column("plans", sa.Column("badge", sa.String(length=64), nullable=True))
    op.add_column("plans", sa.Column("sort_order", sa.Integer(), server_default="0", nullable=False))
    op.add_column("plans", sa.Column("discount_percent", sa.Integer(), server_default="0", nullable=False))
    op.add_column("plans", sa.Column("discount_until", sa.DateTime(timezone=True), nullable=True))

    op.create_table(
        "promo_codes",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("code", sa.String(length=32), nullable=False),
        sa.Column("discount_percent", sa.Integer(), nullable=True),
        sa.Column("discount_amount", sa.Numeric(14, 2), nullable=True),
        sa.Column("plan_codes", sa.JSON(), nullable=False),
        sa.Column("max_uses", sa.Integer(), nullable=True),
        sa.Column("used_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("valid_until", sa.DateTime(timezone=True), nullable=True),
        sa.Column("is_active", sa.Boolean(), server_default=sa.true(), nullable=False),
        sa.Column("note", sa.String(length=255), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_promo_codes_code"), "promo_codes", ["code"], unique=True)

    op.create_table(
        "promo_redemptions",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("promo_id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("subscription_id", sa.Integer(), nullable=True),
        sa.Column("plan_code", sa.String(length=32), nullable=False),
        sa.Column("discount", sa.Numeric(14, 2), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["promo_id"], ["promo_codes.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["subscription_id"], ["subscriptions.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("promo_id", "user_id", name="uq_promo_redemption_user"),
    )
    op.create_index(op.f("ix_promo_redemptions_promo_id"), "promo_redemptions", ["promo_id"], unique=False)
    op.create_index(op.f("ix_promo_redemptions_user_id"), "promo_redemptions", ["user_id"], unique=False)

    conn = op.get_bind()
    conn.execute(
        sa.text(
            "INSERT INTO plans (code, name, price, duration_days, flags, is_active, sort_order, description) "
            "VALUES ('free', 'Bepul', 0, 0, CAST(:flags AS json), true, 0, :desc) ON CONFLICT (code) DO NOTHING"
        ),
        {"flags": json.dumps(FREE_FLAGS), "desc": "Boshlash uchun: soat, avto bio/ism va jadval"},
    )
    conn.execute(
        sa.text("UPDATE plans SET flags = (flags::jsonb || CAST(:flags AS jsonb))::json, sort_order = 1 WHERE code = 'starter'"),
        {"flags": json.dumps(STARTER_FLAGS)},
    )
    conn.execute(sa.text("UPDATE plans SET sort_order = 2, badge = 'Eng ko''p imkoniyat' WHERE code = 'pro'"))


def downgrade() -> None:
    op.execute("DELETE FROM plans WHERE code = 'free'")
    op.drop_index(op.f("ix_promo_redemptions_user_id"), table_name="promo_redemptions")
    op.drop_index(op.f("ix_promo_redemptions_promo_id"), table_name="promo_redemptions")
    op.drop_table("promo_redemptions")
    op.drop_index(op.f("ix_promo_codes_code"), table_name="promo_codes")
    op.drop_table("promo_codes")
    for column in ("discount_until", "discount_percent", "sort_order", "badge", "description"):
        op.drop_column("plans", column)
