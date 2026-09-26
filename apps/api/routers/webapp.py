"""Telegram Mini App uchun API. Har so'rov initData'dan olingan foydalanuvchi tokeni bilan —
foydalanuvchi faqat o'z akkauntlari va xizmatlarini ko'radi/o'zgartiradi."""

import datetime
import logging
import secrets

import httpx
import jwt
from fastapi import APIRouter, Depends, Header, HTTPException, Query
from fastapi.responses import Response
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.billing import PLAN_FEATURES, PromoError, paid_plans, payment_instructions, plan_public, quote
from core.catalog import FIELD_LIMITS, SERVICE_CATALOG, SERVICE_CODES, TEMPLATE_VARIABLES
from core.db.models import Automation, MediaFile, ProfileSnapshot, Schedule, TelegramAccount, User
from core.notify import send_telegram
from core.preview import automation_preview
from core.settings import settings
from core.templates import TemplateContext, render
from core.webapp_auth import InitDataError, create_user_token, decode_user_token, validate_init_data
from deps import get_db
from redis_client import get_redis
from routers import automations as automations_api
from routers import payments as payments_api
from routers.users import get_overview
from schemas import ActionIn, ActivateRequest, AutomationCreate, MediaUpload, PurchaseCreate, ScheduleIn, StopRequest, TopupCreate

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/webapp", tags=["webapp"])

MAX_ITEMS = 10
DEFAULT_INTERVAL = 60
EMOJI_CACHE_SECONDS = 7 * 24 * 3600


# --- Autentifikatsiya ---


class AuthIn(BaseModel):
    init_data: str


async def current_user(
    authorization: str | None = Header(None), t: str | None = Query(None), db: AsyncSession = Depends(get_db)
) -> User:
    # <img src> sarlavha yubora olmaydi — rasm endpointlari uchun token ?t= orqali ham qabul qilinadi.
    token = authorization.removeprefix("Bearer ").strip() if authorization else t
    if not token:
        raise HTTPException(401, "Token yo'q")
    try:
        user_id = decode_user_token(token)
    except jwt.PyJWTError as exc:
        raise HTTPException(401, "Sessiya tugagan — ilovani qayta oching") from exc
    user = await db.get(User, user_id)
    if user is None or user.is_banned:
        raise HTTPException(403, "Hisob bloklangan")
    return user


@router.post("/auth")
async def auth(payload: AuthIn, db: AsyncSession = Depends(get_db)) -> dict:
    try:
        tg_user = validate_init_data(payload.init_data, settings.bot_token)
    except InitDataError as exc:
        logger.warning("webapp auth rad etildi: %s", exc)
        raise HTTPException(401, "Telegram ma'lumotlari tasdiqlanmadi — ilovani bot ichidan oching") from exc

    user = await db.scalar(select(User).where(User.telegram_user_id == tg_user["id"]))
    if user is None:
        user = User(
            telegram_user_id=tg_user["id"],
            username=tg_user.get("username"),
            first_name=tg_user.get("first_name"),
            last_name=tg_user.get("last_name"),
            language_code=tg_user.get("language_code"),
            referral_code=secrets.token_urlsafe(6),
        )
        db.add(user)
        await db.commit()
        await db.refresh(user)
    if user.is_banned:
        raise HTTPException(403, "Hisob bloklangan")
    return {"token": create_user_token(user.id), "user_id": user.id}


# --- Holat (profil ko'rinishi, xizmatlar, tariflar) ---


async def _owned_account(db: AsyncSession, user: User, account_id: int) -> TelegramAccount:
    account = await db.get(TelegramAccount, account_id)
    if account is None or account.user_id != user.id:
        raise HTTPException(404, "Akkaunt topilmadi")
    return account


async def _bot_username() -> str | None:
    redis = get_redis()
    cached = await redis.get("bot_username")
    if cached:
        return cached.decode()
    async with httpx.AsyncClient(timeout=10) as client:
        me = (await client.get(f"https://api.telegram.org/bot{settings.bot_token}/getMe")).json()
    username = me.get("result", {}).get("username")
    if username:
        await redis.set("bot_username", username, ex=86400)
    return username


