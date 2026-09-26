import asyncio
import random

from telethon.errors import FloodWaitError

DEFAULT_MAX_RETRIES = 4


async def call_with_backoff(func, *args, max_retries: int = DEFAULT_MAX_RETRIES, **kwargs):
    """FloodWaitError -> aynan .seconds qadar kut (limitsiz, blind retry emas).
    Boshqa RPC/connection xatolari -> eksponensial backoff, max_retries'dan keyin xato ko'tariladi."""
    attempt = 0
    while True:
        try:
            return await func(*args, **kwargs)
        except FloodWaitError as exc:
            await asyncio.sleep(exc.seconds)
        except Exception:
            if attempt >= max_retries:
                raise
            await asyncio.sleep(min(2**attempt, 30) + random.random())
            attempt += 1
