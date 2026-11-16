"""Kodsiz Web App (Telegram Mini App) konstruktori: hujjat sxemasi, tekshiruv va yordamchilar.

Hujjat (web_apps.draft / published):

    {
      "version": 1,
      "theme": {"preset": "ocean", "adaptive": false, "primary": "#2f80ed", "background": "#f4f6fb",
                "surface": "#ffffff", "text": "#111418", "radius": 16, "font": "system"},
      "settings": {"title": "...", "currency": "so'm", "checkout_fields": [...], "checkout_success": "..."},
      "start": "home",
      "pages": [{"id": "home", "title": "Bosh sahifa", "emoji": "🏠", "in_nav": true, "blocks": [...]}]
    }

Har bir blokda: {"id", "type", "hidden", ...turiga xos maydonlar}. Bloklar turi pastda (BLOCK_TYPES).
Foydalanuvchi matni hech qachon HTML sifatida ko'rsatilmaydi (React escape qiladi), havolalar faqat
http(s)/tg — shuning uchun ilovalar bizning domenda xavfsiz ishlaydi."""

import datetime
import re
from typing import Annotated, Literal, Union

from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator, model_validator

MAX_PAGES = 20
MAX_BLOCKS = 60
_ID = re.compile(r"^[A-Za-z0-9_-]{1,32}$")
_URL = re.compile(r"^(https?://|tg://)[^\s<>\"']{1,1000}$")
_HEX = re.compile(r"^#[0-9a-fA-F]{6}$")
_PHONE = re.compile(r"^\+?[0-9 ()-]{5,20}$")
_TG_USER = re.compile(r"^@?[A-Za-z0-9_]{4,32}$")
_YT = re.compile(r"(?:youtube\.com/(?:watch\?v=|embed/|shorts/)|youtu\.be/)([A-Za-z0-9_-]{11})")
_EMAIL = re.compile(r"^[^@\s]{1,64}@[^@\s]{1,255}\.[A-Za-z]{2,}$")

FONTS = ("system", "rounded", "serif", "mono")
THEME_PRESETS: dict[str, dict] = {
    "telegram": {"title": "Telegram mavzusi", "adaptive": True, "primary": "#2f80ed", "background": "#f1f2f6", "surface": "#ffffff", "text": "#111418"},
    "light": {"title": "Oq", "adaptive": False, "primary": "#2f80ed", "background": "#f4f6fb", "surface": "#ffffff", "text": "#111418"},
    "dark": {"title": "Tun", "adaptive": False, "primary": "#5b9cff", "background": "#0f1115", "surface": "#1a1d24", "text": "#f2f4f8"},
    "ocean": {"title": "Okean", "adaptive": False, "primary": "#0ea5e9", "background": "#eef8fd", "surface": "#ffffff", "text": "#0c2233"},
    "peach": {"title": "Shaftoli", "adaptive": False, "primary": "#f97360", "background": "#fff5f1", "surface": "#ffffff", "text": "#2b1712"},
    "forest": {"title": "O'rmon", "adaptive": False, "primary": "#16a34a", "background": "#f1f8f2", "surface": "#ffffff", "text": "#0f2416"},
    "lavender": {"title": "Lavanda", "adaptive": False, "primary": "#8b5cf6", "background": "#f6f3ff", "surface": "#ffffff", "text": "#1d1433"},
    "gold": {"title": "Qora-oltin", "adaptive": False, "primary": "#d4a72c", "background": "#0d0d0d", "surface": "#1a1a1a", "text": "#f5efe0"},
}

DEFAULT_CHECKOUT_FIELDS = [
    {"id": "name", "type": "text", "label": "Ismingiz", "placeholder": "", "required": True, "options": []},
    {"id": "phone", "type": "phone", "label": "Telefon raqamingiz", "placeholder": "+998 90 123 45 67", "required": True, "options": []},
    {"id": "address", "type": "textarea", "label": "Manzil", "placeholder": "Shahar, ko'cha, uy", "required": False, "options": []},
    {"id": "comment", "type": "textarea", "label": "Izoh", "placeholder": "", "required": False, "options": []},
]


class WebAppError(ValueError):
    """Foydalanuvchiga ko'rsatiladigan tushunarli xato."""


class _M(BaseModel):
    model_config = ConfigDict(extra="ignore")


