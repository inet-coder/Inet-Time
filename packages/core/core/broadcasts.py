"""Admin ommaviy xabarlari: auditoriya (segment), HTML matn, rasm, inline tugmalar va Bot API orqali yuborish.

Telegram cheklovi ~30 xabar/soniya — biz ~20/s yuboramiz, 429 bo'lsa retry_after kutamiz."""

import asyncio
import datetime
import html
import json
import logging

import httpx
from sqlalchemy import exists, select
from sqlalchemy.ext.asyncio import AsyncSession

from core.db.enums import SubscriptionStatus, TelegramAccountStatus
from core.db.models import Plan, Subscription, TelegramAccount, User
from core.settings import settings

logger = logging.getLogger(__name__)

SEND_DELAY = 0.05
MAX_BUTTONS = 6

# Admin paneldagi tayyor uslublar (matn namunasi). {first_name} — har odamga o'z ismi.
STYLES = [
    {"code": "announce", "title": "📢 E'lon", "text": "📢 <b>Muhim e'lon</b>\n\nAssalomu alaykum, {first_name}!\n\n"},
    {"code": "promo", "title": "🎁 Aksiya", "text": "🎁 <b>Maxsus taklif!</b>\n\n{first_name}, faqat siz uchun — Pro tarifga chegirma.\nPromokodni nusxalang va to'lov oynasiga kiriting 👇"},
    {"code": "news", "title": "🆕 Yangilik", "text": "🆕 <b>Yangi imkoniyat</b>\n\nEndi botda: \n\nSinab ko'ring 👇"},
    {"code": "warning", "title": "⚠️ Ogohlantirish", "text": "⚠️ <b>Diqqat</b>\n\n"},
    {"code": "thanks", "title": "💙 Minnatdorchilik", "text": "💙 {first_name}, biz bilan ekaningiz uchun rahmat!\n\n"},
]

SEGMENTS = [
    {"code": "all", "title": "Hammaga"},
    {"code": "paid", "title": "Pullik tarifdagilar"},
    {"code": "free", "title": "Bepul tarifdagilar"},
    {"code": "with_account", "title": "Akkaunt ulaganlar"},
    {"code": "no_account", "title": "Akkaunt ulamaganlar"},
    {"code": "plan", "title": "Tarif bo'yicha"},
    {"code": "admins", "title": "Faqat adminlar (sinov)"},
]


def _active_sub(plan_code: str | None = None):
    now = datetime.datetime.now(datetime.timezone.utc)
    query = (
        select(Subscription.id)
        .join(Plan, Plan.id == Subscription.plan_id)
        .where(Subscription.user_id == User.id, Subscription.status == SubscriptionStatus.ACTIVE, Subscription.expires_at > now)
    )
    if plan_code:
        query = query.where(Plan.code == plan_code)
    else:
        query = query.where(Plan.code != "free")
    return exists(query)


def _has_account():
    return exists(
        select(TelegramAccount.id).where(
            TelegramAccount.user_id == User.id, TelegramAccount.status != TelegramAccountStatus.REVOKED
        )
    )


def segment_query(segment: dict):
    query = select(User.telegram_user_id, User.first_name).where(User.is_banned == False, User.telegram_user_id.is_not(None))  # noqa: E712
    code = segment.get("code", "all")
    if code == "paid":
        query = query.where(_active_sub())
    elif code == "free":
        query = query.where(~_active_sub())
    elif code == "plan":
        query = query.where(_active_sub(segment.get("plan_code") or ""))
    elif code == "with_account":
        query = query.where(_has_account())
    elif code == "no_account":
        query = query.where(~_has_account())
    elif code == "admins":
        query = query.where(User.telegram_user_id.in_(settings.admin_telegram_id_set or {0}))
    return query.order_by(User.id)


async def recipients(db: AsyncSession, segment: dict) -> list[tuple[int, str | None]]:
    return [(row.telegram_user_id, row.first_name) for row in (await db.execute(segment_query(segment))).all()]


def personalize(text: str, first_name: str | None) -> str:
    return text.replace("{first_name}", html.escape(first_name or "do'stim"))


def reply_markup(buttons: list[dict], webapp_url: str | None) -> dict | None:
    rows = []
    for b in buttons[:MAX_BUTTONS]:
        text = (b.get("text") or "").strip()[:64]
        value = (b.get("value") or "").strip()
        kind = b.get("type")
        if not text:
            continue
        if kind == "url" and value.startswith(("https://", "http://", "tg://")):
            rows.append([{"text": text, "url": value}])
        elif kind == "webapp" and webapp_url:
            rows.append([{"text": text, "web_app": {"url": webapp_url}}])
        elif kind == "copy" and value:
            rows.append([{"text": text, "copy_text": {"text": value[:256]}}])
        elif kind in ("plans", "home", "ref"):
            rows.append([{"text": text, "callback_data": {"plans": "plans", "home": "home", "ref": "ref"}[kind]}])
    return {"inline_keyboard": rows} if rows else None


class SendResult:
    OK, BLOCKED, FAILED = "ok", "blocked", "failed"


async def send_one(
    client: httpx.AsyncClient, chat_id: int, text: str, markup: dict | None, photo: bytes | str | None
) -> tuple[str, str | None, str | None]:
    """(natija, rasm file_id — keyingi yuborishlar uchun, xato matni)."""
    base = f"https://api.telegram.org/bot{settings.bot_token}"
    for _ in range(3):
        if photo is None:
            payload = {"chat_id": chat_id, "text": text, "parse_mode": "HTML", "link_preview_options": {"is_disabled": True}}
            if markup:
                payload["reply_markup"] = markup
            resp = await client.post(f"{base}/sendMessage", json=payload)
        elif isinstance(photo, str):
            payload = {"chat_id": chat_id, "photo": photo, "caption": text, "parse_mode": "HTML"}
            if markup:
                payload["reply_markup"] = markup
            resp = await client.post(f"{base}/sendPhoto", json=payload)
        else:
            data = {"chat_id": str(chat_id), "caption": text, "parse_mode": "HTML"}
            if markup:
                data["reply_markup"] = json.dumps(markup)
            resp = await client.post(f"{base}/sendPhoto", data=data, files={"photo": ("image.jpg", photo)})
        body = resp.json() if resp.headers.get("content-type", "").startswith("application/json") else {}
        if resp.status_code == 200 and body.get("ok"):
            file_id = None
            photos = (body.get("result") or {}).get("photo")
            if photos:
                file_id = photos[-1]["file_id"]
            return SendResult.OK, file_id, None
        if resp.status_code == 429:
            await asyncio.sleep(int((body.get("parameters") or {}).get("retry_after", 3)) + 1)
            continue
        description = body.get("description") or f"HTTP {resp.status_code}"
        if resp.status_code == 403:
            return SendResult.BLOCKED, None, description
        return SendResult.FAILED, None, description
    return SendResult.FAILED, None, "Telegram limiti (429)"
