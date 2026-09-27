"""Admin panel: referal boshqaruvi, ommaviy xabarlar, foydalanuvchi tafsilotlari, statistika, jurnal, tizim holati."""

import csv
import datetime
import io

import httpx
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from arq_pool import get_pool
from core import referrals
from core.audit import record_audit
from core.broadcasts import MAX_BUTTONS, SEGMENTS, STYLES, personalize, recipients, reply_markup, segment_query, send_one
from core.db.enums import ActorType, AutomationStatus, PaymentStatus, TransactionType, WorkerJobStatus
from core.db.models import (
    AccountAI,
    AuditLog,
    Automation,
    Broadcast,
    MediaFile,
    Payment,
    Plan,
    PromoCode,
    Referral,
    ReferralReward,
    Service,
    SystemSetting,
    TelegramAccount,
    Transaction,
    User,
    WorkerJob,
)
from core.entitlements import get_entitlement
from core.notify import send_telegram
from core.settings import settings
from core.webapp_url import discover_webapp_url
from deps import get_db
from routers.webapp import current_user
from routers.webapp_admin import _who, current_admin

router = APIRouter(prefix="/webapp/admin", tags=["webapp-admin-tools"])


def _iso(value: datetime.datetime | None) -> str | None:
    return value.isoformat() if value else None


# --- Referal ---


class MilestoneIn(BaseModel):
    count: int = Field(ge=1, le=10000)
    plan_code: str
    days: int = Field(ge=1, le=3650)


class ReferralSettingsIn(BaseModel):
    enabled: bool
    mode: str = Field(pattern="^(start|account)$")
    bonus_per_referral: int = Field(0, ge=0, le=10_000_000)
    milestones: list[MilestoneIn] = []
    friend_plan_code: str = "starter"
    friend_days: int = Field(0, ge=0, le=365)


@router.get("/referrals")
async def referral_overview(admin: User = Depends(current_admin), db: AsyncSession = Depends(get_db)) -> dict:
    counts = dict((await db.execute(select(Referral.status, func.count(Referral.id)).group_by(Referral.status))).all())
    top = (
        await db.execute(
            select(User, func.count(Referral.id).label("n"))
            .join(Referral, Referral.referrer_user_id == User.id)
            .where(Referral.status == "qualified")
            .group_by(User.id)
            .order_by(func.count(Referral.id).desc())
            .limit(10)
        )
    ).all()
    recent = (
        await db.execute(select(Referral).order_by(Referral.id.desc()).limit(40))
    ).scalars().all()
    users = {u.id: u for u in await db.scalars(select(User).where(User.id.in_({r.referrer_user_id for r in recent} | {r.referred_user_id for r in recent} or {0})))}
    plans = [{"code": p.code, "name": p.name} for p in await db.scalars(select(Plan).where(Plan.code != "free").order_by(Plan.sort_order))]
    return {
        "settings": await referrals.get_settings(db),
        "plans": plans,
        "stats": {
            "qualified": counts.get("qualified", 0),
            "pending": counts.get("pending", 0),
            "rejected": counts.get("rejected", 0),
            "rewards": await db.scalar(select(func.count(ReferralReward.id))),
            "bonus_paid": float(
                await db.scalar(
                    select(func.coalesce(func.sum(Transaction.amount), 0)).where(Transaction.type == TransactionType.REFERRAL_BONUS)
                )
            ),
        },
        "top": [{"user_id": u.id, "name": _who(u), "count": n} for u, n in top],
        "recent": [
            {
                "id": r.id,
                "status": r.status,
                "created_at": _iso(r.created_at),
                "referrer": _who(users.get(r.referrer_user_id)) if users.get(r.referrer_user_id) else "—",
                "referred": _who(users.get(r.referred_user_id)) if users.get(r.referred_user_id) else "—",
            }
            for r in recent
        ],
    }