def _url_ok(v: str | None) -> str | None:
    if v is None or v == "":
        return None
    v = v.strip()
    if not _URL.match(v):
        raise ValueError("havola https:// bilan boshlanishi kerak")
    return v


class Action(_M):
    type: Literal["none", "page", "url", "bot", "phone", "share", "cart"] = "none"
    page: str | None = None
    url: str | None = None
    phone: str | None = None

    @model_validator(mode="after")
    def _check(self):
        if self.type == "page" and not self.page:
            raise ValueError("tugma uchun sahifa tanlanmagan")
        if self.type == "url":
            self.url = _url_ok(self.url)
            if not self.url:
                raise ValueError("tugma havolasi kiritilmagan")
        if self.type == "phone" and not (self.phone and _PHONE.match(self.phone)):
            raise ValueError("telefon raqami noto'g'ri")
        return self


class Btn(_M):
    text: str = Field(min_length=1, max_length=40)
    action: Action = Action()


class _Block(_M):
    id: str
    hidden: bool = False

    @field_validator("id")
    @classmethod
    def _id(cls, v: str) -> str:
        if not _ID.match(v):
            raise ValueError("blok identifikatori noto'g'ri")
        return v


class Hero(_Block):
    type: Literal["hero"]
    title: str = Field(min_length=1, max_length=120)
    subtitle: str = Field(default="", max_length=400)
    media_id: int | None = None
    emoji: str = Field(default="", max_length=8)
    align: Literal["center", "left"] = "center"
    button: Btn | None = None


class Heading(_Block):
    type: Literal["heading"]
    text: str = Field(min_length=1, max_length=160)
    size: Literal[1, 2, 3] = 2
    align: Literal["left", "center"] = "left"


class Text(_Block):
    type: Literal["text"]
    text: str = Field(min_length=1, max_length=4000)
    align: Literal["left", "center"] = "left"
    muted: bool = False


class Image(_Block):
    type: Literal["image"]
    media_id: int
    ratio: Literal["auto", "1:1", "4:3", "16:9", "3:4"] = "auto"
    caption: str = Field(default="", max_length=200)
    action: Action = Action()


class Gallery(_Block):
    type: Literal["gallery"]
    media_ids: list[int] = Field(min_length=1, max_length=24)
    columns: Literal[2, 3] = 2


class ButtonBlock(_Block):
    type: Literal["button"]
    text: str = Field(min_length=1, max_length=40)
    style: Literal["primary", "secondary", "outline"] = "primary"
    action: Action = Action()


class Feature(_M):
    emoji: str = Field(default="", max_length=8)
    title: str = Field(min_length=1, max_length=80)
    text: str = Field(default="", max_length=300)


class Features(_Block):
    type: Literal["features"]
    columns: Literal[1, 2] = 2
    items: list[Feature] = Field(min_length=1, max_length=24)


class LinkItem(_M):
    emoji: str = Field(default="", max_length=8)
    title: str = Field(min_length=1, max_length=80)
    subtitle: str = Field(default="", max_length=120)
    action: Action = Action()


class Links(_Block):
    type: Literal["links"]
    items: list[LinkItem] = Field(min_length=1, max_length=30)


class Product(_M):
    id: str
    title: str = Field(min_length=1, max_length=100)
    price: int = Field(ge=0, le=10**12)
    old_price: int | None = Field(default=None, ge=0, le=10**12)
    media_id: int | None = None
    emoji: str = Field(default="", max_length=8)
    text: str = Field(default="", max_length=500)
    badge: str = Field(default="", max_length=20)

    @field_validator("id")
    @classmethod
    def _id(cls, v: str) -> str:
        if not _ID.match(v):
            raise ValueError("mahsulot identifikatori noto'g'ri")
        return v


class Products(_Block):
    type: Literal["products"]
    title: str = Field(default="", max_length=80)
    columns: Literal[1, 2] = 2
    items: list[Product] = Field(min_length=1, max_length=100)


FieldType = Literal["text", "textarea", "phone", "email", "number", "select", "radio", "checkbox", "date"]


class FormField(_M):
    id: str
    type: FieldType = "text"
    label: str = Field(min_length=1, max_length=100)
    placeholder: str = Field(default="", max_length=100)
    required: bool = False
    options: list[str] = Field(default_factory=list, max_length=20)

    @model_validator(mode="after")
    def _check(self):
        if not _ID.match(self.id):
            raise ValueError("maydon identifikatori noto'g'ri")
        self.options = [o.strip()[:80] for o in self.options if o.strip()]
        if self.type in ("select", "radio") and not self.options:
            raise ValueError(f"«{self.label}» uchun variantlar kiritilmagan")
        return self


