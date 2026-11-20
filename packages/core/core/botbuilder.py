"""Bot konstruktori (menu builder): bot hujjati, tekshiruv, o'zgaruvchilar va tayyor shablonlar.

Bot — bitta JSON hujjat (user_bots.menu). Uni Mini App muharriri ham, botning o'zidagi chat-muharrir
(egasi /admin → «✏️ Botni tahrirlash») ham bir xil tahrirlaydi.

    {
      "start": "main",                     # /start bosilganda ochiladigan sahifa
      "first_start": null,                 # birinchi marta kirganlarga boshqa sahifa (ixtiyoriy)
      "pages": [Page...],
      "keywords": [{"words": ["narx"], "match": "contains", "target": "price", "reply": ""}],
      "commands": [{"command": "help", "description": "Yordam", "target": "help"}],
      "variables": [{"key": "ball", "label": "Ball", "default": "0", "scope": "user"}],
      "forms": [Form...],                  # ketma-ket savollar → javoblar o'zgaruvchilarga va jadvalga
      "referral": {"enabled": false, "reward": 1, "var": "balance", ...},
      "channels": [{"chat": "@kanal", "title": "Kanal", "url": "https://t.me/kanal"}],  # majburiy obuna
      "admins": [123456789],               # egasidan tashqari adminlar
      "fallback": "...", "feedback_*": "...", "forward_all": false
    }

Sahifa:
    {"id", "title", "text", "media_id",    # eski (oddiy matn) format — Mini App muharriri
     "messages": [Msg...],                 # bo'lsa — shu xabarlar yuboriladi (HTML, istalgan turdagi media)
     "keyboard": "inline" | "reply", "buttons": [[Button...]],
     "placeholder", "protect", "notify", "ops": [VarOp...]}

Xabar (Msg): {"type": text|photo|video|animation|document|audio|voice|video_note|sticker,
              "text": "<b>HTML</b> {name}", "file_id": "...", "media_id": 12}

Tugma amallari (ACTIONS):
    page      — sahifani ochadi (target)          url       — havola (inline)
    back      — orqaga                            home      — bosh sahifa
    feedback  — keyingi xabar egasiga             webapp    — botning Web App'i
    alert     — qalqib chiquvchi xabar (inline)   form      — formani boshlaydi (form)
    set       — o'zgaruvchini o'zgartiradi (var/op/value), keyin target
    share     — matnni ulashish (referal havola)   check_sub — obunani tekshiradi, keyin target
    contact   — telefon raqamini so'raydi (var)   location  — joylashuvni so'raydi (var)
    notify    — adminga xabar beradi (alert matni), keyin target
    random    — tasodifiy sahifa (targets)

O'zgaruvchilar matnda: {name} {first_name} {last_name} {username} {user_id} {mention} {bot}
{bot_username} {date} {time} {ref_link} {ref_count} {subscribers} va o'zingiz e'lon qilgan {kalit}.
"""

import copy
import datetime
import html
import re
import secrets
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator, model_validator

from core.bot_templates import TEMPLATES

ACTIONS = ("page", "url", "back", "home", "feedback", "webapp", "alert", "form", "set", "share", "check_sub", "contact", "location", "notify", "random")
INLINE_ONLY = ("url", "alert")
KEYBOARDS = ("inline", "reply")
MSG_TYPES = ("text", "photo", "video", "animation", "document", "audio", "voice", "video_note", "sticker")
CAPTIONLESS = ("sticker", "video_note")
MAX_ROWS = 12
MAX_PER_ROW = 8
MAX_TEXT = 4096
MAX_CAPTION = 1024
MAX_MESSAGES = 10
VARIABLES = [
    {"key": "{name}", "label": "Foydalanuvchi ismi"},
    {"key": "{username}", "label": "@username"},
    {"key": "{user_id}", "label": "Foydalanuvchi ID"},
    {"key": "{mention}", "label": "Ism (havola bilan)"},
    {"key": "{bot}", "label": "Bot nomi"},
    {"key": "{date}", "label": "Bugungi sana"},
    {"key": "{time}", "label": "Hozirgi vaqt"},
    {"key": "{ref_link}", "label": "Referal havola"},
    {"key": "{ref_count}", "label": "Taklif qilganlar soni"},
    {"key": "{subscribers}", "label": "Obunachilar soni"},
    {"key": "{cart_count}", "label": "Savatdagi mahsulotlar soni"},
    {"key": "{cart_total}", "label": "Savat summasi"},
]
BUILTIN_VARS = ("name", "first_name", "last_name", "username", "user_id", "mention", "bot", "bot_username", "date", "time", "ref_link", "ref_count", "subscribers", "cart_count", "cart_total")

_PAGE_ID = re.compile(r"^[a-z0-9_-]{1,24}$")
_URL = re.compile(r"^(https?://|tg://)[^\s]{1,500}$")
_VAR = re.compile(r"^[a-z][a-z0-9_]{0,31}$")
_CMD = re.compile(r"^[a-z0-9_]{1,32}$")
_CHAT = re.compile(r"^(@[A-Za-z0-9_]{4,32}|-100\d{5,16})$")


