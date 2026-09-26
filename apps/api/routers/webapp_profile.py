"""🎂 Tug'ilgan kun va 👁 Faollik holati — Mini App (/webapp/...) va bot (ichki /profile/...) uchun."""

import datetime

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.catalog import BIRTHDAY_TEMPLATES
from core.db.enums import AutomationStatus
from core.db.models import Automation, Service, TelegramAccount, User
from core.entitlements import get_entitlement
from core.telegram.presence import get_last_seen, get_telegram_birthday, set_last_seen
from core.templates import parse_birthday, render
from deps import get_db
from routers import automations as automations_api
from routers.webapp import ServiceIn, _ctx, _owned_account, current_user, enable_service
from routers.webapp_ai import _session_string
from schemas import StopRequest

router = APIRouter(prefix="/webapp", tags=["webapp-profile"])
internal_router = APIRouter(prefix="/profile", tags=["profile"])

# Foydalanuvchiga ko'rinadigan rejim -> Telegram maxfiylik qoidasi
PRESENCE_MODES = {
    "online": "everybody",  # onlayn ko'rinishi uchun vaqt hammaga ochiq bo'lishi shart
    "default": "everybody",
    "contacts": "contacts",
    "recently": "nobody",
}
_LAST_SEEN_TO_MODE = {"everybody": "default", "contacts": "contacts", "nobody": "recently"}


# --- Tug'ilgan kun ---


def _birthday_view(account: TelegramAccount) -> dict:
    parsed = parse_birthday(account.birthday)
    ctx = _ctx(account)
    templates = []
    for template in BIRTHDAY_TEMPLATES:
        try:
            templates.append({"template": template, "preview": render(template, ctx)})
        except ValueError as exc:
            templates.append({"template": template, "preview": None, "error": str(exc)})
    return {
        "birthday": account.birthday,
        "day": parsed[2] if parsed else None,
        "month": parsed[1] if parsed else None,
        "year": parsed[0] if parsed else None,
        "templates": templates,
    }


class BirthdayIn(BaseModel):
    day: int
    month: int
    year: int | None = None


async def save_birthday(db: AsyncSession, account: TelegramAccount, payload: BirthdayIn) -> dict:
    this_year = datetime.date.today().year
    if payload.year is not None and not 1900 <= payload.year <= this_year:
        raise HTTPException(400, "Yil noto'g'ri")
    value = (f"{payload.year:04d}-" if payload.year else "") + f"{payload.month:02d}-{payload.day:02d}"
    if parse_birthday(value) is None:
        raise HTTPException(400, "Sana noto'g'ri")
    account.birthday = value
    await db.commit()
    return _birthday_view(account)


async def import_birthday(db: AsyncSession, account: TelegramAccount) -> dict:
    value = await get_telegram_birthday(await _session_string(db, account))
    if not value:
        raise HTTPException(400, "Telegram profilingizda tug'ilgan kun ko'rsatilmagan")
    account.birthday = value
    await db.commit()
    return _birthday_view(account)


@router.get("/birthday")
async def get_birthday(account_id: int, user: User = Depends(current_user), db: AsyncSession = Depends(get_db)) -> dict:
    return _birthday_view(await _owned_account(db, user, account_id))


@router.put("/birthday")
async def put_birthday(account_id: int, payload: BirthdayIn, user: User = Depends(current_user), db: AsyncSession = Depends(get_db)) -> dict:
    return await save_birthday(db, await _owned_account(db, user, account_id), payload)


@router.post("/birthday/import")
async def post_import_birthday(account_id: int, user: User = Depends(current_user), db: AsyncSession = Depends(get_db)) -> dict:
    return await import_birthday(db, await _owned_account(db, user, account_id))


# --- Faollik holati ---


