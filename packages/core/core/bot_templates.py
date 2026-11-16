"""Bot konstruktori uchun tayyor shablonlar.

Har bir shablon — to'liq ishlaydigan menyu (core/botbuilder.py formatida). Foydalanuvchi shablonni tanlab
bot yaratadi, keyin matn va tugmalarni o'z botining /admin panelidan o'zgartiradi.
Matnlardagi «...» — egasi to'ldirishi kerak bo'lgan joylar."""


def _b(text: str, action: str, target: str | None = None, url: str | None = None) -> dict:
    return {"text": text, "action": action, "target": target, "url": url}


def _p(page_id: str, title: str, text: str, buttons: list[list[dict]] | None = None, keyboard: str = "inline") -> dict:
    return {"id": page_id, "title": title, "text": text, "media_id": None, "keyboard": keyboard, "buttons": buttons or []}


BACK = _b("⬅️ Orqaga", "back")
HOME = _b("🏠 Bosh menyu", "home")
NAV = [BACK, HOME]


TEMPLATES: dict[str, dict] = {
    # --- Asosiy ---
    "blank": {
        "icon": "📄",
        "title": "Bo'sh bot",
        "desc": "Faqat salomlashish sahifasi — hammasini o'zingiz quring",
        "menu": {
            "start": "main",
            "pages": [
                _p(
                    "main",
                    "Bosh menyu",
                    "Assalomu alaykum, {name}! 👋\n\n{bot} ga xush kelibsiz.",
                    [[_b("✍️ Biz bilan bog'lanish", "feedback")]],
                )
            ],
        },
    },
    "support": {
        "icon": "💬",
        "title": "Qayta aloqa boti",
        "desc": "Har bir xabar sizga keladi, «Reply» bilan javob berasiz",
        "menu": {
            "start": "main",
            "pages": [
                _p(
                    "main",
                    "Salomlashish",
                    "Assalomu alaykum, {name}! 👋\n\n"
                    "Savol, taklif yoki murojaatingizni shu yerga yozing — xabaringiz mas'ul xodimga yetkaziladi "
                    "va javob shu chatga keladi.",
                )
            ],
            "forward_all": True,
            "feedback_done": "✅ Xabaringiz qabul qilindi. Tez orada javob beramiz.",
        },
    },
    # --- Savdo va xizmatlar ---
    "shop": {
        "icon": "🛍",
        "title": "Internet-do'kon",
        "desc": "Katalog, narxlar, yetkazib berish va buyurtma qabul qilish",
        "menu": {
            "start": "main",
            "pages": [
                _p(
                    "main",
                    "Bosh menyu",
                    "Assalomu alaykum, {name}! 🛍\n\nDo'konimizga xush kelibsiz. Bo'limni tanlang:",
                    [
                        [_b("📦 Katalog", "page", "catalog"), _b("💰 Narxlar", "page", "prices")],
                        [_b("🚚 Yetkazib berish", "page", "delivery"), _b("📍 Manzil", "page", "address")],
                        [_b("🛒 Buyurtma berish", "feedback")],
                    ],
                    "reply",
                ),
                _p(
                    "catalog",
                    "Katalog",
                    "📦 Katalog\n\nKategoriyani tanlang:",
                    [[_b("👕 Kiyimlar", "page", "cat1"), _b("👟 Poyabzal", "page", "cat2")], [BACK]],
                ),
                _p(
                    "cat1",
                    "Kiyimlar",
                    "👕 Kiyimlar\n\n• Futbolka — 120 000 so'm\n• Ko'ylak — 180 000 so'm\n\nBuyurtma uchun pastdagi tugmani bosing.",
                    [[_b("🛒 Buyurtma berish", "feedback")], NAV],
                ),
                _p(
                    "cat2",
                    "Poyabzal",
                    "👟 Poyabzal\n\n• Krossovka — 350 000 so'm\n• Tufli — 420 000 so'm",
                    [[_b("🛒 Buyurtma berish", "feedback")], NAV],
                ),
                _p("prices", "Narxlar", "💰 Narxlar ro'yxati:\n\n• ...\n• ..."),
                _p("delivery", "Yetkazib berish", "🚚 Toshkent bo'ylab — 1 kunda, viloyatlarga — 2–3 kunda.\nBuyurtma 500 000 so'mdan oshsa — bepul."),
                _p(
                    "address",
                    "Manzil",
                    "📍 Manzil: Toshkent sh., ...\n🕘 Ish vaqti: 9:00–20:00\n📞 Telefon: +998 ...",
                    [[_b("🗺 Xaritada ochish", "url", url="https://maps.google.com")]],
                ),
            ],
            "feedback_prompt": "🛒 Buyurtmangizni yozing: mahsulot nomi, soni, manzil va telefon raqamingiz.",
            "feedback_done": "✅ Buyurtmangiz qabul qilindi! Operator tez orada bog'lanadi.",
        },
    },
    "restaurant": {
        "icon": "🍽",
        "title": "Restoran / kafe",
        "desc": "Taomlar menyusi, yetkazib berish, joy band qilish",
        "menu": {
            "start": "main",
            "pages": [
                _p(
                    "main",
                    "Bosh menyu",
                    "Assalomu alaykum, {name}! 🍽\n\n... restoraniga xush kelibsiz.",
                    [
                        [_b("🍽 Menyu", "page", "menu")],
                        [_b("🚚 Yetkazib berish", "page", "delivery"), _b("📍 Manzil", "page", "address")],
                        [_b("🛒 Buyurtma berish", "feedback"), _b("🪑 Joy band qilish", "feedback")],
                    ],
                    "reply",
                ),
                _p(
                    "menu",
                    "Menyu",
                    "🍽 Menyu bo'limini tanlang:",
                    [[_b("🍲 Taomlar", "page", "food"), _b("🥤 Ichimliklar", "page", "drinks")], [_b("🍰 Shirinliklar", "page", "dessert")], [BACK]],
                ),
                _p("food", "Taomlar", "🍲 Taomlar\n\n• Osh — 45 000 so'm\n• Lag'mon — 38 000 so'm\n• Shashlik — 22 000 so'm", [[_b("🛒 Buyurtma berish", "feedback")], NAV]),
                _p("drinks", "Ichimliklar", "🥤 Ichimliklar\n\n• Choy — 8 000 so'm\n• Limonad — 18 000 so'm", [[_b("🛒 Buyurtma berish", "feedback")], NAV]),
                _p("dessert", "Shirinliklar", "🍰 Shirinliklar\n\n• Napoleon — 25 000 so'm\n• Chizkeyk — 30 000 so'm", [[_b("🛒 Buyurtma berish", "feedback")], NAV]),
                _p("delivery", "Yetkazib berish", "🚚 Yetkazib berish: 40–60 daqiqa.\nNarxi: 15 000 so'm, 200 000 so'mdan — bepul."),
                _p("address", "Manzil", "📍 Manzil: ...\n🕘 Ish vaqti: 10:00–23:00\n📞 +998 ..."),
            ],
            "feedback_prompt": "✍️ Buyurtma yoki band qilish uchun yozing: nima, nechta, qachon va telefon raqamingiz.",
            "feedback_done": "✅ Qabul qilindi! Administrator tez orada tasdiqlaydi.",
        },
    },
    "salon": {
        "icon": "💇",
        "title": "Go'zallik saloni",
        "desc": "Xizmatlar va narxlar, ustalar, qabulga yozilish",
        "menu": {
            "start": "main",
            "pages": [
                _p(
                    "main",
                    "Bosh menyu",
                    "Assalomu alaykum, {name}! 💇‍♀️\n\n... go'zallik saloniga xush kelibsiz.",
                    [
                        [_b("💅 Xizmatlar", "page", "services"), _b("👩‍🎨 Ustalarimiz", "page", "masters")],
                        [_b("📍 Manzil", "page", "address")],
                        [_b("📝 Qabulga yozilish", "feedback")],
                    ],
                    "reply",
                ),
                _p(
                    "services",
                    "Xizmatlar",
                    "💅 Xizmat turini tanlang:",
                    [[_b("💇 Soch", "page", "hair"), _b("💅 Manikyur", "page", "nails")], [_b("✨ Kosmetologiya", "page", "cosmo")], [BACK]],
                ),
                _p("hair", "Soch", "💇 Soch xizmatlari\n\n• Soch olish — 80 000 so'm\n• Bo'yash — 250 000 so'mdan", [[_b("📝 Yozilish", "feedback")], NAV]),
                _p("nails", "Manikyur", "💅 Manikyur\n\n• Klassik — 70 000 so'm\n• Gel-lak — 120 000 so'm", [[_b("📝 Yozilish", "feedback")], NAV]),
                _p("cosmo", "Kosmetologiya", "✨ Kosmetologiya\n\n• Yuz tozalash — 200 000 so'm\n• ...", [[_b("📝 Yozilish", "feedback")], NAV]),
                _p("masters", "Ustalarimiz", "👩‍🎨 Ustalarimiz:\n\n• ... — 10 yillik tajriba\n• ... — manikyur ustasi"),
                _p("address", "Manzil", "📍 Manzil: ...\n🕘 Ish vaqti: 9:00–21:00\n📞 +998 ..."),
            ],
            "feedback_prompt": "📝 Yozilish uchun: xizmat turi, qulay sana va vaqt, telefon raqamingiz.",
            "feedback_done": "✅ Arizangiz qabul qilindi! Administrator vaqtni tasdiqlash uchun bog'lanadi.",
        },
    },
    "clinic": {
        "icon": "🏥",
        "title": "Klinika",
        "desc": "Yo'nalishlar, shifokorlar, narxlar, qabulga yozilish",
        "menu": {
            "start": "main",
            "pages": [
                _p(
                    "main",
                    "Bosh menyu",
                    "Assalomu alaykum, {name}! 🏥\n\n... klinikasining rasmiy botiga xush kelibsiz.",
                    [
                        [_b("🩺 Yo'nalishlar", "page", "deps"), _b("💰 Narxlar", "page", "prices")],
                        [_b("📍 Manzil va ish vaqti", "page", "address")],
                        [_b("📝 Qabulga yozilish", "feedback")],
                    ],
                    "reply",
                ),
                _p(
                    "deps",
                    "Yo'nalishlar",
                    "🩺 Yo'nalishni tanlang:",
                    [[_b("Terapevt", "page", "therapist"), _b("Stomatolog", "page", "dentist")], [_b("Pediatr", "page", "pediatr")], [BACK]],
                ),
                _p("therapist", "Terapevt", "👨‍⚕️ Terapevt\n\nShifokor: ...\nQabul: Du–Ju, 9:00–15:00\nKonsultatsiya: 150 000 so'm", [[_b("📝 Yozilish", "feedback")], NAV]),
                _p("dentist", "Stomatolog", "🦷 Stomatolog\n\nShifokor: ...\nQabul: Du–Sha, 10:00–18:00", [[_b("📝 Yozilish", "feedback")], NAV]),
                _p("pediatr", "Pediatr", "👶 Pediatr\n\nShifokor: ...\nQabul: Du–Ju, 9:00–14:00", [[_b("📝 Yozilish", "feedback")], NAV]),
                _p("prices", "Narxlar", "💰 Asosiy xizmatlar narxi:\n\n• Konsultatsiya — ...\n• UZI — ...\n• Tahlillar — ..."),
                _p("address", "Manzil", "📍 Manzil: ...\n🕘 Ish vaqti: Du–Sha, 8:00–18:00\n📞 +998 ..."),
            ],
            "feedback_prompt": "📝 Qabulga yozilish uchun: ism-familiya, yo'nalish, qulay kun va telefon raqamingiz.",
            "feedback_done": "✅ Arizangiz qabul qilindi. Registratura siz bilan bog'lanadi.",
        },
    },
    "auto": {
        "icon": "🚗",
        "title": "Avtoservis",
        "desc": "Xizmatlar, narxlar, servisga yozilish",
        "menu": {
            "start": "main",
            "pages": [
                _p(
                    "main",
                    "Bosh menyu",
                    "Assalomu alaykum, {name}! 🚗\n\n... avtoservisiga xush kelibsiz.",
                    [
                        [_b("🔧 Xizmatlar", "page", "services"), _b("📍 Manzil", "page", "address")],
                        [_b("📝 Servisga yozilish", "feedback")],
                    ],
                    "reply",
                ),
                _p(
                    "services",
                    "Xizmatlar",
                    "🔧 Xizmatlar va narxlar:\n\n• Moy almashtirish — 50 000 so'mdan\n• Diagnostika — 100 000 so'm\n• Shinomontaj — 40 000 so'mdan\n• Kuzov ta'miri — kelishilgan holda",
                    [[_b("📝 Yozilish", "feedback")], [BACK]],
                ),
                _p("address", "Manzil", "📍 Manzil: ...\n🕘 Ish vaqti: 8:00–20:00\n📞 +998 ..."),
            ],
            "feedback_prompt": "📝 Avtomobil rusumi, kerakli xizmat, qulay vaqt va telefon raqamingizni yozing.",
            "feedback_done": "✅ Arizangiz qabul qilindi. Usta vaqtni tasdiqlash uchun bog'lanadi.",
        },
    },
    "realty": {
        "icon": "🏠",
        "title": "Ko'chmas mulk agentligi",
        "desc": "Sotuv va ijara e'lonlari, mulk joylashtirish arizasi",
        "menu": {
            "start": "main",
            "pages": [
                _p(
                    "main",
                    "Bosh menyu",
                    "Assalomu alaykum, {name}! 🏠\n\n... ko'chmas mulk agentligi.",
                    [
                        [_b("🏢 Sotuvda", "page", "sale"), _b("🔑 Ijaraga", "page", "rent")],
                        [_b("📤 Mulkimni joylashtirish", "feedback")],
                        [_b("📞 Aloqa", "page", "contact")],
                    ],
                    "reply",
                ),
                _p(
                    "sale",
                    "Sotuvda",
                    "🏢 Sotuvdagi obyektlar:",
                    [[_b("Kvartiralar", "page", "flats"), _b("Hovli uylar", "page", "houses")], [BACK]],
                ),
                _p("flats", "Kvartiralar", "🏢 Kvartiralar\n\n• 2 xonali, Chilonzor — $45 000\n• 3 xonali, Yunusobod — $68 000", [[_b("📞 Ko'rishga yozilish", "feedback")], NAV]),
                _p("houses", "Hovli uylar", "🏡 Hovli uylar\n\n• 6 sotix, ... — $90 000", [[_b("📞 Ko'rishga yozilish", "feedback")], NAV]),
                _p("rent", "Ijaraga", "🔑 Ijaraga beriladigan obyektlar:\n\n• 1 xonali, ... — $350/oy\n• ...", [[_b("📞 Bog'lanish", "feedback")], [BACK]]),
                _p("contact", "Aloqa", "📞 Telefon: +998 ...\n📍 Ofis: ..."),
            ],
            "feedback_prompt": "✍️ Obyekt haqida yozing: turi, manzili, narxi va telefon raqamingiz.",
            "feedback_done": "✅ Qabul qilindi! Agentimiz siz bilan bog'lanadi.",
        },
    },
    "travel": {
        "icon": "✈️",
        "title": "Turizm agentligi",
        "desc": "Turlar, viza, aviachiptalar, ariza qoldirish",
        "menu": {
            "start": "main",
            "pages": [
                _p(
                    "main",
                    "Bosh menyu",
                    "Assalomu alaykum, {name}! ✈️\n\n... turizm agentligi — sayohatingizni biz rejalashtiramiz.",
                    [
                        [_b("🌍 Turlar", "page", "tours"), _b("🛂 Viza", "page", "visa")],
                        [_b("🎫 Aviachiptalar", "page", "tickets")],
                        [_b("📝 Ariza qoldirish", "feedback")],
                    ],
                    "reply",
                ),
                _p(
                    "tours",
                    "Turlar",
                    "🌍 Yo'nalishni tanlang:",
                    [[_b("🇹🇷 Turkiya", "page", "turkey"), _b("🇦🇪 BAA", "page", "uae")], [_b("🏔 O'zbekiston bo'ylab", "page", "local")], [BACK]],
                ),
                _p("turkey", "Turkiya", "🇹🇷 Turkiya, Antaliya\n\n7 kecha, 5* mehmonxona, hammasi kiritilgan — $750 dan", [[_b("📝 Band qilish", "feedback")], NAV]),
                _p("uae", "BAA", "🇦🇪 Dubay\n\n5 kecha, 4* mehmonxona — $820 dan", [[_b("📝 Band qilish", "feedback")], NAV]),
                _p("local", "Ichki turizm", "🏔 Samarqand–Buxoro–Xiva, 5 kun — 3 500 000 so'mdan", [[_b("📝 Band qilish", "feedback")], NAV]),
                _p("visa", "Viza", "🛂 Viza xizmati: Shengen, AQSh, Buyuk Britaniya va boshqalar.\nHujjatlar ro'yxati uchun ariza qoldiring.", [[_b("📝 Ariza qoldirish", "feedback")], [BACK]]),
                _p("tickets", "Aviachiptalar", "🎫 Istalgan yo'nalishga aviachiptalar. Yo'nalish va sanani yozing — eng arzon variantni topamiz.", [[_b("📝 So'rov yuborish", "feedback")], [BACK]]),
            ],
            "feedback_prompt": "📝 Yo'nalish, sanalar, necha kishi va telefon raqamingizni yozing.",
            "feedback_done": "✅ Arizangiz qabul qilindi! Menejer tez orada bog'lanadi.",
        },
    },
    # --- Ta'lim va tadbirlar ---
    "edu": {
        "icon": "🎓",
        "title": "O'quv markazi",
        "desc": "Kurslar, narxlar, ro'yxatdan o'tish",
        "menu": {
            "start": "main",
            "pages": [
                _p(
                    "main",
                    "Bosh menyu",
                    "Assalomu alaykum, {name}! 🎓\n\nO'quv markazimiz botiga xush kelibsiz.",
                    [[_b("📚 Kurslar", "page", "courses")], [_b("📝 Ro'yxatdan o'tish", "feedback"), _b("📍 Manzil", "page", "address")]],
                    "reply",
                ),
                _p(
                    "courses",
                    "Kurslar",
                    "📚 Kursni tanlang:",
                    [[_b("🇬🇧 Ingliz tili", "page", "english"), _b("💻 Dasturlash", "page", "it")], [BACK]],
                ),
                _p("english", "Ingliz tili", "🇬🇧 Ingliz tili\n\n⏱ Haftasiga 3 kun, 2 soatdan\n💰 Oyiga 450 000 so'm", [[_b("📝 Yozilish", "feedback")], [BACK]]),
                _p("it", "Dasturlash", "💻 Dasturlash (Python)\n\n⏱ Haftasiga 3 kun\n💰 Oyiga 600 000 so'm", [[_b("📝 Yozilish", "feedback")], [BACK]]),
                _p("address", "Manzil", "📍 Manzil: ...\n📞 Telefon: ..."),
            ],
            "feedback_prompt": "📝 Ism-familiyangiz, telefon raqamingiz va qaysi kursga yozilmoqchi ekaningizni yozing.",
            "feedback_done": "✅ Arizangiz qabul qilindi! Administrator siz bilan bog'lanadi.",
        },
    },
    "event": {
        "icon": "🎉",
        "title": "Tadbir / konferensiya",
        "desc": "Dastur, spikerlar, manzil, ro'yxatdan o'tish",
        "menu": {
            "start": "main",
            "pages": [
                _p(
                    "main",
                    "Bosh menyu",
                    "Assalomu alaykum, {name}! 🎉\n\n«...» tadbiri rasmiy botiga xush kelibsiz.\n📅 Sana: ...\n📍 Joy: ...",
                    [
                        [_b("🗓 Dastur", "page", "agenda"), _b("🎤 Spikerlar", "page", "speakers")],
                        [_b("📍 Manzil", "page", "address"), _b("❓ Savollar", "page", "faq")],
                        [_b("📝 Ro'yxatdan o'tish", "feedback")],
                    ],
                    "reply",
                ),
                _p("agenda", "Dastur", "🗓 Dastur\n\n10:00 — Ochilish\n10:30 — ...\n12:00 — Tushlik\n13:00 — ..."),
                _p("speakers", "Spikerlar", "🎤 Spikerlar\n\n• ... — mavzu: ...\n• ... — mavzu: ..."),
                _p("address", "Manzil", "📍 Manzil: ...", [[_b("🗺 Xaritada ochish", "url", url="https://maps.google.com")]]),
                _p("faq", "Savollar", "❓ Ko'p beriladigan savollar\n\n• Kirish pullikmi? — ...\n• Sertifikat beriladimi? — ..."),
            ],
            "feedback_prompt": "📝 Ro'yxatdan o'tish uchun: ism-familiya, tashkilot va telefon raqamingiz.",
            "feedback_done": "✅ Ro'yxatdan o'tdingiz! Tadbir oldidan eslatma yuboramiz.",
        },
    },
    # --- Media va shaxsiy ---
    "channel": {
        "icon": "📢",
        "title": "Kanal / media boti",
        "desc": "Kanal havolalari, reklama narxlari, reklama buyurtmasi",
        "menu": {
            "start": "main",
            "pages": [
                _p(
                    "main",
                    "Bosh menyu",
                    "Assalomu alaykum, {name}! 📢\n\n... kanalining rasmiy boti.",
                    [
                        [_b("📢 Kanalga o'tish", "url", url="https://t.me/")],
                        [_b("💰 Reklama narxlari", "page", "ads"), _b("🤝 Hamkorlik", "page", "partner")],
                        [_b("✍️ Adminga yozish", "feedback")],
                    ],
                ),
                _p(
                    "ads",
                    "Reklama narxlari",
                    "💰 Reklama narxlari\n\n• 1/24 — ... so'm\n• 2/48 — ... so'm\n• Doimiy post — ... so'm\n\n📊 Obunachilar: ...\n👁 O'rtacha ko'rishlar: ...",
                    [[_b("🛒 Reklama buyurtma qilish", "feedback")], [BACK]],
                ),
                _p("partner", "Hamkorlik", "🤝 Hamkorlik va o'zaro reklama bo'yicha takliflaringizni yozing.", [[_b("✍️ Taklif yuborish", "feedback")], [BACK]]),
            ],
            "feedback_prompt": "✍️ Xabaringizni yozing — admin javob beradi.",
        },
    },
    "faq": {
        "icon": "❓",
        "title": "Yordam markazi (FAQ)",
        "desc": "Ko'p beriladigan savollarga javoblar va operator bilan aloqa",
        "menu": {
            "start": "main",
            "pages": [
                _p(
                    "main",
                    "Savollar",
                    "Assalomu alaykum, {name}! ❓\n\nSavolingizni tanlang — javob darhol chiqadi:",
                    [
                        [_b("Qanday buyurtma beraman?", "page", "q1")],
                        [_b("To'lov usullari", "page", "q2")],
                        [_b("Yetkazib berish muddati", "page", "q3")],
                        [_b("Qaytarish va almashtirish", "page", "q4")],
                        [_b("💬 Operator bilan bog'lanish", "feedback")],
                    ],
                ),
                _p("q1", "Buyurtma", "🛒 Buyurtma berish uchun ...", [NAV]),
                _p("q2", "To'lov", "💳 To'lov usullari: naqd, Click, Payme, karta orqali.", [NAV]),
                _p("q3", "Yetkazib berish", "🚚 Toshkent bo'ylab 1 kunda, viloyatlarga 2–3 kunda.", [NAV]),
                _p("q4", "Qaytarish", "↩️ Mahsulotni 14 kun ichida qaytarish yoki almashtirish mumkin ...", [NAV]),
            ],
            "feedback_prompt": "💬 Savolingizni yozing — operator javob beradi.",
        },
    },
    "anon": {
        "icon": "🤫",
        "title": "Anonim savollar",
        "desc": "Odamlar sizga anonim yozadi, siz javob qaytarasiz",
        "menu": {
            "start": "main",
            "pages": [
                _p(
                    "main",
                    "Bosh sahifa",
                    "🤫 Bu yerda menga anonim savol yoki fikr yozishingiz mumkin.\n\nKim yozgani menga ko'rinmaydi.",
                    [[_b("✍️ Anonim yozish", "feedback")]],
                )
            ],
            "feedback_prompt": "✍️ Xabaringizni yozing — u anonim yetkaziladi.",
            "feedback_done": "✅ Yuborildi! Javob kelsa, shu yerga keladi.",
            "feedback_anonymous": True,
        },
    },
    "portfolio": {
        "icon": "👤",
        "title": "Portfolio / frilanser",
        "desc": "O'zingiz, xizmatlaringiz, ishlaringiz va buyurtma",
        "menu": {
            "start": "main",
            "pages": [
                _p(
                    "main",
                    "Bosh menyu",
                    "👋 Salom, {name}! Men — ...\n\nQuyidan tanlang:",
                    [
                        [_b("👤 Men haqimda", "page", "about"), _b("🛠 Xizmatlar", "page", "services")],
                        [_b("🖼 Ishlarim", "url", url="https://t.me/"), _b("✉️ Bog'lanish", "feedback")],
                    ],
                ),
                _p("about", "Men haqimda", "👤 Men haqimda qisqacha ...", [[BACK]]),
                _p("services", "Xizmatlar", "🛠 Xizmatlar va narxlar:\n\n• ...\n• ...", [[_b("✉️ Buyurtma berish", "feedback")], [BACK]]),
            ],
        },
    },
}
