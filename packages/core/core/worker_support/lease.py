import uuid

LEASE_TTL_SECONDS = 30

# Bitta worker processi umri davomida barqaror identifikator.
WORKER_ID = uuid.uuid4().hex


class AccountBusyError(RuntimeError):
    """Lease band — vaqtinchalik holat (boshqa worker band qilgan), automationni ERROR qilmaydi."""


async def acquire_lease(redis, account_id: int) -> bool:
    """`account:{id}` bitta workerga biriktiriladi. Boshqa (tirik) worker egalik qilsa False."""
    key = f"lease:account:{account_id}"
    current = await redis.get(key)
    if current is not None:
        current_id = current.decode() if isinstance(current, bytes) else current
        if current_id != WORKER_ID:
            return False
    await redis.set(key, WORKER_ID, ex=LEASE_TTL_SECONDS)
    return True


async def require_lease(redis, account_id: int) -> None:
    if not await acquire_lease(redis, account_id):
        raise AccountBusyError(f"account {account_id} boshqa worker tomonidan band (lease)")


async def release_lease(redis, account_id: int) -> None:
    key = f"lease:account:{account_id}"
    current = await redis.get(key)
    if current is not None:
        current_id = current.decode() if isinstance(current, bytes) else current
        if current_id == WORKER_ID:
            await redis.delete(key)
