import logging

import httpx

from core.settings import settings

logger = logging.getLogger(__name__)


async def send_telegram(chat_id: int, text: str) -> None:
    """Bot processidan tashqarida (scheduler) foydalanuvchiga xabar yuborish. Xato bo'lsa — faqat log."""
    if not settings.bot_token:
        return
    url = f"https://api.telegram.org/bot{settings.bot_token}/sendMessage"
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.post(url, json={"chat_id": chat_id, "text": text})
        if resp.status_code != 200:
            logger.warning("telegram xabar yuborilmadi: chat=%s status=%s", chat_id, resp.status_code)
    except httpx.HTTPError as exc:
        logger.warning("telegram xabar yuborilmadi: chat=%s %s", chat_id, type(exc).__name__)
