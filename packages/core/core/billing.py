"""Tarif narxi (aksiya chegirmasi + promokod), Bepul tarif va to'lov rekvizitlari — API va bot uchun umumiy."""

import datetime
import decimal
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.db.models import Plan, PromoCode, PromoRedemption, SystemSetting
from core.settings import settings

FREE_CODE = "free"
PAYMENT_SETTING_KEY = "payment"

# Admin paneldagi tarif muharriri uchun: qaysi flag nimani ochadi.
PLAN_LIMITS = [
    {"key": "account_limit", "title": "Akkauntlar soni", "min": 1, "max": 50},
    {"key": "scheduler_limit", "title": "Bir vaqtda xizmatlar", "min": 1, "max": 100},
]
PLAN_FEATURES = [
    {"key": "schedule_service", "title": "Jadval", "service": "schedule"},
    {"key": "playlist_service", "title": "Bio playlist", "service": "playlist"},
    {"key": "online_service", "title": "24/7 Online", "service": "online"},
    {"key": "emoji_service", "title": "Emoji status", "service": "emoji"},
    {"key": "photo_service", "title": "Rasm almashtirish", "service": "photo"},
]

_CENT = decimal.Decimal("1")


def _now() -> datetime.datetime:
    return datetime.datetime.now(datetime.timezone.utc)


def plan_discount_active(plan: Plan, now: datetime.datetime | None = None) -> bool:
    if not plan.discount_percent:
        return False
    return plan.discount_until is None or plan.discount_until > (now or _now())


def plan_price(plan: Plan, now: datetime.datetime | None = None) -> decimal.Decimal:
    """Aksiya hisobga olingan narx (butun so'mga yaxlitlanadi)."""
    price = decimal.Decimal(plan.price)
    if plan_discount_active(plan, now):
        price = price * (100 - plan.discount_percent) / 100
    return price.quantize(_CENT, rounding=decimal.ROUND_HALF_UP)


def plan_public(plan: Plan, now: datetime.datetime | None = None) -> dict:
    active = plan_discount_active(plan, now)
    return {
        "code": plan.code,
        "name": plan.name,
        "price": float(plan.price),
        "final_price": float(plan_price(plan, now)),
        "discount_percent": plan.discount_percent if active else 0,
        "discount_until": plan.discount_until.isoformat() if active and plan.discount_until else None,
        "duration_days": plan.duration_days,
        "flags": plan.flags,
        "badge": plan.badge,
        "description": plan.description,
    }


async def get_free_plan(db: AsyncSession) -> Plan | None:
    return await db.scalar(select(Plan).where(Plan.code == FREE_CODE))


async def paid_plans(db: AsyncSession) -> list[Plan]:
    return list(
        await db.scalars(
            select(Plan)
            .where(Plan.is_active == True, Plan.code != FREE_CODE)  # noqa: E712
            .order_by(Plan.sort_order, Plan.price)
        )
    )


def normalize_code(code: str) -> str:
    return code.strip().upper()


@dataclass
class Quote:
    plan_code: str
    base_price: decimal.Decimal
    price: decimal.Decimal  # aksiyadan keyin
    promo: PromoCode | None
    promo_discount: decimal.Decimal
    final: decimal.Decimal

    def public(self) -> dict:
        return {
            "plan_code": self.plan_code,
            "base_price": float(self.base_price),
            "price": float(self.price),
            "promo_code": self.promo.code if self.promo else None,
            "promo_discount": float(self.promo_discount),
            "final_price": float(self.final),
        }


class PromoError(Exception):
    pass


async def find_promo(db: AsyncSession, code: str, user_id: int, plan: Plan, now: datetime.datetime | None = None) -> PromoCode:
    """Promokodni tekshiradi; yaroqsiz bo'lsa foydalanuvchiga tushunarli PromoError."""
    now = now or _now()
    promo = await db.scalar(select(PromoCode).where(PromoCode.code == normalize_code(code)))
    if promo is None or not promo.is_active:
        raise PromoError("Bunday promokod yo'q")
    if promo.valid_until is not None and promo.valid_until <= now:
        raise PromoError("Promokod muddati tugagan")
    if promo.max_uses is not None and promo.used_count >= promo.max_uses:
        raise PromoError("Promokod limiti tugagan")
    if promo.plan_codes and plan.code not in promo.plan_codes:
        raise PromoError(f"Bu promokod {plan.name} tarifiga amal qilmaydi")
    used = await db.scalar(
        select(PromoRedemption.id).where(PromoRedemption.promo_id == promo.id, PromoRedemption.user_id == user_id)
    )
    if used is not None:
        raise PromoError("Siz bu promokodni ishlatib bo'lgansiz")
    return promo


async def quote(db: AsyncSession, user_id: int, plan: Plan, promo_code: str | None, now: datetime.datetime | None = None) -> Quote:
    now = now or _now()
    price = plan_price(plan, now)
    promo = None
    discount = decimal.Decimal(0)
    if promo_code and promo_code.strip():
        promo = await find_promo(db, promo_code, user_id, plan, now)
        if promo.discount_percent:
            discount = price * promo.discount_percent / 100
        elif promo.discount_amount:
            discount = decimal.Decimal(promo.discount_amount)
        discount = min(price, discount).quantize(_CENT, rounding=decimal.ROUND_HALF_UP)
    return Quote(
        plan_code=plan.code,
        base_price=decimal.Decimal(plan.price),
        price=price,
        promo=promo,
        promo_discount=discount,
        final=price - discount,
    )


async def payment_instructions(db: AsyncSession) -> str:
    """Admin paneldan saqlangan to'lov rekvizitlari; bo'lmasa .env'dagi PAYMENT_INSTRUCTIONS."""
    row = await db.scalar(select(SystemSetting).where(SystemSetting.key == PAYMENT_SETTING_KEY))
    if row is not None and row.value.get("instructions"):
        return row.value["instructions"]
    return settings.payment_instructions
