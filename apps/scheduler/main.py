import asyncio
import datetime
from zoneinfo import ZoneInfo

from arq import create_pool
from arq.connections import RedisSettings
from redis.asyncio import Redis
from sqlalchemy import select, update

from core.db.base import async_session
from core.db.enums import AutomationStatus, ProfileField, SubscriptionStatus, TriggerType
from core.db.models import (
    Automation,
    AutomationAction,
    Notification,
    Plan,
    Schedule,
    Subscription,
    TelegramAccount,
    User,
)
from core.entitlements import Entitlement, get_entitlement
from core.job_dispatch import enqueue_job
from core.notify import send_telegram
from core.scheduling import compute_next_run, is_due
from core.settings import settings
from core.worker_support.leader import try_acquire_or_renew_leader

TICK_SECONDS = 10


REMIND_BEFORE = datetime.timedelta(hours=24)


async def enforce_limits_after_expiry(pool, db, user_id: int) -> tuple[Entitlement, int]:
    """Obuna tugagach yangi (odatda Bepul) tarif limitidan ortiq xizmatlar to'xtatiladi —
    eng yangilari birinchi, profil asl holiga qaytariladi (restore). (yangi tarif, to'xtatilganlar soni)."""
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
    return ent, len(to_stop)


async def expire_subscriptions(pool, db, now: datetime.datetime) -> None:
    expired = (
        await db.execute(
            update(Subscription)
            .where(Subscription.status == SubscriptionStatus.ACTIVE, Subscription.expires_at <= now)
            .values(status=SubscriptionStatus.EXPIRED)
            .returning(Subscription.user_id, Subscription.plan_id)
        )
    ).all()
    await db.commit()

    for user_id, plan_id in expired:
        ent, stopped = await enforce_limits_after_expiry(pool, db, user_id)
        plan = await db.get(Plan, plan_id)
        user = await db.get(User, user_id)
        text = f"⌛ {plan.name} tarifingiz muddati tugadi. Endi siz {ent.plan_name} tarifdasiz."
        if stopped:
            text += f"\n{stopped} ta xizmat to'xtatildi va profilingiz asl holiga qaytarildi."
        text += "\n\nUzaytirish uchun: /start → 💎 Tariflar"
        if user.telegram_user_id:
            await send_telegram(user.telegram_user_id, text)


async def remind_expiring(db, now: datetime.datetime) -> None:
    """Muddat tugashiga 24 soatdan kam qolganda bir marta eslatma (notifications orqali takrorlanmaydi)."""
    rows = (
        await db.execute(
            select(Subscription, Plan, User)
            .join(Plan, Plan.id == Subscription.plan_id)
            .join(User, User.id == Subscription.user_id)
            .where(
                Subscription.status == SubscriptionStatus.ACTIVE,
                Subscription.expires_at > now,
                Subscription.expires_at <= now + REMIND_BEFORE,
            )
        )
    ).all()
    for subscription, plan, user in rows:
        # Uzaytirilsa expires_at o'zgaradi — yangi muddat uchun yana eslatiladi.
        key = f"sub_expiring:{subscription.id}:{subscription.expires_at:%Y%m%d%H}"
        if await db.scalar(select(Notification.id).where(Notification.user_id == user.id, Notification.type == key)):
            continue
        local_expiry = subscription.expires_at.astimezone(ZoneInfo(settings.default_timezone))
        text = (
            f"⏰ {plan.name} tarifingiz {local_expiry:%d.%m.%Y %H:%M} da tugaydi.\n"
            "Uzaytirmasangiz, Bepul tarifga qaytasiz va ortiqcha xizmatlar to'xtaydi.\n\n"
            "Uzaytirish uchun: /start → 💎 Tariflar"
        )
        db.add(Notification(user_id=user.id, type=key, title="Tarif tugayapti", message=text))
        await db.commit()
        if user.telegram_user_id:
            await send_telegram(user.telegram_user_id, text)


async def tick(pool) -> None:
    now = datetime.datetime.now(datetime.timezone.utc)
    async with async_session() as db:
        await expire_subscriptions(pool, db, now)
        await remind_expiring(db, now)

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
