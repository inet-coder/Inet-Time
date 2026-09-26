"""Botda ko'rsatiladigan xizmatlar — har biri bitta tugma bilan yoqiladi."""

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
