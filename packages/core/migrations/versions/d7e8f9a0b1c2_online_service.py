"""online service

Revision ID: d7e8f9a0b1c2
Revises: 5906a99b96c9
Create Date: 2026-09-26 11:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "d7e8f9a0b1c2"
down_revision: Union[str, None] = "5906a99b96c9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

services_table = sa.table(
    "services",
    sa.column("code", sa.String),
    sa.column("name", sa.String),
    sa.column("description", sa.Text),
    sa.column("is_active", sa.Boolean),
)


def upgrade() -> None:
    op.bulk_insert(
        services_table,
        [{"code": "online", "name": "24/7 Online", "description": "Akkaunt doim online ko'rinadi", "is_active": True}],
    )


def downgrade() -> None:
    op.execute(services_table.delete().where(services_table.c.code == "online"))
