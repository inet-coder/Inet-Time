"""Tayyor tizimlar galereyasi: AI'siz, 30 soniyada ishlaydigan bot.

Har bir tizim — reja (bo'limlar) + tayyor matnlar. Matnlardagi {biz} {biz_tel} {biz_manzil} {biz_vaqt}... — global
o'zgaruvchilar: egasi bot ichidagi sozlash ustasida bir marta javob beradi, hamma matnlarga o'zi joylashadi
(keyin ham /admin → Sozlamalar → O'zgaruvchilar orqali o'zgartiriladi). Tizim bot_ai.compile_plan orqali yig'iladi —
AI quradigan botlar bilan bir xil sifat va navigatsiya."""

from core import bot_ai

COMMON_VARS = [
    {"key": "biz", "label": "Bot/biznes nomi", "default": "Bizning biznes", "scope": "global"},
    {"key": "biz_tel", "label": "Telefon", "default": "+998 90 123 45 67", "scope": "global"},
    {"key": "biz_manzil", "label": "Manzil", "default": "Toshkent shahri", "scope": "global"},
    {"key": "biz_vaqt", "label": "Ish vaqti", "default": "Har kuni 09:00–21:00", "scope": "global"},
]
COMMON_STEPS = [
    {"key": "biz", "label": "🏷 Biznesingiz (botingiz) nomi nima?", "example": "Gul Saroyi"},
    {"key": "biz_tel", "label": "📞 Mijozlar qaysi telefon raqamga qo'ng'iroq qilsin?", "example": "+998 90 123 45 67"},
    {"key": "biz_manzil", "label": "📍 Manzilingiz (shahar, ko'cha)?", "example": "Toshkent, Chilonzor 5"},
    {"key": "biz_vaqt", "label": "🕘 Ish vaqtingiz?", "example": "Har kuni 09:00–21:00"},
]

CONTACTS = (
    "<b>📍 Aloqa</b>\n\n📞 {biz_tel}\n📍 {biz_manzil}\n🕘 {biz_vaqt}\n\nSavolingiz bo'lsa — «💬 Yozish» tugmasi orqali yozing, tez javob beramiz."
)
MAP = [[{"text": "🗺 Xaritada ochish", "url": "https://maps.google.com/?q={biz_manzil}"}]]


def _sec(id_, parent, title, kind, **extra):
    return {"id": id_, "parent": parent, "title": title, "kind": kind, "purpose": title, **extra}


def _post(text, buttons=None):
    return {"posts": [{"text": text, "buttons": buttons or []}]}


