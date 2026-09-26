"""Profilning hozirgi va keyingi holatini hisoblash (Mini App'dagi "Hozir / Keyingi" ko'rinishi uchun)."""

import datetime
from zoneinfo import ZoneInfo

from core.templates import TemplateContext, render


def slot_index(times: list[str], now_hhmm: str) -> int:
    """Jadval: hozirgi vaqtdan oldingi eng oxirgi slot; birinchi slotdan oldin — kechagi oxirgisi."""
    order = sorted(range(len(times)), key=lambda i: times[i])
    past = [i for i in order if times[i] <= now_hhmm]
    return past[-1] if past else order[-1]


def next_slot_index(times: list[str], now_hhmm: str) -> int:
    order = sorted(range(len(times)), key=lambda i: times[i])
    future = [i for i in order if times[i] > now_hhmm]
    return future[0] if future else order[0]


def _next_minute(now: datetime.datetime) -> datetime.datetime:
    return (now + datetime.timedelta(minutes=1)).replace(second=0, microsecond=0)


def automation_preview(
    automation: dict,
    ctx: TemplateContext,
    now: datetime.datetime,
    last_applied: str | None,
    next_run_at: datetime.datetime | None,
    last_index: int,
) -> dict:
    """automation: overview'dagi ko'rinish (field, actions[{template, at_time}], selection_strategy).
    Qaytaradi: {field, current, next, next_at} — next None bo'lsa, o'zgarish kutilmaydi."""
    field = automation["field"]
    templates = [a["template"] for a in automation["actions"]]
    strategy = automation["selection_strategy"]
    local_now = now.astimezone(ZoneInfo(ctx.timezone))

    def r(template: str, at: datetime.datetime | None = None) -> str:
        return render(template, ctx, at or now)

    if field == "online":
        return {"field": field, "current": "online", "next": None, "next_at": None}

    if strategy == "BY_TIME":
        times = [a["at_time"] for a in automation["actions"]]
        hhmm = local_now.strftime("%H:%M")
        current_i, next_i = slot_index(times, hhmm), next_slot_index(times, hhmm)
        hour, minute = map(int, times[next_i].split(":"))
        next_local = local_now.replace(hour=hour, minute=minute, second=0, microsecond=0)
        if next_local <= local_now:
            next_local += datetime.timedelta(days=1)
        return {
            "field": field,
            "current": r(templates[current_i]),
            "next": r(templates[next_i], next_local),
            "next_at": next_local.astimezone(datetime.timezone.utc),
        }

    if len(templates) > 1:
        current = last_applied or r(templates[(last_index - 1) % len(templates)])
        if strategy == "RANDOM":
            return {"field": field, "current": current, "next": "🎲", "next_at": next_run_at}
        return {"field": field, "current": current, "next": r(templates[last_index % len(templates)]), "next_at": next_run_at}

    current = last_applied or r(templates[0])
    upcoming_at = _next_minute(now)
    upcoming = r(templates[0], upcoming_at)
    if upcoming == r(templates[0]):
        return {"field": field, "current": current, "next": None, "next_at": None}
    return {"field": field, "current": current, "next": upcoming, "next_at": upcoming_at}
