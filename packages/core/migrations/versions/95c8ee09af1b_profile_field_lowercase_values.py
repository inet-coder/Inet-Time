"""profile field lowercase values

ProfileField enum a'zolari (NAME, BIO, ...) va qiymatlari (name, bio, ...)
mos kelmagani uchun SQLAlchemy ustunga enum NOMINI (katta harf) yozib
kelgan edi. Ustun turi o'zgarmaydi (VARCHAR) — faqat mavjud satrlarni
kanonik (kichik harf) qiymatga o'tkazamiz.

Revision ID: 95c8ee09af1b
Revises: bb933d0f1c2b
Create Date: 2026-09-26 07:50:00.000000

"""
from typing import Sequence, Union

from alembic import op

revision: str = "95c8ee09af1b"
down_revision: Union[str, None] = "bb933d0f1c2b"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    for table in ("automation_actions", "profile_snapshots"):
        op.execute(f"UPDATE {table} SET field = lower(field) WHERE field = upper(field)")


def downgrade() -> None:
    for table in ("automation_actions", "profile_snapshots"):
        op.execute(f"UPDATE {table} SET field = upper(field) WHERE field = lower(field)")
