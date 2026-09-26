import secrets

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.billing import get_free_plan, plan_public
from core.db.enums import AutomationStatus, TelegramAccountStatus
from core.db.models import Automation, AutomationAction, Referral, Schedule, Service, TelegramAccount, User
from core.entitlements import FREE_PLAN, get_entitlement
from deps import get_db
from schemas import UserCreate, UserGetOrCreate, UserOut

router = APIRouter(prefix="/users", tags=["users"])


@router.post("", response_model=UserOut)
async def create_user(payload: UserCreate, db: AsyncSession = Depends(get_db)) -> User:
    user = User(
        telegram_user_id=payload.telegram_user_id,
        username=payload.username,
        first_name=payload.first_name,
        referral_code=secrets.token_urlsafe(6),
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user


@router.post("/get-or-create", response_model=UserOut)
async def get_or_create_user(payload: UserGetOrCreate, db: AsyncSession = Depends(get_db)) -> User:
    """Bot /start bosqichida chaqiriladi — idempotent, referral_code bo'lsa referral yozuvini yaratadi."""
    user = await db.scalar(select(User).where(User.telegram_user_id == payload.telegram_user_id))
    if user is not None:
        return user

    referrer = None
    if payload.referral_code:
        referrer = await db.scalar(select(User).where(User.referral_code == payload.referral_code))

    user = User(
        telegram_user_id=payload.telegram_user_id,
        username=payload.username,
        first_name=payload.first_name,
        last_name=payload.last_name,
        language_code=payload.language_code,
        referral_code=secrets.token_urlsafe(6),
        referred_by_user_id=referrer.id if referrer else None,
    )
    db.add(user)
    await db.flush()

    if referrer is not None:
        db.add(Referral(referrer_user_id=referrer.id, referred_user_id=user.id, code=payload.referral_code))

    await db.commit()
    await db.refresh(user)
    return user


@router.get("/{user_id}", response_model=UserOut)
async def get_user(user_id: int, db: AsyncSession = Depends(get_db)) -> User:
    user = await db.get(User, user_id)
    if user is None:
        raise HTTPException(404, "Foydalanuvchi topilmadi")
    return user


_SHOWN_AUTOMATION_STATUSES = (AutomationStatus.ACTIVE, AutomationStatus.STARTING, AutomationStatus.ERROR)


@router.get("/{user_id}/overview")
async def get_overview(user_id: int, db: AsyncSession = Depends(get_db)) -> dict:
    """Bot bosh ekrani uchun: tarif, limitlar, balans, akkauntlar va ulardagi faol xizmatlar — bitta so'rovda."""
    user = await db.get(User, user_id)
    if user is None:
        raise HTTPException(404, "Foydalanuvchi topilmadi")
    ent = await get_entitlement(db, user_id)

    accounts = list(
        await db.scalars(
            select(TelegramAccount)
            .where(TelegramAccount.user_id == user_id, TelegramAccount.status != TelegramAccountStatus.REVOKED)
            .order_by(TelegramAccount.id)
        )
    )
    rows = (
        await db.execute(
            select(Automation, Service.code, Schedule.interval_seconds, AutomationAction)
            .join(Service, Service.id == Automation.service_id)
            .join(AutomationAction, AutomationAction.automation_id == Automation.id)
            .outerjoin(Schedule, Schedule.automation_id == Automation.id)
            .where(
                Automation.telegram_account_id.in_([a.id for a in accounts] or [0]),
                Automation.status.in_(_SHOWN_AUTOMATION_STATUSES),
            )
            .order_by(Automation.id, AutomationAction.order_index)
        )
    ).all()
    automations: dict[int, dict] = {}
    for automation, service_code, interval_seconds, action in rows:
        item = automations.setdefault(
            automation.id,
            {
                "id": automation.id,
                "account_id": automation.telegram_account_id,
                "service_code": service_code,
                "status": automation.status.value,
                "field": action.field.value,
                "template": action.template,
                "selection_strategy": automation.selection_strategy.value,
                "interval_seconds": interval_seconds,
                "error_message": automation.error_message,
                "actions": [],
            },
        )
        item["actions"].append({"field": action.field.value, "template": action.template, "at_time": action.at_time})
    by_account: dict[int, list[dict]] = {}
    for item in automations.values():
        by_account.setdefault(item.pop("account_id"), []).append(item)
    free = await get_free_plan(db)

    return {
        "user": {
            "id": user.id,
            "balance": float(user.balance),
            "is_banned": user.is_banned,
            "referral_code": user.referral_code,
        },
        "plan": {
            "code": ent.plan_code,
            "name": ent.plan_name,
            "expires_at": ent.expires_at.isoformat() if ent.expires_at else None,
            "flags": ent.flags,
        },
        "usage": {"accounts": ent.accounts_used, "automations": ent.automations_used},
        "free_plan": plan_public(free) if free else {**FREE_PLAN, "price": 0, "final_price": 0, "description": None},
        "accounts": [
            {
                "id": a.id,
                "username": a.username,
                "first_name": a.first_name,
                "status": a.status.value,
                "is_premium": a.is_premium,
                "automations": by_account.get(a.id, []),
            }
            for a in accounts
        ],
    }
