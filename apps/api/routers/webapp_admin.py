"""Mini App ichidagi admin panel: tariflar, aksiyalar, promokodlar, to'lovlar, foydalanuvchilar.

Kirish — oddiy Mini App tokeni + Telegram ID ADMIN_TELEGRAM_IDS ro'yxatida bo'lishi. Pul bilan ishlaydigan
amallar mavjud admin API funksiyalari orqali bajariladi (serializable tranzaksiya, audit)."""

import datetime
import decimal
import re

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from core.audit import record_audit
from core.billing import FREE_CODE, PAYMENT_SETTING_KEY, PLAN_FEATURES, PLAN_LIMITS, normalize_code, payment_instructions
from core.db.enums import ActorType, AutomationStatus, PaymentStatus, SubscriptionStatus, TransactionType
from core.db.models import (
    AdminUser,
    Automation,
    Payment,
    Plan,
    PromoCode,
    SystemSetting,
    Subscription,
    TelegramAccount,
    Transaction,
    User,
)
from core.entitlements import get_entitlement
from core.notify import send_telegram
from core.settings import settings
from deps import get_db
from routers import admin as admin_api
from routers import payments as payments_api
from routers.webapp import current_user
from schemas import BalanceAdjust, RejectPaymentAdmin

router = APIRouter(prefix="/webapp/admin", tags=["webapp-admin"])


def _money(amount: float | decimal.Decimal) -> str:
    return f"{int(amount):,}".replace(",", " ") + " so'm"


async def current_admin(user: User = Depends(current_user)) -> User:
    if user.telegram_user_id not in settings.admin_telegram_id_set:
        raise HTTPException(403, "Faqat admin uchun")
    return user


async def _service_admin(db: AsyncSession) -> AdminUser:
    """To'lov tasdig'i kabi amallar admin_users qatoriga bog'lanadi — bot ham shu "admin" hisobidan ishlaydi."""
    admin = await db.scalar(select(AdminUser).where(AdminUser.username == "admin", AdminUser.is_active == True))  # noqa: E712
    if admin is None:
        admin = await db.scalar(select(AdminUser).where(AdminUser.is_active == True).order_by(AdminUser.id))  # noqa: E712
    if admin is None:
        raise HTTPException(500, "admin_users jadvalida faol admin yo'q")
    return admin


def _who(user: User) -> str:
    return f"@{user.username}" if user.username else (user.first_name or str(user.telegram_user_id))


# --- Umumiy ko'rsatkichlar ---


@router.get("/stats")
async def stats(admin: User = Depends(current_admin), db: AsyncSession = Depends(get_db)) -> dict:
    now = datetime.datetime.now(datetime.timezone.utc)
    month_ago = now - datetime.timedelta(days=30)
    week_ago = now - datetime.timedelta(days=7)
    paid = (
        select(func.count(func.distinct(Subscription.user_id)))
        .join(Plan, Plan.id == Subscription.plan_id)
        .where(Subscription.status == SubscriptionStatus.ACTIVE, Subscription.expires_at > now, Plan.code != FREE_CODE)
    )
    return {
        "users": await db.scalar(select(func.count(User.id))),
        "users_week": await db.scalar(select(func.count(User.id)).where(User.created_at > week_ago)),
        "paid_users": await db.scalar(paid),
        "accounts": await db.scalar(select(func.count(TelegramAccount.id))),
        "active_services": await db.scalar(
            select(func.count(Automation.id)).where(Automation.status == AutomationStatus.ACTIVE)
        ),
        "pending_payments": await db.scalar(select(func.count(Payment.id)).where(Payment.status == PaymentStatus.PENDING)),
        # Daromad = tasdiqlangan to'ldirishlar (real pul kirimi), 30 kun.
        "revenue_month": float(
            await db.scalar(
                select(func.coalesce(func.sum(Transaction.amount), 0)).where(
                    Transaction.type == TransactionType.TOPUP, Transaction.created_at > month_ago
                )
            )
        ),
        "sales_month": await db.scalar(
            select(func.count(Transaction.id)).where(
                Transaction.type == TransactionType.PURCHASE, Transaction.created_at > month_ago
            )
        ),
    }


# --- Tariflar ---


