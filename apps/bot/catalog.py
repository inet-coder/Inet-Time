"""Botda ko'rsatiladigan xizmatlar va umumiy matn bo'laklari. Matnlar qisqa: bitta fikr — bitta qator."""

import datetime
import math
from zoneinfo import ZoneInfo

from core.settings import settings

UPDATE_INTERVAL_SECONDS = 60

# Mini App nomi — hamma joyda bir xil.
STUDIO = "✨ Profil studiyasi"
STUDIO_SHORT = "✨ Studiya"

SERVICES = {
    "clock_name": {
        "title": "🕐 Soat ismda",
        "field": "name",
        "default": "{first_name} {time}",
        "desc": "Ismingiz yonida joriy soat. Har daqiqa yangilanadi.",
    },
    "auto_bio": {
        "title": "📝 Avto bio",
        "field": "bio",
        "default": "🕐 {time} · {weekday}",
        "desc": "Bio o'zi yangilanib turadi: soat, sana, hafta kuni.",
    },
    "auto_name": {
        "title": "✏️ Avto ism",
        "field": "name",
        "default": "{first_name} | {weekday}",
        "desc": "Ism shablon bo'yicha o'zgaradi, masalan hafta kuni bilan.",
    },
    "online": {
        "title": "🟢 24/7 Online",
        "field": "online",
        "default": "true",
        "desc": "Akkaunt doim «online» ko'rinadi.\nℹ️ Boshqalar buni maxfiylik sozlamangiz ruxsat bersa ko'radi.",
        "pro_flag": "online_service",
    },
}

BASIC_SERVICES = ("clock_name", "auto_bio", "auto_name")

# "Ko'proq xizmatlar" bo'limi. "online" oddiy (bitta shablonli) xizmat — SERVICES'dagi ekran orqali ishlaydi;
# qolganlari sozlash bosqichlari bo'lgan murakkab xizmatlar (handlers/pro.py).
PRO_SERVICES = {
    "online": {"title": "🟢 24/7 Online", "flag": "online_service", "short": "doim online"},
    "playlist": {
        "title": "🔁 Bio playlist",
        "flag": "playlist_service",
        "short": "bir nechta bio navbat bilan",
        "desc": "Bir nechta bio yozasiz — navbat bilan yoki tasodifiy almashadi.",
    },
    "schedule": {
        "title": "🗓 Jadval",
        "flag": "schedule_service",
        "short": "vaqtga qarab bio yoki ism",
        "desc": "Bio yoki ism vaqtga qarab o'zgaradi:\n09:00 → Ishdaman 💼\n18:00 → Uydaman 🏠",
    },
    "emoji": {
        "title": "😀 Emoji status",
        "flag": "emoji_service",
        "short": "Premium emoji almashadi",
        "desc": "Ism yonidagi emoji status o'zi almashadi.\n⭐ Telegram Premium kerak.",
    },
    "photo": {
        "title": "🖼 Rasm almashtirish",
        "flag": "photo_service",
        "short": "profil rasmi navbat bilan",
        "desc": "Profil rasmi navbat bilan almashadi.\nO'chirsangiz — asl rasmingiz qaytadi.",
    },
}

INTERVAL_CHOICES = {
    "playlist": [600, 1800, 3600, 10800, 86400],
    "emoji": [600, 3600, 10800, 86400],
    "photo": [3600, 21600, 86400],
}

TEMPLATE_HELP = (
    "🔤 O'zgaruvchilar:\n"
    "{first_name} ism · {name} to'liq ism · {username}\n"
    "{time} soat · {date} sana · {weekday} hafta kuni"
)

STATUS_ICONS = {"ACTIVE": "✅", "STARTING": "⏳", "ERROR": "⚠️"}
STATUS_TEXT = {"ACTIVE": "✅ yoqilgan", "STARTING": "⏳ yoqilmoqda", "ERROR": "⚠️ xatolik"}
ERROR_HINT = "⚠️ Telegram bilan muammo bo'ldi. O'chirib, qayta yoqing."

PLAN_ICONS = {"free": "🆓", "starter": "⭐", "pro": "🚀"}


def interval_text(seconds: int) -> str:
    if seconds % 86400 == 0:
        return f"{seconds // 86400} kun"
    if seconds % 3600 == 0:
        return f"{seconds // 3600} soat"
    return f"{seconds // 60} daqiqa"


def pro_unlocked(flags: dict) -> list[str]:
    return [meta["title"] for meta in PRO_SERVICES.values() if flags.get(meta["flag"])]


def plan_features(flags: dict) -> str:
    """Bir qatorda: «2 akkaunt · 6 xizmat · Jadval, Playlist»."""
    names = [meta["title"].split(" ", 1)[1] for meta in PRO_SERVICES.values() if flags.get(meta["flag"])]
    extras = "barcha xizmatlar" if len(names) == len(PRO_SERVICES) else ", ".join(names)
    base = f"{flags.get('account_limit', 1)} akkaunt · {flags.get('scheduler_limit', 1)} xizmat"
    return f"{base} · {extras}" if extras else base


def unlocking_plan(plans: list[dict], flag: str) -> dict | None:
    """Xizmatni ochadigan eng arzon tarif — «Pro'da» o'rniga aniq nom aytish uchun."""
    candidates = [p for p in plans if p["flags"].get(flag)]
    return min(candidates, key=lambda p: p["final_price"]) if candidates else None


def expiry_text(expires_at_iso: str) -> str:
    expires_at = datetime.datetime.fromisoformat(expires_at_iso)
    seconds_left = (expires_at - datetime.datetime.now(datetime.timezone.utc)).total_seconds()
    days_left = max(0, math.ceil(seconds_left / 86400))
    local = expires_at.astimezone(ZoneInfo(settings.default_timezone))
    return f"{local:%d.%m} gacha · {days_left} kun"


def plan_line(overview: dict) -> str:
    """«💎 Pro · 26.10 gacha · 30 kun» yoki «💎 Bepul»."""
    plan = overview["plan"]
    line = f"{PLAN_ICONS.get(plan['code'], '💎')} {plan['name']}"
    return f"{line} · {expiry_text(plan['expires_at'])}" if plan["expires_at"] else line


def usage_line(overview: dict) -> str:
    usage, flags = overview["usage"], overview["plan"]["flags"]
    return f"⚙️ {usage['automations']}/{flags['scheduler_limit']} xizmat · 👤 {usage['accounts']}/{flags['account_limit']} akkaunt"
