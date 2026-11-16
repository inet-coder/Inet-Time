"""Kodsiz Web App konstruktori.

Konstruktor (bot egasi, Mini App tokeni bilan):  /webapp/bots/{bot_id}/app...
Ilovaning o'zi (ommaviy, Telegram ichida ochiladi): /webapp/apps/{app_id}...
    — e'lon qilingan nusxani o'qish va rasmlar: autentifikatsiyasiz;
    — forma/buyurtma yuborish: Telegram initData (shu botning tokeni bilan imzolangan) talab qilinadi."""

import datetime
import json
import logging

import httpx
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
from pydantic import BaseModel, Field
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from core import crypto
from core.botapi import BotApiError, call
from core.botbuilder import OWNER_START_HINT
from core.db.models import MediaFile, User, UserBot, WebApp, WebAppSubmission
from core.entitlements import get_entitlement
from core.webapp_auth import InitDataError, validate_init_data
from core.webapp_builder import (
    BLOCK_TYPES,
    MAX_BLOCKS,
    MAX_PAGES,
    THEME_PRESETS,
    WebAppError,
    clean_values,
    compute_order,
    find_block,
    money,
    referenced_media,
    validate_app,
)
from core.webapp_templates import template_doc, templates_public
from core.webapp_url import discover_webapp_url
from deps import get_db
from redis_client import get_redis
from routers.webapp import _bot_username, current_user
from routers.webapp_bots import SYNC_KEY, _owned_bot

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/webapp", tags=["webapp-apps"])

SUBMIT_LIMIT_PER_MINUTE = 6
FEEDBACK_TTL = 30 * 24 * 3600  # botrunner: ub:{bot}:fb:{msg} — egasi «Reply» qilsa javob mijozga boradi


async def app_url(app_id: int) -> str | None:
    base = await discover_webapp_url()
    return f"{base.split('?')[0].rstrip('/')}/app/{app_id}" if base else None


async def _app_for(db: AsyncSession, bot: UserBot) -> WebApp | None:
    return await db.scalar(select(WebApp).where(WebApp.bot_id == bot.id))


async def _detail(app: WebApp) -> dict:
    return {
        "id": app.id,
        "draft": app.draft,
        "published": app.published is not None,
        "published_at": app.published_at.isoformat() if app.published_at else None,
        "has_changes": app.published != app.draft,
        "menu_button": app.menu_button,
        "menu_button_text": app.menu_button_text,
        "url": await app_url(app.id),
    }


def _meta() -> dict:
    return {
        "templates": templates_public(),
        "themes": THEME_PRESETS,
        "block_types": BLOCK_TYPES,
        "limits": {"pages": MAX_PAGES, "blocks": MAX_BLOCKS},
    }


async def _owned_media(db: AsyncSession, user: User, doc: dict) -> set[int]:
    ids = referenced_media(doc)
    if not ids:
        return set()
    return set(await db.scalars(select(MediaFile.id).where(MediaFile.id.in_(ids), MediaFile.user_id == user.id)))


async def _notify_runner() -> None:
    await get_redis().incr(SYNC_KEY)


# --- Konstruktor ---


@router.get("/bots/{bot_id}/app")
async def get_app(bot_id: int, user: User = Depends(current_user), db: AsyncSession = Depends(get_db)) -> dict:
    bot = await _owned_bot(db, user, bot_id)
    app = await _app_for(db, bot)
    return {"app": await _detail(app) if app else None, "bot_username": bot.username, **_meta()}


class CreateIn(BaseModel):
    template: str = "blank"


