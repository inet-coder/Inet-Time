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
    {"key": "{bday}", "label": "🎂 Tug'ilgan kun"},
    {"key": "{bday_days}", "label": "🎂 Necha kun qoldi"},
    {"key": "{age}", "label": "Yosh"},
    {"key": "{newyear_days}", "label": "🎄 Yangi yilgacha"},
    {"key": "{year_bar}", "label": "⏳ Yil ▓░"},
    {"key": "{year_percent}", "label": "Yil %"},
    {"key": "{weekend}", "label": "📆 Dam olishgacha"},
    {"key": "{daypart}", "label": "☀️ Xayrli tong/kech"},
]

# Bio playlist uchun tayyor to'plamlar — bir bosishda to'ldiriladi. Har matn ≤ 70 belgi (Telegram bio chegarasi).
PLAYLIST_PACKS = [
    {
        "code": "fun",
        "title": "😂 Hazil",
        "items": [
            "Wi-Fi paroli: avval salom bering 😏",
            "Bu bio hozircha yuklanmoqda... ⏳",
            "Dangasalik bo'yicha jahon chempioni 🏆",
            "Dushanbadan boshlayman. Qaysi dushanba — noma'lum 📅",
            "Aqlli ko'rinish uchun ko'zoynak taqqanman 🤓",
            "Oshni sevaman, oshga ham shuni ayting 🍚",
        ],
    },
    {
        "code": "coder",
        "title": "💻 Dasturchi",
        "items": [
            "while (alive) { code(); coffee++; } ☕️",
            "Ishlayapti — tegmang! 🙏",
            "Bug emas, bu feature 🐞✨",
            "git commit -m 'oxirgi tuzatish' (7-marta) 😅",
            "Kodim ishladi, lekin nega — bilmayman 🤷‍♂️",
            "Stack Overflow — ikkinchi uyim 🏠",
        ],
    },
    {
        "code": "mood",
        "title": "☕️ Kayfiyat",
        "items": [
            "Hozir: qahva + musiqa 🎧☕️",
            "Bugun ajoyib kun bo'ladi ☀️",
            "Rejim: jim va samarali 🔕",
            "Kayfiyat: shokolad kerak 🍫",
            "Yomg'ir, choy va kitob 🌧📖",
            "Hamma narsa yaxshi bo'ladi ✨",
        ],
    },
    {
        "code": "work",
        "title": "💼 Ish",
        "items": [
            "Hozir uchrashuvdaman, keyinroq yozaman 📞",
            "Loyiha ustida ishlayapman 🚀",
            "Dedlayn yaqin, men esa tinchman 😌",
            "Emaildan ko'ra Telegram tezroq ⚡️",
            "Ish vaqti: 9:00–18:00 🕘",
            "Bugun samarali kun 📈",
        ],
    },
    {
        "code": "student",
        "title": "🎓 Talaba",
        "items": [
            "Sessiya yaqin, uyqu uzoq 📚😴",
            "Konspekt kimda bor? 🙋",
            "Imtihondan keyin odam bo'laman 🎓",
            "Stipendiya kuni — bayram kuni 💸",
            "Kutubxonada yashayapman 🏛",
            "Bilim — kuch, uyqu — undan ham kuchli 😴",
        ],
    },
    {
        "code": "sport",
        "title": "🏋️ Sport",
        "items": [
            "Zalga ketdim, qaytmasam — oqsil ichib qolganman 💪",
            "Bugun oyoq kuni 🦵",
            "Yugurish: 5 km ✅ Qolgani: dangasalik ❌",
            "No pain, no gain 🔥",
            "Futbol — hayotim ⚽️",
            "Ertaga albatta boshlayman... ertaga 🏃",
        ],
    },
    {
        "code": "wise",
        "title": "🌙 Hikmat",
        "items": [
            "Sabr — eng yaxshi javob 🌿",
            "Kichik qadam ham oldinga qadam 👣",
            "Bugun qilgan ishing ertangi kuningdir ✨",
            "Jimlik ham javob 🤍",
            "Kim harakat qilsa, o'sha yetadi 🏔",
            "Har kun — yangi imkoniyat 🌅",
        ],
    },
    {
        "code": "food",
        "title": "🍔 Ovqat",
        "items": [
            "Palov bo'lsa chaqiring 🍚",
            "Parhez dushanbadan (qaysi yil — aniq emas) 🥗",
            "Somsa yeyapman, bezovta qilmang 🥟",
            "Choy + non = baxt ☕️🍞",
            "Ovqat haqida gaplashsak — doim tayyorman 🍔",
            "Muzqaymoq — sevgi tili 🍦",
        ],
    },
    {
        "code": "live",
        "title": "⏳ Jonli",
        "items": [
            "{daypart} · {time}",
            "📆 {weekday} · {date}",
            "🎄 Yangi yilga {newyear_days} kun",
            "⏳ {year}: {year_bar} {year_percent}%",
            "📆 {weekend}",
            "🕐 Toshkentda hozir {time}",
        ],
    },
]

# 🎂 kartasidagi tayyor shablonlar (bio uchun). Tug'ilgan kun kiritilgan bo'lishi kerak.
BIRTHDAY_TEMPLATES = [
    "🎂 {bday}",
    "🎈 {bday_days} kundan keyin tug'ilgan kunim!",
    "🎂 {age} yosh · keyingisiga {bday_days} kun",
    "🥳 {bday} · {date}",
    "🎁 Sovg'alar qabul qilinadi: {bday_days} kun qoldi",
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
        "presets": [
            "🕐 {time} · {weekday}",
            "📅 {date} · {weekday}",
            "{daypart} · {time}",
            "📍 Toshkent · {time}",
            "🎄 Yangi yilga {newyear_days} kun",
            "⏳ {year}: {year_bar} {year_percent}%",
            "📆 {weekend} · {time}",
            "🎂 {bday}",
        ],
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
        "packs": PLAYLIST_PACKS,
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

SERVICE_CATALOG += [
    {
        "code": "birthday",
        "kind": "birthday",
        "field": "bio",
        "title": "Tug'ilgan kun",
        "icon": "🎂",
        "desc": "Bio'da tug'ilgan kuningizgacha qancha qolgani",
        "flag": None,
    },
    {
        "code": "presence",
        "kind": "presence",
        "field": "presence",
        "title": "Faollik holati",
        "icon": "👁",
        "desc": "Onlayn, «yaqinda onlayn edi» yoki aniq vaqt",
        "flag": None,
    },
]

# Profil maydonini o'zgartirmaydigan (yoki o'z oynasi bor) xizmatlar — automation sifatida yoqilmaydi.
NON_AUTOMATION_KINDS = {"ai_reply", "stories", "birthday", "presence"}

# Automation sifatida yoqiladigan xizmatlar (profil maydonini o'zgartiradi).
SERVICE_CODES = {s["code"] for s in SERVICE_CATALOG if s["kind"] not in NON_AUTOMATION_KINDS}
FIELD_LIMITS = {"name": 64, "bio": 70}