@router.put("/referrals/settings")
async def save_referral_settings(payload: ReferralSettingsIn, admin: User = Depends(current_admin), db: AsyncSession = Depends(get_db)) -> dict:
    codes = set(await db.scalars(select(Plan.code)))
    for m in payload.milestones:
        if m.plan_code not in codes:
            raise HTTPException(400, f"Noma'lum tarif: {m.plan_code}")
    if payload.friend_days and payload.friend_plan_code not in codes:
        raise HTTPException(400, f"Noma'lum tarif: {payload.friend_plan_code}")
    counts = [m.count for m in payload.milestones]
    if len(counts) != len(set(counts)):
        raise HTTPException(400, "Bosqichlardagi sonlar takrorlanmasin")
    row = await db.scalar(select(SystemSetting).where(SystemSetting.key == referrals.SETTING_KEY))
    if row is None:
        row = SystemSetting(key=referrals.SETTING_KEY, value={})
        db.add(row)
    row.value = {**payload.model_dump(), "milestones": sorted([m.model_dump() for m in payload.milestones], key=lambda m: m["count"])}
    await record_audit(
        db, actor_type=ActorType.ADMIN, actor_id=None, action="referral_settings_updated", entity_type="system_setting",
        entity_id=None, meta={"by_telegram_id": admin.telegram_user_id, **row.value},
    )
    await db.commit()
    return await referral_overview(admin, db)


@router.post("/referrals/{referral_id}/{action}")
async def referral_action(referral_id: int, action: str, admin: User = Depends(current_admin), db: AsyncSession = Depends(get_db)) -> dict:
    referral = await db.get(Referral, referral_id)
    if referral is None:
        raise HTTPException(404, "Referal topilmadi")
    messages = []
    if action == "qualify":
        messages = await referrals.qualify(db, referral)
    elif action == "reject":
        if referral.status == "qualified":
            raise HTTPException(400, "Hisoblangan referalni rad etib bo'lmaydi (sovg'a berilgan bo'lishi mumkin)")
        referral.status = "rejected"
    else:
        raise HTTPException(400, "Noma'lum amal")
    await record_audit(
        db, actor_type=ActorType.ADMIN, actor_id=None, action=f"referral_{action}", entity_type="referral",
        entity_id=referral.id, meta={"by_telegram_id": admin.telegram_user_id},
    )
    await db.commit()
    for chat_id, text in messages:
        await send_telegram(chat_id, text)
    return {"ok": True}


# --- Ommaviy xabarlar ---


class ButtonIn(BaseModel):
    type: str = Field(pattern="^(url|webapp|copy|plans|home|ref)$")
    text: str = Field(min_length=1, max_length=64)
    value: str = Field("", max_length=256)


class BroadcastIn(BaseModel):
    text: str = Field(min_length=1, max_length=4000)
    segment: dict = {"code": "all"}
    media_id: int | None = None
    buttons: list[ButtonIn] = Field(default_factory=list, max_length=MAX_BUTTONS)


def _broadcast_view(b: Broadcast) -> dict:
    return {
        "id": b.id,
        "status": b.status,
        "text": b.text,
        "segment": b.segment,
        "media_id": b.media_id,
        "buttons": b.buttons,
        "total": b.total,
        "sent": b.sent,
        "failed": b.failed,
        "blocked": b.blocked,
        "created_at": _iso(b.created_at),
        "started_at": _iso(b.started_at),
        "finished_at": _iso(b.finished_at),
    }


def _check_media(media: MediaFile | None, admin: User) -> None:
    if media is None or media.user_id != admin.id:
        raise HTTPException(400, "Rasm topilmadi — qaytadan yuklang")


@router.get("/broadcasts")
async def list_broadcasts(admin: User = Depends(current_admin), db: AsyncSession = Depends(get_db)) -> dict:
    rows = await db.scalars(select(Broadcast).order_by(Broadcast.id.desc()).limit(20))
    promos = await db.scalars(select(PromoCode).where(PromoCode.is_active == True).order_by(PromoCode.id.desc()))  # noqa: E712
    plans = [{"code": p.code, "name": p.name} for p in await db.scalars(select(Plan).order_by(Plan.sort_order))]
    return {
        "broadcasts": [_broadcast_view(b) for b in rows],
        "styles": STYLES,
        "segments": SEGMENTS,
        "plans": plans,
        "promos": [
            {"code": p.code, "label": f"{p.code} · " + (f"−{p.discount_percent}%" if p.discount_percent else f"−{int(p.discount_amount or 0)} so'm")}
            for p in promos
        ],
    }


