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
