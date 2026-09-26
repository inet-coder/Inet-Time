from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.db.models import WorkerJob
from deps import get_db
from schemas import JobStatusOut

router = APIRouter(prefix="/jobs", tags=["jobs"])


@router.get("/{job_id}", response_model=JobStatusOut)
async def get_job(job_id: str, db: AsyncSession = Depends(get_db)) -> WorkerJob:
    job = await db.scalar(select(WorkerJob).where(WorkerJob.job_id == job_id))
    if job is None:
        raise HTTPException(404, "Job topilmadi")
    return job
