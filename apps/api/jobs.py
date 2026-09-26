from sqlalchemy.ext.asyncio import AsyncSession

from arq_pool import get_pool
from core.job_dispatch import enqueue_job


async def enqueue(
    db: AsyncSession,
    *,
    task_name: str,
    telegram_account_id: int,
    automation_id: int | None,
    task_kwargs: dict,
) -> str:
    pool = await get_pool()
    job_id = await enqueue_job(
        pool,
        db,
        task_name=task_name,
        telegram_account_id=telegram_account_id,
        automation_id=automation_id,
        task_kwargs=task_kwargs,
    )
    assert job_id is not None  # tasodifiy uuid — kolliziya bo'lmaydi
    return job_id