def _plan_admin(plan: Plan) -> dict:
    return {
        "id": plan.id,
        "code": plan.code,
        "name": plan.name,
        "price": float(plan.price),
        "duration_days": plan.duration_days,
        "flags": plan.flags,
        "is_active": plan.is_active,
        "description": plan.description,
        "badge": plan.badge,
        "sort_order": plan.sort_order,
        "discount_percent": plan.discount_percent,
        "discount_until": plan.discount_until.isoformat() if plan.discount_until else None,
    }


class PlanIn(BaseModel):
    name: str = Field(min_length=1, max_length=64)
    price: float = Field(ge=0)
    duration_days: int = Field(ge=0, le=3650)
    flags: dict
    is_active: bool = True
    description: str | None = Field(None, max_length=500)
    badge: str | None = Field(None, max_length=64)
    sort_order: int = 0
    discount_percent: int = Field(0, ge=0, le=95)
    discount_until: datetime.datetime | None = None


class PlanCreate(PlanIn):
    code: str


def _clean_flags(raw: dict, existing: dict) -> dict:
    """Faqat ma'lum kalitlar; boshqa (eski) flag'lar saqlanib qoladi."""
    flags = dict(existing)
    for limit in PLAN_LIMITS:
        if limit["key"] in raw:
            value = int(raw[limit["key"]])
            if not limit["min"] <= value <= limit["max"]:
                raise HTTPException(400, f"{limit['title']}: {limit['min']}–{limit['max']} oralig'ida bo'lsin")
            flags[limit["key"]] = value
    for feature in PLAN_FEATURES:
        if feature["key"] in raw:
            flags[feature["key"]] = bool(raw[feature["key"]])
    return flags


def _apply_plan(plan: Plan, payload: PlanIn) -> None:
    plan.name = payload.name.strip()
    plan.flags = _clean_flags(payload.flags, plan.flags or {})
    plan.description = (payload.description or "").strip() or None
    plan.badge = (payload.badge or "").strip() or None
    plan.sort_order = payload.sort_order
    if plan.code == FREE_CODE:
        # Bepul tarif doim faol va tekin; chegirma ma'nosiz.
        plan.price, plan.duration_days, plan.is_active = decimal.Decimal(0), 0, True
        plan.discount_percent, plan.discount_until = 0, None
        return
    if payload.price <= 0 or payload.duration_days < 1:
        raise HTTPException(400, "Pullik tarif narxi va muddati musbat bo'lsin")
    plan.price = decimal.Decimal(str(payload.price))
    plan.duration_days = payload.duration_days
    plan.is_active = payload.is_active
    plan.discount_percent = payload.discount_percent
    plan.discount_until = payload.discount_until if payload.discount_percent else None


@router.get("/plans")
async def list_plans(admin: User = Depends(current_admin), db: AsyncSession = Depends(get_db)) -> dict:
    plans = list(await db.scalars(select(Plan).order_by(Plan.sort_order, Plan.price)))
    counts = dict(
        (
            await db.execute(
                select(Subscription.plan_id, func.count(Subscription.id))
                .where(Subscription.status == SubscriptionStatus.ACTIVE, Subscription.expires_at > func.now())
                .group_by(Subscription.plan_id)
            )
        ).all()
    )
    return {
        "plans": [{**_plan_admin(p), "subscribers": counts.get(p.id, 0)} for p in plans],
        "limits": PLAN_LIMITS,
        "features": PLAN_FEATURES,
    }


@router.post("/plans")
async def create_plan(payload: PlanCreate, admin: User = Depends(current_admin), db: AsyncSession = Depends(get_db)) -> dict:
    code = payload.code.strip().lower()
    if not re.fullmatch(r"[a-z0-9_]{2,32}", code) or code == FREE_CODE:
        raise HTTPException(400, "Kod: 2–32 ta lotin harf, raqam yoki _")
    if await db.scalar(select(Plan.id).where(Plan.code == code)):
        raise HTTPException(400, "Bu kodli tarif bor")
    plan = Plan(code=code, flags={}, price=0, duration_days=30)
    _apply_plan(plan, payload)
    db.add(plan)
    await db.flush()
    await record_audit(
        db, actor_type=ActorType.ADMIN, actor_id=None, action="plan_created", entity_type="plan", entity_id=plan.id,
        meta={"by_telegram_id": admin.telegram_user_id, "code": code},
    )
    await db.commit()
    return _plan_admin(plan)


