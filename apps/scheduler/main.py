import asyncio
import datetime

from arq import create_pool
from arq.connections import RedisSettings
from redis.asyncio import Redis
from sqlalchemy import select, update

from core.db.base import async_session
from core.db.enums import AutomationStatus, ProfileField, SubscriptionStatus, TriggerType
from core.db.models import Automation, AutomationAction, Schedule, Subscription, TelegramAccount
from core.entitlements import get_entitlement
from core.job_dispatch import enqueue_job
from core.scheduling import compute_next_run, is_due
from core.settings import settings
from core.worker_support.leader import try_acquire_or_renew_leader

TICK_SECONDS = 10


async def enforce_limits_after_expiry(pool, db, user_id: int) -> None:
    """Obuna tugagach yangi (odatda Bepul) tarif limitidan ortiq xizmatlar to'xtatiladi —
    eng yangilari birinchi, profil asl holiga qaytariladi (restore)."""
    ent = await get_entitlement(db, user_id)
    live = list(
        await db.scalars(
            select(Automation)
            .join(TelegramAccount, TelegramAccount.id == Automation.telegram_account_id)
            .where(TelegramAccount.user_id == user_id, Automation.status == AutomationStatus.ACTIVE)
            .order_by(Automation.started_at.desc())
        )
    )
    online_ids = set(
        await db.scalars(
            select(AutomationAction.automation_id).where(
                AutomationAction.automation_id.in_([a.id for a in live] or [0]),
                AutomationAction.field == ProfileField.ONLINE,
            )
        )
    )

    to_stop = []
    kept = 0
    for automation in reversed(live):  # eng eskilari saqlanadi
        if automation.id in online_ids and not ent.flags.get("online_service"):
            to_stop.append(automation)
        elif kept < ent.scheduler_limit:
            kept += 1
        else:
            to_stop.append(automation)

    for automation in to_stop:
        await enqueue_job(
            pool,
            db,
            task_name="stop_automation_job",
            telegram_account_id=automation.telegram_account_id,
            automation_id=automation.id,
            task_kwargs={"automation_id": automation.id, "restore": True},
        )


async def expire_subscriptions(pool, db, now: datetime.datetime) -> None:
    expired_user_ids = set(
        (
            await db.execute(
                update(Subscription)
                .where(Subscription.status == SubscriptionStatus.ACTIVE, Subscription.expires_at <= now)
                .values(status=SubscriptionStatus.EXPIRED)
                .returning(Subscription.user_id)
            )
        ).scalars()
    )
    await db.commit()
    for user_id in expired_user_ids:
        await enforce_limits_after_expiry(pool, db, user_id)


async def tick(pool) -> None:
    now = datetime.datetime.now(datetime.timezone.utc)
    async with async_session() as db:
        await expire_subscriptions(pool, db, now)

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
