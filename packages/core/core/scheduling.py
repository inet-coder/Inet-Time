import datetime
from zoneinfo import ZoneInfo

from croniter import croniter

from core.db.enums import TriggerType
from core.db.models import Schedule


def is_due(schedule: Schedule, now_utc: datetime.datetime) -> bool:
    if schedule.trigger_type == TriggerType.INTERVAL:
        return schedule.next_run_at is None or now_utc >= schedule.next_run_at

    if schedule.trigger_type == TriggerType.SCHEDULE:
        if not schedule.cron_expr:
            return False
        return schedule.next_run_at is None or now_utc >= schedule.next_run_at

    if schedule.trigger_type == TriggerType.WINDOW:
        if schedule.window_start_at is None or schedule.window_end_at is None:
            return False
        if not (schedule.window_start_at <= now_utc <= schedule.window_end_at):
            return False
        # Har window bosqichida bir marta ishga tushadi.
        return schedule.last_run_at is None or schedule.last_run_at < schedule.window_start_at

    return False


def compute_next_run(schedule: Schedule, now_utc: datetime.datetime) -> datetime.datetime | None:
    """INTERVAL/SCHEDULE uchun keyingi ishga tushish vaqti. WINDOW uchun kerak emas (last_run_at yetarli)."""
    if schedule.trigger_type == TriggerType.INTERVAL:
        seconds = schedule.interval_seconds or 60
        return now_utc + datetime.timedelta(seconds=seconds)

    if schedule.trigger_type == TriggerType.SCHEDULE:
        tz = ZoneInfo(schedule.timezone)
        local_now = now_utc.astimezone(tz)
        it = croniter(schedule.cron_expr, local_now)
        next_local = it.get_next(datetime.datetime)
        if next_local.tzinfo is None:
            next_local = next_local.replace(tzinfo=tz)
        return next_local.astimezone(datetime.timezone.utc)

    return None
