import uuid

LEADER_KEY = "leader:scheduler"
LEADER_TTL_SECONDS = 15

# Bitta scheduler processi umri davomida barqaror identifikator.
INSTANCE_ID = uuid.uuid4().hex


async def try_acquire_or_renew_leader(redis) -> bool:
    """Bitta scheduler instance faol bo'lishi uchun oddiy Redis-based leader election."""
    acquired = await redis.set(LEADER_KEY, INSTANCE_ID, nx=True, ex=LEADER_TTL_SECONDS)
    if acquired:
        return True
    current = await redis.get(LEADER_KEY)
    current_id = current.decode() if isinstance(current, bytes) else current
    if current_id == INSTANCE_ID:
        await redis.expire(LEADER_KEY, LEADER_TTL_SECONDS)
        return True
    return False