def _unique_fields(fields: list[FormField], where: str) -> list[FormField]:
    ids = [f.id for f in fields]
    if len(set(ids)) != len(ids):
        raise ValueError(f"{where}: maydonlar takrorlanmasin")
    return fields


class Form(_Block):
    type: Literal["form"]
    title: str = Field(default="", max_length=120)
    fields: list[FormField] = Field(min_length=1, max_length=20)
    submit_text: str = Field(default="Yuborish", min_length=1, max_length=40)
    success_text: str = Field(default="✅ Yuborildi! Tez orada bog'lanamiz.", max_length=300)

    @model_validator(mode="after")
    def _check(self):
        _unique_fields(self.fields, self.title or "Forma")
        return self


class Contacts(_Block):
    type: Literal["contacts"]
    phone: str | None = None
    telegram: str | None = None
    instagram: str | None = None
    website: str | None = None
    address: str = Field(default="", max_length=200)
    map_url: str | None = None

    @model_validator(mode="after")
    def _check(self):
        if self.phone and not _PHONE.match(self.phone):
            raise ValueError("telefon raqami noto'g'ri")
        for name in ("telegram", "instagram"):
            v = getattr(self, name)
            if v:
                if not _TG_USER.match(v):
                    raise ValueError(f"{name} nomi noto'g'ri (masalan: @nomi)")
                setattr(self, name, v.lstrip("@"))
            else:
                setattr(self, name, None)
        self.website = _url_ok(self.website)
        self.map_url = _url_ok(self.map_url)
        self.phone = self.phone or None
        return self


class FaqItem(_M):
    q: str = Field(min_length=1, max_length=200)
    a: str = Field(min_length=1, max_length=1500)


class Faq(_Block):
    type: Literal["faq"]
    items: list[FaqItem] = Field(min_length=1, max_length=40)


class Plan(_M):
    name: str = Field(min_length=1, max_length=60)
    price: str = Field(default="", max_length=40)
    period: str = Field(default="", max_length=30)
    features: list[str] = Field(default_factory=list, max_length=12)
    highlight: bool = False
    button: Btn | None = None


class Pricing(_Block):
    type: Literal["pricing"]
    items: list[Plan] = Field(min_length=1, max_length=6)


class Stat(_M):
    value: str = Field(min_length=1, max_length=20)
    label: str = Field(default="", max_length=60)


class Stats(_Block):
    type: Literal["stats"]
    items: list[Stat] = Field(min_length=1, max_length=6)


class Countdown(_Block):
    type: Literal["countdown"]
    title: str = Field(default="", max_length=120)
    date: datetime.datetime
    done_text: str = Field(default="Boshlandi! 🎉", max_length=200)


class Video(_Block):
    type: Literal["video"]
    url: str
    caption: str = Field(default="", max_length=200)

    @field_validator("url")
    @classmethod
    def _yt(cls, v: str) -> str:
        if not youtube_id(v):
            raise ValueError("faqat YouTube havolasi (youtube.com yoki youtu.be)")
        return v.strip()


class Divider(_Block):
    type: Literal["divider"]
    style: Literal["line", "space"] = "line"
    size: Literal["s", "m", "l"] = "m"


Block = Annotated[
    Union[Hero, Heading, Text, Image, Gallery, ButtonBlock, Features, Links, Products, Form, Contacts, Faq, Pricing, Stats, Countdown, Video, Divider],
    Field(discriminator="type"),
]

BLOCK_TYPES = [
    "hero", "heading", "text", "image", "gallery", "button", "features", "links",
    "products", "form", "contacts", "faq", "pricing", "stats", "countdown", "video", "divider",
]


class Page(_M):
    id: str
    title: str = Field(min_length=1, max_length=40)
    emoji: str = Field(default="", max_length=8)
    in_nav: bool = True
    blocks: list[Block] = Field(default_factory=list, max_length=MAX_BLOCKS)

    @field_validator("id")
    @classmethod
    def _id(cls, v: str) -> str:
        if not _ID.match(v):
            raise ValueError("sahifa identifikatori noto'g'ri")
        return v