@router.put("/plans/{plan_id}")
async def update_plan(plan_id: int, payload: PlanIn, admin: User = Depends(current_admin), db: AsyncSession = Depends(get_db)) -> dict:
    plan = await db.get(Plan, plan_id)
    if plan is None:
        raise HTTPException(404, "Tarif topilmadi")
    before = _plan_admin(plan)
    _apply_plan(plan, payload)
    await record_audit(
        db, actor_type=ActorType.ADMIN, actor_id=None, action="plan_updated", entity_type="plan", entity_id=plan.id,
        meta={"by_telegram_id": admin.telegram_user_id, "before": before},
    )
    await db.commit()
    return _plan_admin(plan)


# --- Promokodlar ---


def _promo_admin(promo: PromoCode) -> dict:
    return {
        "id": promo.id,
        "code": promo.code,
        "discount_percent": promo.discount_percent,
        "discount_amount": float(promo.discount_amount) if promo.discount_amount is not None else None,
        "plan_codes": promo.plan_codes or [],
        "max_uses": promo.max_uses,
        "used_count": promo.used_count,
        "valid_until": promo.valid_until.isoformat() if promo.valid_until else None,
        "is_active": promo.is_active,
        "note": promo.note,
        "created_at": promo.created_at.isoformat() if promo.created_at else None,
    }


class PromoIn(BaseModel):
    code: str
    discount_percent: int | None = Field(None, ge=1, le=100)
    discount_amount: float | None = Field(None, gt=0)
    plan_codes: list[str] = []
    max_uses: int | None = Field(None, ge=1)
    valid_until: datetime.datetime | None = None
    is_active: bool = True
    note: str | None = Field(None, max_length=255)


async def _apply_promo(db: AsyncSession, promo: PromoCode, payload: PromoIn) -> None:
    if (payload.discount_percent is None) == (payload.discount_amount is None):
        raise HTTPException(400, "Chegirma foizda yoki summada — bittasini kiriting")
    known = set(await db.scalars(select(Plan.code).where(Plan.code != FREE_CODE)))
    unknown = [c for c in payload.plan_codes if c not in known]
    if unknown:
        raise HTTPException(400, f"Noma'lum tarif: {', '.join(unknown)}")
    promo.discount_percent = payload.discount_percent
    promo.discount_amount = decimal.Decimal(str(payload.discount_amount)) if payload.discount_amount else None
    promo.plan_codes = payload.plan_codes
    promo.max_uses = payload.max_uses
    promo.valid_until = payload.valid_until
    promo.is_active = payload.is_active
    promo.note = (payload.note or "").strip() or None


@router.get("/promos")
async def list_promos(admin: User = Depends(current_admin), db: AsyncSession = Depends(get_db)) -> list[dict]:
    return [_promo_admin(p) for p in await db.scalars(select(PromoCode).order_by(PromoCode.id.desc()))]


@router.post("/promos")
async def create_promo(payload: PromoIn, admin: User = Depends(current_admin), db: AsyncSession = Depends(get_db)) -> dict:
    code = normalize_code(payload.code)
    if not re.fullmatch(r"[A-Z0-9_-]{3,32}", code):
        raise HTTPException(400, "Promokod: 3–32 ta lotin harf, raqam, - yoki _")
    if await db.scalar(select(PromoCode.id).where(PromoCode.code == code)):
        raise HTTPException(400, "Bunday promokod bor")
    promo = PromoCode(code=code, used_count=0)
    await _apply_promo(db, promo, payload)
    db.add(promo)
    await db.flush()
    await record_audit(
        db, actor_type=ActorType.ADMIN, actor_id=None, action="promo_created", entity_type="promo_code", entity_id=promo.id,
        meta={"by_telegram_id": admin.telegram_user_id, "code": code},
    )
    await db.commit()
    await db.refresh(promo)
    return _promo_admin(promo)


@router.put("/promos/{promo_id}")
async def update_promo(promo_id: int, payload: PromoIn, admin: User = Depends(current_admin), db: AsyncSession = Depends(get_db)) -> dict:
    promo = await db.get(PromoCode, promo_id)
    if promo is None:
        raise HTTPException(404, "Promokod topilmadi")
    await _apply_promo(db, promo, payload)
    await record_audit(
        db, actor_type=ActorType.ADMIN, actor_id=None, action="promo_updated", entity_type="promo_code", entity_id=promo.id,
        meta={"by_telegram_id": admin.telegram_user_id},
    )
    await db.commit()
    await db.refresh(promo)
    return _promo_admin(promo)


