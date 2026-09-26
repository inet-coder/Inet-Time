import datetime
import re
from dataclasses import dataclass
from zoneinfo import ZoneInfo

WEEKDAYS_UZ = ["Dushanba", "Seshanba", "Chorshanba", "Payshanba", "Juma", "Shanba", "Yakshanba"]
MONTHS_UZ = [
    "Yanvar", "Fevral", "Mart", "Aprel", "May", "Iyun",
    "Iyul", "Avgust", "Sentabr", "Oktabr", "Noyabr", "Dekabr",
]  # fmt: skip

_BIRTHDAY = re.compile(r"^(?:(\d{4})-)?(\d{2})-(\d{2})$")
_NEEDS_BIRTHDAY = ("{bday}", "{bday_days}", "{age}")
YEAR_BAR_LENGTH = 10


@dataclass
class TemplateContext:
    first_name: str | None = None
    last_name: str | None = None
    username: str | None = None
    timezone: str = "UTC"
    # "MM-DD" yoki "YYYY-MM-DD"
    birthday: str | None = None

    @property
    def name(self) -> str:
        return f"{self.first_name or ''} {self.last_name or ''}".strip()


def parse_birthday(value: str | None) -> tuple[int | None, int, int] | None:
    """(yil yoki None, oy, kun) — noto'g'ri bo'lsa None."""
    match = _BIRTHDAY.match(value or "")
    if not match:
        return None
    year = int(match.group(1)) if match.group(1) else None
    month, day = int(match.group(2)), int(match.group(3))
    try:
        datetime.date(year or 2000, month, day)  # 2000 — kabisa yil: 29-fevral ham to'g'ri
    except ValueError:
        return None
    return year, month, day


def _next_birthday(today: datetime.date, month: int, day: int) -> datetime.date:
    for year in (today.year, today.year + 1):
        try:
            candidate = datetime.date(year, month, day)
        except ValueError:  # 29-fevral kabisa bo'lmagan yilda — 28-fevral
            candidate = datetime.date(year, 2, 28)
        if candidate >= today:
            return candidate
    raise AssertionError("unreachable")


def _birthday_values(ctx: TemplateContext, today: datetime.date) -> dict:
    parsed = parse_birthday(ctx.birthday)
    if parsed is None:
        return {}
    year, month, day = parsed
    days = (_next_birthday(today, month, day) - today).days
    if days == 0:
        text = "Bugun tug'ilgan kunim! 🎉"
    elif days == 1:
        text = "Ertaga tug'ilgan kunim! 🎈"
    else:
        text = f"Tug'ilgan kunimga {days} kun qoldi"
    values = {"bday": text, "bday_days": str(days)}
    if year:
        age = today.year - year - ((today.month, today.day) < (month, day))
        values["age"] = str(age)
    return values


def _daypart(hour: int) -> str:
    if 5 <= hour < 11:
        return "Xayrli tong ☀️"
    if 11 <= hour < 17:
        return "Xayrli kun 🌤"
    if 17 <= hour < 22:
        return "Xayrli kech 🌆"
    return "Xayrli tun 🌙"


def _weekend(moment: datetime.datetime) -> str:
    weekday = moment.weekday()  # 5 — shanba, 6 — yakshanba
    if weekday >= 5:
        return "Dam olish kuni 🎉"
    return f"Dam olishga {5 - weekday} kun"


def render(template: str, ctx: TemplateContext, now: datetime.datetime | None = None) -> str:
    """{name} {first_name} {last_name} {username} {time} {date} {day} {weekday} {month} {year} {timezone}
    {bday} {bday_days} {age} {newyear_days} {year_percent} {year_bar} {weekend} {daypart}"""
    moment = (now or datetime.datetime.now(datetime.timezone.utc)).astimezone(ZoneInfo(ctx.timezone))
    today = moment.date()
    year_start = datetime.date(today.year, 1, 1)
    year_days = (datetime.date(today.year + 1, 1, 1) - year_start).days
    year_part = (today - year_start).days / year_days
    filled = round(year_part * YEAR_BAR_LENGTH)
    values = {
        "name": ctx.name,
        "first_name": ctx.first_name or "",
        "last_name": ctx.last_name or "",
        "username": ctx.username or "",
        "time": moment.strftime("%H:%M"),
        "date": moment.strftime("%d.%m.%Y"),
        "day": str(moment.day),
        "weekday": WEEKDAYS_UZ[moment.weekday()],
        "month": MONTHS_UZ[moment.month - 1],
        "year": str(moment.year),
        "timezone": ctx.timezone,
        "newyear_days": str((datetime.date(today.year + 1, 1, 1) - today).days),
        "year_percent": str(int(year_part * 100)),
        "year_bar": "▓" * filled + "░" * (YEAR_BAR_LENGTH - filled),
        "weekend": _weekend(moment),
        "daypart": _daypart(moment.hour),
        **_birthday_values(ctx, today),
    }
    if any(key in template for key in _NEEDS_BIRTHDAY) and "bday" not in values:
        raise ValueError("Tug'ilgan kun kiritilmagan")
    if "{age}" in template and "age" not in values:
        raise ValueError("Yoshni ko'rsatish uchun tug'ilgan yilni ham kiriting")
    try:
        return template.format(**values)
    except (KeyError, IndexError) as exc:
        raise ValueError(f"Noma'lum shablon o'zgaruvchisi: {exc}") from exc