def _ctx(account: dict | TelegramAccount) -> TemplateContext:
    get = account.get if isinstance(account, dict) else lambda k: getattr(account, k)
    return TemplateContext(
        first_name=get("first_name"), last_name=get("last_name"), username=get("username"), timezone=settings.default_timezone
    )


@router.get("/state")
async def state(account_id: int | None = None, user: User = Depends(current_user), db: AsyncSession = Depends(get_db)) -> dict:
    overview = await get_overview(user.id, db)
    plans = await paid_plans(db)
    flags = overview["plan"]["flags"]
    catalog = [{**s, "unlocked": s["flag"] is None or bool(flags.get(s["flag"]))} for s in SERVICE_CATALOG]

    base = {
        "user": overview["user"],
        "plan": overview["plan"],
        "usage": overview["usage"],
        "plans": [plan_public(p) for p in plans],
        "free_plan": overview["free_plan"],
        "features": PLAN_FEATURES,
        "is_admin": user.telegram_user_id in settings.admin_telegram_id_set,
        "catalog": catalog,
        "variables": TEMPLATE_VARIABLES,
        "limits": FIELD_LIMITS,
        "timezone": settings.default_timezone,
        "payment_instructions": await payment_instructions(db),
        "bot_username": await _bot_username(),
        "accounts": [{k: a[k] for k in ("id", "username", "first_name", "status", "is_premium")} for a in overview["accounts"]],
    }
    account = next((a for a in overview["accounts"] if a["id"] == account_id), None) or (
        overview["accounts"][0] if overview["accounts"] else None
    )
    if account is None:
        return {**base, "account": None}

    now = datetime.datetime.now(datetime.timezone.utc)
    ctx = _ctx(account)
    automation_ids = [a["id"] for a in account["automations"]]
    extra = {
        row.id: row
        for row in (
            await db.execute(
                select(Automation.id, Automation.last_playlist_index, Schedule.next_run_at)
                .outerjoin(Schedule, Schedule.automation_id == Automation.id)
                .where(Automation.id.in_(automation_ids or [0]))
            )
        ).all()
    }
    redis = get_redis()

    services = []
    for automation in account["automations"]:
        cached = await redis.get(f"last_applied:{automation['id']}:{automation['field']}")
        info = extra.get(automation["id"])
        preview = automation_preview(
            automation,
            ctx,
            now,
            cached.decode() if cached else None,
            info.next_run_at if info else None,
            info.last_playlist_index if info else 0,
        )
        services.append({**automation, "preview": {**preview, "next_at": preview["next_at"].isoformat() if preview["next_at"] else None}})

    originals = {
        s.field.value: s.value
        for s in await db.scalars(
            select(ProfileSnapshot).where(ProfileSnapshot.telegram_account_id == account["id"], ProfileSnapshot.restored == False)  # noqa: E712
        )
    }
    return {**base, "account": {k: v for k, v in account.items() if k != "automations"}, "services": services, "originals": originals}


class PreviewIn(BaseModel):
    account_id: int
    field: str
    template: str


@router.post("/preview")
async def preview(payload: PreviewIn, user: User = Depends(current_user), db: AsyncSession = Depends(get_db)) -> dict:
    """Shablon yozilayotganda jonli ko'rinish: hozir va 1 daqiqadan keyin qanday bo'lishi."""
    account = await _owned_account(db, user, payload.account_id)
    limit = FIELD_LIMITS.get(payload.field, 70) * (2 if payload.field == "bio" and account.is_premium else 1)
    now = datetime.datetime.now(datetime.timezone.utc)
    try:
        current = render(payload.template, _ctx(account), now)
        later = render(payload.template, _ctx(account), now + datetime.timedelta(minutes=1))
    except ValueError:
        return {"ok": False, "error": "Shablonda noma'lum o'zgaruvchi bor", "limit": limit}
    if not current.strip():
        return {"ok": False, "error": "Bo'sh bo'lmasligi kerak", "now": current, "limit": limit, "length": 0}
    if len(current) > limit:
        return {"ok": False, "error": f"Juda uzun ({len(current)}/{limit})", "now": current, "limit": limit, "length": len(current)}
    return {"ok": True, "now": current, "later": later, "limit": limit, "length": len(current)}


