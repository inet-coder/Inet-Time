"""Web App konstruktori uchun tayyor shablonlar. Rasmlar o'rnida emoji — egasi o'z rasmlarini yuklaydi."""

import copy

from core.webapp_builder import DEFAULT_CHECKOUT_FIELDS, THEME_PRESETS


def _theme(preset: str, radius: int = 16, font: str = "system") -> dict:
    p = THEME_PRESETS[preset]
    return {"preset": preset, "adaptive": p["adaptive"], "primary": p["primary"], "background": p["background"],
            "surface": p["surface"], "text": p["text"], "radius": radius, "font": font}


def _act(kind: str = "none", **kw) -> dict:
    return {"type": kind, "page": kw.get("page"), "url": kw.get("url"), "phone": kw.get("phone")}


def _settings(title: str, success: str = "✅ Buyurtmangiz qabul qilindi! Tez orada bog'lanamiz.") -> dict:
    return {"title": title, "currency": "so'm", "checkout_fields": copy.deepcopy(DEFAULT_CHECKOUT_FIELDS), "checkout_success": success}


def _p(pid: str, price: int, title: str, emoji: str, text: str = "", old: int | None = None, badge: str = "") -> dict:
    return {"id": pid, "title": title, "price": price, "old_price": old, "media_id": None, "emoji": emoji, "text": text, "badge": badge}


def _field(fid: str, ftype: str, label: str, required: bool = False, placeholder: str = "", options: list[str] | None = None) -> dict:
    return {"id": fid, "type": ftype, "label": label, "placeholder": placeholder, "required": required, "options": options or []}


