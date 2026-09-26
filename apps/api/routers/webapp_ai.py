"""AI avto-javob sozlamalari, AI bilan matn yozish va Stories — Mini App (/webapp/...) va bot (ichki /ai/...) uchun."""

import base64

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core import ai, crypto
from core.db.models import AccountAI, EncryptedSession, TelegramAccount, User
from core.entitlements import get_entitlement
from core.telegram.stories import StoryError, list_stories
from deps import get_db
from jobs import enqueue
from redis_client import get_redis
from routers.webapp import _owned_account, current_user

router = APIRouter(prefix="/webapp", tags=["webapp-ai"])
internal_router = APIRouter(prefix="/ai", tags=["ai"])


# --- Umumiy mantiq (Mini App va bot) ---


async def _require_flag(db: AsyncSession, user: User, flag: str, title: str) -> dict:
    ent = await get_entitlement(db, user.id)
    if not ent.flags.get(flag):
        raise HTTPException(402, f"{title} {ent.plan_name} tarifida yo'q — tarifni yangilang")
    return ent.flags


async def _ai_row(db: AsyncSession, account_id: int) -> AccountAI | None:
    return await db.scalar(select(AccountAI).where(AccountAI.telegram_account_id == account_id))


async def ai_state(db: AsyncSession, user: User, account: TelegramAccount) -> dict:
    ent = await get_entitlement(db, user.id)
    config = await ai.get_config(db)
    row = await _ai_row(db, account.id)
    return {
        "available": config["configured"] and config["enabled"],
        "unlocked": bool(ent.flags.get("ai_service")),
        "daily_limit": int(ent.flags.get("ai_daily_limit", 0)),
        "used_today": await ai.used_today(get_redis(), user.id),
        "presets": [{"code": code, "title": meta["title"], "desc": meta["desc"]} for code, meta in ai.PRESETS.items()],
        "max_style_len": ai.MAX_STYLE_LEN,
        "settings": {
            "enabled": bool(row and row.enabled),
            "preset": row.preset if row else ai.DEFAULT_PRESET,
            "style": (row.style if row else None) or "",
            "only_when_away": row.only_when_away if row else True,
            "signature": row.signature if row else True,
        },
    }


class AISettingsIn(BaseModel):
    enabled: bool
    preset: str = ai.DEFAULT_PRESET
    style: str = Field("", max_length=ai.MAX_STYLE_LEN)
    only_when_away: bool = True
    signature: bool = True


async def save_ai(db: AsyncSession, user: User, account: TelegramAccount, payload: AISettingsIn) -> dict:
    if payload.preset not in ai.PRESETS and payload.preset != "custom":
        raise HTTPException(400, "Noma'lum uslub")
    if payload.preset == "custom" and not payload.style.strip():
        raise HTTPException(400, "O'z uslubingizni yozing")
    if payload.enabled:
        await _require_flag(db, user, "ai_service", "AI avto-javob")
        await ai.ensure_available(db)
    row = await _ai_row(db, account.id)
    if row is None:
        row = AccountAI(telegram_account_id=account.id)
        db.add(row)
    row.enabled = payload.enabled
    row.preset = payload.preset
    row.style = payload.style.strip() or None
    row.only_when_away = payload.only_when_away
    row.signature = payload.signature
    await db.commit()
    return await ai_state(db, user, account)


async def _session_string(db: AsyncSession, account: TelegramAccount) -> str:
    row = await db.scalar(select(EncryptedSession).where(EncryptedSession.telegram_account_id == account.id))
    if row is None or row.revoked_at is not None:
        raise HTTPException(400, "Akkaunt sessiyasi yo'q — qayta ulang")
    return crypto.decrypt(row.ciphertext, row.nonce, row.key_version)


async def enqueue_stories(db: AsyncSession, user: User, account: TelegramAccount, username: str, story_ids: list[int] | None) -> None:
    await _require_flag(db, user, "stories_service", "Stories")
    if not user.telegram_user_id:
        raise HTTPException(400, "Telegram chat topilmadi")
    await enqueue(
        db, task_name="send_stories_job", telegram_account_id=account.id, automation_id=None,
        task_kwargs={"account_id": account.id, "username": username.strip().lstrip("@"),
                     "chat_id": user.telegram_user_id, "story_ids": story_ids},
    )


# --- Mini App ---


@router.get("/ai")
async def get_ai(account_id: int, user: User = Depends(current_user), db: AsyncSession = Depends(get_db)) -> dict:
    return await ai_state(db, user, await _owned_account(db, user, account_id))