@router.post("/broadcasts/count")
async def count_recipients(segment: dict, admin: User = Depends(current_admin), db: AsyncSession = Depends(get_db)) -> dict:
    total = await db.scalar(select(func.count()).select_from(segment_query(segment).subquery()))
    return {"total": total}


@router.post("/broadcasts/test")
async def test_broadcast(payload: BroadcastIn, admin: User = Depends(current_admin), db: AsyncSession = Depends(get_db)) -> dict:
    """Faqat adminning o'ziga — formatlash va tugmalarni tekshirish uchun."""
    photo = None
    if payload.media_id:
        media = await db.get(MediaFile, payload.media_id)
        _check_media(media, admin)
        photo = media.data
    markup = reply_markup([b.model_dump() for b in payload.buttons], await discover_webapp_url())
    async with httpx.AsyncClient(timeout=30) as client:
        result, _, error = await send_one(client, admin.telegram_user_id, personalize(payload.text, admin.first_name), markup, photo)
    if result != "ok":
        raise HTTPException(400, f"Telegram qabul qilmadi: {error}")
    return {"ok": True}


@router.post("/broadcasts")
async def start_broadcast(payload: BroadcastIn, admin: User = Depends(current_admin), db: AsyncSession = Depends(get_db)) -> dict:
    if payload.media_id:
        _check_media(await db.get(MediaFile, payload.media_id), admin)
    if await db.scalar(select(Broadcast.id).where(Broadcast.status == "sending")):
        raise HTTPException(409, "Boshqa xabar hali yuborilmoqda — tugashini kuting yoki to'xtating")
    broadcast = Broadcast(
        created_by=admin.telegram_user_id,
        status="sending",
        segment=payload.segment,
        text=payload.text,
        media_id=payload.media_id,
        buttons=[b.model_dump() for b in payload.buttons],
        total=len(await recipients(db, payload.segment)),
    )
    db.add(broadcast)
    await db.flush()
    await record_audit(
        db, actor_type=ActorType.ADMIN, actor_id=None, action="broadcast_started", entity_type="broadcast",
        entity_id=broadcast.id, meta={"by_telegram_id": admin.telegram_user_id, "segment": payload.segment, "total": broadcast.total},
    )
    await db.commit()
    pool = await get_pool()
    await pool.enqueue_job("broadcast_job", broadcast_id=broadcast.id, _job_id=f"broadcast:{broadcast.id}")
    return _broadcast_view(broadcast)


@router.get("/broadcasts/{broadcast_id}")
async def get_broadcast(broadcast_id: int, admin: User = Depends(current_admin), db: AsyncSession = Depends(get_db)) -> dict:
    broadcast = await db.get(Broadcast, broadcast_id)
    if broadcast is None:
        raise HTTPException(404, "Topilmadi")
    return _broadcast_view(broadcast)


@router.post("/broadcasts/{broadcast_id}/cancel")
async def cancel_broadcast(broadcast_id: int, admin: User = Depends(current_admin), db: AsyncSession = Depends(get_db)) -> dict:
    broadcast = await db.get(Broadcast, broadcast_id)
    if broadcast is None:
        raise HTTPException(404, "Topilmadi")
    if broadcast.status == "sending":
        broadcast.status = "cancelled"
        await db.commit()
    return _broadcast_view(broadcast)


# --- Foydalanuvchi tafsilotlari va shaxsiy xabar ---