# Tizim: icon, title, desc, style, sections, content, fallback, setup (qo'shimcha qadamlar), variables, referral
SYSTEMS: dict[str, dict] = {
    "sys_shop": {
        "icon": "🛍",
        "title": "Onlayn do'kon",
        "desc": "Katalog, savat, buyurtmalar, yetkazish — mahsulotlarni rasm bilan botning o'zida qo'shasiz",
        "style": "hybrid",
        "sections": [
            _sec("start", None, "🏠 Bosh menyu", "menu"),
            _sec("catalog", "start", "🛍 Katalog", "catalog"),
            _sec("cart", "start", "🛒 Savat", "cart"),
            _sec("orders", "start", "📦 Buyurtmalarim", "orders"),
            _sec("about", "start", "ℹ️ Biz haqimizda", "info"),
            _sec("contacts", "start", "📍 Aloqa", "contacts"),
            _sec("chat", "start", "💬 Yozish", "feedback"),
        ],
        "content": {
            "start": _post("Assalomu alaykum, {name}! 👋\n\n<b>{biz}</b> — onlayn do'konimizga xush kelibsiz.\n\n🛍 Katalogdan tanlang, 🛒 savatga qo'shing va buyurtma bering — tez va oson!"),
            "catalog": _post("<b>🛍 Katalog</b>\n\nKerakli mahsulotni tanlang 👇"),
            "about": _post("<b>ℹ️ {biz}</b>\n\nSifatli mahsulotlar, qulay narxlar va tez yetkazib berish.\n\n✅ Buyurtmani botdan bering\n🚚 Yetkazib berish\n📞 {biz_tel}"),
            "contacts": _post(CONTACTS, MAP),
        },
        "fallback": "Menyudan tanlang 👇",
        "auto": [{"trigger": "cart", "hours": 3, "text": "🛒 {name}, savatingizda <b>{cart_count}</b> ta mahsulot qoldi ({cart_total}).\nBuyurtmani yakunlang — biz tayyormiz! 👇", "section": "cart"}],
    },
    "sys_cafe": {
        "icon": "🍽",
        "title": "Kafe / restoran",
        "desc": "Menyu, savat, yetkazib berish, stol band qilish, aksiyalar",
        "style": "hybrid",
        "sections": [
            _sec("start", None, "🏠 Bosh menyu", "menu"),
            _sec("menu", "start", "🍽 Menyu", "catalog", layout="cards"),
            _sec("cart", "start", "🛒 Savat", "cart"),
            _sec("orders", "start", "📦 Buyurtmalarim", "orders"),
            _sec("book", "start", "🪑 Stol band qilish", "form", fields=[
                {"key": "ism", "label": "👤 Ismingiz?", "type": "text"},
                {"key": "telefon", "label": "📱 Telefon raqamingiz?", "type": "phone"},
                {"key": "sana", "label": "📅 Qaysi kun va soatga? (masalan: 25-may, 19:00)", "type": "text"},
                {"key": "kishi", "label": "👥 Necha kishi?", "type": "number"},
            ]),
            _sec("promo", "start", "🎁 Aksiyalar", "info"),
            _sec("contacts", "start", "📍 Manzil", "contacts"),
            _sec("chat", "start", "💬 Yozish", "feedback"),
        ],
        "content": {
            "start": _post("Assalomu alaykum, {name}! 👋\n\n<b>{biz}</b>ga xush kelibsiz! 🍽\n\nMenyuni ko'ring, buyurtma bering yoki stol band qiling."),
            "menu": _post("<b>🍽 Menyu</b>\n\nTaomlarni tanlang va savatga qo'shing 👇"),
            "book": _post("<b>🪑 Stol band qilish</b>\n\n4 ta qisqa savolga javob bering — administrator sizga qo'ng'iroq qilib tasdiqlaydi.", []),
            "promo": _post("<b>🎁 Aksiyalar</b>\n\nHozircha maxsus aksiya yo'q — yangiliklarni kuzatib boring! Egasi bu matnni «✏️ Botni tahrirlash» orqali o'zgartiradi."),
            "contacts": _post(CONTACTS, MAP),
        },
        "done": {"book": "✅ Rahmat, {ism}! Arizangiz qabul qilindi — tez orada {telefon} raqamingizga qo'ng'iroq qilamiz."},
        "auto": [{"trigger": "cart", "hours": 2, "text": "🍽 {name}, savatingizda <b>{cart_count}</b> ta taom qoldi. Issiq-issiq yetkazamiz! 👇", "section": "cart"}],
    },
    "sys_booking": {
        "icon": "📅",
        "title": "Yozilish (salon, klinika, servis)",
        "desc": "Xizmatlar va narxlar, qabulga yozilish formasi, savollar — navbatni egasi tasdiqlaydi",
        "style": "hybrid",
        "sections": [
            _sec("start", None, "🏠 Bosh menyu", "menu"),
            _sec("services", "start", "✨ Xizmatlar", "info"),
            _sec("book", "start", "📅 Yozilish", "booking"),
            _sec("prices", "start", "💰 Narxlar", "info"),
            _sec("faq", "start", "❓ Savol-javob", "faq"),
            _sec("contacts", "start", "📍 Manzil", "contacts"),
            _sec("chat", "start", "💬 Yozish", "feedback"),
        ],
        "content": {
            "start": _post("Assalomu alaykum, {name}! 👋\n\n<b>{biz}</b> — qabulga onlayn yoziling, navbatsiz va qulay.\n\n📅 «Yozilish» tugmasini bosing — 4 ta savol, 1 daqiqa."),
            "services": _post("<b>✨ Xizmatlarimiz</b>\n\n1️⃣ Birinchi xizmat\n2️⃣ Ikkinchi xizmat\n3️⃣ Uchinchi xizmat\n\n<i>Egasi: «✏️ Botni tahrirlash» orqali xizmatlaringizni yozing.</i>"),
            "book": _post("<b>📅 Qabulga yozilish</b>\n\nXizmat, kun va qulay vaqtni tanlang — administrator tasdiqlaydi va oldindan eslatamiz."),
            "prices": _post("<b>💰 Narxlar</b>\n\nNarxlar ro'yxati shu yerda bo'ladi.\n\n<i>Egasi: «✏️ Botni tahrirlash» orqali narxlarni yozing.</i>"),
            "faq": _post("<b>❓ Ko'p so'raladigan savollar</b>\n\n<b>Qanday yozilaman?</b>\n«📅 Yozilish» tugmasi orqali.\n\n<b>Vaqtni o'zgartirsam bo'ladimi?</b>\nHa, {biz_tel} ga qo'ng'iroq qiling.\n\n<b>Ish vaqtingiz?</b>\n{biz_vaqt}"),
            "contacts": _post(CONTACTS, MAP),
        },
        "booking": {"services": [{"title": "Birinchi qabul", "minutes": 30, "price": 0}], "hours": "Du-Sha 09:00-18:00\nYa yopiq", "confirm": "manual"},
    },
    "sys_channel": {
        "icon": "📢",
        "title": "Kanal yordamchisi",
        "desc": "Majburiy obuna, do'stlarni taklif qilish, murojaatlar — kanal egalari uchun",
        "style": "reply",
        "sections": [
            _sec("start", None, "🏠 Bosh menyu", "menu"),
            _sec("about", "start", "ℹ️ Kanal haqida", "info"),
            _sec("invite", "start", "🎁 Do'st taklif qilish", "referral"),
            _sec("profile", "start", "👤 Mening ballarim", "profile"),
            _sec("chat", "start", "💬 Adminga yozish", "feedback"),
        ],
        "content": {
            "start": _post("Assalomu alaykum, {name}! 👋\n\n<b>{biz}</b> botiga xush kelibsiz. Kanalimizdagi eng foydali materiallar — shu yerda."),
            "about": _post("<b>ℹ️ {biz}</b>\n\n📢 Kanalimiz: {kanal}\n\nHar kuni foydali kontent, yangiliklar va aksiyalar."),
            "invite": _post("<b>🎁 Do'stlaringizni taklif qiling</b>\n\nHar bir taklif uchun <b>ball</b> olasiz.\n\n🔗 Havolangiz:\n{ref_link}\n\n👥 Taklif qilganlaringiz: <b>{ref_count}</b>"),
            "profile": _post("<b>👤 Profilingiz</b>\n\n💎 Ballaringiz: <b>{ball}</b>\n👥 Takliflar: <b>{ref_count}</b>"),
        },
        "variables": [
            {"key": "kanal", "label": "Kanal havolasi", "default": "https://t.me/", "scope": "global"},
            {"key": "ball", "label": "Ball", "default": "0", "scope": "user"},
        ],
        "referral": {"enabled": True, "reward": 5, "var": "ball"},
        "auto": [{"trigger": "inactive", "hours": 168, "text": "👋 {name}, sizni sog'indik! Kanalimizda yangi materiallar bor — bir ko'z tashlang.", "section": "about"}],
        "steps": [
            {"key": "biz", "label": "🏷 Kanalingiz (botingiz) nomi?", "example": "Foydali maslahatlar"},
            {"key": "kanal", "label": "📢 Kanalingiz havolasi?", "example": "https://t.me/mening_kanalim"},
        ],
        "use_common": False,
    },
    "sys_support": {
        "icon": "🎫",
        "title": "Yordam xizmati",
        "desc": "Har bir xabar sizga keladi, «Reply» bilan javob berasiz; tez-tez so'ralgan savollar",
        "style": "reply",
        "sections": [
            _sec("start", None, "🏠 Bosh menyu", "menu"),
            _sec("faq", "start", "❓ Savol-javob", "faq"),
            _sec("contacts", "start", "📞 Aloqa", "contacts"),
            _sec("chat", "start", "✍️ Savol yozish", "feedback"),
        ],
        "content": {
            "start": _post("Assalomu alaykum, {name}! 👋\n\n<b>{biz}</b> yordam xizmati. Savolingizni shu yerga yozing — mas'ul xodim javob beradi.\n\n⏱ Javob vaqti: {biz_vaqt}"),
            "faq": _post("<b>❓ Ko'p so'raladigan savollar</b>\n\n<b>Qancha vaqtda javob berasiz?</b>\nIsh vaqtida (<i>{biz_vaqt}</i>) tez.\n\n<b>Telefonda bog'lansa bo'ladimi?</b>\nHa: {biz_tel}"),
            "contacts": _post(CONTACTS, MAP),
        },
        "forward_all": True,
    },
    "sys_apply": {
        "icon": "📝",
        "title": "Ariza va ro'yxatga olish",
        "desc": "Tadbir, vakansiya, tanlov uchun ariza — javoblar sizga keladi va CSV'ga yuklanadi",
        "style": "reply",
        "sections": [
            _sec("start", None, "🏠 Bosh menyu", "menu"),
            _sec("about", "start", "ℹ️ Batafsil", "info"),
            _sec("apply", "start", "📝 Ariza topshirish", "form", fields=[
                {"key": "ism", "label": "👤 Ism-familiyangiz?", "type": "text"},
                {"key": "telefon", "label": "📱 Telefon raqamingiz?", "type": "phone"},
                {"key": "yosh", "label": "🎂 Yoshingiz?", "type": "number"},
                {"key": "izoh", "label": "✍️ O'zingiz haqingizda qisqacha yozing", "type": "text"},
            ]),
            _sec("faq", "start", "❓ Savollar", "faq"),
            _sec("contacts", "start", "📍 Aloqa", "contacts"),
            _sec("chat", "start", "💬 Yozish", "feedback"),
        ],
        "content": {
            "start": _post("Assalomu alaykum, {name}! 👋\n\n<b>{biz}</b> uchun ariza qabul qilinmoqda.\n\n📝 «Ariza topshirish» tugmasini bosing — 4 ta savol."),
            "about": _post("<b>ℹ️ Batafsil</b>\n\nShartlar, muddatlar va talablar shu yerda.\n\n<i>Egasi: «✏️ Botni tahrirlash» orqali yozing.</i>"),
            "apply": _post("<b>📝 Ariza</b>\n\nQisqa savollarga javob bering — arizangiz tashkilotchilarga yetkaziladi."),
            "faq": _post("<b>❓ Savollar</b>\n\n<b>Natija qachon ma'lum bo'ladi?</b>\nSiz bilan {biz_tel} orqali bog'lanamiz."),
            "contacts": _post(CONTACTS, MAP),
        },
        "done": {"apply": "✅ Rahmat, {ism}! Arizangiz qabul qilindi. Natijani {telefon} orqali xabar qilamiz."},
    },
    "sys_bonus": {
        "icon": "🎁",
        "title": "Bonus va referal dasturi",
        "desc": "Do'st taklif qilish, ball yig'ish, kunlik bonus, mukofotlar",
        "style": "hybrid",
        "sections": [
            _sec("start", None, "🏠 Bosh menyu", "menu"),
            _sec("profile", "start", "👤 Mening ballarim", "profile"),
            _sec("invite", "start", "👥 Do'st taklif qilish", "referral"),
            _sec("rules", "start", "📜 Qoidalar", "info"),
            _sec("prizes", "start", "🏆 Mukofotlar", "info"),
            _sec("chat", "start", "💬 Yozish", "feedback"),
        ],
        "content": {
            "start": _post("Assalomu alaykum, {name}! 👋\n\n<b>{biz}</b> bonus dasturi. Do'stlaringizni taklif qiling, ball yig'ing va mukofot oling! 🎁"),
            "profile": _post("<b>👤 Sizning hisobingiz</b>\n\n💎 Ballar: <b>{ball}</b>\n👥 Taklif qilinganlar: <b>{ref_count}</b>"),
            "invite": _post("<b>👥 Do'stlarni taklif qiling</b>\n\nHar bir do'stingiz botga kirsa — <b>10 ball</b>!\n\n🔗 Havolangiz:\n{ref_link}"),
            "rules": _post("<b>📜 Qoidalar</b>\n\n1️⃣ Havolangizni do'stlarga yuboring\n2️⃣ Do'stingiz botni ishga tushirsa — ball olasiz\n3️⃣ Ballarni mukofotga almashtiring"),
            "prizes": _post("<b>🏆 Mukofotlar</b>\n\n50 ball — birinchi sovg'a\n100 ball — ikkinchi sovg'a\n\n<i>Egasi: «✏️ Botni tahrirlash» orqali o'z mukofotlaringizni yozing.</i>"),
        },
        "variables": [{"key": "ball", "label": "Ball", "default": "0", "scope": "user"}],
        "referral": {"enabled": True, "reward": 10, "var": "ball"},
        "steps": [{"key": "biz", "label": "🏷 Dastur (botingiz) nomi?", "example": "Mening bonuslarim"}],
        "use_common": False,
    },
    "sys_course": {
        "icon": "🎓",
        "title": "Kurs va o'quv markazi",
        "desc": "Kurslar, jadval, narxlar, ro'yxatdan o'tish, savollar",
        "style": "hybrid",
        "sections": [
            _sec("start", None, "🏠 Bosh menyu", "menu"),
            _sec("courses", "start", "📚 Kurslar", "info"),
            _sec("schedule", "start", "🗓 Jadval", "info"),
            _sec("prices", "start", "💰 Narxlar", "info"),
            _sec("join", "start", "📝 Ro'yxatdan o'tish", "form", fields=[
                {"key": "ism", "label": "👤 Ismingiz?", "type": "text"},
                {"key": "telefon", "label": "📱 Telefon raqamingiz?", "type": "phone"},
                {"key": "kurs", "label": "📚 Qaysi kurs qiziqtiradi?", "type": "text"},
            ]),
            _sec("faq", "start", "❓ Savol-javob", "faq"),
            _sec("contacts", "start", "📍 Manzil", "contacts"),
            _sec("chat", "start", "💬 Yozish", "feedback"),
        ],
        "content": {
            "start": _post("Assalomu alaykum, {name}! 👋\n\n<b>{biz}</b> — bilim va kelajak sari birinchi qadam. Kurslar, jadval va narxlarni ko'ring, ro'yxatdan o'ting."),
            "courses": _post("<b>📚 Kurslarimiz</b>\n\n1️⃣ Birinchi kurs\n2️⃣ Ikkinchi kurs\n\n<i>Egasi: «✏️ Botni tahrirlash» orqali kurslaringizni yozing.</i>"),
            "schedule": _post("<b>🗓 Dars jadvali</b>\n\nDushanba, chorshanba, juma — 18:00\n\n<i>Egasi: matnni o'zgartiring.</i>"),
            "prices": _post("<b>💰 Narxlar</b>\n\nOylik to'lov va chegirmalar shu yerda."),
            "join": _post("<b>📝 Ro'yxatdan o'tish</b>\n\n3 ta savol — menejer siz bilan bog'lanadi."),
            "faq": _post("<b>❓ Savol-javob</b>\n\n<b>Sinov darsi bormi?</b>\n{biz_tel} ga qo'ng'iroq qiling.\n\n<b>Manzil?</b>\n{biz_manzil}"),
            "contacts": _post(CONTACTS, MAP),
        },
        "done": {"join": "✅ Rahmat, {ism}! {kurs} bo'yicha menejerimiz {telefon} raqamingizga tez orada bog'lanadi."},
    },
    "sys_quiz": {
        "icon": "🧠",
        "title": "Viktorina va o'yin boti",
        "desc": "Savol-javob viktorinasi, reyting, kunlik bonus, do'st taklif qilish — kanal va jamoalar uchun",
        "style": "hybrid",
        "sections": [
            _sec("start", None, "🏠 Bosh menyu", "menu"),
            _sec("quiz", "start", "🧠 Viktorina", "quiz", questions=[
                {"q": "O'zbekiston poytaxti qaysi shahar?", "options": ["Samarqand", "Toshkent", "Buxoro"], "answer": 1, "explain": "Toshkent — 2000 yildan ortiq tarixga ega shahar."},
                {"q": "Quyoshga eng yaqin sayyora qaysi?", "options": ["Venera", "Yer", "Merkuriy", "Mars"], "answer": 2, "explain": ""},
                {"q": "Bir yilda necha oy bor?", "options": ["10", "12", "13"], "answer": 1, "explain": ""},
                {"q": "Suvning kimyoviy formulasi qaysi?", "options": ["CO2", "H2O", "O2"], "answer": 1, "explain": "Ikki vodorod va bir kislorod atomi."},
            ]),
            _sec("top", "start", "🏆 Reyting", "top"),
            _sec("bonus", "start", "🎁 Kunlik bonus", "bonus"),
            _sec("invite", "start", "👥 Do'st taklif qilish", "referral"),
            _sec("chat", "start", "💬 Yozish", "feedback"),
        ],
        "content": {
            "start": _post("Assalomu alaykum, {name}! 👋\n\n<b>{biz}</b> — o'ynang, ball yig'ing va reytingda yuqoriga chiqing! 🏆\n\n💎 Sizning ballaringiz: <b>{ball}</b>"),
            "invite": _post("<b>👥 Do'stlarni taklif qiling</b>\n\nHar bir do'stingiz uchun <b>10 ball</b>!\n\n🔗 Havolangiz:\n{ref_link}\n\n👥 Takliflar: <b>{ref_count}</b>"),
        },
        "variables": [{"key": "ball", "label": "Ball", "default": "0", "scope": "user"}],
        "referral": {"enabled": True, "reward": 10, "var": "ball"},
        "bonus": {"points": 5, "streak_bonus": 1},
        "steps": [{"key": "biz", "label": "🏷 Botingiz nomi?", "example": "Bilimdonlar klubi"}],
        "use_common": False,
    },
    "sys_card": {
        "icon": "🏢",
        "title": "Vizitka (kompaniya, mutaxassis)",
        "desc": "Haqimizda, xizmatlar, portfolio, aloqa — oddiy va chiroyli tanishtiruv boti",
        "style": "reply",
        "sections": [
            _sec("start", None, "🏠 Bosh menyu", "menu"),
            _sec("about", "start", "ℹ️ Biz haqimizda", "info"),
            _sec("services", "start", "✨ Xizmatlar", "info"),
            _sec("works", "start", "🖼 Ishlarimiz", "info"),
            _sec("contacts", "start", "📍 Aloqa", "contacts"),
            _sec("chat", "start", "💬 Yozish", "feedback"),
        ],
        "content": {
            "start": _post("Assalomu alaykum, {name}! 👋\n\n<b>{biz}</b> — rasmiy botimizga xush kelibsiz."),
            "about": _post("<b>ℹ️ {biz}</b>\n\nBiz haqimizda qisqacha: tajriba, qadriyatlar, nima bilan ajralib turamiz.\n\n<i>Egasi: «✏️ Botni tahrirlash» orqali yozing.</i>"),
            "services": _post("<b>✨ Xizmatlar</b>\n\nXizmatlaringiz ro'yxati va narxlari shu yerda."),
            "works": _post("<b>🖼 Ishlarimiz</b>\n\nPortfolio: rasm, video va havolalarni «📝 Postlar muharriri» bilan qo'shing."),
            "contacts": _post(CONTACTS, MAP),
        },
    },
}


