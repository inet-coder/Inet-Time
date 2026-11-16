"""bot_broadcasts: istalgan turdagi xabarni nusxalab tarqatish (egasi o'z botida yuborgan xabar)

Revision ID: e7f8a9b0c1d2
Revises: d6e7f8a9b0c1
Create Date: 2026-11-16 10:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "e7f8a9b0c1d2"
down_revision: Union[str, None] = "d6e7f8a9b0c1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("bot_broadcasts", sa.Column("from_chat_id", sa.BigInteger(), nullable=True))
    op.add_column("bot_broadcasts", sa.Column("message_id", sa.Integer(), nullable=True))


def downgrade() -> None:
    op.drop_column("bot_broadcasts", "message_id")
    op.drop_column("bot_broadcasts", "from_chat_id")
