import uuid

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from core.db.enums import WorkerJobStatus
from core.db.models import WorkerJob


async def enqueue_job(
    pool,
    db: AsyncSession,
    *,
    task_name: str,
    telegram_account_id: int,
    automation_id: int | None,
    task_kwargs: dict,
    job_id: str | None = None,
) -> str | None:
    """WorkerJob yozuvi (idempotency) + arq navbatiga qo'yish.

    `job_id` berilmasa tasodifiy generatsiya qilinadi (API'dan qo'lda chaqiriqlar uchun).
    Deterministik job_id (masalan scheduler'dan) allaqachon mavjud bo'lsa — jim o'tkazib
    yuboriladi (None qaytaradi), chunki bu slot uchun job allaqachon rejalashtirilgan.
    """
    if job_id is None:
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
    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()
        return None

    await pool.enqueue_job(task_name, job_id=job_id, _job_id=job_id, **task_kwargs)
    return job_id