WEBAPP_TEMPLATES: dict[str, dict] = {
    "blank": {
        "icon": "📄",
        "title": "Bo'sh ilova",
        "desc": "Bitta sahifa — hammasini o'zingiz quring",
        "doc": {
            "version": 1,
            "theme": _theme("telegram"),
            "settings": _settings(""),
            "start": "home",
            "pages": [
                {
                    "id": "home", "title": "Bosh sahifa", "emoji": "🏠", "in_nav": True,
                    "blocks": [
                        {"id": "b1", "type": "hero", "hidden": False, "title": "Xush kelibsiz!", "subtitle": "Bu yerda ilovangiz haqida qisqacha yozing.",
                         "media_id": None, "emoji": "👋", "align": "center", "button": None},
                    ],
                }
            ],
        },
    },
    "shop": {
        "icon": "🛍️",
        "title": "Internet-do'kon",
        "desc": "Katalog, savatcha va buyurtma — buyurtmalar sizga botda keladi",
        "doc": {
            "version": 1,
            "theme": _theme("light", 18),
            "settings": _settings("Do'kon"),
            "start": "home",
            "pages": [
                {
                    "id": "home", "title": "Do'kon", "emoji": "🛍️", "in_nav": True,
                    "blocks": [
                        {"id": "h1", "type": "hero", "hidden": False, "title": "Yangi kolleksiya", "subtitle": "Toshkent bo'ylab 1 kunda yetkazib beramiz",
                         "media_id": None, "emoji": "🛍️", "align": "left", "button": None},
                        {"id": "p1", "type": "products", "hidden": False, "title": "Kiyimlar", "columns": 2, "items": [
                            _p("tshirt", 120000, "Futbolka", "👕", "100% paxta, barcha o'lchamlar", 150000, "-20%"),
                            _p("hoodie", 280000, "Xudi", "🧥", "Issiq, flis astarli"),
                            _p("jeans", 240000, "Jinsi shim", "👖", "Klassik kesim"),
                            _p("cap", 70000, "Kepka", "🧢", "Bitta o'lcham", badge="Yangi"),
                        ]},
                        {"id": "p2", "type": "products", "hidden": False, "title": "Poyabzal", "columns": 2, "items": [
                            _p("sneakers", 350000, "Krossovka", "👟", "Yengil, yugurish uchun"),
                            _p("boots", 520000, "Botinka", "🥾", "Charm, qishki"),
                        ]},
                    ],
                },
                {
                    "id": "info", "title": "Ma'lumot", "emoji": "ℹ️", "in_nav": True,
                    "blocks": [
                        {"id": "f1", "type": "features", "hidden": False, "columns": 1, "items": [
                            {"emoji": "🚚", "title": "Yetkazib berish", "text": "Toshkent — 1 kun, viloyatlar — 2–3 kun. 500 000 so'mdan bepul."},
                            {"emoji": "💳", "title": "To'lov", "text": "Naqd, Click, Payme yoki karta orqali — qabul qilganda."},
                            {"emoji": "↩️", "title": "Qaytarish", "text": "14 kun ichida qaytarish yoki almashtirish mumkin."},
                        ]},
                        {"id": "c1", "type": "contacts", "hidden": False, "phone": "+998 90 000 00 00", "telegram": None, "instagram": None,
                         "website": None, "address": "Toshkent sh., ...", "map_url": None},
                    ],
                },
            ],
        },
    },
    "restaurant": {
        "icon": "🍽",
        "title": "Restoran menyusi",
        "desc": "Taomlar menyusi, savatcha va yetkazib berishga buyurtma",
        "doc": {
            "version": 1,
            "theme": _theme("peach", 20, "rounded"),
            "settings": _settings("Restoran", "✅ Buyurtma qabul qilindi! Operator tasdiqlash uchun qo'ng'iroq qiladi."),
            "start": "menu",
            "pages": [
                {
                    "id": "menu", "title": "Menyu", "emoji": "🍽", "in_nav": True,
                    "blocks": [
                        {"id": "h1", "type": "hero", "hidden": False, "title": "Mazali taomlar uyingizgacha", "subtitle": "40–60 daqiqada yetkazib beramiz",
                         "media_id": None, "emoji": "🍲", "align": "center", "button": None},
                        {"id": "p1", "type": "products", "hidden": False, "title": "Asosiy taomlar", "columns": 1, "items": [
                            _p("osh", 45000, "Osh", "🍚", "Toshkent oshi, 400 g"),
                            _p("lagmon", 38000, "Lag'mon", "🍜", "Qo'lda cho'zilgan, 450 g"),
                            _p("shashlik", 22000, "Shashlik", "🍢", "Mol go'shti, 1 six", badge="Xit"),
                        ]},
                        {"id": "p2", "type": "products", "hidden": False, "title": "Ichimliklar", "columns": 2, "items": [
                            _p("tea", 8000, "Choy", "🍵"),
                            _p("lemonade", 18000, "Limonad", "🍋"),
                        ]},
                    ],
                },
                {
                    "id": "about", "title": "Biz haqimizda", "emoji": "📍", "in_nav": True,
                    "blocks": [
                        {"id": "t1", "type": "text", "hidden": False, "text": "2015-yildan beri sizni milliy va Yevropa taomlari bilan siylaymiz.", "align": "left", "muted": False},
                        {"id": "c1", "type": "contacts", "hidden": False, "phone": "+998 90 000 00 00", "telegram": None, "instagram": None,
                         "website": None, "address": "Toshkent sh., ...", "map_url": "https://maps.google.com"},
                    ],
                },
            ],
        },
    },
    "services": {
        "icon": "💼",
        "title": "Xizmatlar va yozilish",
        "desc": "Xizmatlar, narxlar, sharhlar va onlayn yozilish formasi",
        "doc": {
            "version": 1,
            "theme": _theme("lavender", 16),
            "settings": _settings("Xizmatlar"),
            "start": "home",
            "pages": [
                {
                    "id": "home", "title": "Asosiy", "emoji": "🏠", "in_nav": True,
                    "blocks": [
                        {"id": "h1", "type": "hero", "hidden": False, "title": "Professional xizmat", "subtitle": "10 yillik tajriba, 2000+ mamnun mijoz",
                         "media_id": None, "emoji": "✨", "align": "center", "button": {"text": "Yozilish", "action": _act("page", page="book")}},
                        {"id": "s1", "type": "stats", "hidden": False, "items": [{"value": "10+", "label": "yil tajriba"}, {"value": "2000+", "label": "mijoz"}, {"value": "4.9", "label": "reyting"}]},
                        {"id": "pr1", "type": "pricing", "hidden": False, "items": [
                            {"name": "Standart", "price": "150 000 so'm", "period": "", "features": ["Konsultatsiya", "Asosiy xizmat"], "highlight": False,
                             "button": {"text": "Tanlash", "action": _act("page", page="book")}},
                            {"name": "Premium", "price": "300 000 so'm", "period": "", "features": ["Konsultatsiya", "To'liq xizmat", "Kafolat 30 kun"], "highlight": True,
                             "button": {"text": "Tanlash", "action": _act("page", page="book")}},
                        ]},
                        {"id": "q1", "type": "faq", "hidden": False, "items": [
                            {"q": "Qancha vaqt oladi?", "a": "Odatda 1–2 soat."},
                            {"q": "Uyga chiqib xizmat ko'rsatasizmi?", "a": "Ha, Toshkent bo'ylab qo'shimcha to'lov bilan."},
                        ]},
                    ],
                },
                {
                    "id": "book", "title": "Yozilish", "emoji": "📝", "in_nav": True,
                    "blocks": [
                        {"id": "fm1", "type": "form", "hidden": False, "title": "Onlayn yozilish", "fields": [
                            _field("name", "text", "Ismingiz", True),
                            _field("phone", "phone", "Telefon", True, "+998 90 123 45 67"),
                            _field("service", "select", "Xizmat", True, options=["Standart", "Premium"]),
                            _field("date", "date", "Qulay sana", True),
                            _field("note", "textarea", "Izoh"),
                        ], "submit_text": "Yozilish", "success_text": "✅ Yozildingiz! Vaqtni tasdiqlash uchun bog'lanamiz."},
                    ],
                },
            ],
        },
    },
    "event": {
        "icon": "🎉",
        "title": "Tadbir sahifasi",
        "desc": "Ortga sanash, dastur, spikerlar va ro'yxatdan o'tish",
        "doc": {
            "version": 1,
            "theme": _theme("dark", 18),
            "settings": _settings("Tadbir"),
            "start": "home",
            "pages": [
                {
                    "id": "home", "title": "Tadbir", "emoji": "🎉", "in_nav": True,
                    "blocks": [
                        {"id": "h1", "type": "hero", "hidden": False, "title": "Tech Conference 2027", "subtitle": "Toshkent · 15-mart · 10:00",
                         "media_id": None, "emoji": "🎤", "align": "center", "button": {"text": "Ro'yxatdan o'tish", "action": _act("page", page="reg")}},
                        {"id": "cd1", "type": "countdown", "hidden": False, "title": "Tadbirgacha qoldi", "date": "2027-03-15T10:00:00+05:00", "done_text": "Tadbir boshlandi! 🎉"},
                        {"id": "l1", "type": "links", "hidden": False, "items": [
                            {"emoji": "🗓", "title": "10:00 — Ochilish", "subtitle": "Asosiy zal", "action": _act()},
                            {"emoji": "🎤", "title": "10:30 — AI va biznes", "subtitle": "Spiker: ...", "action": _act()},
                            {"emoji": "☕", "title": "12:00 — Kofe-breyk", "subtitle": "", "action": _act()},
                        ]},
                    ],
                },
                {
                    "id": "reg", "title": "Ro'yxat", "emoji": "📝", "in_nav": True,
                    "blocks": [
                        {"id": "fm1", "type": "form", "hidden": False, "title": "Ro'yxatdan o'tish", "fields": [
                            _field("name", "text", "Ism-familiya", True),
                            _field("phone", "phone", "Telefon", True),
                            _field("company", "text", "Tashkilot"),
                            _field("role", "radio", "Siz kimsiz?", True, options=["Talaba", "Mutaxassis", "Rahbar"]),
                        ], "submit_text": "Ro'yxatdan o'tish", "success_text": "✅ Ro'yxatdan o'tdingiz! Tadbir oldidan eslatma yuboramiz."},
                    ],
                },
            ],
        },
    },
    "portfolio": {
        "icon": "👤",
        "title": "Portfolio / vizitka",
        "desc": "O'zingiz, ishlaringiz, ijtimoiy tarmoqlar va aloqa",
        "doc": {
            "version": 1,
            "theme": _theme("gold", 14, "serif"),
            "settings": _settings("Portfolio"),
            "start": "home",
            "pages": [
                {
                    "id": "home", "title": "Men", "emoji": "👤", "in_nav": False,
                    "blocks": [
                        {"id": "h1", "type": "hero", "hidden": False, "title": "Ism Familiya", "subtitle": "Dizayner · Toshkent",
                         "media_id": None, "emoji": "🎨", "align": "center", "button": {"text": "Bog'lanish", "action": _act("bot")}},
                        {"id": "f1", "type": "features", "hidden": False, "columns": 2, "items": [
                            {"emoji": "🖌", "title": "Logo", "text": "Brend uchun noyob logo"},
                            {"emoji": "📱", "title": "UI/UX", "text": "Ilova va sayt dizayni"},
                        ]},
                        {"id": "c1", "type": "contacts", "hidden": False, "phone": None, "telegram": "telegram", "instagram": None,
                         "website": None, "address": "", "map_url": None},
                    ],
                },
            ],
        },
    },
}


def template_doc(code: str) -> dict:
    return copy.deepcopy((WEBAPP_TEMPLATES.get(code) or WEBAPP_TEMPLATES["blank"])["doc"])


def templates_public() -> list[dict]:
    return [{"code": c, "icon": t["icon"], "title": t["title"], "desc": t["desc"]} for c, t in WEBAPP_TEMPLATES.items()]
