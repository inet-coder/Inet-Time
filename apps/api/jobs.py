import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from core.db.enums import WorkerJobStatus
from core.db.models import WorkerJob
from arq_pool import get_pool


async def enqueue(
    db: AsyncSession,
    *,
    task_name: str,
    telegram_account_id: int,
    automation_id: int | None,
    task_kwargs: dict,
) -> str:
    job_id = f"{task_name}:{uuid.uuid4().hex}"
    db.add(
        WorkerJob(
            job_id=job_id,
            telegram_account_id=telegram_account_id,
            automation_id=automation_id,
            status=WorkerJobStatus.PENDING,
            payload={"task": task_name, **task_kwargs},
        )
    )
    await db.commit()

    pool = await get_pool()
    await pool.enqueue_job(task_name, job_id=job_id, _job_id=job_id, **task_kwargs)
    return job_id
