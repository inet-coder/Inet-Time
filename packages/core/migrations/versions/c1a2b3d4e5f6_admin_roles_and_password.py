"""admin roles and default password

Qolgan admin rollari (ADMIN, SUPPORT, FINANCE, OPERATOR) seed qilinadi
va PHASE 8'da bo'sh password_hash bilan yaratilgan "admin" test
foydalanuvchisiga haqiqiy parol beriladi (admin123 — faqat dev/test
uchun, productionda albatta almashtirilishi kerak).

Revision ID: c1a2b3d4e5f6
Revises: b49b9de64f06
Create Date: 2026-09-26 08:30:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "c1a2b3d4e5f6"
down_revision: Union[str, None] = "b49b9de64f06"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

admin_roles_table = sa.table(
    "admin_roles",
    sa.column("name", sa.String),
    sa.column("permissions", sa.JSON),
)

admin_users_table = sa.table(
    "admin_users",
    sa.column("username", sa.String),
    sa.column("password_hash", sa.String),
)

ROLES = [
    (
        "ADMIN",
        {
            "users": True,
            "accounts": True,
            "services": True,
            "subscriptions": True,
            "payments": True,
            "referrals": True,
            "jobs": True,
            "transactions": True,
            "workers": True,
        },
    ),
    ("SUPPORT", {"users": True, "accounts": True}),
    ("FINANCE", {"payments": True, "subscriptions": True, "transactions": True, "balance.adjust": True}),
    ("OPERATOR", {"services": True, "jobs": True, "workers": True}),
]

# PHASE 8'da yaratilgan test admin uchun bcrypt("admin123")
DEFAULT_ADMIN_PASSWORD_HASH = "$2b$12$SbIyWbEGlYhPzyv2cp6vKumnhb5Y2Ssp0Ci8ERj7fWE1geMGG0dk6"


def upgrade() -> None:
    op.bulk_insert(admin_roles_table, [{"name": name, "permissions": perms} for name, perms in ROLES])
    op.execute(
        admin_users_table.update()
        .where(admin_users_table.c.username == "admin")
        .values(password_hash=DEFAULT_ADMIN_PASSWORD_HASH)
    )


def downgrade() -> None:
    op.execute(admin_users_table.update().where(admin_users_table.c.username == "admin").values(password_hash=""))
    op.execute(admin_roles_table.delete().where(admin_roles_table.c.name.in_([n for n, _ in ROLES])))