async def _online_automation(db: AsyncSession, account_id: int) -> Automation | None:
    return await db.scalar(
        select(Automation)
        .join(Service, Service.id == Automation.service_id)
        .where(
            Automation.telegram_account_id == account_id,
            Service.code == "online",
            Automation.status.in_([AutomationStatus.ACTIVE, AutomationStatus.STARTING]),
        )
    )


async def presence_state(db: AsyncSession, user: User, account: TelegramAccount) -> dict:
    ent = await get_entitlement(db, user.id)
    if await _online_automation(db, account.id):
        mode = "online"
    else:
        mode = _LAST_SEEN_TO_MODE[await get_last_seen(await _session_string(db, account))]
    return {"mode": mode, "online_unlocked": bool(ent.flags.get("online_service"))}


class PresenceIn(BaseModel):
    mode: str


async def save_presence(db: AsyncSession, user: User, account: TelegramAccount, mode: str) -> dict:
    if mode not in PRESENCE_MODES:
        raise HTTPException(400, "Noma'lum holat")
    session_string = await _session_string(db, account)
    online = await _online_automation(db, account.id)
    if mode == "online":
        if not (await get_entitlement(db, user.id)).flags.get("online_service"):
            raise HTTPException(402, "24/7 Online tarifingizda yo'q — tarifni yangilang")
        await set_last_seen(session_string, PRESENCE_MODES[mode])
        if online is None:
            await enable_service(
                ServiceIn(account_id=account.id, service_code="online", items=[{"template": "true"}]), user=user, db=db
            )
    else:
        if online is not None:
            await automations_api.stop_automation(online.id, StopRequest(restore=True), db)
        await set_last_seen(session_string, PRESENCE_MODES[mode])
    return {"mode": mode, "online_unlocked": bool((await get_entitlement(db, user.id)).flags.get("online_service"))}


@router.get("/presence")
async def get_presence(account_id: int, user: User = Depends(current_user), db: AsyncSession = Depends(get_db)) -> dict:
    return await presence_state(db, user, await _owned_account(db, user, account_id))


@router.put("/presence")
async def put_presence(account_id: int, payload: PresenceIn, user: User = Depends(current_user), db: AsyncSession = Depends(get_db)) -> dict:
    return await save_presence(db, user, await _owned_account(db, user, account_id), payload.mode)


# --- Bot uchun (ichki API) ---


async def _internal(db: AsyncSession, user_id: int, account_id: int) -> tuple[User, TelegramAccount]:
    user = await db.get(User, user_id)
    if user is None:
        raise HTTPException(404, "Foydalanuvchi topilmadi")
    return user, await _owned_account(db, user, account_id)


@internal_router.get("/{user_id}/{account_id}/birthday")
async def internal_get_birthday(user_id: int, account_id: int, db: AsyncSession = Depends(get_db)) -> dict:
    _, account = await _internal(db, user_id, account_id)
    return _birthday_view(account)


@internal_router.put("/{user_id}/{account_id}/birthday")
async def internal_put_birthday(user_id: int, account_id: int, payload: BirthdayIn, db: AsyncSession = Depends(get_db)) -> dict:
    _, account = await _internal(db, user_id, account_id)
    return await save_birthday(db, account, payload)


@internal_router.post("/{user_id}/{account_id}/birthday/import")
async def internal_import_birthday(user_id: int, account_id: int, db: AsyncSession = Depends(get_db)) -> dict:
    _, account = await _internal(db, user_id, account_id)
    return await import_birthday(db, account)


@internal_router.get("/{user_id}/{account_id}/presence")
async def internal_get_presence(user_id: int, account_id: int, db: AsyncSession = Depends(get_db)) -> dict:
    user, account = await _internal(db, user_id, account_id)
    return await presence_state(db, user, account)


@internal_router.put("/{user_id}/{account_id}/presence")
async def internal_put_presence(user_id: int, account_id: int, payload: PresenceIn, db: AsyncSession = Depends(get_db)) -> dict:
    user, account = await _internal(db, user_id, account_id)
    return await save_presence(db, user, account, payload.mode)
