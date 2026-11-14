import asyncio
import random

from telethon.errors import FloodWaitError

from core.telegram.errors import is_retryable

DEFAULT_MAX_RETRIES = 3
# Bundan uzoq FloodWait'ni job ichida kutmaymiz (lock va job timeout'i tugab qoladi) — xato ko'tariladi,
# chaqiruvchi akkauntni shu muddatga «dam oldiradi».
DEFAULT_MAX_FLOOD_WAIT = 60


async def call_with_backoff(
    func, *args, max_retries: int = DEFAULT_MAX_RETRIES, max_flood_wait: int = DEFAULT_MAX_FLOOD_WAIT, **kwargs
):
    """FloodWaitError -> qisqa bo'lsa aynan .seconds kutiladi, uzun bo'lsa xato ko'tariladi.
    Vaqtinchalik xatolar (tarmoq, timeout, Telegram 5xx) -> eksponensial backoff.
    Sessiya tugagan yoki so'rov noto'g'ri bo'lsa — darhol ko'tariladi (qayta urinish befoyda)."""
    attempt = 0
    while True:
        try:
            return await func(*args, **kwargs)
        except FloodWaitError as exc:
            if exc.seconds > max_flood_wait:
                raise
            await asyncio.sleep(exc.seconds + 1)
        except Exception as exc:
            if attempt >= max_retries or not is_retryable(exc):
                raise
            await asyncio.sleep(min(2**attempt, 10) + random.random())
            attempt += 1