class MenuError(ValueError):
    """Foydalanuvchiga ko'rsatiladigan tushunarli xato."""


class _M(BaseModel):
    model_config = ConfigDict(extra="ignore")


def _var_key(v: str | None, what: str = "o'zgaruvchi") -> str | None:
    if v in (None, ""):
        return None
    v = v.strip().lower().lstrip("{").rstrip("}")
    if not _VAR.match(v):
        raise ValueError(f"{what} nomi faqat lotin kichik harf, raqam va _ bo'lsin")
    return v


class Cond(_M):
    """Tugma ko'rinish sharti: {var} op value."""

    var: str
    op: Literal["eq", "ne", "gt", "lt", "ge", "le", "set", "unset", "contains"] = "eq"
    value: str = Field(default="", max_length=100)

    @field_validator("var")
    @classmethod
    def _v(cls, v: str) -> str:
        return _var_key(v) or ""


class VarOp(_M):
    var: str
    op: Literal["set", "add", "sub", "clear"] = "set"
    value: str = Field(default="", max_length=200)

    @field_validator("var")
    @classmethod
    def _v(cls, v: str) -> str:
        return _var_key(v) or ""


class Button(_M):
    text: str = Field(min_length=1, max_length=64)
    action: str
    target: str | None = None
    url: str | None = None
    alert: str = Field(default="", max_length=200)
    form: str | None = None
    var: str | None = None
    op: Literal["set", "add", "sub", "clear"] = "set"
    value: str = Field(default="", max_length=200)
    targets: list[str] = Field(default_factory=list, max_length=20)
    share_text: str = Field(default="", max_length=300)
    cond: Cond | None = None
    admin_only: bool = False
    hidden: bool = False  # ko'rinmaydi, lekin nomini yozsa ishlaydi
    need_sub: bool = False  # bosishdan oldin majburiy obunani tekshiradi

    @field_validator("text")
    @classmethod
    def _strip(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("tugma nomi bo'sh")
        return v

    @field_validator("var")
    @classmethod
    def _var(cls, v: str | None) -> str | None:
        return _var_key(v)

    @model_validator(mode="after")
    def _check(self):
        if self.action not in ACTIONS:
            raise ValueError(f"noma'lum amal: {self.action}")
        if self.action == "page" and not self.target:
            raise ValueError(f"«{self.text}» tugmasi uchun sahifa tanlanmagan")
        if self.action == "url" and not (self.url and _URL.match(self.url)):
            raise ValueError(f"«{self.text}» tugmasi havolasi noto'g'ri (https:// bilan boshlansin)")
        if self.action == "alert" and not self.alert.strip():
            raise ValueError(f"«{self.text}»: ogohlantirish matni kiritilmagan")
        if self.action == "form" and not self.form:
            raise ValueError(f"«{self.text}»: forma tanlanmagan")
        if self.action == "set" and not self.var:
            raise ValueError(f"«{self.text}»: o'zgaruvchi tanlanmagan")
        if self.action == "random" and not self.targets:
            raise ValueError(f"«{self.text}»: tasodifiy sahifalar tanlanmagan")
        if self.action in ("contact", "location") and not self.var:
            self.var = "phone" if self.action == "contact" else "location"
        if self.action not in ("page", "set", "check_sub", "contact", "location", "notify", "form"):
            self.target = None
        if self.action != "url":
            self.url = None
        if self.action != "random":
            self.targets = []
        return self


INPUT_TYPES = ("text", "number", "phone", "email", "photo", "choice", "location")


class Msg(_M):
    type: str = "text"
    text: str = Field(default="", max_length=MAX_TEXT)
    file_id: str | None = Field(default=None, max_length=300)
    media_id: int | None = None
    # Postning o'z inline tugmalari (xabar ostida)
    buttons: list[list[Button]] = Field(default_factory=list, max_length=MAX_ROWS)
    # type == "question": foydalanuvchidan javob so'raladi va o'zgaruvchiga saqlanadi
    var: str | None = None
    input: str = "text"
    options: list[str] = Field(default_factory=list, max_length=12)

    @field_validator("var")
    @classmethod
    def _var(cls, v: str | None) -> str | None:
        return _var_key(v)

    @model_validator(mode="after")
    def _check(self):
        if self.type not in MSG_TYPES + ("question",):
            raise ValueError(f"noma'lum xabar turi: {self.type}")
        self.buttons = [row for row in self.buttons if row]
        for row in self.buttons:
            if len(row) > MAX_PER_ROW:
                raise ValueError(f"bir qatorda ko'pi bilan {MAX_PER_ROW} tugma")
            for b in row:
                if b.action in ("contact", "location"):
                    raise ValueError(f"«{b.text}»: telefon/joylashuv so'rash faqat klaviatura tugmasida")
        if self.type == "question":
            if not self.text.strip():
                raise ValueError("savol matni bo'sh")
            if not self.var:
                raise ValueError("savol javobi saqlanadigan o'zgaruvchi ko'rsatilmagan")
            if self.input not in INPUT_TYPES:
                raise ValueError("noma'lum javob turi")
            self.options = [o.strip()[:64] for o in self.options if o.strip()]
            if self.input == "choice" and not self.options:
                raise ValueError("tanlov savoli uchun variantlar kiritilmagan")
            self.file_id = self.media_id = None
            self.buttons = []
            return self
        self.var, self.options = None, []
        if self.type == "text":
            if not self.text.strip():
                raise ValueError("bo'sh matnli xabar")
            self.file_id = self.media_id = None
        else:
            if not self.file_id and not (self.type == "photo" and self.media_id):
                raise ValueError("media fayli topilmadi")
            if self.type in CAPTIONLESS:
                self.text = ""
            elif len(self.text) > MAX_CAPTION:
                raise ValueError(f"rasm/video izohi {MAX_CAPTION} belgidan oshmasin")
        return self


class Page(_M):
    id: str
    title: str = Field(min_length=1, max_length=64)
    text: str = Field(min_length=1, max_length=MAX_TEXT)
    media_id: int | None = None
    messages: list[Msg] = Field(default_factory=list, max_length=MAX_MESSAGES)
    keyboard: str = "inline"
    buttons: list[list[Button]] = []
    placeholder: str = Field(default="", max_length=64)
    protect: bool = False  # nusxa olish / uzatishni taqiqlash
    notify: bool = False  # foydalanuvchi ochganda egasiga xabar
    ops: list[VarOp] = Field(default_factory=list, max_length=5)  # ochilganda o'zgaruvchilar
    nav: bool = False  # menyuda «⬅️ Orqaga | 🏠 Bosh menyu» qatori avtomatik
    random_post: bool = False  # postlardan bittasi tasodifiy yuboriladi
    # Maxsus modul: catalog — shu bo'lim mahsulotlari; cart — savatcha; orders — buyurtmalarim
    module: "Module | None" = None

    @model_validator(mode="after")
    def _check(self):
        if not _PAGE_ID.match(self.id):
            raise ValueError(f"sahifa identifikatori noto'g'ri: {self.id}")
        if self.keyboard not in KEYBOARDS:
            raise ValueError("klaviatura turi inline yoki reply bo'lsin")
        if not self.messages and self.media_id is not None and len(self.text) > MAX_CAPTION:
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
                    if button.action in INLINE_ONLY:
                        raise ValueError(f"«{self.title}» → «{button.text}»: bu amal faqat «xabar ostidagi» (inline) tugmada ishlaydi")
                    if button.text in labels:
                        raise ValueError(f"«{self.title}»: «{button.text}» nomli tugma ikki marta")
                    labels.add(button.text)
        return self


class Keyword(_M):
    words: list[str] = Field(min_length=1, max_length=30)
    match: Literal["exact", "contains", "start"] = "exact"
    target: str | None = None
    reply: str = Field(default="", max_length=MAX_TEXT)

    @model_validator(mode="after")
    def _check(self):
        self.words = [w.strip().lower()[:100] for w in self.words if w.strip()]
        if not self.words:
            raise ValueError("kalit so'z bo'sh")
        if not self.target and not self.reply.strip():
            raise ValueError(f"«{self.words[0]}»: javob yoki sahifa tanlanmagan")
        return self


class Command(_M):
    command: str
    description: str = Field(default="", max_length=256)
    target: str

    @field_validator("command")
    @classmethod
    def _c(cls, v: str) -> str:
        v = v.strip().lstrip("/").lower()
        if not _CMD.match(v) or v in ("start", "admin", "cancel"):
            raise ValueError(f"/{v}: buyruq nomi noto'g'ri yoki band")
        return v


class SetupStep(_M):
    """Sozlash ustasi qadami: egasidan bot ma'lumotini (global o'zgaruvchi) so'raydi."""

    key: str
    label: str = Field(min_length=1, max_length=300)
    example: str = Field(default="", max_length=200)

    @field_validator("key")
    @classmethod
    def _k(cls, v: str) -> str:
        return _var_key(v, "qadam") or ""


class Variable(_M):
    key: str
    label: str = Field(default="", max_length=64)
    default: str = Field(default="", max_length=200)
    scope: Literal["user", "global"] = "user"

    @field_validator("key")
    @classmethod
    def _k(cls, v: str) -> str:
        v = _var_key(v) or ""
        if v in BUILTIN_VARS:
            raise ValueError(f"{{{v}}} — tizim o'zgaruvchisi, boshqa nom tanlang")
        return v


class FormStep(_M):
    key: str
    question: str = Field(min_length=1, max_length=MAX_TEXT)
    type: Literal["text", "number", "phone", "email", "photo", "choice", "contact", "location"] = "text"
    options: list[str] = Field(default_factory=list, max_length=12)

    @field_validator("key")
    @classmethod
    def _k(cls, v: str) -> str:
        return _var_key(v, "javob") or ""

    @model_validator(mode="after")
    def _check(self):
        self.options = [o.strip()[:64] for o in self.options if o.strip()]
        if self.type == "choice" and not self.options:
            raise ValueError("tanlov savoli uchun variantlar kiritilmagan")
        return self


class Form(_M):
    id: str
    title: str = Field(min_length=1, max_length=64)
    steps: list[FormStep] = Field(min_length=1, max_length=20)
    done_text: str = Field(default="✅ Rahmat! Javoblaringiz qabul qilindi.", max_length=MAX_TEXT)
    target: str | None = None
    notify: bool = True  # javoblar egasiga yuboriladi

    @field_validator("id")
    @classmethod
    def _id(cls, v: str) -> str:
        if not _PAGE_ID.match(v):
            raise ValueError("forma identifikatori noto'g'ri")
        return v


class Referral(_M):
    enabled: bool = False
    reward: int = Field(default=1, ge=0, le=1_000_000)
    var: str = "balance"
    notify: bool = True
    text: str = Field(default="🎉 {name} sizning havolangiz orqali qo'shildi! Sizga +{reward} ball.", max_length=1000)

    @field_validator("var")
    @classmethod
    def _v(cls, v: str) -> str:
        return _var_key(v) or "balance"


class Channel(_M):
    chat: str
    title: str = Field(default="", max_length=64)
    url: str | None = None

    @model_validator(mode="after")
    def _check(self):
        self.chat = self.chat.strip()
        if not _CHAT.match(self.chat):
            raise ValueError(f"{self.chat}: kanal @username yoki -100... ID bo'lsin")
        if self.url and not _URL.match(self.url):
            self.url = None
        if not self.url and self.chat.startswith("@"):
            self.url = f"https://t.me/{self.chat[1:]}"
        return self


class Module(_M):
    type: Literal["catalog", "cart", "orders", "booking", "mybookings"]
    layout: Literal["list", "cards"] = "list"  # list — bitta xabarda ro'yxat; cards — har mahsulot alohida xabar
    per_page: int = Field(default=8, ge=1, le=20)


class ShopItem(_M):
    id: str
    category: str  # module=catalog bo'lgan sahifa id'si
    title: str = Field(min_length=1, max_length=64)
    text: str = Field(default="", max_length=900)  # HTML
    price: int = Field(ge=0, le=10_000_000_000)
    old_price: int | None = Field(default=None, ge=0, le=10_000_000_000)
    badge: str = Field(default="", max_length=20)
    file_id: str | None = Field(default=None, max_length=300)  # egasi yuborgan rasm
    media_id: int | None = None
    active: bool = True

    @field_validator("id")
    @classmethod
    def _id(cls, v: str) -> str:
        if not _PAGE_ID.match(v):
            raise ValueError("mahsulot identifikatori noto'g'ri")
        return v


class CheckoutField(_M):
    key: str
    label: str = Field(min_length=1, max_length=200)
    type: Literal["text", "number", "phone", "email", "choice", "location"] = "text"
    options: list[str] = Field(default_factory=list, max_length=12)

    @field_validator("key")
    @classmethod
    def _k(cls, v: str) -> str:
        return _var_key(v, "maydon") or ""


DEFAULT_BOOKING_FIELDS = [
    {"key": "ism", "label": "👤 Ismingiz?", "type": "text", "options": []},
    {"key": "telefon", "label": "📱 Telefon raqamingiz?", "type": "phone", "options": []},
]

DEFAULT_CHECKOUT = [
    {"key": "ism", "label": "👤 Ismingiz?", "type": "text", "options": []},
    {"key": "telefon", "label": "📱 Telefon raqamingiz?", "type": "phone", "options": []},
    {"key": "manzil", "label": "📍 Yetkazib berish manzili? (yoki joylashuvni yuboring)", "type": "text", "options": []},
]


class Shop(_M):
    enabled: bool = False
    currency: str = Field(default="so'm", max_length=12)
    items: list[ShopItem] = Field(default_factory=list, max_length=500)
    checkout: list[CheckoutField] = Field(default_factory=lambda: [CheckoutField(**f) for f in DEFAULT_CHECKOUT], min_length=1, max_length=10)
    delivery_fee: int = Field(default=0, ge=0, le=100_000_000)
    free_from: int = Field(default=0, ge=0, le=10_000_000_000)  # shu summadan yetkazish bepul (0 — yo'q)
    min_order: int = Field(default=0, ge=0, le=10_000_000_000)
    done_text: str = Field(default="✅ Buyurtmangiz qabul qilindi! Raqami: <b>#{order}</b>\nTez orada bog'lanamiz.", max_length=1000)

    @model_validator(mode="after")
    def _check(self):
        ids = [i.id for i in self.items]
        if len(set(ids)) != len(ids):
            raise ValueError("mahsulot identifikatorlari takrorlanmasin")
        keys = [f.key for f in self.checkout]
        if len(set(keys)) != len(keys):
            raise ValueError("buyurtma formasi maydonlari takrorlanmasin")
        return self


_HOURS = re.compile(r"^(?:|([01]\d|2[0-3]):([0-5]\d)-([01]\d|2[0-3]):([0-5]\d))$")
DEFAULT_HOURS = {"0": "09:00-18:00", "1": "09:00-18:00", "2": "09:00-18:00", "3": "09:00-18:00", "4": "09:00-18:00", "5": "09:00-18:00", "6": ""}
WEEKDAYS = ["Dushanba", "Seshanba", "Chorshanba", "Payshanba", "Juma", "Shanba", "Yakshanba"]


class BkService(_M):
    id: str
    title: str = Field(min_length=1, max_length=64)
    minutes: int = Field(default=30, ge=5, le=720)
    price: int = Field(default=0, ge=0, le=10_000_000_000)

    @field_validator("id")
    @classmethod
    def _id(cls, v: str) -> str:
        if not _PAGE_ID.match(v):
            raise ValueError("xizmat identifikatori noto'g'ri")
        return v


class BkStaff(_M):
    id: str
    title: str = Field(min_length=1, max_length=64)

    @field_validator("id")
    @classmethod
    def _id(cls, v: str) -> str:
        if not _PAGE_ID.match(v):
            raise ValueError("xodim identifikatori noto'g'ri")
        return v


class Booking(_M):
    """Yozilish tizimi: xizmatlar × (ixtiyoriy) xodimlar × haftalik ish jadvali → bo'sh vaqtlar."""

    enabled: bool = False
    services: list[BkService] = Field(default_factory=list, max_length=40)
    staff: list[BkStaff] = Field(default_factory=list, max_length=20)
    hours: dict[str, str] = Field(default_factory=lambda: dict(DEFAULT_HOURS))  # "0"=dushanba ... "6"=yakshanba; "" — dam
    step: int = Field(default=30, ge=10, le=240)  # vaqt oralig'i (daqiqa)
    days_ahead: int = Field(default=14, ge=1, le=90)
    min_notice: int = Field(default=1, ge=0, le=72)  # soat: hozirdan shuncha soat oldin yozilib bo'lmaydi
    tz: int = Field(default=5, ge=-12, le=14)  # UTC farqi (Toshkent +5)
    confirm: Literal["manual", "auto"] = "manual"  # manual — egasi tasdiqlaydi
    remind: list[int] = Field(default_factory=lambda: [24, 2], max_length=3)  # necha soat oldin eslatish
    fields: list[CheckoutField] = Field(default_factory=lambda: [CheckoutField(**f) for f in DEFAULT_BOOKING_FIELDS], min_length=1, max_length=8)
    done_text: str = Field(default="✅ Yozilishingiz qabul qilindi!\n\n<b>#{booking}</b> · {service}\n📅 {when}", max_length=1000)

    @model_validator(mode="after")
    def _check(self):
        for coll, what in ((self.services, "xizmat"), (self.staff, "xodim")):
            ids = [x.id for x in coll]
            if len(set(ids)) != len(ids):
                raise ValueError(f"{what} identifikatorlari takrorlanmasin")
        for k, v in self.hours.items():
            if k not in {str(i) for i in range(7)} or not _HOURS.match(v or ""):
                raise ValueError("ish vaqti HH:MM-HH:MM ko'rinishida bo'lsin")
            if v and v[:5] >= v[6:]:
                raise ValueError("ish vaqti tugashi boshlanishidan keyin bo'lsin")
        for i in range(7):
            self.hours.setdefault(str(i), "")
        self.remind = sorted({h for h in self.remind if 1 <= h <= 168}, reverse=True)
        keys = [f.key for f in self.fields]
        if len(set(keys)) != len(keys):
            raise ValueError("yozilish formasi maydonlari takrorlanmasin")
        return self


STYLES = ("reply", "inline", "hybrid")


class Menu(_M):
    start: str
    # Yangi bo'limlar uslubi: reply — klaviatura tugmalari; inline — xabar ostidagi tugmalar; hybrid — ikkalasi
    style: Literal["reply", "inline", "hybrid"] = "reply"
    first_start: str | None = None
    pages: list[Page] = Field(min_length=1)
    keywords: list[Keyword] = Field(default_factory=list, max_length=100)
    commands: list[Command] = Field(default_factory=list, max_length=50)
    variables: list[Variable] = Field(default_factory=list, max_length=50)
    forms: list[Form] = Field(default_factory=list, max_length=20)
    referral: Referral = Referral()
    channels: list[Channel] = Field(default_factory=list, max_length=10)
    sub_text: str = Field(default="📢 Botdan foydalanish uchun quyidagi kanallarga obuna bo'ling va «✅ Tekshirish» tugmasini bosing.", max_length=1000)
    admins: list[int] = Field(default_factory=list, max_length=10)
    fallback: str = Field(default="", max_length=1000)
    feedback_prompt: str = Field(default="", max_length=1000)
    feedback_done: str = Field(default="", max_length=1000)
    # true — egasiga yozgan odamning ismi ko'rsatilmaydi (anonim savollar)
    feedback_anonymous: bool = False
    # true — menyuda yo'q har qanday xabar egasiga yuboriladi (qayta aloqa / Livegram uslubi)
    forward_all: bool = False
    shop: Shop = Shop()
    booking: Booking = Booking()
    # Tayyor tizim kodi (sys_shop...) va hali bajarilmagan sozlash ustasi qadamlari (bo'sh — usta tugagan)
    system: str = Field(default="", max_length=32)
    setup: list[SetupStep] = Field(default_factory=list, max_length=12)

    @model_validator(mode="after")
    def _check(self):
        ids = [p.id for p in self.pages]
        if len(set(ids)) != len(ids):
            raise ValueError("sahifa identifikatorlari takrorlanmasin")
        if self.start not in ids:
            raise ValueError("bosh sahifa topilmadi")
        known = set(ids)
        if self.first_start and self.first_start not in known:
            self.first_start = None
        forms = {f.id for f in self.forms}
        if len(forms) != len(self.forms):
            raise ValueError("formalar takrorlanmasin")
        for page in self.pages:
            all_rows = list(page.buttons) + [row for m in page.messages for row in m.buttons]
            for row in all_rows:
                for button in row:
                    if button.target and button.target not in known:
                        raise ValueError(f"«{page.title}» → «{button.text}»: bog'langan sahifa o'chirilgan")
                    if button.action == "random":
                        button.targets = [t for t in button.targets if t in known]
                        if not button.targets:
                            raise ValueError(f"«{page.title}» → «{button.text}»: tasodifiy sahifalar o'chirilgan")
                    if button.action == "form" and button.form not in forms:
                        raise ValueError(f"«{page.title}» → «{button.text}»: forma o'chirilgan")
        for kw in self.keywords:
            if kw.target and kw.target not in known:
                kw.target = None
                if not kw.reply.strip():
                    raise ValueError(f"kalit so'z «{kw.words[0]}»: sahifa o'chirilgan")
        self.commands = [c for c in self.commands if c.target in known]
        if len({c.command for c in self.commands}) != len(self.commands):
            raise ValueError("buyruqlar takrorlanmasin")
        if len({v.key for v in self.variables}) != len(self.variables):
            raise ValueError("o'zgaruvchilar takrorlanmasin")
        for form in self.forms:
            if form.target and form.target not in known:
                form.target = None
        self.admins = list(dict.fromkeys(a for a in self.admins if a > 0))
        catalogs = {p.id for p in self.pages if p.module and p.module.type == "catalog"}
        missing = [i.title for i in self.shop.items if i.category not in catalogs]
        if missing:
            raise ValueError(f"«{missing[0]}» mahsuloti katalog bo'limiga bog'lanmagan (bo'lim o'chirilgan bo'lishi mumkin)")
        return self


# Egasi o'z botiga hali /start bosmagan — Telegram unga xabar yuborishga ruxsat bermaydi.
OWNER_START_HINT = "Xabarlarni olish uchun o'z botingizga kirib /start bosing"

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
            ids = [page.media_id] + [m.media_id for m in page.messages]
            for media_id in ids:
                if media_id is not None and media_id not in owned_media:
                    raise MenuError(f"«{page.title}»: rasm topilmadi — qayta yuklang")
    data = menu.model_dump()
    for key, default in DEFAULT_TEXTS.items():
        data[key] = (data.get(key) or "").strip() or default
    return data


def iter_buttons(page: dict):
    """Sahifadagi barcha tugmalar: menyu (klaviatura) va postlar ostidagi inline tugmalar."""
    for row in page.get("buttons") or []:
        yield from row
    for m in page.get("messages") or []:
        for row in m.get("buttons") or []:
            yield from row


def menu_media(raw: dict) -> set[int]:
    ids: set[int] = set()
    for page in raw.get("pages", []):
        if page.get("media_id"):
            ids.add(int(page["media_id"]))
        for m in page.get("messages") or []:
            if m.get("media_id"):
                ids.add(int(m["media_id"]))
    return ids


def page_by_id(menu: dict, page_id: str | None) -> dict | None:
    for page in menu.get("pages", []):
        if page["id"] == page_id:
            return page
    return None


def form_by_id(menu: dict, form_id: str | None) -> dict | None:
    for form in menu.get("forms", []):
        if form["id"] == form_id:
            return form
    return None


def new_page_id() -> str:
    return "p" + secrets.token_hex(3)


# --- O'zgaruvchilar va shartlar ---

_TOKEN = re.compile(r"\{([a-z][a-z0-9_]{0,31})\}")


def render_text(text: str, *, name: str | None, username: str | None, bot: str) -> str:
    """Eski (oddiy matn) sahifalar uchun."""
    return (
        text.replace("{name}", name or "do'stim")
        .replace("{username}", f"@{username}" if username else (name or ""))
        .replace("{bot}", bot)
    )


def fill(text: str, values: dict[str, str], *, escape: bool) -> str:
    """{kalit} → qiymat. escape=True — HTML matn uchun qiymatlar xavfsizlanadi. Noma'lum kalit o'zgarishsiz qoladi."""

    def sub(m: re.Match) -> str:
        key = m.group(1)
        if key not in values:
            return m.group(0)
        value = str(values[key])
        if key == "mention" and escape:
            return value  # o'zi tayyor HTML havola
        return html.escape(value, quote=False) if escape else value

    return _TOKEN.sub(sub, text)


def _num(v) -> float | None:
    try:
        return float(str(v).replace(",", ".").replace(" ", ""))
    except (TypeError, ValueError):
        return None


def check_cond(cond: dict | None, values: dict[str, str]) -> bool:
    if not cond:
        return True
    raw = values.get(cond.get("var", ""))
    cur = "" if raw is None else str(raw)
    op, want = cond.get("op", "eq"), str(cond.get("value", ""))
    if op == "set":
        return cur.strip() != "" and cur != "0"
    if op == "unset":
        return cur.strip() == "" or cur == "0"
    if op == "contains":
        return want.lower() in cur.lower()
    a, b = _num(cur), _num(want)
    if op in ("gt", "lt", "ge", "le"):
        if a is None or b is None:
            return False
        return {"gt": a > b, "lt": a < b, "ge": a >= b, "le": a <= b}[op]
    same = (a == b) if a is not None and b is not None else cur.strip().lower() == want.strip().lower()
    return same if op == "eq" else not same


def apply_op(current: str | None, op: str, value: str) -> str:
    if op == "clear":
        return ""
    if op in ("add", "sub"):
        a, b = _num(current) or 0, _num(value) or 0
        r = a + b if op == "add" else a - b
        return str(int(r)) if float(r).is_integer() else f"{r:.2f}".rstrip("0").rstrip(".")
    return value


COND_OPS = {"=": "eq", "==": "eq", "!=": "ne", ">": "gt", "<": "lt", ">=": "ge", "<=": "le"}


def parse_cond(text: str) -> dict | None:
    """«vip = 1», «ball > 10», «phone bor», «phone yo'q» → shart."""
    t = text.strip()
    m = re.match(r"^\{?([a-z][a-z0-9_]{0,31})\}?\s*(>=|<=|!=|==|=|>|<)\s*(.{0,100})$", t, re.I)
    if m:
        return {"var": m.group(1).lower(), "op": COND_OPS[m.group(2)], "value": m.group(3).strip()}
    m = re.match(r"^\{?([a-z][a-z0-9_]{0,31})\}?\s+(bor|yo'q|yoq|mavjud|bo'sh)$", t, re.I)
    if m:
        return {"var": m.group(1).lower(), "op": "set" if m.group(2).lower() in ("bor", "mavjud") else "unset", "value": ""}
    return None


def parse_op(text: str) -> dict | None:
    """«ball +1», «ball -5», «vip = 1», «promo tozalash» → amal."""
    t = text.strip()
    m = re.match(r"^\{?([a-z][a-z0-9_]{0,31})\}?\s*([+-])\s*(\d+(?:[.,]\d+)?)$", t, re.I)
    if m:
        return {"var": m.group(1).lower(), "op": "add" if m.group(2) == "+" else "sub", "value": m.group(3).replace(",", ".")}
    m = re.match(r"^\{?([a-z][a-z0-9_]{0,31})\}?\s*=\s*(.{0,200})$", t, re.I)
    if m:
        return {"var": m.group(1).lower(), "op": "set", "value": m.group(2).strip()}
    m = re.match(r"^\{?([a-z][a-z0-9_]{0,31})\}?\s+(tozalash|o'chirish|clear)$", t, re.I)
    if m:
        return {"var": m.group(1).lower(), "op": "clear", "value": ""}
    return None


def describe_cond(c: dict | None) -> str:
    if not c:
        return "yo'q"
    sym = {"eq": "=", "ne": "≠", "gt": ">", "lt": "<", "ge": "≥", "le": "≤", "contains": "ichida"}
    if c["op"] == "set":
        return f"{{{c['var']}}} bor"
    if c["op"] == "unset":
        return f"{{{c['var']}}} yo'q"
    return f"{{{c['var']}}} {sym.get(c['op'], '=')} {c.get('value', '')}"


def now_values() -> dict[str, str]:
    now = datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=5)))  # Toshkent
    return {"date": now.strftime("%d.%m.%Y"), "time": now.strftime("%H:%M")}


