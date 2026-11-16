"""app data: app_collections, app_records (Web App ma'lumotlar bazasi)

Revision ID: b0c1d2e3f4a5
Revises: a9b0c1d2e3f4
Create Date: 2026-11-17 14:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "b0c1d2e3f4a5"
down_revision: Union[str, None] = "a9b0c1d2e3f4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "app_collections",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("app_id", sa.Integer(), nullable=False),
        sa.Column("key", sa.String(length=32), nullable=False),
        sa.Column("name", sa.String(length=64), nullable=False),
        sa.Column("fields", sa.JSON(), nullable=False),
        sa.Column("read", sa.String(length=8), nullable=False, server_default="public"),
        sa.Column("create", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["app_id"], ["web_apps.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("app_id", "key", name="uq_app_collection_key"),
    )
    op.create_index(op.f("ix_app_collections_app_id"), "app_collections", ["app_id"], unique=False)
    op.create_table(
        "app_records",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("collection_id", sa.Integer(), nullable=False),
        sa.Column("data", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_by_tg", sa.BigInteger(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["collection_id"], ["app_collections.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_app_records_collection_id"), "app_records", ["collection_id"], unique=False)
    op.create_index(op.f("ix_app_records_created_by_tg"), "app_records", ["created_by_tg"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_app_records_created_by_tg"), table_name="app_records")
    op.drop_index(op.f("ix_app_records_collection_id"), table_name="app_records")
    op.drop_table("app_records")
    op.drop_index(op.f("ix_app_collections_app_id"), table_name="app_collections")
    op.drop_table("app_collections")