@router.post("/bots/{bot_id}/app")
async def create_app(bot_id: int, payload: CreateIn, user: User = Depends(current_user), db: AsyncSession = Depends(get_db)) -> dict:
    """Ilova yo'q bo'lsa — yaratadi; bo'lsa — qoralamani shablon bilan almashtiradi (e'lon qilingan nusxa saqlanadi)."""
    bot = await _owned_bot(db, user, bot_id)
    doc = template_doc(payload.template)
    if not doc["settings"].get("title"):
        doc["settings"]["title"] = bot.name
    app = await _app_for(db, bot)
    if app is None:
        app = WebApp(bot_id=bot.id, draft=doc, menu_button=True, menu_button_text="Ochish")
        db.add(app)
    else:
        app.draft = doc
    await db.commit()
    return {"app": await _detail(app), "bot_username": bot.username, **_meta()}


class DraftIn(BaseModel):
    doc: dict


async def _require_app(db: AsyncSession, user: User, bot_id: int) -> tuple[UserBot, WebApp]:
    bot = await _owned_bot(db, user, bot_id)
    app = await _app_for(db, bot)
    if app is None:
        raise HTTPException(404, "Ilova hali yaratilmagan")
    return bot, app


@router.put("/bots/{bot_id}/app/draft")
async def save_draft(bot_id: int, payload: DraftIn, user: User = Depends(current_user), db: AsyncSession = Depends(get_db)) -> dict:
    _, app = await _require_app(db, user, bot_id)
    try:
        doc = validate_app(payload.doc, await _owned_media(db, user, payload.doc))
    except WebAppError as exc:
        raise HTTPException(400, str(exc)) from exc
    app.draft = doc
    await db.commit()
    return await _detail(app)


@router.post("/bots/{bot_id}/app/publish")
async def publish(bot_id: int, user: User = Depends(current_user), db: AsyncSession = Depends(get_db)) -> dict:
    _, app = await _require_app(db, user, bot_id)
    try:
        doc = validate_app(app.draft, await _owned_media(db, user, app.draft))
    except WebAppError as exc:
        raise HTTPException(400, str(exc)) from exc
    app.draft = doc
    app.published = doc
    app.published_at = datetime.datetime.now(datetime.timezone.utc)
    await db.commit()
    await _notify_runner()
    return await _detail(app)


@router.post("/bots/{bot_id}/app/unpublish")
async def unpublish(bot_id: int, user: User = Depends(current_user), db: AsyncSession = Depends(get_db)) -> dict:
    _, app = await _require_app(db, user, bot_id)
    app.published = None
    app.published_at = None
    await db.commit()
    await _notify_runner()
    return await _detail(app)


class AppSettingsIn(BaseModel):
    menu_button: bool
    menu_button_text: str = Field(min_length=1, max_length=32)


@router.put("/bots/{bot_id}/app/settings")
async def save_settings(bot_id: int, payload: AppSettingsIn, user: User = Depends(current_user), db: AsyncSession = Depends(get_db)) -> dict:
    _, app = await _require_app(db, user, bot_id)
    app.menu_button = payload.menu_button
    app.menu_button_text = payload.menu_button_text.strip()
    await db.commit()
    await _notify_runner()
    return await _detail(app)


def _submission_out(s: WebAppSubmission) -> dict:
    return {
        "id": s.id,
        "kind": s.kind,
        "title": s.title,
        "data": s.data,
        "total": float(s.total) if s.total is not None else None,
        "status": s.status,
        "user": {"id": s.tg_user_id, "name": s.tg_name, "username": s.tg_username},
        "created_at": s.created_at.isoformat() if s.created_at else None,
    }


@router.get("/bots/{bot_id}/app/submissions")
async def submissions(bot_id: int, status: str | None = None, user: User = Depends(current_user), db: AsyncSession = Depends(get_db)) -> dict:
    _, app = await _require_app(db, user, bot_id)
    query = select(WebAppSubmission).where(WebAppSubmission.app_id == app.id)
    if status in ("new", "done"):
        query = query.where(WebAppSubmission.status == status)
    rows = list(await db.scalars(query.order_by(WebAppSubmission.id.desc()).limit(100)))
    return {"items": [_submission_out(s) for s in rows]}