@router.delete("/promos/{promo_id}")
async def delete_promo(promo_id: int, admin: User = Depends(current_admin), db: AsyncSession = Depends(get_db)) -> dict:
    promo = await db.get(PromoCode, promo_id)
    if promo is None:
        raise HTTPException(404, "Promokod topilmadi")
    if promo.used_count:
        # Ishlatilgan promokod hisobotlar uchun qoladi — faqat o'chirib qo'yiladi.
        raise HTTPException(400, "Promokod ishlatilgan — o'chirib bo'lmaydi, faolsizlantiring")
    await db.delete(promo)
    await db.commit()
    return {"ok": True}


# --- To'lovlar ---


@router.get("/payments")
async def list_payments(status: str = "PENDING", admin: User = Depends(current_admin), db: AsyncSession = Depends(get_db)) -> list[dict]:
    query = select(Payment, User, Plan.name).join(User, User.id == Payment.user_id).outerjoin(Plan, Plan.id == Payment.plan_id)
    if status != "all":
        query = query.where(Payment.status == PaymentStatus(status))
    rows = (await db.execute(query.order_by(Payment.id.desc()).limit(50))).all()
    return [
        {
            "id": p.id,
            "amount": float(p.amount),
            "status": p.status.value,
            "plan_name": plan_name,
            "created_at": p.created_at.isoformat(),
            "confirmed_at": p.confirmed_at.isoformat() if p.confirmed_at else None,
            "user": {"id": u.id, "telegram_user_id": u.telegram_user_id, "name": _who(u)},
        }
        for p, u, plan_name in rows
    ]


@router.post("/payments/{payment_id}/confirm")
async def confirm_payment(payment_id: int, admin: User = Depends(current_admin), db: AsyncSession = Depends(get_db)) -> dict:
    service_admin = await _service_admin(db)
    payment = await payments_api.confirm_payment(payment_id, admin=service_admin)
    user = await db.get(User, payment.user_id)
    await db.refresh(user)
    if user.telegram_user_id:
        await send_telegram(
            user.telegram_user_id,
            f"✅ To'lov #{payment.id} tasdiqlandi — {_money(payment.amount)}.\n💰 Balans: {_money(user.balance)}",
        )
    return {"ok": True}


class RejectIn(BaseModel):
    reason: str = "Admin tomonidan rad etildi"


@router.post("/payments/{payment_id}/reject")
async def reject_payment(payment_id: int, payload: RejectIn, admin: User = Depends(current_admin), db: AsyncSession = Depends(get_db)) -> dict:
    service_admin = await _service_admin(db)
    payment = await payments_api.reject_payment(payment_id, RejectPaymentAdmin(reason=payload.reason), admin=service_admin, db=db)
    user = await db.get(User, payment.user_id)
    if user and user.telegram_user_id:
        await send_telegram(user.telegram_user_id, f"❌ To'lov so'rovi #{payment.id} rad etildi. Savol bo'lsa admin bilan bog'laning.")
    return {"ok": True}


# --- Foydalanuvchilar ---


async def _user_admin(db: AsyncSession, user: User) -> dict:
    ent = await get_entitlement(db, user.id)
    return {
        "id": user.id,
        "telegram_user_id": user.telegram_user_id,
        "name": _who(user),
        "first_name": user.first_name,
        "balance": float(user.balance),
        "is_banned": user.is_banned,
        "is_admin": user.telegram_user_id in settings.admin_telegram_id_set,
        "created_at": user.created_at.isoformat() if user.created_at else None,
        "plan": {"code": ent.plan_code, "name": ent.plan_name, "expires_at": ent.expires_at.isoformat() if ent.expires_at else None},
        "usage": {"accounts": ent.accounts_used, "automations": ent.automations_used},
    }


@router.get("/users")
async def list_users(q: str = "", admin: User = Depends(current_admin), db: AsyncSession = Depends(get_db)) -> list[dict]:
    query = select(User)
    q = q.strip().lstrip("@")
    if q:
        conditions = [User.username.ilike(f"%{q}%"), User.first_name.ilike(f"%{q}%")]
        if q.isdigit():
            conditions += [User.telegram_user_id == int(q), User.id == int(q)]
        query = query.where(or_(*conditions))
    users = list(await db.scalars(query.order_by(User.id.desc()).limit(30)))
    return [await _user_admin(db, u) for u in users]


class BalanceIn(BaseModel):
    amount: float
    reason: str = Field(min_length=1, max_length=200)


