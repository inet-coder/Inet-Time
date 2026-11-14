"""Bot konstruktori (menu builder): menyu hujjati, tekshiruv va tayyor shablonlar.

Menyu — bitta JSON hujjat (user_bots.menu):

    {
      "start": "main",                       # /start bosilganda ochiladigan sahifa
      "pages": [
        {
          "id": "main",                      # [a-z0-9_-], 1..24
          "title": "Bosh menyu",             # faqat konstruktorda ko'rinadi
          "text": "Salom, {name}! ...",      # {name}, {username}, {bot} — o'zgaruvchilar
          "media_id": null,                  # rasm (media_files.id) — bo'lsa matn izoh bo'ladi (≤1024)
          "keyboard": "inline",              # inline — xabar ostida; reply — klaviatura o'rnida
          "buttons": [[{"text": "📦 Katalog", "action": "page", "target": "catalog"}], ...]
        }
      ],
      "fallback": "...",                     # tushunarsiz xabarga javob
      "feedback_prompt": "...",              # «Adminga yozish» bosilganda
      "feedback_done": "...",                # xabar yetkazilgach
      "feedback_anonymous": false            # egasiga yozuvchining ismi ko'rsatilmasin
    }

Tugma amallari:
    page      — boshqa sahifani ochadi (target)
    url       — havolani ochadi (faqat inline klaviaturada)
    back      — oldingi sahifaga qaytadi
    home      — bosh sahifaga
    feedback  — keyingi xabar egasiga yuboriladi, ega «reply» qilsa javob foydalanuvchiga qaytadi
"""

import copy
import re
import secrets

from pydantic import BaseModel, Field, ValidationError, field_validator, model_validator

ACTIONS = ("page", "url", "back", "home", "feedback")
KEYBOARDS = ("inline", "reply")
MAX_ROWS = 10
MAX_PER_ROW = 4
MAX_TEXT = 4096
MAX_CAPTION = 1024
VARIABLES = [
    {"key": "{name}", "label": "Foydalanuvchi ismi"},
    {"key": "{username}", "label": "@username"},
    {"key": "{bot}", "label": "Bot nomi"},
]

_PAGE_ID = re.compile(r"^[a-z0-9_-]{1,24}$")
_URL = re.compile(r"^(https?://|tg://)[^\s]{1,500}$")


class MenuError(ValueError):
    """Foydalanuvchiga ko'rsatiladigan tushunarli xato."""


