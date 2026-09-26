from contextlib import asynccontextmanager


@asynccontextmanager
async def profile_lock(redis, account_id: int, timeout: int = 15, blocking_timeout: int = 10):
    """`account:{id}:profile` — bir akkauntga parallel profil yangilanishining oldini oladi."""
    lock = redis.lock(f"lock:account:{account_id}:profile", timeout=timeout, blocking_timeout=blocking_timeout)
    acquired = await lock.acquire()
    if not acquired:
        raise TimeoutError(f"account {account_id} uchun profile lock band")
    try:
        yield
    finally:
        await lock.release()