# --- Telegram entities → HTML (egasi yuborgan formatlangan matn aynan saqlanadi) ---

_TAGS = {
    "bold": ("<b>", "</b>"),
    "italic": ("<i>", "</i>"),
    "underline": ("<u>", "</u>"),
    "strikethrough": ("<s>", "</s>"),
    "spoiler": ("<tg-spoiler>", "</tg-spoiler>"),
    "code": ("<code>", "</code>"),
    "blockquote": ("<blockquote>", "</blockquote>"),
    "expandable_blockquote": ("<blockquote expandable>", "</blockquote>"),
}


def entities_to_html(text: str, entities: list[dict] | None) -> str:
    """Telegram offsetlari UTF-16 birliklarida — shunga mos hisoblanadi."""
    if not text:
        return ""
    if not entities:
        return html.escape(text, quote=False)
    units = text.encode("utf-16-le")
    n = len(units) // 2
    opens: dict[int, list[tuple[int, str]]] = {}
    closes: dict[int, list[tuple[int, str]]] = {}
    for i, e in enumerate(entities):
        kind = e.get("type")
        start, end = e.get("offset", 0), e.get("offset", 0) + e.get("length", 0)
        if kind in _TAGS:
            o, c = _TAGS[kind]
        elif kind == "pre":
            lang = e.get("language")
            o, c = (f'<pre><code class="language-{html.escape(lang)}">', "</code></pre>") if lang else ("<pre>", "</pre>")
        elif kind == "text_link" and e.get("url"):
            o, c = f'<a href="{html.escape(e["url"])}">', "</a>"
        elif kind == "text_mention" and e.get("user", {}).get("id"):
            o, c = f'<a href="tg://user?id={int(e["user"]["id"])}">', "</a>"
        elif kind == "custom_emoji" and e.get("custom_emoji_id"):
            o, c = f'<tg-emoji emoji-id="{html.escape(str(e["custom_emoji_id"]))}">', "</tg-emoji>"
        else:
            continue
        # uzunroq (tashqi) teg avval ochilsin va keyin yopilsin
        opens.setdefault(start, []).append((-(end - start), o))
        closes.setdefault(end, []).append((end - start, c))
        _ = i
    out: list[str] = []
    i = 0
    while i <= n:
        for _, c in sorted(closes.get(i, [])):
            out.append(c)
        for _, o in sorted(opens.get(i, [])):
            out.append(o)
        if i == n:
            break
        cu = int.from_bytes(units[2 * i : 2 * i + 2], "little")
        if 0xD800 <= cu <= 0xDBFF and i + 1 < n:
            ch = units[2 * i : 2 * i + 4].decode("utf-16-le")
            out.append(html.escape(ch, quote=False))
            i += 2
            continue
        out.append(html.escape(units[2 * i : 2 * i + 2].decode("utf-16-le", errors="ignore"), quote=False))
        i += 1
    return "".join(out)