# --- Xizmatlarni yoqish / o'chirish ---


class ServiceIn(BaseModel):
    account_id: int
    service_code: str
    field: str | None = None
    items: list[dict]  # [{"template": ..., "at_time": "HH:MM"?}]
    interval_seconds: int = DEFAULT_INTERVAL
    selection_strategy: str = "NONE"


@router.post("/services")
async def enable_service(payload: ServiceIn, user: User = Depends(current_user), db: AsyncSession = Depends(get_db)) -> dict:
    account = await _owned_account(db, user, payload.account_id)
    if payload.service_code not in SERVICE_CODES:
        raise HTTPException(400, "Noma'lum xizmat")
    meta = next(s for s in SERVICE_CATALOG if s["code"] == payload.service_code)
    field = payload.field if meta["kind"] == "schedule" and payload.field in ("bio", "name") else meta["field"]
    if not 1 <= len(payload.items) <= MAX_ITEMS:
        raise HTTPException(400, f"1 tadan {MAX_ITEMS} tagacha element bo'lishi kerak")
    if payload.interval_seconds < 60:
        raise HTTPException(400, "Eng kichik interval — 1 daqiqa")

    if field in FIELD_LIMITS:
        limit = FIELD_LIMITS[field] * (2 if field == "bio" and account.is_premium else 1)
        for item in payload.items:
            try:
                rendered = render(item["template"], _ctx(account))
            except (ValueError, KeyError) as exc:
                raise HTTPException(400, "Shablonda noma'lum o'zgaruvchi bor") from exc
            if not rendered.strip() or len(rendered) > limit:
                raise HTTPException(400, f"«{item['template']}» bo'sh yoki juda uzun ({len(rendered)}/{limit})")

    create = AutomationCreate(
        telegram_account_id=account.id,
        service_code=payload.service_code,
        selection_strategy=payload.selection_strategy,
        actions=[
            ActionIn(field=field, template=str(item["template"]), order_index=i, at_time=item.get("at_time"))
            for i, item in enumerate(payload.items)
        ],
        schedule=ScheduleIn(trigger_type="INTERVAL", interval_seconds=payload.interval_seconds, timezone=settings.default_timezone),
    )
    automation = await automations_api.create_automation(create, db)
    await automations_api.activate_automation(automation.id, ActivateRequest(resolution="replace"), db)
    return {"ok": True, "automation_id": automation.id}


@router.post("/services/{automation_id}/stop")
async def stop_service(
    automation_id: int, restore: bool = True, user: User = Depends(current_user), db: AsyncSession = Depends(get_db)
) -> dict:
    automation = await db.get(Automation, automation_id)
    if automation is None:
        raise HTTPException(404, "Xizmat topilmadi")
    await _owned_account(db, user, automation.telegram_account_id)
    await automations_api.stop_automation(automation_id, StopRequest(restore=restore), db)
    return {"ok": True}


# --- Rasmlar va emoji ---


class MediaIn(BaseModel):
    data_b64: str
    mime: str = "image/jpeg"


@router.post("/media")
async def upload_media(payload: MediaIn, user: User = Depends(current_user), db: AsyncSession = Depends(get_db)) -> dict:
    return await automations_api.upload_media(MediaUpload(user_id=user.id, data_b64=payload.data_b64, mime=payload.mime), db)


@router.get("/media/{media_id}")
async def get_media(media_id: int, user: User = Depends(current_user), db: AsyncSession = Depends(get_db)) -> Response:
    media = await db.get(MediaFile, media_id)
    if media is None or media.user_id != user.id:
        raise HTTPException(404, "Rasm topilmadi")
    return Response(media.data, media_type=media.mime, headers={"Cache-Control": "private, max-age=86400"})


