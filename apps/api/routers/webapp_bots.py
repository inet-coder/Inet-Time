"""Bot konstruktori (Mini App): foydalanuvchi o'z botini token bilan ulaydi va menyusini quradi.
Botlarni apps/botrunner ishga tushiradi; bu yerda faqat sozlamalar saqlanadi."""

import datetime

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from arq_pool import get_pool
from core import crypto
from core.botapi import BotApiError, get_me, looks_like_token
from core.botbuilder import VARIABLES, MenuError, menu_media, template_menu, templates_public, validate_menu
from core.db.models import BotBroadcast, BotSubscriber, MediaFile, User, UserBot
from core.entitlements import get_entitlement
from core.settings import settings
from core.webapp_auth import InitDataError, create_user_token, validate_init_data
from deps import get_db
from redis_client import get_redis
from routers.webapp import current_user

router = APIRouter(prefix="/webapp/bots", tags=["webapp-bots"])
# Asosiy bot uchun (ichki, X-Internal-Token bilan): foydalanuvchi bot orqali bot yaratadi va boshqaradi.
internal_router = APIRouter(prefix="/userbots", tags=["userbots"])

# botrunner shu kalitni kuzatadi — o'zgarish bo'lsa darhol qayta sinxronlanadi.
SYNC_KEY = "userbots:sync"
MAX_BROADCAST_TEXT = 4096


async def _notify_runner() -> None:
    await get_redis().incr(SYNC_KEY)


async def _owned_bot(db: AsyncSession, user: User, bot_id: int) -> UserBot:
    bot = await db.get(UserBot, bot_id)
    if bot is None or bot.user_id != user.id:
        raise HTTPException(404, "Bot topilmadi")
    return bot


def _short(bot: UserBot, subscribers: int = 0) -> dict:
    return {
        "id": bot.id,
        "username": bot.username,
        "name": bot.name,
        "status": bot.status,
        "error_message": bot.error_message,
        "pages": len((bot.menu or {}).get("pages", [])),
        "subscribers": subscribers,
    }


class BotAuthIn(BaseModel):
    init_data: str
    bot_id: int


@router.post("/auth")
async def bot_auth(payload: BotAuthIn, db: AsyncSession = Depends(get_db)) -> dict:
    """Menyu muharriri foydalanuvchining O'Z botidan (/admin → «Menyu») ochiladi — initData o'sha bot tokeni
    bilan imzolangan. Faqat bot egasi kira oladi."""
    bot = await db.get(UserBot, payload.bot_id)
    if bot is None:
        raise HTTPException(404, "Bot topilmadi")
    try:
        tg_user = validate_init_data(payload.init_data, crypto.decrypt_packed(bot.token_encrypted))
    except InitDataError as exc:
        raise HTTPException(401, "Muharrirni botingizdagi /admin panelidan oching") from exc
    owner = await db.get(User, bot.user_id)
    if owner is None or owner.telegram_user_id != tg_user["id"]:
        raise HTTPException(403, "Bu botni faqat uning egasi sozlay oladi")
    if owner.is_banned:
        raise HTTPException(403, "Hisob bloklangan")
    return {"token": create_user_token(owner.id), "user_id": owner.id, "bot_id": bot.id}


@router.get("")
async def list_bots(user: User = Depends(current_user), db: AsyncSession = Depends(get_db)) -> dict:
    ent = await get_entitlement(db, user.id)
    rows = (
        await db.execute(
            select(UserBot, func.count(BotSubscriber.id))
            .outerjoin(BotSubscriber, (BotSubscriber.bot_id == UserBot.id) & (BotSubscriber.blocked == False))  # noqa: E712
            .where(UserBot.user_id == user.id)
            .group_by(UserBot.id)
            .order_by(UserBot.id)
        )
    ).all()
    return {
        "bots": [_short(bot, count) for bot, count in rows],
        "limit": ent.bot_limit,
        "pages_limit": ent.bot_pages_limit,
        "plan_name": ent.plan_name,
        "templates": templates_public(),
        "variables": VARIABLES,
    }


class ConnectIn(BaseModel):
    token: str = Field(min_length=1, max_length=200)
    template: str = "blank"