def html_to_plain(text: str) -> str:
    return html.unescape(re.sub(r"<[^>]+>", "", text or ""))


def message_to_msg(message: dict) -> dict | None:
    """Egasi yuborgan istalgan Telegram xabari → sahifa xabari (Msg)."""
    caption = entities_to_html(message.get("caption") or "", message.get("caption_entities"))
    if message.get("text"):
        return {"type": "text", "text": entities_to_html(message["text"], message.get("entities")), "file_id": None, "media_id": None}
    if message.get("photo"):
        return {"type": "photo", "text": caption, "file_id": message["photo"][-1]["file_id"], "media_id": None}
    for kind in ("video", "animation", "document", "audio", "voice", "video_note", "sticker"):
        if message.get(kind):
            return {"type": kind, "text": "" if kind in CAPTIONLESS else caption, "file_id": message[kind]["file_id"], "media_id": None}
    return None


MSG_LABELS = {
    "text": "📝 Matn",
    "photo": "🖼 Rasm",
    "video": "🎬 Video",
    "animation": "🎞 GIF",
    "document": "📎 Fayl",
    "audio": "🎵 Audio",
    "voice": "🎤 Ovozli xabar",
    "video_note": "⭕ Video-xabar",
    "sticker": "💟 Stiker",
}

ACTION_LABELS = {
    "page": "📄 Sahifa",
    "url": "🔗 Havola",
    "back": "⬅️ Orqaga",
    "home": "🏠 Bosh menyu",
    "feedback": "💬 Adminga yozish",
    "webapp": "🌐 Web App",
    "alert": "🔔 Ogohlantirish",
    "form": "📝 Forma",
    "set": "🔢 O'zgaruvchi",
    "share": "📤 Ulashish",
    "check_sub": "✅ Obunani tekshirish",
    "contact": "📱 Telefon so'rash",
    "location": "📍 Joylashuv so'rash",
    "notify": "🔔 Adminga bildirish",
    "random": "🎲 Tasodifiy sahifa",
}


