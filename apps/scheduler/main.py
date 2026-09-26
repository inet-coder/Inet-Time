import asyncio
import datetime

from arq import create_pool
from arq.connections import RedisSettings
from redis.asyncio import Redis
from sqlalchemy import select

from core.db.base import async_session
from core.db.enums import AutomationStatus, TriggerType
from core.db.models import Automation, Schedule
from core.job_dispatch import enqueue_job
from core.scheduling import compute_next_run, is_due
from core.settings import settings
from core.worker_support.leader import try_acquire_or_renew_leader

TICK_SECONDS = 10


async def tick(pool) -> None:
    now = datetime.datetime.now(datetime.timezone.utc)
    async with async_session() as db:
        rows = (
            await db.execute(
                select(Automation, Schedule)
                .join(Schedule, Schedule.automation_id == Automation.id)
                .where(Automation.status == AutomationStatus.ACTIVE)
            )
        ).all()

        for automation, schedule in rows:
            if not is_due(schedule, now):
                continue

            # Avval next_run_at/last_run_at yangilanadi — shu tikda yoki leader
            # almashganda bir xil slot ikki marta ishga tushmasligi uchun.
            if schedule.trigger_type in (TriggerType.INTERVAL, TriggerType.SCHEDULE):
                schedule.next_run_at = compute_next_run(schedule, now)
            schedule.last_run_at = now
            await db.commit()

            job_id = f"scheduled:{automation.id}:{now.strftime('%Y%m%dT%H%M%S')}"
            await enqueue_job(
                pool,
                db,
                task_name="run_automation_once",
                telegram_account_id=automation.telegram_account_id,
                automation_id=automation.id,
                task_kwargs={"automation_id": automation.id},
                job_id=job_id,
            )


async def main() -> None:
    redis = Redis.from_url(settings.redis_url or "redis://redis:6379")
    pool = await create_pool(RedisSettings.from_dsn(settings.redis_url or "redis://redis:6379"))

    print("scheduler ishga tushdi")
    while True:
        try:
            if await try_acquire_or_renew_leader(redis):
                await tick(pool)
        except Exception as exc:  # noqa: BLE001 — bitta tik xatosi butun schedulerni qulatmasligi kerak
            print(f"scheduler tick xatosi: {exc}")
        await asyncio.sleep(TICK_SECONDS)


if __name__ == "__main__":
    asyncio.run(main())
