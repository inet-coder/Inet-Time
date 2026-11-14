from contextlib import asynccontextmanager

from redis.exceptions import LockError


@asynccontextmanager
async def profile_lock(redis, account_id: int, timeout: int = 180, blocking_timeout: int = 60):
    """`account:{id}:profile` — bir akkauntga parallel profil yangilanishining oldini oladi.

    timeout bitta yangilanishning eng uzun davomidan (backoff + qisqa FloodWait) katta bo'lishi kerak:
    avval 15 soniya edi — sekin ulanishda lock muddati tugab, release() xato berar va xizmat ERROR bo'lardi."""
    lock = redis.lock(f"lock:account:{account_id}:profile", timeout=timeout, blocking_timeout=blocking_timeout)
    acquired = await lock.acquire()
    if not acquired:
        raise TimeoutError(f"account {account_id} uchun profile lock band")
    try:
        yield
    finally:
        try:
            await lock.release()
        except LockError:
            pass  # muddati tugagan — ish baribir bajarildi, xizmatni buzmaymiz