@router.get("/emoji/{emoji_id}")
async def get_emoji(emoji_id: str, user: User = Depends(current_user)) -> Response:
    """Premium emoji rasmi (statik thumbnail) — Bot API orqali olinadi; bot tokeni brauzerga chiqmaydi."""
    if not emoji_id.isdigit():
        raise HTTPException(404, "Emoji topilmadi")
    redis = get_redis()
    cached = await redis.get(f"emoji_img:{emoji_id}")
    if cached:
        return Response(cached, media_type="image/webp", headers={"Cache-Control": "private, max-age=86400"})

    base = f"https://api.telegram.org/bot{settings.bot_token}"
    async with httpx.AsyncClient(timeout=10) as client:
        stickers = (await client.post(f"{base}/getCustomEmojiStickers", json={"custom_emoji_ids": [emoji_id]})).json()
        if not stickers.get("ok") or not stickers["result"]:
            raise HTTPException(404, "Emoji topilmadi")
        sticker = stickers["result"][0]
        file_id = (sticker.get("thumbnail") or {}).get("file_id") or sticker["file_id"]
        file_path = (await client.post(f"{base}/getFile", json={"file_id": file_id})).json()["result"]["file_path"]
        data = (await client.get(f"https://api.telegram.org/file/bot{settings.bot_token}/{file_path}")).content
    await redis.set(f"emoji_img:{emoji_id}", data, ex=EMOJI_CACHE_SECONDS)
    return Response(data, media_type="image/webp", headers={"Cache-Control": "private, max-age=86400"})


# --- Tarif va balans ---


class BuyIn(BaseModel):
    promo_code: str | None = None


@router.post("/plans/{plan_code}/quote")
async def quote_plan(plan_code: str, payload: BuyIn, user: User = Depends(current_user), db: AsyncSession = Depends(get_db)) -> dict:
    """Promokodni tekshirish va yakuniy narxni ko'rsatish (hech narsa yechilmaydi)."""
    plan = next((p for p in await paid_plans(db) if p.code == plan_code), None)
    if plan is None:
        raise HTTPException(404, "Tarif topilmadi")
    try:
        q = await quote(db, user.id, plan, payload.promo_code)
    except PromoError as exc:
        return {"ok": False, "error": str(exc)}
    return {"ok": True, **q.public()}


@router.post("/plans/{plan_code}/buy")
async def buy_plan(plan_code: str, payload: BuyIn | None = None, user: User = Depends(current_user)) -> dict:
    promo = payload.promo_code if payload else None
    subscription = await payments_api.buy_with_balance(PurchaseCreate(user_id=user.id, plan_code=plan_code, promo_code=promo))
    return {"ok": True, "expires_at": subscription.expires_at.isoformat()}


class TopupIn(BaseModel):
    amount: int


@router.post("/topup")
async def topup(payload: TopupIn, user: User = Depends(current_user), db: AsyncSession = Depends(get_db)) -> dict:
    if payload.amount < 1000:
        raise HTTPException(400, "Kamida 1 000 so'm")
    payment = await payments_api.create_topup(TopupCreate(user_id=user.id, amount=payload.amount), db)
    who = f"@{user.username}" if user.username else (user.first_name or str(user.telegram_user_id))
    amount_text = f"{payload.amount:,}".replace(",", " ")
    for admin_id in settings.admin_telegram_id_set:
        await send_telegram(
            admin_id,
            f"💳 Yangi to'ldirish so'rovi #{payment.id} (Mini App)\n👤 {who} (id {user.telegram_user_id})\nSumma: {amount_text} so'm",
            buttons=[[("✅ Tasdiqlash", f"adm_ok:{payment.id}"), ("❌ Rad etish", f"adm_no:{payment.id}")]],
        )
    return {"ok": True, "payment_id": payment.id, "instructions": await payment_instructions(db)}