@router.get("/users/{user_id}/details")
async def user_details(user_id: int, admin: User = Depends(current_admin), db: AsyncSession = Depends(get_db)) -> dict:
    user = await db.get(User, user_id)
    if user is None:
        raise HTTPException(404, "Foydalanuvchi topilmadi")
    accounts = list(await db.scalars(select(TelegramAccount).where(TelegramAccount.user_id == user.id).order_by(TelegramAccount.id)))
    services = (
        await db.execute(
            select(Automation.telegram_account_id, Service.code)
            .join(Service, Service.id == Automation.service_id)
            .where(Automation.telegram_account_id.in_([a.id for a in accounts] or [0]), Automation.status == AutomationStatus.ACTIVE)
        )
    ).all()
    ai_on = set(await db.scalars(select(AccountAI.telegram_account_id).where(AccountAI.enabled == True)))  # noqa: E712
    payments = await db.scalars(select(Payment).where(Payment.user_id == user.id).order_by(Payment.id.desc()).limit(5))
    referred_by = await db.get(User, user.referred_by_user_id) if user.referred_by_user_id else None
    ref = await referrals.summary(db, user)
    return {
        "accounts": [
            {
                "id": a.id,
                "name": f"@{a.username}" if a.username else (a.first_name or f"#{a.id}"),
                "status": a.status.value,
                "premium": a.is_premium,
                "services": [code for acc, code in services if acc == a.id] + (["ai_reply"] if a.id in ai_on else []),
            }
            for a in accounts
        ],
        "payments": [
            {"id": p.id, "amount": float(p.amount), "status": p.status.value, "created_at": _iso(p.created_at)} for p in payments
        ],
        "referral": {"qualified": ref["qualified"], "pending": ref["pending"], "referred_by": _who(referred_by) if referred_by else None},
    }


class MessageIn(BaseModel):
    text: str = Field(min_length=1, max_length=4000)


@router.post("/users/{user_id}/message")
async def message_user(user_id: int, payload: MessageIn, admin: User = Depends(current_admin), db: AsyncSession = Depends(get_db)) -> dict:
    user = await db.get(User, user_id)
    if user is None or not user.telegram_user_id:
        raise HTTPException(404, "Foydalanuvchi topilmadi")
    async with httpx.AsyncClient(timeout=30) as client:
        result, _, error = await send_one(client, user.telegram_user_id, personalize(payload.text, user.first_name), None, None)
    if result != "ok":
        raise HTTPException(400, "Foydalanuvchi botni bloklagan" if result == "blocked" else f"Yuborilmadi: {error}")
    await record_audit(
        db, actor_type=ActorType.ADMIN, actor_id=None, action="user_messaged", entity_type="user", entity_id=user.id,
        meta={"by_telegram_id": admin.telegram_user_id},
    )
    await db.commit()
    return {"ok": True}


# --- Statistika, jurnal, tizim, eksport ---


@router.get("/timeseries")
async def timeseries(days: int = 14, admin: User = Depends(current_admin), db: AsyncSession = Depends(get_db)) -> dict:
    days = max(7, min(days, 60))
    since = datetime.datetime.now(datetime.timezone.utc).date() - datetime.timedelta(days=days - 1)
    day = func.date(func.timezone(settings.default_timezone, User.created_at))
    users = dict((await db.execute(select(day, func.count(User.id)).where(User.created_at >= since).group_by(day))).all())
    tday = func.date(func.timezone(settings.default_timezone, Transaction.created_at))
    revenue = dict(
        (
            await db.execute(
                select(tday, func.sum(Transaction.amount))
                .where(Transaction.type == TransactionType.TOPUP, Transaction.created_at >= since)
                .group_by(tday)
            )
        ).all()
    )
    points = []
    for i in range(days):
        d = since + datetime.timedelta(days=i)
        points.append({"date": d.isoformat(), "users": int(users.get(d, 0)), "revenue": float(revenue.get(d, 0) or 0)})
    return {"points": points}


_ACTION_TITLES = {
    "plan_purchased": "Tarif sotib olindi",
    "payment_confirmed": "To'lov tasdiqlandi",
    "payment_rejected": "To'lov rad etildi",
    "balance_adjusted": "Balans o'zgartirildi",
    "plan_granted": "Tarif sovg'a qilindi",
    "plan_updated": "Tarif o'zgartirildi",
    "plan_created": "Tarif yaratildi",
    "promo_created": "Promokod yaratildi",
    "promo_updated": "Promokod o'zgartirildi",
    "user_banned": "Bloklandi",
    "user_unbanned": "Blokdan chiqarildi",
    "broadcast_started": "Ommaviy xabar",
    "user_messaged": "Shaxsiy xabar",
    "referral_settings_updated": "Referal sozlamalari",
    "referral_qualify": "Referal qo'lda tasdiqlandi",
    "referral_reject": "Referal rad etildi",
    "ai_settings_updated": "AI sozlamalari",
    "payment_settings_updated": "To'lov rekvizitlari",
    "playlist_packs_updated": "Playlist to'plamlari",
}