# --- Tayyor shablonlar (core/bot_templates.py) ---


def template_menu(code: str) -> dict:
    if code.startswith("sys_"):
        from core.systems import build_system

        built = build_system(code)
        if built is not None:
            return built
    template = TEMPLATES.get(code) or TEMPLATES["blank"]
    menu = copy.deepcopy(template["menu"])
    for key, default in DEFAULT_TEXTS.items():
        menu.setdefault(key, default)
    return menu


def templates_public() -> list[dict]:
    """Tayyor tizimlar (savollar bilan sozlanadi) birinchi, keyin oddiy shablonlar."""
    from core.systems import systems_public

    # Eski shablonlar (shop, salon...) tizimlar bilan almashtirilgan — kod bo'yicha hamon ishlaydi, ro'yxatda ko'rinmaydi
    return systems_public() + [
        {"code": code, "icon": t["icon"], "title": t["title"], "desc": t["desc"], "pages": len(t["menu"]["pages"])}
        for code, t in TEMPLATES.items()
        if code == "blank"
    ]


Page.model_rebuild()


def money(amount: int, currency: str = "so'm") -> str:
    return f"{amount:,}".replace(",", " ") + f" {currency}"


def shop_item(menu: dict, item_id: str | None) -> dict | None:
    for item in (menu.get("shop") or {}).get("items") or []:
        if item["id"] == item_id:
            return item
    return None


def catalog_pages(menu: dict) -> list[dict]:
    return [p for p in menu.get("pages", []) if (p.get("module") or {}).get("type") == "catalog"]
