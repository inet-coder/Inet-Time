"""Botda ko'rsatiladigan xizmatlar — har biri bitta tugma bilan yoqiladi."""

import datetime
import math
from zoneinfo import ZoneInfo

from core.settings import settings

UPDATE_INTERVAL_SECONDS = 60

SERVICES = {
    "clock_name": {
        "title": "🕐 Soat ismda",
        "field": "name",
        "default": "{first_name} {time}",
        "desc": "Ismingiz yonida joriy vaqt ko'rinadi va har daqiqada yangilanadi.",
    },
    "auto_bio": {
        "title": "📝 Avto bio",
        "field": "bio",
        "default": "🕐 {time} · {weekday}",
        "desc": "Bio (o'zingiz haqingizda) matni shablon bo'yicha yangilanib turadi.",
    },
    "auto_name": {
        "title": "✏️ Avto ism",
        "field": "name",
        "default": "{first_name} | {weekday}",
        "desc": "Ismingiz shablon bo'yicha o'zgarib turadi (masalan hafta kuni bilan).",
    },
    "online": {
        "title": "🟢 24/7 Online",
        "field": "online",
        "default": "true",
        "desc": (
            "Akkauntingiz doim «online» ko'rinadi.\n"
            "Eslatma: telefoningizda Telegram'ni yopsangiz holat qisqa vaqtga o'zgarishi mumkin, "
            "va boshqalar buni faqat maxfiylik sozlamalaringiz ruxsat bersa ko'radi."
        ),
        "pro_flag": "online_service",
    },
}

TEMPLATE_HELP = (
    "O'zgaruvchilar:\n"
    "{first_name} — ism, {last_name} — familiya, {name} — to'liq ism, {username}\n"
    "{time} — soat (14:05), {date} — sana, {weekday} — hafta kuni, {day}, {month}, {year}"
)

STATUS_ICONS = {"ACTIVE": "✅", "STARTING": "⏳", "ERROR": "⚠️"}


def plan_features(flags: dict) -> list[str]:
    """Tarif flag'larini foydalanuvchi tushunadigan ro'yxatga aylantiradi."""
    features = [
        f"{flags.get('account_limit', 1)} ta akkaunt ulash",
        f"bir vaqtda {flags.get('scheduler_limit', 1)} ta xizmat",
    ]
    features.append("🟢 24/7 Online" if flags.get("online_service") else "🔒 24/7 Online yo'q")
    return features


def expiry_text(expires_at_iso: str) -> str:
    expires_at = datetime.datetime.fromisoformat(expires_at_iso)
    seconds_left = (expires_at - datetime.datetime.now(datetime.timezone.utc)).total_seconds()
    days_left = max(0, math.ceil(seconds_left / 86400))
    local = expires_at.astimezone(ZoneInfo(settings.default_timezone))
    return f"{local:%d.%m.%Y} gacha ({days_left} kun qoldi)"


def plan_status_lines(overview: dict) -> list[str]:
    """Bosh ekran va Tariflar uchun: tarif faolmi, qachongacha, limitdan qanchasi ishlatilgan."""
    plan, usage, flags = overview["plan"], overview["usage"], overview["plan"]["flags"]
    usage_line = (
        f"   📊 Xizmatlar {usage['automations']}/{flags['scheduler_limit']} · "
        f"Akkauntlar {usage['accounts']}/{flags['account_limit']}"
    )
    if plan["expires_at"]:
        return [f"💎 Tarif: {plan['name']} ✅ faol", f"   ⏳ {expiry_text(plan['expires_at'])}", usage_line]
    return [f"💎 Tarif: {plan['name']} (pullik tarif yo'q)", usage_line]