@router.put("/ai")
async def put_ai(account_id: int, payload: AISettingsIn, user: User = Depends(current_user), db: AsyncSession = Depends(get_db)) -> dict:
    try:
        return await save_ai(db, user, await _owned_account(db, user, account_id), payload)
    except ai.AIError as exc:
        raise HTTPException(503, str(exc)) from exc


class SuggestIn(BaseModel):
    field: str = Field(pattern="^(bio|name|playlist|schedule)$")
    topic: str = Field("", max_length=200)


@router.post("/ai/suggest")
async def suggest(payload: SuggestIn, user: User = Depends(current_user), db: AsyncSession = Depends(get_db)) -> dict:
    """Studiyada «✨ AI bilan yozish»: 5 ta variant. Kunlik limitdan 1 ta so'rov yechiladi."""
    flags = await _require_flag(db, user, "ai_service", "AI yozish")
    redis = get_redis()
    try:
        config = await ai.ensure_available(db)
        if not await ai.take_quota(redis, user.id, int(flags.get("ai_daily_limit", 0))):
            raise HTTPException(429, "Bugungi AI limiti tugadi — ertaga yana urinib ko'ring")
        try:
            items, result = await ai.suggest(config["model"], payload.field, payload.topic)
        except ai.AIError:
            await ai.refund_quota(redis, user.id)
            raise
    except ai.AIError as exc:
        raise HTTPException(503, str(exc)) from exc
    await ai.log_usage(db, user.id, "suggest", result)
    return {"items": items, "used_today": await ai.used_today(redis, user.id)}


class StoriesIn(BaseModel):
    account_id: int
    username: str = Field(min_length=1, max_length=64)


@router.post("/stories/list")
async def stories_list(payload: StoriesIn, user: User = Depends(current_user), db: AsyncSession = Depends(get_db)) -> dict:
    await _require_flag(db, user, "stories_service", "Stories")
    account = await _owned_account(db, user, payload.account_id)
    session_string = await _session_string(db, account)
    try:
        peer, infos = await list_stories(session_string, payload.username)
    except StoryError as exc:
        raise HTTPException(400, str(exc)) from exc
    return {
        "peer": {"name": peer.name, "username": peer.username},
        "items": [
            {
                "id": i.id,
                "date": i.date,
                "expire_date": i.expire_date,
                "kind": i.kind,
                "protected": i.protected,
                "caption": i.caption,
                "thumb": f"data:image/jpeg;base64,{base64.b64encode(i.thumb).decode()}" if i.thumb else None,
            }
            for i in infos
        ],
    }


class StoriesSendIn(StoriesIn):
    story_ids: list[int] | None = None


@router.post("/stories/send")
async def stories_send(payload: StoriesSendIn, user: User = Depends(current_user), db: AsyncSession = Depends(get_db)) -> dict:
    account = await _owned_account(db, user, payload.account_id)
    await enqueue_stories(db, user, account, payload.username, payload.story_ids)
    return {"ok": True}


# --- Bot uchun (ichki API) ---


async def _internal_account(db: AsyncSession, user_id: int, account_id: int) -> tuple[User, TelegramAccount]:
    user = await db.get(User, user_id)
    if user is None:
        raise HTTPException(404, "Foydalanuvchi topilmadi")
    return user, await _owned_account(db, user, account_id)


@internal_router.get("/{user_id}/{account_id}")
async def internal_get_ai(user_id: int, account_id: int, db: AsyncSession = Depends(get_db)) -> dict:
    user, account = await _internal_account(db, user_id, account_id)
    return await ai_state(db, user, account)


@internal_router.put("/{user_id}/{account_id}")
async def internal_put_ai(user_id: int, account_id: int, payload: AISettingsIn, db: AsyncSession = Depends(get_db)) -> dict:
    user, account = await _internal_account(db, user_id, account_id)
    try:
        return await save_ai(db, user, account, payload)
    except ai.AIError as exc:
        raise HTTPException(409, str(exc)) from exc


class InternalStoriesIn(BaseModel):
    username: str = Field(min_length=1, max_length=64)


@internal_router.post("/{user_id}/{account_id}/stories")
async def internal_stories(user_id: int, account_id: int, payload: InternalStoriesIn, db: AsyncSession = Depends(get_db)) -> dict:
    user, account = await _internal_account(db, user_id, account_id)
    await enqueue_stories(db, user, account, payload.username, None)
    return {"ok": True}