class SubmissionStatusIn(BaseModel):
    status: str = Field(pattern="^(new|done)$")


@router.post("/bots/{bot_id}/app/submissions/{submission_id}/status")
async def submission_status(
    bot_id: int, submission_id: int, payload: SubmissionStatusIn, user: User = Depends(current_user), db: AsyncSession = Depends(get_db)
) -> dict:
    _, app = await _require_app(db, user, bot_id)
    await db.execute(
        update(WebAppSubmission).where(WebAppSubmission.id == submission_id, WebAppSubmission.app_id == app.id).values(status=payload.status)
    )
    await db.commit()
    return {"ok": True}


# --- Ilovaning o'zi (ommaviy) ---


async def _public_app(db: AsyncSession, app_id: int) -> tuple[WebApp, UserBot]:
    app = await db.get(WebApp, app_id)
    if app is None or app.published is None:
        raise HTTPException(404, "Ilova topilmadi yoki hali e'lon qilinmagan")
    bot = await db.get(UserBot, app.bot_id)
    if bot is None or bot.status != "active":
        raise HTTPException(404, "Ilova vaqtincha ishlamayapti")
    return app, bot


@router.get("/apps/{app_id}")
async def public_app(app_id: int, db: AsyncSession = Depends(get_db)) -> Response:
    app, bot = await _public_app(db, app_id)
    ent = await get_entitlement(db, bot.user_id)
    branding = None
    if not ent.flags.get("bot_no_branding"):
        platform = await _bot_username()
        branding = f"@{platform}" if platform else None
    body = json.dumps({"id": app.id, "doc": app.published, "bot_username": bot.username, "branding": branding}, ensure_ascii=False)
    # E'lon qilingan zahoti yangisi ko'rinsin
    return Response(body, media_type="application/json", headers={"Cache-Control": "no-cache"})


@router.get("/apps/{app_id}/media/{media_id}")
async def public_media(app_id: int, media_id: int, db: AsyncSession = Depends(get_db)) -> Response:
    app, _ = await _public_app(db, app_id)
    # Faqat e'lon qilingan ilovada ishlatilgan rasmlar ochiq — egasining boshqa rasmlari emas.
    if media_id not in referenced_media(app.published):
        raise HTTPException(404, "Rasm topilmadi")
    media = await db.get(MediaFile, media_id)
    if media is None:
        raise HTTPException(404, "Rasm topilmadi")
    return Response(media.data, media_type=media.mime, headers={"Cache-Control": "public, max-age=604800"})


class OrderItem(BaseModel):
    id: str = Field(max_length=32)
    qty: int = Field(ge=1, le=999)


class SubmitIn(BaseModel):
    init_data: str = Field(max_length=4096)
    kind: str = Field(pattern="^(form|order)$")
    block_id: str | None = Field(default=None, max_length=32)
    values: dict = Field(default_factory=dict)
    items: list[OrderItem] = Field(default_factory=list, max_length=100)