@router.post("")
async def connect_bot(payload: ConnectIn, user: User = Depends(current_user), db: AsyncSession = Depends(get_db)) -> dict:
    token = payload.token.strip()
    if not looks_like_token(token):
        raise HTTPException(400, "Bu token emas. @BotFather bergan to'liq tokenni yuboring (123456:ABC... ko'rinishida)")
    if settings.bot_token and token.split(":", 1)[0] == settings.bot_token.split(":", 1)[0]:
        raise HTTPException(400, "Bu platformaning o'z boti — o'zingiz yaratgan botni ulang")
    try:
        me = await get_me(token)
    except BotApiError as exc:
        if exc.token_revoked:
            raise HTTPException(400, "Token noto'g'ri yoki bekor qilingan. @BotFather'dan yangisini oling") from exc
        raise HTTPException(502, "Telegram bilan bog'lanib bo'lmadi, qayta urinib ko'ring") from exc

    existing = await db.scalar(select(UserBot).where(UserBot.bot_telegram_id == me["id"]))
    if existing is not None and existing.user_id != user.id:
        raise HTTPException(409, "Bu bot boshqa foydalanuvchiga ulangan")

    if existing is None:
        ent = await get_entitlement(db, user.id)
        used = await db.scalar(select(func.count(UserBot.id)).where(UserBot.user_id == user.id))
        if used >= ent.bot_limit:
            if ent.bot_limit == 0:
                raise HTTPException(402, f"Bot konstruktori {ent.plan_name} tarifida yo'q — tarifni yangilang")
            raise HTTPException(402, f"{ent.plan_name} tarifida ko'pi bilan {ent.bot_limit} ta bot — tarifni yangilang")
        bot = UserBot(user_id=user.id, bot_telegram_id=me["id"], menu=template_menu(payload.template))
        db.add(bot)
    else:
        bot = existing  # token yangilandi (BotFather'da almashtirilgan) — menyu saqlanadi
    bot.username = me.get("username") or ""
    bot.name = me.get("first_name") or bot.username
    bot.token_encrypted = crypto.encrypt_packed(token)
    bot.status = "active"
    bot.error_message = None
    await db.commit()
    await _notify_runner()
    return await bot_detail(bot.id, user, db)


@router.get("/{bot_id}")
async def bot_detail(bot_id: int, user: User = Depends(current_user), db: AsyncSession = Depends(get_db)) -> dict:
    bot = await _owned_bot(db, user, bot_id)
    now = datetime.datetime.now(datetime.timezone.utc)
    base = select(func.count(BotSubscriber.id)).where(BotSubscriber.bot_id == bot.id)
    total = await db.scalar(base.where(BotSubscriber.blocked == False))  # noqa: E712
    active = await db.scalar(base.where(BotSubscriber.last_active_at >= now - datetime.timedelta(days=1)))
    new_week = await db.scalar(base.where(BotSubscriber.started_at >= now - datetime.timedelta(days=7)))
    blocked = await db.scalar(base.where(BotSubscriber.blocked == True))  # noqa: E712
    last = await db.scalar(select(BotBroadcast).where(BotBroadcast.bot_id == bot.id).order_by(BotBroadcast.id.desc()).limit(1))
    ent = await get_entitlement(db, user.id)
    return {
        **_short(bot, total),
        "menu": bot.menu,
        "pages_limit": ent.bot_pages_limit,
        "stats": {"subscribers": total, "active_24h": active, "new_7d": new_week, "blocked": blocked},
        "last_broadcast": (
            {"id": last.id, "status": last.status, "total": last.total, "sent": last.sent, "failed": last.failed}
            if last
            else None
        ),
    }


class MenuIn(BaseModel):
    menu: dict


@router.put("/{bot_id}/menu")
async def save_menu(bot_id: int, payload: MenuIn, user: User = Depends(current_user), db: AsyncSession = Depends(get_db)) -> dict:
    bot = await _owned_bot(db, user, bot_id)
    ent = await get_entitlement(db, user.id)
    try:
        media_ids = menu_media(payload.menu)
    except (TypeError, ValueError, AttributeError):
        media_ids = set()
    owned = set(
        await db.scalars(select(MediaFile.id).where(MediaFile.id.in_(media_ids or {0}), MediaFile.user_id == user.id))
    )
    # Admin limitni kamaytirgan bo'lsa ham, avval saqlangan sahifalarni tahrirlash mumkin (faqat ko'paytirib bo'lmaydi).
    limit = max(ent.bot_pages_limit, len((bot.menu or {}).get("pages", [])))
    try:
        menu = validate_menu(payload.menu, limit, owned)
    except MenuError as exc:
        raise HTTPException(400, str(exc)) from exc
    bot.menu = menu
    await db.commit()
    await _notify_runner()
    return {"ok": True, "menu": menu}