class Button(BaseModel):
    text: str = Field(min_length=1, max_length=64)
    action: str
    target: str | None = None
    url: str | None = None

    @field_validator("text")
    @classmethod
    def _strip(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("tugma nomi bo'sh")
        return v

    @model_validator(mode="after")
    def _check(self):
        if self.action not in ACTIONS:
            raise ValueError(f"noma'lum amal: {self.action}")
        if self.action == "page" and not self.target:
            raise ValueError(f"«{self.text}» tugmasi uchun sahifa tanlanmagan")
        if self.action == "url" and not (self.url and _URL.match(self.url)):
            raise ValueError(f"«{self.text}» tugmasi havolasi noto'g'ri (https:// bilan boshlansin)")
        if self.action != "page":
            self.target = None
        if self.action != "url":
            self.url = None
        return self


class Page(BaseModel):
    id: str
    title: str = Field(min_length=1, max_length=64)
    text: str = Field(min_length=1, max_length=MAX_TEXT)
    media_id: int | None = None
    keyboard: str = "inline"
    buttons: list[list[Button]] = []

    @model_validator(mode="after")
    def _check(self):
        if not _PAGE_ID.match(self.id):
            raise ValueError(f"sahifa identifikatori noto'g'ri: {self.id}")
        if self.keyboard not in KEYBOARDS:
            raise ValueError("klaviatura turi inline yoki reply bo'lsin")
        if self.media_id is not None and len(self.text) > MAX_CAPTION:
            raise ValueError(f"«{self.title}»: rasmli sahifa matni {MAX_CAPTION} belgidan oshmasin")
        self.buttons = [row for row in self.buttons if row]
        if len(self.buttons) > MAX_ROWS:
            raise ValueError(f"«{self.title}»: ko'pi bilan {MAX_ROWS} qator tugma")
        labels: set[str] = set()
        for row in self.buttons:
            if len(row) > MAX_PER_ROW:
                raise ValueError(f"«{self.title}»: bir qatorda ko'pi bilan {MAX_PER_ROW} tugma")
            for button in row:
                if self.keyboard == "reply":
                    if button.action == "url":
                        raise ValueError(f"«{self.title}»: havola tugmasi faqat «xabar ostidagi» (inline) menyuda ishlaydi")
                    if button.text in labels:
                        raise ValueError(f"«{self.title}»: «{button.text}» nomli tugma ikki marta")
                    labels.add(button.text)
        return self


class Menu(BaseModel):
    start: str
    pages: list[Page] = Field(min_length=1)
    fallback: str = Field(default="", max_length=1000)
    feedback_prompt: str = Field(default="", max_length=1000)
    feedback_done: str = Field(default="", max_length=1000)
    # true — egasiga yozgan odamning ismi ko'rsatilmaydi (anonim savollar)
    feedback_anonymous: bool = False

    @model_validator(mode="after")
    def _check(self):
        ids = [p.id for p in self.pages]
        if len(set(ids)) != len(ids):
            raise ValueError("sahifa identifikatorlari takrorlanmasin")
        if self.start not in ids:
            raise ValueError("bosh sahifa topilmadi")
        known = set(ids)
        for page in self.pages:
            for row in page.buttons:
                for button in row:
                    if button.action == "page" and button.target not in known:
                        raise ValueError(f"«{page.title}» → «{button.text}»: bog'langan sahifa o'chirilgan")
        return self


DEFAULT_TEXTS = {
    "fallback": "Menyudan tanlang 👇",
    "feedback_prompt": "✍️ Xabaringizni yozing — adminga yetkazaman.",
    "feedback_done": "✅ Xabaringiz yuborildi. Tez orada javob beramiz.",
}


def validate_menu(raw: dict, pages_limit: int, owned_media: set[int] | None = None) -> dict:
    """Tekshiradi va tozalangan hujjatni qaytaradi. Xato bo'lsa MenuError (o'zbekcha matn bilan)."""
    try:
        menu = Menu.model_validate(raw)
    except ValidationError as exc:
        first = exc.errors()[0]
        msg = str(first.get("msg", "noto'g'ri menyu")).removeprefix("Value error, ")
        raise MenuError(msg) from exc
    if len(menu.pages) > pages_limit:
        raise MenuError(f"Tarifingizda ko'pi bilan {pages_limit} ta sahifa — tarifni yangilang yoki sahifalarni kamaytiring")
    if owned_media is not None:
        for page in menu.pages:
            if page.media_id is not None and page.media_id not in owned_media:
                raise MenuError(f"«{page.title}»: rasm topilmadi — qayta yuklang")
    data = menu.model_dump()
    for key, default in DEFAULT_TEXTS.items():
        data[key] = (data.get(key) or "").strip() or default
    return data


def page_by_id(menu: dict, page_id: str | None) -> dict | None:
    for page in menu.get("pages", []):
        if page["id"] == page_id:
            return page
    return None


def render_text(text: str, *, name: str | None, username: str | None, bot: str) -> str:
    return (
        text.replace("{name}", name or "do'stim")
        .replace("{username}", f"@{username}" if username else (name or ""))
        .replace("{bot}", bot)
    )


def new_page_id() -> str:
    return "p" + secrets.token_hex(3)


# --- Tayyor shablonlar ---


def _b(text: str, action: str, target: str | None = None, url: str | None = None) -> dict:
    return {"text": text, "action": action, "target": target, "url": url}


TEMPLATES: dict[str, dict] = {
    "blank": {
        "title": "Bo'sh",
        "desc": "Faqat bosh sahifa — o'zingiz quring",
        "menu": {
            "start": "main",
            "pages": [
                {
                    "id": "main",
                    "title": "Bosh menyu",
                    "text": "Assalomu alaykum, {name}! 👋\n\n{bot} ga xush kelibsiz.",
                    "media_id": None,
                    "keyboard": "inline",
                    "buttons": [[_b("✍️ Adminga yozish", "feedback")]],
                }
            ],
        },
    },
    "shop": {
        "title": "Do'kon",
        "desc": "Katalog, narxlar, yetkazib berish, buyurtma",
        "menu": {
            "start": "main",
            "pages": [
                {
                    "id": "main",
                    "title": "Bosh menyu",
                    "text": "Assalomu alaykum, {name}! 🛍\n\nDo'konimizga xush kelibsiz. Bo'limni tanlang:",
                    "media_id": None,
                    "keyboard": "reply",
                    "buttons": [
                        [_b("📦 Katalog", "page", "catalog"), _b("💰 Narxlar", "page", "prices")],
                        [_b("🚚 Yetkazib berish", "page", "delivery"), _b("📍 Manzil", "page", "address")],
                        [_b("🛒 Buyurtma berish", "feedback")],
                    ],
                },
                {
                    "id": "catalog",
                    "title": "Katalog",
                    "text": "📦 Katalog\n\nKategoriyani tanlang:",
                    "media_id": None,
                    "keyboard": "inline",
                    "buttons": [
                        [_b("👕 Kiyimlar", "page", "cat1"), _b("👟 Poyabzal", "page", "cat2")],
                        [_b("⬅️ Orqaga", "back")],
                    ],
                },
                {
                    "id": "cat1",
                    "title": "Kiyimlar",
                    "text": "👕 Kiyimlar\n\n• Futbolka — 120 000 so'm\n• Ko'ylak — 180 000 so'm\n\nBuyurtma uchun «Buyurtma berish» ni bosing.",
                    "media_id": None,
                    "keyboard": "inline",
                    "buttons": [[_b("🛒 Buyurtma berish", "feedback")], [_b("⬅️ Orqaga", "back"), _b("🏠 Bosh menyu", "home")]],
                },
                {
                    "id": "cat2",
                    "title": "Poyabzal",
                    "text": "👟 Poyabzal\n\n• Krossovka — 350 000 so'm\n• Tufli — 420 000 so'm",
                    "media_id": None,
                    "keyboard": "inline",
                    "buttons": [[_b("🛒 Buyurtma berish", "feedback")], [_b("⬅️ Orqaga", "back"), _b("🏠 Bosh menyu", "home")]],
                },
                {
                    "id": "prices",
                    "title": "Narxlar",
                    "text": "💰 Narxlar ro'yxati shu yerda bo'ladi.",
                    "media_id": None,
                    "keyboard": "inline",
                    "buttons": [],
                },
                {
                    "id": "delivery",
                    "title": "Yetkazib berish",
                    "text": "🚚 Toshkent bo'ylab — 1 kunda, viloyatlarga — 2–3 kunda.",
                    "media_id": None,
                    "keyboard": "inline",
                    "buttons": [],
                },
                {
                    "id": "address",
                    "title": "Manzil",
                    "text": "📍 Manzil: Toshkent sh., ...\n🕘 Ish vaqti: 9:00–20:00",
                    "media_id": None,
                    "keyboard": "inline",
                    "buttons": [[_b("🗺 Xaritada ochish", "url", url="https://maps.google.com")]],
                },
            ],
            "feedback_prompt": "🛒 Nima buyurtma qilmoqchisiz? Mahsulot nomi, soni va telefon raqamingizni yozing.",
            "feedback_done": "✅ Buyurtmangiz qabul qilindi! Operator tez orada bog'lanadi.",
        },
    },
    "edu": {
        "title": "O'quv markazi",
        "desc": "Kurslar, narxlar, ro'yxatdan o'tish",
        "menu": {
            "start": "main",
            "pages": [
                {
                    "id": "main",
                    "title": "Bosh menyu",
                    "text": "Assalomu alaykum, {name}! 🎓\n\nO'quv markazimiz botiga xush kelibsiz.",
                    "media_id": None,
                    "keyboard": "reply",
                    "buttons": [
                        [_b("📚 Kurslar", "page", "courses")],
                        [_b("📝 Ro'yxatdan o'tish", "feedback"), _b("📍 Manzil", "page", "address")],
                    ],
                },
                {
                    "id": "courses",
                    "title": "Kurslar",
                    "text": "📚 Kursni tanlang:",
                    "media_id": None,
                    "keyboard": "inline",
                    "buttons": [
                        [_b("🇬🇧 Ingliz tili", "page", "english"), _b("💻 Dasturlash", "page", "it")],
                        [_b("⬅️ Orqaga", "back")],
                    ],
                },
                {
                    "id": "english",
                    "title": "Ingliz tili",
                    "text": "🇬🇧 Ingliz tili\n\n⏱ Haftasiga 3 kun, 2 soatdan\n💰 Oyiga 450 000 so'm",
                    "media_id": None,
                    "keyboard": "inline",
                    "buttons": [[_b("📝 Yozilish", "feedback")], [_b("⬅️ Orqaga", "back")]],
                },
                {
                    "id": "it",
                    "title": "Dasturlash",
                    "text": "💻 Dasturlash (Python)\n\n⏱ Haftasiga 3 kun\n💰 Oyiga 600 000 so'm",
                    "media_id": None,
                    "keyboard": "inline",
                    "buttons": [[_b("📝 Yozilish", "feedback")], [_b("⬅️ Orqaga", "back")]],
                },
                {
                    "id": "address",
                    "title": "Manzil",
                    "text": "📍 Manzil: ...\n📞 Telefon: ...",
                    "media_id": None,
                    "keyboard": "inline",
                    "buttons": [],
                },
            ],
            "feedback_prompt": "📝 Ism-familiyangiz, telefon raqamingiz va qaysi kursga yozilmoqchi ekaningizni yozing.",
            "feedback_done": "✅ Arizangiz qabul qilindi! Administrator siz bilan bog'lanadi.",
        },
    },
    "anon": {
        "title": "Anonim savollar",
        "desc": "Odamlar sizga anonim yozadi, siz javob qaytarasiz",
        "menu": {
            "start": "main",
            "pages": [
                {
                    "id": "main",
                    "title": "Bosh sahifa",
                    "text": "🤫 Bu yerda menga anonim savol yoki fikr yozishingiz mumkin.\n\nKim yozgani menga ko'rinmaydi.",
                    "media_id": None,
                    "keyboard": "inline",
                    "buttons": [[_b("✍️ Anonim yozish", "feedback")]],
                }
            ],
            "feedback_prompt": "✍️ Xabaringizni yozing — u anonim yetkaziladi.",
            "feedback_anonymous": True,
            "feedback_done": "✅ Yuborildi! Javob kelsa, shu yerga keladi.",
        },
    },
    "portfolio": {
        "title": "Portfolio / xizmatlar",
        "desc": "O'zingiz, xizmatlaringiz va aloqa",
        "menu": {
            "start": "main",
            "pages": [
                {
                    "id": "main",
                    "title": "Bosh menyu",
                    "text": "👋 Salom, {name}! Men — ...\n\nQuyidan tanlang:",
                    "media_id": None,
                    "keyboard": "inline",
                    "buttons": [
                        [_b("👤 Men haqimda", "page", "about"), _b("🛠 Xizmatlar", "page", "services")],
                        [_b("🖼 Ishlarim", "url", url="https://t.me/"), _b("✉️ Bog'lanish", "feedback")],
                    ],
                },
                {
                    "id": "about",
                    "title": "Men haqimda",
                    "text": "👤 Men haqimda qisqacha ...",
                    "media_id": None,
                    "keyboard": "inline",
                    "buttons": [[_b("⬅️ Orqaga", "back")]],
                },
                {
                    "id": "services",
                    "title": "Xizmatlar",
                    "text": "🛠 Xizmatlar va narxlar:\n\n• ...\n• ...",
                    "media_id": None,
                    "keyboard": "inline",
                    "buttons": [[_b("✉️ Buyurtma berish", "feedback")], [_b("⬅️ Orqaga", "back")]],
                },
            ],
        },
    },
}


def template_menu(code: str) -> dict:
    template = TEMPLATES.get(code) or TEMPLATES["blank"]
    menu = copy.deepcopy(template["menu"])
    for key, default in DEFAULT_TEXTS.items():
        menu.setdefault(key, default)
    return menu


def templates_public() -> list[dict]:
    return [
        {"code": code, "title": t["title"], "desc": t["desc"], "pages": len(t["menu"]["pages"])}
        for code, t in TEMPLATES.items()
    ]
