"""bot engine v2: foydalanuvchi o'zgaruvchilari, referal, bloklash, global o'zgaruvchilar, forma javoblari

Revision ID: d2e3f4a5b6c7
Revises: c1d2e3f4a5b6
Create Date: 2026-11-18 18:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "d2e3f4a5b6c7"
down_revision: Union[str, None] = "c1d2e3f4a5b6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("user_bots", sa.Column("vars", postgresql.JSONB(), nullable=False, server_default="{}"))
    op.add_column("bot_subscribers", sa.Column("data", postgresql.JSONB(), nullable=False, server_default="{}"))
    op.add_column("bot_subscribers", sa.Column("referred_by", sa.BigInteger(), nullable=True))
    op.add_column("bot_subscribers", sa.Column("ref_count", sa.Integer(), nullable=False, server_default="0"))
    op.add_column("bot_subscribers", sa.Column("banned", sa.Boolean(), nullable=False, server_default=sa.false()))
    op.create_table(
        "bot_form_answers",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("bot_id", sa.Integer(), nullable=False),
        sa.Column("tg_user_id", sa.BigInteger(), nullable=False),
        sa.Column("form_id", sa.String(length=24), nullable=False),
        sa.Column("data", postgresql.JSONB(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["bot_id"], ["user_bots.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_bot_form_answers_bot_form", "bot_form_answers", ["bot_id", "form_id"])


def downgrade() -> None:
    op.drop_index("ix_bot_form_answers_bot_form", table_name="bot_form_answers")
    op.drop_table("bot_form_answers")
    op.drop_column("bot_subscribers", "banned")
    op.drop_column("bot_subscribers", "ref_count")
    op.drop_column("bot_subscribers", "referred_by")
    op.drop_column("bot_subscribers", "data")
    op.drop_column("user_bots", "vars")