@router.get("/audit")
async def audit_log(admin: User = Depends(current_admin), db: AsyncSession = Depends(get_db)) -> list[dict]:
    rows = await db.scalars(select(AuditLog).order_by(AuditLog.id.desc()).limit(60))
    return [
        {
            "id": r.id,
            "action": _ACTION_TITLES.get(r.action, r.action),
            "actor": r.actor_type.value,
            "entity": f"{r.entity_type or ''} #{r.entity_id}" if r.entity_id else (r.entity_type or ""),
            "created_at": _iso(r.created_at),
        }
        for r in rows
    ]


@router.get("/system")
async def system_status(admin: User = Depends(current_admin), db: AsyncSession = Depends(get_db)) -> dict:
    day_ago = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(days=1)
    jobs = dict(
        (
            await db.execute(
                select(WorkerJob.status, func.count(WorkerJob.id)).where(WorkerJob.created_at >= day_ago).group_by(WorkerJob.status)
            )
        ).all()
    )
    last_errors = (
        await db.execute(
            select(WorkerJob.payload, WorkerJob.error, WorkerJob.finished_at)
            .where(WorkerJob.status == WorkerJobStatus.FAILED, WorkerJob.created_at >= day_ago)
            .order_by(WorkerJob.id.desc())
            .limit(5)
        )
    ).all()
    return {
        "jobs": {status.value: count for status, count in jobs.items()},
        "errors": [{"task": (p or {}).get("task"), "error": (e or "")[:160], "at": _iso(f)} for p, e, f in last_errors],
        "active_automations": await db.scalar(select(func.count(Automation.id)).where(Automation.status == AutomationStatus.ACTIVE)),
        "error_automations": await db.scalar(select(func.count(Automation.id)).where(Automation.status == AutomationStatus.ERROR)),
        "ai_accounts": await db.scalar(select(func.count(AccountAI.id)).where(AccountAI.enabled == True)),  # noqa: E712
        "pending_payments": await db.scalar(select(func.count(Payment.id)).where(Payment.status == PaymentStatus.PENDING)),
        "webapp_url": await discover_webapp_url(),
    }


@router.get("/export/users.csv")
async def export_users(admin: User = Depends(current_admin), db: AsyncSession = Depends(get_db)) -> Response:
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(["id", "telegram_id", "username", "first_name", "balance", "plan", "plan_expires", "accounts", "banned", "created_at"])
    for user in await db.scalars(select(User).order_by(User.id)):
        ent = await get_entitlement(db, user.id)
        writer.writerow([
            user.id, user.telegram_user_id, user.username or "", user.first_name or "", float(user.balance),
            ent.plan_name, _iso(ent.expires_at) or "", ent.accounts_used, user.is_banned, _iso(user.created_at),
        ])  # fmt: skip
    name = f"users-{datetime.date.today().isoformat()}.csv"
    return Response(
        "﻿" + buffer.getvalue(),  # BOM — Excel UTF-8'ni to'g'ri o'qisin
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{name}"'},
    )


# --- Foydalanuvchi uchun: referal ---

user_router = APIRouter(prefix="/webapp", tags=["webapp-referral"])
internal_router = APIRouter(prefix="/referral", tags=["referral"])


async def _referral_view(db: AsyncSession, user: User) -> dict:
    return await referrals.summary(db, user)


@user_router.get("/referral")
async def my_referral(user: User = Depends(current_user), db: AsyncSession = Depends(get_db)) -> dict:
    return await _referral_view(db, user)


@internal_router.get("/{user_id}")
async def internal_referral(user_id: int, db: AsyncSession = Depends(get_db)) -> dict:
    user = await db.get(User, user_id)
    if user is None:
        raise HTTPException(404, "Foydalanuvchi topilmadi")
    return await _referral_view(db, user)