@router.post("/apps/{app_id}/submit")
async def submit(app_id: int, payload: SubmitIn, db: AsyncSession = Depends(get_db)) -> dict:
    app, bot = await _public_app(db, app_id)
    token = crypto.decrypt_packed(bot.token_encrypted)
    try:
        tg_user = validate_init_data(payload.init_data, token)
    except InitDataError as exc:
        raise HTTPException(401, "Ilovani Telegram ichida, bot orqali oching") from exc

    redis = get_redis()
    rl_key = f"wa:rl:{app.id}:{tg_user['id']}"
    count = await redis.incr(rl_key)
    if count == 1:
        await redis.expire(rl_key, 60)
    if count > SUBMIT_LIMIT_PER_MINUTE:
        raise HTTPException(429, "Juda ko'p urinish — bir daqiqadan keyin qayta yuboring")

    doc = app.published
    settings_ = doc.get("settings", {})
    currency = settings_.get("currency", "")
    total = None
    try:
        if payload.kind == "order":
            lines, total = compute_order(doc, [i.model_dump() for i in payload.items])
            values = clean_values(settings_.get("checkout_fields", []), payload.values)
            title = "Buyurtma"
            data = {"items": lines, "fields": values}
            success = settings_.get("checkout_success") or "✅ Buyurtmangiz qabul qilindi!"
        else:
            block = find_block(doc, payload.block_id or "")
            if block is None or block.get("type") != "form":
                raise WebAppError("Forma topilmadi — ilovani qayta oching")
            values = clean_values(block["fields"], payload.values)
            title = (block.get("title") or "Ariza")[:128]
            data = {"fields": values}
            success = block.get("success_text") or "✅ Yuborildi!"
    except WebAppError as exc:
        raise HTTPException(400, str(exc)) from exc

    name = " ".join(x for x in (tg_user.get("first_name"), tg_user.get("last_name")) if x)[:128] or None
    item = WebAppSubmission(
        app_id=app.id, tg_user_id=tg_user["id"], tg_name=name, tg_username=(tg_user.get("username") or None),
        kind=payload.kind, title=title, data=data, total=total,
    )
    db.add(item)
    await db.commit()

    await _notify(db, bot, app, item, currency)
    return {"ok": True, "id": item.id, "message": success}


def _owner_text(app: WebApp, item: WebAppSubmission, currency: str) -> str:
    app_title = (app.published or {}).get("settings", {}).get("title") or "Web App"
    head = f"🛒 Yangi buyurtma #{item.id}" if item.kind == "order" else f"📝 Yangi ariza #{item.id} · {item.title}"
    who = item.tg_name or "Foydalanuvchi"
    if item.tg_username:
        who += f" (@{item.tg_username})"
    lines = [f"{head}\n🌐 {app_title}", f"👤 {who} · 🆔 {item.tg_user_id}", ""]
    for line in item.data.get("items", []):
        lines.append(f"• {line['title']} × {line['qty']} = {money(line['sum'], currency)}")
    if item.total is not None:
        lines += [f"💰 Jami: {money(int(item.total), currency)}", ""]
    for label, value in item.data.get("fields", {}).items():
        lines.append(f"▫️ {label}: {value}")
    lines += ["", "↩️ Javob berish uchun shu xabarga «Reply» qiling."]
    return "\n".join(lines)[:4000]


async def _notify(db: AsyncSession, bot: UserBot, app: WebApp, item: WebAppSubmission, currency: str) -> None:
    """Egasiga — o'z botida (Reply bilan javob berish mumkin), mijozga — tasdiq. Ikkalasi ham best-effort."""
    token = crypto.decrypt_packed(bot.token_encrypted)
    owner = await db.get(User, bot.user_id)
    async with httpx.AsyncClient(timeout=15) as client:
        if owner and owner.telegram_user_id:
            try:
                sent = await call(client, token, "sendMessage", {"chat_id": owner.telegram_user_id, "text": _owner_text(app, item, currency)})
                await get_redis().set(f"ub:{bot.id}:fb:{sent['message_id']}", item.tg_user_id, ex=FEEDBACK_TTL)
            except BotApiError as exc:
                logger.info("web app: egasiga yetkazilmadi (bot %s): %s", bot.id, exc.description)
                if not bot.error_message:
                    bot.error_message = OWNER_START_HINT
                    await db.commit()
        if item.tg_user_id != (owner.telegram_user_id if owner else None):
            summary = f"#{item.id} qabul qilindi."
            if item.total is not None:
                summary = f"Buyurtma #{item.id} · {money(int(item.total), currency)}"
            try:
                await call(client, token, "sendMessage", {"chat_id": item.tg_user_id, "text": f"✅ {summary}\nJavob shu chatga keladi."})
            except BotApiError:
                pass
