"""to'lovlar: provayder tokeni, buyurtma to'lov/chegirma ustunlari

Revision ID: d8e9f0a1b2c3
Revises: c7d8e9f0a1b2
Create Date: 2026-11-25 10:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "d8e9f0a1b2c3"
down_revision: Union[str, None] = "c7d8e9f0a1b2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("user_bots", sa.Column("pay_token_encrypted", sa.LargeBinary(), nullable=True))
    op.add_column("bot_orders", sa.Column("paid", sa.Boolean(), nullable=False, server_default="false"))
    op.add_column("bot_orders", sa.Column("payment", sa.String(length=8), nullable=False, server_default=""))
    op.add_column("bot_orders", sa.Column("discount", sa.BigInteger(), nullable=False, server_default="0"))
    op.add_column("bot_orders", sa.Column("promo", sa.String(length=16), nullable=False, server_default=""))


def downgrade() -> None:
    op.drop_column("bot_orders", "promo")
    op.drop_column("bot_orders", "discount")
    op.drop_column("bot_orders", "payment")
    op.drop_column("bot_orders", "paid")
    op.drop_column("user_bots", "pay_token_encrypted")