def build_system(code: str) -> dict | None:
    """Tizimni bot hujjatiga aylantiradi (validatsiyadan oldingi xom ko'rinish emas — tayyor, tekshirilgan)."""
    from core.botbuilder import validate_menu

    system = SYSTEMS.get(code)
    if system is None:
        return None
    use_common = system.get("use_common", True)
    plan = {
        "style": system["style"],
        "sections": [dict(s) for s in system["sections"]],
        "variables": (COMMON_VARS if use_common else COMMON_VARS[:1]) + system.get("variables", []),
        "referral": system.get("referral") or {},
        "booking": system.get("booking"),
        "auto": system.get("auto"),
        "bonus": system.get("bonus"),
    }
    content = {"sections": {}, "fallback": system.get("fallback", "Menyudan tanlang 👇")}
    for sid, data in system["content"].items():
        content["sections"][sid] = dict(data)
    for sid, text in (system.get("done") or {}).items():
        content["sections"].setdefault(sid, {"posts": []})["done_text"] = text
    doc = bot_ai.compile_plan(bot_ai._plan_fix(plan, 100), content)
    if system.get("forward_all"):
        doc["forward_all"] = True
    doc["system"] = code
    doc["setup"] = (COMMON_STEPS if use_common else []) + system.get("steps", [])
    # Global o'zgaruvchilar ustada so'raladiganlardan keyin ham sozlanadi — takrorlanuvchilar olib tashlanadi
    seen: set = set()
    doc["setup"] = [s for s in doc["setup"] if not (s["key"] in seen or seen.add(s["key"]))]
    doc, _, _ = bot_ai.lint(bot_ai.prepare(doc, {}))
    return validate_menu(doc, 100)


def systems_public() -> list[dict]:
    return [
        {"code": code, "icon": s["icon"], "title": s["title"], "desc": s["desc"], "pages": len(s["sections"]) - sum(1 for x in s["sections"] if x["kind"] == "feedback"), "system": True}
        for code, s in SYSTEMS.items()
    ]
