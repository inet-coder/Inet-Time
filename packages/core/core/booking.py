"""Yozilish mantig'i (toza funksiyalar): ish jadvali, bo'sh vaqtlar. Telegramga bog'liq emas — alohida testlanadi."""

import datetime
import re

from core.botbuilder import WEEKDAYS

DAY_ALIASES = {
    "du": 0, "dush": 0, "dushanba": 0, "se": 1, "sesh": 1, "seshanba": 1, "chor": 2, "cho": 2, "chorshanba": 2,
    "pay": 3, "pa": 3, "payshanba": 3, "ju": 4, "jum": 4, "juma": 4, "sha": 5, "shan": 5, "shanba": 5, "ya": 6, "yak": 6, "yakshanba": 6,
}
SHORT_DAYS = ["Du", "Se", "Chor", "Pay", "Ju", "Sha", "Ya"]
_TIME = re.compile(r"(\d{1,2})[:.](\d{2})\s*[-–—]\s*(\d{1,2})[:.](\d{2})")


def hm(minutes: int) -> str:
    return f"{minutes // 60:02d}:{minutes % 60:02d}"


def parse_hours(text: str) -> dict[str, str] | None:
    """«Du-Sha 09:00-18:00» / «Ya yopiq» qatorlari → {"0": "09:00-18:00", ..., "6": ""}. Xato bo'lsa None."""
    out: dict[str, str] = {}
    for raw in (text or "").lower().replace(",", "\n").splitlines():
        line = raw.strip()
        if not line:
            continue
        m = re.match(r"^([a-z']+)(?:\s*[-–—]\s*([a-z']+))?\s+(.*)$", line)
        if not m:
            return None
        a, b, rest = m.group(1), m.group(2), m.group(3).strip()
        if a not in DAY_ALIASES or (b and b not in DAY_ALIASES):
            return None
        first, last = DAY_ALIASES[a], DAY_ALIASES[b] if b else DAY_ALIASES[a]
        if last < first:
            return None
        if rest.startswith(("yopiq", "dam")):
            value = ""
        else:
            t = _TIME.search(rest)
            if not t:
                return None
            h1, m1, h2, m2 = (int(x) for x in t.groups())
            if not (0 <= h1 < 24 and 0 <= h2 < 24 and m1 < 60 and m2 < 60) or (h1, m1) >= (h2, m2):
                return None
            value = f"{h1:02d}:{m1:02d}-{h2:02d}:{m2:02d}"
        for d in range(first, last + 1):
            out[str(d)] = value
    if not out:
        return None
    return {str(i): out.get(str(i), "") for i in range(7)}


def hours_text(hours: dict[str, str]) -> str:
    return "\n".join(f"{WEEKDAYS[i]}: {hours.get(str(i)) or 'dam olish'}" for i in range(7))


def day_range(booking: dict, day: datetime.date) -> tuple[int, int] | None:
    v = (booking.get("hours") or {}).get(str(day.weekday()), "")
    if not v:
        return None
    return int(v[:2]) * 60 + int(v[3:5]), int(v[6:8]) * 60 + int(v[9:11])


def local_now(booking: dict, now_utc: datetime.datetime | None = None) -> datetime.datetime:
    now = now_utc or datetime.datetime.now(datetime.timezone.utc)
    return (now + datetime.timedelta(hours=int(booking.get("tz", 5)))).replace(tzinfo=None)


def to_utc(booking: dict, day: datetime.date, minutes: int) -> datetime.datetime:
    local = datetime.datetime.combine(day, datetime.time()) + datetime.timedelta(minutes=minutes)
    return (local - datetime.timedelta(hours=int(booking.get("tz", 5)))).replace(tzinfo=datetime.timezone.utc)


def to_local(booking: dict, when: datetime.datetime) -> datetime.datetime:
    return (when.astimezone(datetime.timezone.utc) + datetime.timedelta(hours=int(booking.get("tz", 5)))).replace(tzinfo=None)


def open_days(booking: dict, now_local: datetime.datetime) -> list[datetime.date]:
    today = now_local.date()
    return [today + datetime.timedelta(days=i) for i in range(int(booking.get("days_ahead", 14)) + 1) if day_range(booking, today + datetime.timedelta(days=i))]


def free_slots(booking: dict, minutes: int, day: datetime.date, busy: list[tuple[int, int]], now_local: datetime.datetime) -> list[int]:
    """Kunning bo'sh boshlanish vaqtlari (kun boshidan daqiqalarda). busy — shu kun band intervallari (boshi, oxiri)."""
    rng = day_range(booking, day)
    if rng is None:
        return []
    start, end = rng
    step = int(booking.get("step", 30))
    earliest = None
    if day == now_local.date():
        earliest = now_local.hour * 60 + now_local.minute + int(booking.get("min_notice", 1)) * 60
    elif day < now_local.date():
        return []
    out = []
    t = start
    while t + minutes <= end:
        if (earliest is None or t >= earliest) and all(not (b0 < t + minutes and t < b1) for b0, b1 in busy):
            out.append(t)
        t += step
    return out
