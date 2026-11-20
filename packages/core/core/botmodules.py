"""Bot modullari reyestri: admin panel va «Boshlash» ro'yxati shu yerdan chiziladi.

Modul botda mavjud bo'lsa (present) — panelda o'z bo'limi paydo bo'ladi. Yangi modul qo'shish: bu ro'yxatga bitta
yozuv qo'shiladi (panelga qo'lda tegilmaydi). `cb` — admin panel callback'i (bo'limni ochadi)."""

from core.botbuilder import catalog_pages


def _shop(m: dict) -> bool:
    return bool((m.get("shop") or {}).get("enabled")) or bool(catalog_pages(m))


MODULES: list[dict] = [
    {"id": "shop", "icon": "🛒", "title": "Do'kon", "desc": "Katalog, savat, buyurtmalar", "cb": "sh:home", "present": _shop},
    {"id": "booking", "icon": "📅", "title": "Yozilishlar", "desc": "Xizmatlar, bo'sh vaqtlar, eslatmalar", "cb": "bm:home", "present": lambda m: bool((m.get("booking") or {}).get("enabled"))},
    {"id": "auto", "icon": "⚡", "title": "Avto xabarlar", "desc": "Salom, qaytarish, savat eslatmasi, jadval", "cb": "au:home", "present": lambda m: bool(m.get("auto"))},
    {
        "id": "games", "icon": "🎮", "title": "O'yinlar", "desc": "Viktorina, reyting, bonus, konkurs, kapcha", "cb": "gm:home",
        "present": lambda m: bool(m.get("quizzes") or m.get("contests") or (m.get("bonus") or {}).get("enabled") or m.get("captcha")),
    },
    {"id": "forms", "icon": "📝", "title": "Arizalar", "desc": "Ko'p bosqichli formalar", "cb": "adm:form", "present": lambda m: bool(m.get("forms"))},
    {"id": "referral", "icon": "👥", "title": "Referal", "desc": "Taklif, ball, mukofot", "cb": "adm:ref", "present": lambda m: bool((m.get("referral") or {}).get("enabled"))},
    {"id": "channels", "icon": "📢", "title": "Majburiy obuna", "desc": "Kanalga obuna sharti", "cb": "adm:ch", "present": lambda m: bool(m.get("channels"))},
    {"id": "tickets", "icon": "🎫", "title": "Murojaatlar", "desc": "Tiketlar, operatorlar, shablon javoblar", "cb": "tk:home", "present": lambda m: bool((m.get("tickets") or {}).get("enabled"))},
    {"id": "feedback", "icon": "💬", "title": "Murojaatlar", "desc": "Har bir xabar egasiga", "cb": "adm:fbk", "present": lambda m: bool(m.get("forward_all"))},
]


def active(menu: dict) -> list[dict]:
    return [mod for mod in MODULES if mod["present"](menu)]


def listing(menu: dict) -> list[tuple[dict, bool]]:
    return [(mod, bool(mod["present"](menu))) for mod in MODULES]


def checklist(menu: dict, globals_: dict, flags: set[str]) -> list[dict]:
    """«Birinchi 5 daqiqa»: [{done, text, cb}]. flags — egasi bajargan harakatlar (tried)."""
    items: list[dict] = []
    steps = menu.get("setup") or []
    if menu.get("system") or steps:
        items.append({"done": not steps, "text": "Bot ma'lumotlarini kiriting (nom, telefon, manzil...)", "cb": "adm:su"})
    if _shop(menu):
        items.append({"done": bool(catalog_pages(menu)), "text": "Do'kon kategoriyalarini yarating", "cb": "sh:setup"})
        items.append({"done": bool((menu.get("shop") or {}).get("items")), "text": "Mahsulot qo'shing (rasm + nom + narx)", "cb": "sh:add"})
    bk = menu.get("booking") or {}
    if bk.get("enabled"):
        items.append({"done": bool(bk.get("services")), "text": "Xizmatlar va narxlarni kiriting", "cb": "bm:svc"})
        items.append({"done": "hours" in flags, "text": "Ish jadvalini tekshiring", "cb": "bm:hrs"})
    items.append({"done": "tried" in flags, "text": "Botni o'zingiz sinab ko'ring", "cb": "adm:view"})
    items.append({"done": "shared" in flags, "text": "Havolani mijozlarga yuboring", "cb": "adm:share"})
    return items
