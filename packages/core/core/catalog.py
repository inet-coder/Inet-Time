"""Mini App'da ko'rsatiladigan xizmatlar katalogi. kind — frontend qaysi tahrirlagichni ochishini bildiradi."""

TEMPLATE_VARIABLES = [
    {"key": "{first_name}", "label": "Ism"},
    {"key": "{last_name}", "label": "Familiya"},
    {"key": "{name}", "label": "To'liq ism"},
    {"key": "{username}", "label": "Username"},
    {"key": "{time}", "label": "Soat"},
    {"key": "{date}", "label": "Sana"},
    {"key": "{weekday}", "label": "Hafta kuni"},
    {"key": "{day}", "label": "Kun"},
    {"key": "{month}", "label": "Oy"},
    {"key": "{year}", "label": "Yil"},
]

SERVICE_CATALOG = [
    {
        "code": "clock_name",
        "kind": "template",
        "field": "name",
        "title": "Soat ismda",
        "icon": "🕐",
        "desc": "Ismingiz yonida joriy vaqt, har daqiqada yangilanadi",
        "flag": None,
        "default": "{first_name} {time}",
        "presets": ["{first_name} {time}", "{first_name} | {time}", "{first_name} 🕐 {time}", "{first_name} · {time} · {weekday}"],
    },
    {
        "code": "auto_bio",
        "kind": "template",
        "field": "bio",
        "title": "Avto bio",
        "icon": "📝",
        "desc": "Bio shablon bo'yicha yangilanib turadi",
        "flag": None,
        "default": "🕐 {time} · {weekday}",
        "presets": ["🕐 {time} · {weekday}", "📅 {date} · {weekday}", "☕️ Hozir soat {time}", "📍 Toshkent · {time}"],
    },
    {
        "code": "auto_name",
        "kind": "template",
        "field": "name",
        "title": "Avto ism",
        "icon": "✏️",
        "desc": "Ism shablon bo'yicha o'zgaradi",
        "flag": None,
        "default": "{first_name} | {weekday}",
        "presets": ["{first_name} | {weekday}", "{first_name} 📅 {date}", "{first_name} ✨"],
    },
    {
        "code": "online",
        "kind": "online",
        "field": "online",
        "title": "24/7 Online",
        "icon": "🟢",
        "desc": "Akkaunt doim «online» ko'rinadi",
        "flag": "online_service",
    },
    {
        "code": "playlist",
        "kind": "playlist",
        "field": "bio",
        "title": "Bio playlist",
        "icon": "🔁",
        "desc": "Bir nechta bio navbat bilan yoki tasodifiy almashadi",
        "flag": "playlist_service",
        "intervals": [600, 1800, 3600, 10800, 86400],
    },
    {
        "code": "schedule",
        "kind": "schedule",
        "field": "bio",
        "title": "Jadval",
        "icon": "🗓",
        "desc": "Bio yoki ism belgilangan vaqtlarda o'zgaradi",
        "flag": "schedule_service",
    },
    {
        "code": "emoji",
        "kind": "emoji",
        "field": "emoji_status",
        "title": "Emoji status",
        "icon": "😀",
        "desc": "Premium emoji status (faqat Telegram Premium akkauntlar)",
        "flag": "emoji_service",
        "intervals": [600, 3600, 10800, 86400],
    },
    {
        "code": "photo",
        "kind": "photo",
        "field": "photo",
        "title": "Rasm almashtirish",
        "icon": "🖼",
        "desc": "Profil rasmi navbat bilan almashadi",
        "flag": "photo_service",
        "intervals": [3600, 21600, 86400],
    },
    {
        "code": "ai_reply",
        "kind": "ai_reply",
        "field": "ai",
        "title": "AI avto-javob",
        "icon": "🤖",
        "desc": "Shaxsiy chatlarda siz nomingizdan AI javob beradi",
        "flag": "ai_service",
    },
    {
        "code": "stories",
        "kind": "stories",
        "field": "stories",
        "title": "Stories",
        "icon": "👀",
        "desc": "Istalgan odamning hikoyalarini ko'rish va yuklab olish",
        "flag": "stories_service",
    },
]

# Profil maydonini o'zgartirmaydigan xizmatlar — automation emas, alohida sozlanadi.
NON_AUTOMATION_KINDS = {"ai_reply", "stories"}

# Automation sifatida yoqiladigan xizmatlar (profil maydonini o'zgartiradi).
SERVICE_CODES = {s["code"] for s in SERVICE_CATALOG if s["kind"] not in NON_AUTOMATION_KINDS}
FIELD_LIMITS = {"name": 64, "bio": 70}