class StatusIn(BaseModel):
    active: bool


@router.post("/{bot_id}/status")
async def set_status(bot_id: int, payload: StatusIn, user: User = Depends(current_user), db: AsyncSession = Depends(get_db)) -> dict:
    bot = await _owned_bot(db, user, bot_id)
    bot.status = "active" if payload.active else "paused"
    bot.error_message = None
    await db.commit()
    await _notify_runner()
    return _short(bot)


@router.delete("/{bot_id}")
async def delete_bot(bot_id: int, user: User = Depends(current_user), db: AsyncSession = Depends(get_db)) -> dict:
    bot = await _owned_bot(db, user, bot_id)
    await db.delete(bot)
    await db.commit()
    await _notify_runner()
    return {"ok": True}


class BroadcastIn(BaseModel):
    text: str = Field(min_length=1, max_length=MAX_BROADCAST_TEXT)
    media_id: int | None = None


@router.post("/{bot_id}/broadcast")
async def broadcast(bot_id: int, payload: BroadcastIn, user: User = Depends(current_user), db: AsyncSession = Depends(get_db)) -> dict:
    bot = await _owned_bot(db, user, bot_id)
    if bot.status != "active":
        raise HTTPException(400, "Avval botni yoqing")
    if payload.media_id is not None:
        media = await db.get(MediaFile, payload.media_id)
        if media is None or media.user_id != user.id:
            raise HTTPException(404, "Rasm topilmadi")
        if len(payload.text) > 1024:
            raise HTTPException(400, "Rasmli xabar matni 1024 belgidan oshmasin")
    running = await db.scalar(select(BotBroadcast.id).where(BotBroadcast.bot_id == bot.id, BotBroadcast.status == "sending"))
    if running:
        raise HTTPException(409, "Oldingi xabar hali yuborilmoqda")
    item = BotBroadcast(bot_id=bot.id, text=payload.text.strip(), media_id=payload.media_id)
    db.add(item)
    await db.commit()
    pool = await get_pool()
    await pool.enqueue_job("user_bot_broadcast_job", broadcast_id=item.id, _job_id=f"userbot_broadcast:{item.id}")
    return {"id": item.id, "status": item.status}


# --- Asosiy bot uchun ichki endpointlar (foydalanuvchi user_id bilan) ---


async def _user(db: AsyncSession, user_id: int) -> User:
    user = await db.get(User, user_id)
    if user is None:
        raise HTTPException(404, "Foydalanuvchi topilmadi")
    return user


@internal_router.get("/templates")
async def internal_templates() -> list[dict]:
    return templates_public()


@internal_router.get("/{user_id}")
async def internal_list(user_id: int, db: AsyncSession = Depends(get_db)) -> dict:
    return await list_bots(await _user(db, user_id), db)


@internal_router.post("/{user_id}")
async def internal_connect(user_id: int, payload: ConnectIn, db: AsyncSession = Depends(get_db)) -> dict:
    return await connect_bot(payload, await _user(db, user_id), db)


@internal_router.get("/{user_id}/{bot_id}")
async def internal_detail(user_id: int, bot_id: int, db: AsyncSession = Depends(get_db)) -> dict:
    return await bot_detail(bot_id, await _user(db, user_id), db)


@internal_router.post("/{user_id}/{bot_id}/status")
async def internal_status(user_id: int, bot_id: int, payload: StatusIn, db: AsyncSession = Depends(get_db)) -> dict:
    return await set_status(bot_id, payload, await _user(db, user_id), db)


@internal_router.delete("/{user_id}/{bot_id}")
async def internal_delete(user_id: int, bot_id: int, db: AsyncSession = Depends(get_db)) -> dict:
    return await delete_bot(bot_id, await _user(db, user_id), db)
