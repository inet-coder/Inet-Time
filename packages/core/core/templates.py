import datetime
from dataclasses import dataclass
from zoneinfo import ZoneInfo

WEEKDAYS_UZ = ["Dushanba", "Seshanba", "Chorshanba", "Payshanba", "Juma", "Shanba", "Yakshanba"]
MONTHS_UZ = [
    "Yanvar", "Fevral", "Mart", "Aprel", "May", "Iyun",
    "Iyul", "Avgust", "Sentabr", "Oktabr", "Noyabr", "Dekabr",
]  # fmt: skip


@dataclass
class TemplateContext:
    first_name: str | None = None
    last_name: str | None = None
    username: str | None = None
    timezone: str = "UTC"

    @property
    def name(self) -> str:
        return f"{self.first_name or ''} {self.last_name or ''}".strip()


def render(template: str, ctx: TemplateContext, now: datetime.datetime | None = None) -> str:
    """{name} {first_name} {last_name} {username} {time} {date} {day} {weekday} {month} {year} {timezone}"""
    moment = (now or datetime.datetime.now(datetime.timezone.utc)).astimezone(ZoneInfo(ctx.timezone))
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
    }
    try:
        return template.format(**values)
    except (KeyError, IndexError) as exc:
        raise ValueError(f"Noma'lum shablon o'zgaruvchisi: {exc}") from exc