class Theme(_M):
    preset: str = "telegram"
    adaptive: bool = True
    primary: str = "#2f80ed"
    background: str = "#f1f2f6"
    surface: str = "#ffffff"
    text: str = "#111418"
    radius: int = Field(default=16, ge=0, le=28)
    font: Literal["system", "rounded", "serif", "mono"] = "system"

    @model_validator(mode="after")
    def _check(self):
        for name in ("primary", "background", "surface", "text"):
            if not _HEX.match(getattr(self, name)):
                raise ValueError("rang #RRGGBB ko'rinishida bo'lsin")
        return self


class Settings(_M):
    title: str = Field(default="", max_length=64)
    currency: str = Field(default="so'm", max_length=12)
    checkout_fields: list[FormField] = Field(default_factory=lambda: [FormField(**f) for f in DEFAULT_CHECKOUT_FIELDS], max_length=12)
    checkout_success: str = Field(default="✅ Buyurtmangiz qabul qilindi! Tez orada bog'lanamiz.", max_length=300)

    @model_validator(mode="after")
    def _check(self):
        _unique_fields(self.checkout_fields, "Buyurtma formasi")
        return self


class AppDoc(_M):
    version: int = 1
    theme: Theme = Theme()
    settings: Settings = Settings()
    start: str
    pages: list[Page] = Field(min_length=1, max_length=MAX_PAGES)

    @model_validator(mode="after")
    def _check(self):
        page_ids = [p.id for p in self.pages]
        if len(set(page_ids)) != len(page_ids):
            raise ValueError("sahifalar takrorlanmasin")
        if self.start not in page_ids:
            raise ValueError("bosh sahifa topilmadi")
        known = set(page_ids)
        block_ids: set[str] = set()
        product_ids: set[str] = set()
        for page in self.pages:
            for block in page.blocks:
                if block.id in block_ids:
                    raise ValueError(f"«{page.title}»: bloklar takrorlanmasin")
                block_ids.add(block.id)
                for action in _actions(block):
                    if action.type == "page" and action.page not in known:
                        raise ValueError(f"«{page.title}»: tugma o'chirilgan sahifaga bog'langan")
                if isinstance(block, Products):
                    for item in block.items:
                        if item.id in product_ids:
                            raise ValueError(f"«{page.title}»: mahsulotlar takrorlanmasin")
                        product_ids.add(item.id)
        return self


def _actions(block) -> list[Action]:
    out: list[Action] = []
    if isinstance(block, (ButtonBlock, Image)):
        out.append(block.action)
    elif isinstance(block, Hero) and block.button:
        out.append(block.button.action)
    elif isinstance(block, Links):
        out += [i.action for i in block.items]
    elif isinstance(block, Pricing):
        out += [p.button.action for p in block.items if p.button]
    return out


_ERR_UZ = {
    "greater_than_equal": "qiymat {ge} dan kam bo'lmasin",
    "less_than_equal": "qiymat {le} dan oshmasin",
    "string_too_short": "bo'sh qolmasin",
    "string_too_long": "matn juda uzun ({max_length} belgigacha)",
    "too_short": "kamida bitta element qo'shing",
    "too_long": "ko'pi bilan {max_length} ta",
    "missing": "to'ldirilmagan",
    "int_parsing": "butun son kiriting",
    "int_type": "butun son kiriting",
    "literal_error": "noto'g'ri tanlov",
    "datetime_parsing": "sana noto'g'ri",
    "datetime_from_date_parsing": "sana noto'g'ri",
    "union_tag_invalid": "noma'lum blok turi",
    "union_tag_not_found": "blok turi ko'rsatilmagan",
}


def _error_message(exc: ValidationError, raw: dict) -> str:
    err = exc.errors()[0]
    template = _ERR_UZ.get(err.get("type", ""))
    if template:
        try:
            msg = template.format(**(err.get("ctx") or {}))
        except (KeyError, IndexError):
            msg = template
    else:
        msg = str(err.get("msg", "noto'g'ri qiymat")).removeprefix("Value error, ")
    loc = err.get("loc", ())
    try:
        if len(loc) >= 2 and loc[0] == "pages":
            page = raw["pages"][loc[1]]
            where = f"«{page.get('title') or 'sahifa'}»"
            if len(loc) >= 4 and loc[2] == "blocks":
                where += f", {loc[3] + 1}-blok"
            return f"{where}: {msg}"
        if loc and loc[0] == "theme":
            return f"Uslub: {msg}"
        if loc and loc[0] == "settings":
            return f"Sozlamalar: {msg}"
    except (KeyError, IndexError, TypeError):
        pass
    return msg


