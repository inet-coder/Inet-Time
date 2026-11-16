"""web_app_versions: e'lon qilingan versiyalar tarixi

Revision ID: a9b0c1d2e3f4
Revises: f8a9b0c1d2e3
Create Date: 2026-11-17 10:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "a9b0c1d2e3f4"
down_revision: Union[str, None] = "f8a9b0c1d2e3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "web_app_versions",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("app_id", sa.Integer(), nullable=False),
        sa.Column("doc", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["app_id"], ["web_apps.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_web_app_versions_app_id"), "web_app_versions", ["app_id"], unique=False)
    # Mavjud e'lon qilingan ilovalar — birinchi versiya sifatida
    op.execute(
        "INSERT INTO web_app_versions (app_id, doc, created_at) "
        "SELECT id, published, COALESCE(published_at, now()) FROM web_apps WHERE published IS NOT NULL"
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_web_app_versions_app_id"), table_name="web_app_versions")
    op.drop_table("web_app_versions")
