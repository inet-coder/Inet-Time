import logging

import httpx

from core.settings import settings

logger = logging.getLogger(__name__)


async def send_telegram(chat_id: int, text: str, buttons: list[list[tuple[str, str]]] | None = None) -> None:
    """Bot processidan tashqarida (scheduler, API) xabar yuborish. buttons — [[(matn, callback_data)]].
    Tugmalar bosilganda callback'ni bot qabul qiladi (token bir xil). Xato bo'lsa — faqat log."""
    if not settings.bot_token:
        return
    url = f"https://api.telegram.org/bot{settings.bot_token}/sendMessage"
    body: dict = {"chat_id": chat_id, "text": text}
    if buttons:
        body["reply_markup"] = {
            "inline_keyboard": [[{"text": t, "callback_data": d} for t, d in row] for row in buttons]
        }
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.post(url, json=body)
        if resp.status_code != 200:
            logger.warning("telegram xabar yuborilmadi: chat=%s status=%s", chat_id, resp.status_code)
    except httpx.HTTPError as exc:
        logger.warning("telegram xabar yuborilmadi: chat=%s %s", chat_id, type(exc).__name__)


async def send_media(chat_id: int, kind: str, data: bytes, caption: str = "") -> bool:
    """Rasm yoki video faylni bot orqali yuborish (Bot API, ≤50 MB). kind: photo | video."""
    if not settings.bot_token:
        return False
    method, field, name = ("sendPhoto", "photo", "story.jpg") if kind == "photo" else ("sendVideo", "video", "story.mp4")
    url = f"https://api.telegram.org/bot{settings.bot_token}/{method}"
    try:
        async with httpx.AsyncClient(timeout=120) as client:
            resp = await client.post(url, data={"chat_id": str(chat_id), "caption": caption[:1000]}, files={field: (name, data)})
        if resp.status_code != 200:
            logger.warning("media yuborilmadi: chat=%s status=%s %s", chat_id, resp.status_code, resp.text[:200])
            return False
        return True
    except httpx.HTTPError as exc:
        logger.warning("media yuborilmadi: chat=%s %s", chat_id, type(exc).__name__)
        return False