def validate_app(raw: dict, owned_media: set[int] | None = None) -> dict:
    """Tekshiradi va tozalangan hujjatni qaytaradi. Xato bo'lsa WebAppError (o'zbekcha)."""
    try:
        doc = AppDoc.model_validate(raw)
    except ValidationError as exc:
        raise WebAppError(_error_message(exc, raw if isinstance(raw, dict) else {})) from exc
    data = doc.model_dump(mode="json")
    if owned_media is not None:
        missing = referenced_media(data) - owned_media
        if missing:
            raise WebAppError("Ba'zi rasmlar topilmadi — ularni qayta yuklang")
    return data


def referenced_media(doc: dict) -> set[int]:
    ids: set[int] = set()
    for page in doc.get("pages", []):
        for b in page.get("blocks", []):
            if b.get("media_id"):
                ids.add(int(b["media_id"]))
            for m in b.get("media_ids") or []:
                ids.add(int(m))
            if b.get("type") == "products":
                ids |= {int(i["media_id"]) for i in b.get("items", []) if i.get("media_id")}
    return ids


def find_block(doc: dict, block_id: str) -> dict | None:
    for page in doc.get("pages", []):
        for b in page.get("blocks", []):
            if b.get("id") == block_id and not b.get("hidden"):
                return b
    return None


def products_index(doc: dict) -> dict[str, dict]:
    out: dict[str, dict] = {}
    for page in doc.get("pages", []):
        for b in page.get("blocks", []):
            if b.get("type") == "products" and not b.get("hidden"):
                for item in b.get("items", []):
                    out[item["id"]] = item
    return out


def compute_order(doc: dict, items: list[dict]) -> tuple[list[dict], int]:
    """Savatchani e'lon qilingan narxlar bo'yicha QAYTA hisoblaydi (mijoz yuborgan narxga ishonilmaydi)."""
    index = products_index(doc)
    lines: list[dict] = []
    total = 0
    for item in items[:100]:
        product = index.get(str(item.get("id")))
        try:
            qty = int(item.get("qty", 0))
        except (TypeError, ValueError):
            qty = 0
        if product is None or not 1 <= qty <= 999:
            continue
        line_total = product["price"] * qty
        lines.append({"id": product["id"], "title": product["title"], "price": product["price"], "qty": qty, "sum": line_total})
        total += line_total
    if not lines:
        raise WebAppError("Savatcha bo'sh yoki mahsulotlar o'zgargan — sahifani yangilang")
    return lines, total


def clean_values(fields: list[dict], values: dict) -> dict[str, str]:
    """Forma qiymatlarini maydonlar bo'yicha tekshiradi. {label: qiymat} qaytaradi (egasiga ko'rsatish uchun)."""
    out: dict[str, str] = {}
    for f in fields:
        raw = values.get(f["id"])
        if f["type"] == "checkbox":
            value = "Ha" if raw in (True, "true", "1", "on") else ""
        else:
            value = str(raw if raw is not None else "").strip()[:2000]
        if not value:
            if f.get("required"):
                raise WebAppError(f"«{f['label']}» to'ldirilmagan")
            continue
        if f["type"] == "phone" and not _PHONE.match(value):
            raise WebAppError(f"«{f['label']}»: telefon raqami noto'g'ri")
        if f["type"] == "email" and not _EMAIL.match(value):
            raise WebAppError(f"«{f['label']}»: email noto'g'ri")
        if f["type"] == "number":
            try:
                float(value.replace(",", "."))
            except ValueError as exc:
                raise WebAppError(f"«{f['label']}»: son kiriting") from exc
        if f["type"] in ("select", "radio") and value not in f.get("options", []):
            raise WebAppError(f"«{f['label']}»: variantlardan birini tanlang")
        out[f["label"]] = value
    return out


def youtube_id(url: str | None) -> str | None:
    if not url:
        return None
    m = _YT.search(url)
    return m.group(1) if m else None


def money(amount: int, currency: str) -> str:
    return f"{amount:,}".replace(",", " ") + (f" {currency}" if currency else "")