@router.post("/users/{user_id}/balance")
async def adjust_balance(user_id: int, payload: BalanceIn, admin: User = Depends(current_admin), db: AsyncSession = Depends(get_db)) -> dict:
    if payload.amount == 0:
        raise HTTPException(400, "Summa 0 bo'lmasin")
    service_admin = await _service_admin(db)
    result = await admin_api.balance_adjust(user_id, BalanceAdjust(amount=payload.amount, reason=payload.reason), admin=service_admin)
    user = await db.get(User, user_id)
    await db.refresh(user)
    if user.telegram_user_id:
        sign = "+" if payload.amount > 0 else "−"
        await send_telegram(
            user.telegram_user_id,
            f"💰 Balansingiz o'zgardi: {sign}{_money(abs(payload.amount))} ({payload.reason}).\nJoriy balans: {_money(user.balance)}",
        )
    return {"ok": True, "balance": result["balance"], "user": await _user_admin(db, user)}


class GrantIn(BaseModel):
    plan_code: str
    days: int = Field(ge=1, le=3650)


@router.post("/users/{user_id}/grant")
async def grant_plan(user_id: int, payload: GrantIn, admin: User = Depends(current_admin), db: AsyncSession = Depends(get_db)) -> dict:
    """Tarifni tekinga berish yoki uzaytirish (sovg'a, kompensatsiya)."""
    user = await db.get(User, user_id)
    plan = await db.scalar(select(Plan).where(Plan.code == payload.plan_code))
    if user is None or plan is None or plan.code == FREE_CODE:
        raise HTTPException(404, "Foydalanuvchi yoki tarif topilmadi")
    now = datetime.datetime.now(datetime.timezone.utc)
    subscription = await payments_api._extend_or_create_subscription(db, user.id, plan, now, days=payload.days)
    await record_audit(
        db, actor_type=ActorType.ADMIN, actor_id=None, action="plan_granted", entity_type="subscription",
        entity_id=subscription.id, meta={"by_telegram_id": admin.telegram_user_id, "plan": plan.code, "days": payload.days},
    )
    await db.commit()
    if user.telegram_user_id:
        await send_telegram(
            user.telegram_user_id, f"🎁 Sizga {plan.name} tarifi {payload.days} kunga berildi! Imkoniyatlar allaqachon ochiq."
        )
    return {"ok": True, "user": await _user_admin(db, user)}


class BanIn(BaseModel):
    banned: bool


@router.post("/users/{user_id}/ban")
async def set_ban(user_id: int, payload: BanIn, admin: User = Depends(current_admin), db: AsyncSession = Depends(get_db)) -> dict:
    user = await db.get(User, user_id)
    if user is None:
        raise HTTPException(404, "Foydalanuvchi topilmadi")
    if user.telegram_user_id in settings.admin_telegram_id_set:
        raise HTTPException(400, "Adminni bloklab bo'lmaydi")
    user.is_banned = payload.banned
    await record_audit(
        db, actor_type=ActorType.ADMIN, actor_id=None, action="user_banned" if payload.banned else "user_unbanned",
        entity_type="user", entity_id=user.id, meta={"by_telegram_id": admin.telegram_user_id},
    )
    await db.commit()
    return {"ok": True, "user": await _user_admin(db, user)}


# --- To'lov rekvizitlari ---


class PaymentSettingsIn(BaseModel):
    instructions: str = Field(max_length=1000)


@router.get("/settings/payment")
async def get_payment_settings(admin: User = Depends(current_admin), db: AsyncSession = Depends(get_db)) -> dict:
    return {"instructions": await payment_instructions(db)}


@router.put("/settings/payment")
async def set_payment_settings(
    payload: PaymentSettingsIn, admin: User = Depends(current_admin), db: AsyncSession = Depends(get_db)
) -> dict:
    row = await db.scalar(select(SystemSetting).where(SystemSetting.key == PAYMENT_SETTING_KEY))
    if row is None:
        row = SystemSetting(key=PAYMENT_SETTING_KEY, value={})
        db.add(row)
    row.value = {**(row.value or {}), "instructions": payload.instructions.strip()}
    await record_audit(
        db, actor_type=ActorType.ADMIN, actor_id=None, action="payment_settings_updated", entity_type="system_setting",
        entity_id=None, meta={"by_telegram_id": admin.telegram_user_id},
    )
    await db.commit()
    return {"instructions": row.value["instructions"]}
