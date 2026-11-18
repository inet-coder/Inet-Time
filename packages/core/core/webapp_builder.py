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
# Google Fonts (ilova ochilganda kerak bo'lganlari yuklanadi): kalit -> oila nomi
GOOGLE_FONTS: dict[str, str] = {
    "inter": "Inter",
    "manrope": "Manrope",
    "montserrat": "Montserrat",
    "rubik": "Rubik",
    "nunito": "Nunito",
    "poppins": "Poppins",
    "raleway": "Raleway",
    "playfair": "Playfair Display",
    "lora": "Lora",
    "oswald": "Oswald",
    "comfortaa": "Comfortaa",
    "jetbrains": "JetBrains Mono",
}
FONT_KEYS = FONTS + tuple(GOOGLE_FONTS)
ICONS = frozenset(['Activity', 'AlertCircle', 'ArrowLeft', 'ArrowRight', 'ArrowUpRight', 'Award', 'Baby', 'Bath', 'BedDouble', 'Bell', 'Bike', 'Book', 'BookOpen', 'Box', 'Briefcase', 'Brush', 'Building', 'Building2', 'Cake', 'Calendar', 'CalendarCheck', 'Camera', 'Car', 'ChartBar', 'Check', 'ChevronRight', 'CircleCheck', 'CircleHelp', 'Clock', 'Cloud', 'Code', 'Coffee', 'Compass', 'Copy', 'Cpu', 'CreditCard', 'Crown', 'Database', 'Diamond', 'Dog', 'Download', 'Dumbbell', 'Eye', 'Filter', 'Flame', 'Flower2', 'Gem', 'Gift', 'Globe', 'GraduationCap', 'Hammer', 'Headphones', 'Heart', 'Hotel', 'House', 'Image', 'Info', 'Key', 'Laptop', 'Leaf', 'Link', 'Lock', 'Mail', 'Map', 'MapPin', 'MessageCircle', 'MessageSquare', 'Mic', 'Minus', 'Monitor', 'Moon', 'Music', 'Navigation', 'Package', 'Palette', 'PawPrint', 'Pen', 'PenLine', 'Percent', 'Phone', 'PieChart', 'Pill', 'Pizza', 'Plane', 'Play', 'Plus', 'Rocket', 'Scissors', 'Search', 'Send', 'Settings', 'Share2', 'Shield', 'ShieldCheck', 'Shirt', 'ShoppingBag', 'ShoppingCart', 'Smartphone', 'Smile', 'Sofa', 'Sparkles', 'Star', 'Stethoscope', 'Store', 'Sun', 'Tag', 'Target', 'ThumbsUp', 'Ticket', 'TrendingUp', 'Trophy', 'Truck', 'Umbrella', 'Upload', 'User', 'Users', 'Utensils', 'Video', 'Wallet', 'Wifi', 'Wrench', 'X', 'Zap'])
MAX_NODES = 400
MAX_DEPTH = 10
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
    type: Literal["none", "page", "url", "bot", "phone", "share", "cart", "detail"] = "none"
    page: str | None = None
    url: str | None = None
    phone: str | None = None

    @model_validator(mode="after")
    def _check(self):
        if self.type in ("page", "detail") and not self.page:
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



def _hex_or_none(v: str | None) -> str | None:
    if v in (None, ""):
        return None
    if not _HEX.match(v):
        raise ValueError("rang #RRGGBB ko'rinishida bo'lsin")
    return v


# Mavzu ranglari: ilova mavzusi o'zgarsa (yoki tun rejimi) — element ham moslashadi
COLOR_TOKENS = ("$primary", "$on_primary", "$bg", "$surface", "$text", "$hint", "$line")


def _color_or_none(v: str | None) -> str | None:
    if v in COLOR_TOKENS:
        return v
    return _hex_or_none(v)


class Style(_M):
    """Har qanday blok yoki element uchun uslub. Hammasi ixtiyoriy — berilmagani mavzudan olinadi."""

    px: int | None = Field(default=None, ge=0, le=160)
    py: int | None = Field(default=None, ge=0, le=200)
    mt: int | None = Field(default=None, ge=-80, le=200)
    mb: int | None = Field(default=None, ge=-80, le=200)
    width: Literal["auto", "full", "fit"] | None = None
    max_width: int | None = Field(default=None, ge=0, le=1600)
    min_height: int | None = Field(default=None, ge=0, le=1200)
    bg: str | None = None
    bg2: str | None = None
    bg_angle: int = Field(default=160, ge=0, le=360)
    bg_image: int | None = None
    overlay: int = Field(default=0, ge=0, le=90)
    color: str | None = None
    border: int | None = Field(default=None, ge=0, le=12)
    border_color: str | None = None
    radius: int | None = Field(default=None, ge=0, le=999)
    shadow: Literal["none", "s", "m", "l", "xl", "glow", "inner", "hard"] | None = None
    opacity: int | None = Field(default=None, ge=5, le=100)
    font: str | None = None
    size: int | None = Field(default=None, ge=8, le=120)
    weight: int | None = Field(default=None, ge=100, le=900)
    align: Literal["left", "center", "right"] | None = None
    line: float | None = Field(default=None, ge=0.8, le=3)
    letter: int | None = Field(default=None, ge=-10, le=40)
    uppercase: bool = False
    # --- 1.2: kreativ dizayn ---
    italic: bool = False
    decoration: Literal["underline", "line-through"] | None = None
    clamp: int | None = Field(default=None, ge=1, le=12)  # matn n qatordan keyin «…»
    nowrap: bool = False
    text_grad: str | None = None  # matn gradienti (2 rang)
    text_grad2: str | None = None
    w: int | None = Field(default=None, ge=0, le=1600)  # aniq kenglik (px)
    w_pct: int | None = Field(default=None, ge=1, le=100)  # kenglik (%)
    h: int | None = Field(default=None, ge=0, le=1600)  # aniq balandlik (px)
    aspect: Literal["1:1", "4:3", "3:2", "16:9", "21:9", "3:4", "2:3", "9:16"] | None = None
    grow: bool = False  # qatorda bo'sh joyni egallasin
    self_align: Literal["start", "center", "end", "stretch"] | None = None
    overflow: Literal["hidden", "visible", "scroll"] | None = None
    pos: Literal["relative", "absolute", "sticky", "fixed"] | None = None
    top: int | None = Field(default=None, ge=-800, le=2000)
    right: int | None = Field(default=None, ge=-800, le=2000)
    bottom: int | None = Field(default=None, ge=-800, le=2000)
    left: int | None = Field(default=None, ge=-800, le=2000)
    z: int | None = Field(default=None, ge=-10, le=100)
    rotate: int | None = Field(default=None, ge=-360, le=360)
    scale: int | None = Field(default=None, ge=10, le=400)  # %
    tx: int | None = Field(default=None, ge=-800, le=800)
    ty: int | None = Field(default=None, ge=-800, le=800)
    skew: int | None = Field(default=None, ge=-45, le=45)
    bg_type: Literal["linear", "radial", "conic"] | None = None
    bg_alpha: int | None = Field(default=None, ge=0, le=100)  # fon rangining shaffofligi
    bg_size: Literal["cover", "contain", "tile"] | None = None
    blur: int | None = Field(default=None, ge=0, le=60)
    backdrop: int | None = Field(default=None, ge=0, le=60)  # «shisha» effekti
    bright: int | None = Field(default=None, ge=0, le=200)
    gray: int | None = Field(default=None, ge=0, le=100)
    border_style: Literal["solid", "dashed", "dotted", "double"] | None = None
    shadow_color: str | None = None
    gap: int | None = Field(default=None, ge=0, le=120)
    span: int | None = Field(default=None, ge=1, le=8)  # to'rda nechta ustun egallaydi
    row_span: int | None = Field(default=None, ge=1, le=8)

    @model_validator(mode="after")
    def _check(self):
        for name in ("bg", "bg2", "color", "border_color", "text_grad", "text_grad2", "shadow_color"):
            setattr(self, name, _color_or_none(getattr(self, name)))
        if self.font is not None and self.font not in FONT_KEYS:
            raise ValueError("noma'lum shrift")
        return self


Anim = Literal["none", "fade", "up", "down", "zoom", "zoomout", "left", "right", "flip", "blur", "rotate"]
Loop = Literal["none", "float", "pulse", "spin", "shake", "bounce", "glow", "wiggle", "breathe"]

_DKEY = re.compile(r"^[a-z][a-z0-9_]{0,31}$")


def _dkey(v: str | None, what: str = "maydon") -> str | None:
    if v in (None, ""):
        return None
    if not _DKEY.match(v):
        raise ValueError(f"{what} kaliti noto'g'ri")
    return v


class Query(_M):
    """To'plamdan qaysi yozuvlar olinadi."""

    collection: str
    limit: int = Field(default=20, ge=1, le=100)
    sort_field: str | None = None
    sort_dir: Literal["asc", "desc"] = "desc"
    filter_field: str | None = None
    filter_value: str | None = Field(default=None, max_length=200)
    search: bool = False
    empty_text: str = Field(default="Hozircha hech narsa yo'q", max_length=200)

    @model_validator(mode="after")
    def _check(self):
        _dkey(self.collection, "to'plam")
        self.sort_field = _dkey(self.sort_field)
        self.filter_field = _dkey(self.filter_field)
        return self


class _Node(_M):
    id: str
    name: str = Field(default="", max_length=40)  # qatlam nomi; yorliq/akkordeonda sarlavha
    hidden: bool = False
    style: Style | None = None
    wide: Style | None = None  # keng oyna (≥560px) uchun ustiga yoziladigan qiymatlar
    hover: Style | None = None  # sichqoncha ustida / bosilganda
    anim: Anim = "none"
    delay: int = Field(default=0, ge=0, le=5000)  # animatsiya kechikishi (ms)
    loop: Loop = "none"  # doimiy animatsiya

    @field_validator("id")
    @classmethod
    def _id(cls, v: str) -> str:
        if not _ID.match(v):
            raise ValueError("element identifikatori noto'g'ri")
        return v


class BoxNode(_Node):
    kind: Literal["box"]
    # scroll — gorizontal karusel; stack — qatlamlar ustma-ust; tabs/accordion — bolalar panel bo'ladi
    # (sarlavha — bolaning nomi); marquee — cheksiz yuguruvchi lenta
    layout: Literal["column", "row", "grid", "scroll", "stack", "tabs", "accordion", "marquee"] = "column"
    gap: int = Field(default=12, ge=0, le=96)
    item_w: int | None = Field(default=None, ge=40, le=1200)  # karusel elementi kengligi (px)
    autoplay: int = Field(default=0, ge=0, le=30)  # karusel: har n soniyada
    dots: bool = False
    tabs_style: Literal["pills", "underline", "segmented"] = "pills"
    open_first: bool = True
    speed: int = Field(default=20, ge=3, le=120)  # marquee: bir aylanish (soniya)
    align: Literal["start", "center", "end", "stretch"] = "stretch"
    justify: Literal["start", "center", "end", "between", "around"] = "start"
    wrap: bool = True
    columns: int = Field(default=2, ge=1, le=6)
    columns_wide: int | None = Field(default=None, ge=1, le=8)
    action: "Action | None" = None
    # Takrorlovchi: bolalar to'plamdagi har bir yozuv uchun chiziladi ({{maydon}} bilan)
    repeat: Query | None = None
    children: list["Node"] = Field(default_factory=list, max_length=60)


class TextNode(_Node):
    kind: Literal["text"]
    text: str = Field(min_length=1, max_length=4000)
    tag: Literal["h1", "h2", "h3", "p", "small"] = "p"


class ImageNode(_Node):
    kind: Literal["image"]
    media_id: int | None = None
    fit: Literal["cover", "contain"] = "cover"
    ratio: Literal["auto", "1:1", "4:3", "16:9", "3:4", "21:9", "9:16"] = "auto"
    bind: str | None = None  # rasm yozuvning shu maydonidan olinadi
    action: "Action | None" = None

    @field_validator("bind")
    @classmethod
    def _bind(cls, v: str | None) -> str | None:
        return _dkey(v)


class ButtonNode(_Node):
    kind: Literal["button"]
    text: str = Field(min_length=1, max_length=60)
    variant: Literal["primary", "secondary", "outline", "ghost", "link"] = "primary"
    icon: str | None = None
    action: "Action" = Field(default_factory=lambda: Action())

    @field_validator("icon")
    @classmethod
    def _icon(cls, v: str | None) -> str | None:
        if v and v not in ICONS:
            raise ValueError("noma'lum ikonka")
        return v or None


class IconNode(_Node):
    kind: Literal["icon"]
    icon: str
    size: int = Field(default=28, ge=10, le=160)
    emoji: str = Field(default="", max_length=8)  # ikonka o'rniga emoji
    action: "Action | None" = None

    @field_validator("icon")
    @classmethod
    def _icon(cls, v: str) -> str:
        if v not in ICONS:
            raise ValueError("noma'lum ikonka")
        return v


class SpacerNode(_Node):
    kind: Literal["spacer"]
    size: int = Field(default=16, ge=0, le=240)


class DividerNode(_Node):
    kind: Literal["divider"]


class VideoNode(_Node):
    kind: Literal["video"]
    url: str = ""  # YouTube havolasi

    @field_validator("url")
    @classmethod
    def _yt(cls, v: str) -> str:
        v = (v or "").strip()
        if v and not _YT.search(v):
            raise ValueError("faqat YouTube havolasi")
        return v


class ProgressNode(_Node):
    kind: Literal["progress"]
    value: int = Field(default=60, ge=0, le=100)
    label: str = Field(default="", max_length=80)
    show_value: bool = True
    bar: str | None = None
    thickness: int = Field(default=8, ge=2, le=40)
    shape: Literal["bar", "ring"] = "bar"

    @field_validator("bar")
    @classmethod
    def _bar(cls, v: str | None) -> str | None:
        return _color_or_none(v)


class RatingNode(_Node):
    kind: Literal["rating"]
    value: float = Field(default=4.5, ge=0, le=5)
    size: int = Field(default=18, ge=10, le=60)
    star: str | None = None
    show_value: bool = False

    @field_validator("star")
    @classmethod
    def _star(cls, v: str | None) -> str | None:
        return _color_or_none(v)


class TimerNode(_Node):
    kind: Literal["timer"]
    until: datetime.datetime
    done_text: str = Field(default="Boshlandi!", max_length=80)
    labels: bool = True


class MapNode(_Node):
    kind: Literal["map"]
    query: str = Field(min_length=2, max_length=200)  # manzil yoki «41.31,69.24»
    zoom: int = Field(default=15, ge=3, le=20)
    height: int = Field(default=240, ge=120, le=800)


Node = Annotated[
    Union[BoxNode, TextNode, ImageNode, ButtonNode, IconNode, SpacerNode, DividerNode, VideoNode, ProgressNode, RatingNode, TimerNode, MapNode],
    Field(discriminator="kind"),
]
NODE_KINDS = ["box", "text", "image", "button", "icon", "spacer", "divider", "video", "progress", "rating", "timer", "map"]


class _Block(_M):
    id: str
    hidden: bool = False
    style: Style | None = None  # har qanday blokka umumiy uslub (fon, masofa, burchak...)
    anim: Anim = "none"

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
    save_to: str | None = None  # javoblar shu to'plamga ham yoziladi

    @model_validator(mode="after")
    def _check(self):
        _unique_fields(self.fields, self.title or "Forma")
        self.save_to = _dkey(self.save_to, "to'plam")
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


class CollectionList(_Block):
    """To'plamdagi yozuvlar ro'yxati — kartalar, ro'yxat yoki to'r ko'rinishida."""

    type: Literal["collection"]
    title: str = Field(default="", max_length=80)
    query: Query
    layout: Literal["cards", "list", "grid"] = "cards"
    columns: int = Field(default=2, ge=1, le=4)
    title_field: str | None = None
    subtitle_field: str | None = None
    image_field: str | None = None
    price_field: str | None = None
    badge_field: str | None = None
    detail_page: str | None = None

    @model_validator(mode="after")
    def _check(self):
        for name in ("title_field", "subtitle_field", "image_field", "price_field", "badge_field"):
            setattr(self, name, _dkey(getattr(self, name)))
        return self


class Custom(_Block):
    """Erkin bo'lim: elementlar daraxti (konteyner, matn, rasm, tugma, ikonka...) — istalgan dizayn."""

    type: Literal["custom"]
    name: str = Field(default="Erkin bo'lim", max_length=60)
    root: BoxNode

    @model_validator(mode="after")
    def _check(self):
        count = 0

        def walk(node, depth: int) -> None:
            nonlocal count
            count += 1
            if depth > MAX_DEPTH:
                raise ValueError(f"elementlar {MAX_DEPTH} qavatdan chuqur bo'lmasin")
            for child in getattr(node, "children", []):
                walk(child, depth + 1)

        walk(self.root, 1)
        if count > MAX_NODES:
            raise ValueError(f"bitta bo'limda ko'pi bilan {MAX_NODES} ta element")
        return self


Block = Annotated[
    Union[Hero, Heading, Text, Image, Gallery, ButtonBlock, Features, Links, Products, Form, Contacts, Faq, Pricing, Stats, Countdown, Video, Divider, Custom, CollectionList],
    Field(discriminator="type"),
]

BLOCK_TYPES = [
    "hero", "heading", "text", "image", "gallery", "button", "features", "links",
    "products", "form", "contacts", "faq", "pricing", "stats", "countdown", "video", "divider", "custom", "collection",
]


BoxNode.model_rebuild()
ImageNode.model_rebuild()
ButtonNode.model_rebuild()
IconNode.model_rebuild()
Custom.model_rebuild()


CollectionList.model_rebuild()


class Page(_M):
    id: str
    title: str = Field(min_length=1, max_length=40)
    emoji: str = Field(default="", max_length=8)
    in_nav: bool = True
    # Batafsil sahifa: shu to'plamning bitta yozuvi uchun ochiladi ({{maydon}} bilan)
    collection: str | None = None
    blocks: list[Block] = Field(default_factory=list, max_length=MAX_BLOCKS)

    @field_validator("id")
    @classmethod
    def _id(cls, v: str) -> str:
        if not _ID.match(v):
            raise ValueError("sahifa identifikatori noto'g'ri")
        return v

    @field_validator("collection")
    @classmethod
    def _coll(cls, v: str | None) -> str | None:
        return _dkey(v, "to'plam")


class Theme(_M):
    preset: str = "telegram"
    adaptive: bool = True
    primary: str = "#2f80ed"
    background: str = "#f1f2f6"
    surface: str = "#ffffff"
    text: str = "#111418"
    radius: int = Field(default=16, ge=0, le=28)
    font: str = "system"

    @model_validator(mode="after")
    def _check(self):
        if self.font not in FONT_KEYS:
            raise ValueError("noma'lum shrift")
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
                    if action.type in ("page", "detail") and action.page not in known:
                        raise ValueError(f"«{page.title}»: tugma o'chirilgan sahifaga bog'langan")
                if isinstance(block, CollectionList) and block.detail_page and block.detail_page not in known:
                    raise ValueError(f"«{page.title}»: ro'yxat o'chirilgan sahifaga bog'langan")
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
    elif isinstance(block, Custom):
        stack = [block.root]
        while stack:
            node = stack.pop()
            if getattr(node, "action", None) is not None:
                out.append(node.action)
            stack.extend(getattr(node, "children", []))
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


def used_collections(doc: dict) -> set[str]:
    keys: set[str] = set()
    for page in doc.get("pages", []):
        if page.get("collection"):
            keys.add(page["collection"])
        for b in page.get("blocks", []):
            if b.get("type") == "collection":
                keys.add(b["query"]["collection"])
            if b.get("type") == "form" and b.get("save_to"):
                keys.add(b["save_to"])
            if b.get("type") == "custom":
                stack = [b["root"]]
                while stack:
                    n = stack.pop()
                    if n.get("repeat"):
                        keys.add(n["repeat"]["collection"])
                    stack.extend(n.get("children") or [])
    return keys


def validate_app(raw: dict, owned_media: set[int] | None = None, collections: set[str] | None = None) -> dict:
    """Tekshiradi va tozalangan hujjatni qaytaradi. Xato bo'lsa WebAppError (o'zbekcha)."""
    try:
        doc = AppDoc.model_validate(raw)
    except ValidationError as exc:
        raise WebAppError(_error_message(exc, raw if isinstance(raw, dict) else {})) from exc
    data = doc.model_dump(mode="json")
    if collections is not None:
        missing = used_collections(data) - collections
        if missing:
            raise WebAppError(f"«{sorted(missing)[0]}» to'plami topilmadi — «Ma'lumotlar» bo'limida yarating yoki bog'lanishni o'zgartiring")
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
            if (b.get("style") or {}).get("bg_image"):
                ids.add(int(b["style"]["bg_image"]))
            if b.get("type") == "custom" and b.get("root"):
                stack = [b["root"]]
                while stack:
                    node = stack.pop()
                    if node.get("media_id"):
                        ids.add(int(node["media_id"]))
                    for st in (node.get("style") or {}, node.get("wide") or {}, node.get("hover") or {}):
                        if st.get("bg_image"):
                            ids.add(int(st["bg_image"]))
                    stack.extend(node.get("children") or [])
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


MAX_COMPONENTS = 100


def validate_component(node: dict, owned_media: set[int] | None = None) -> dict:
    """Saqlanadigan komponent: ildizi konteyner bo'lgan elementlar daraxti."""
    raw = {"id": "component", "type": "custom", "root": node}
    try:
        block = Custom.model_validate(raw)
    except ValidationError as exc:
        raise WebAppError(_error_message(exc, {})) from exc
    data = block.model_dump(mode="json")["root"]
    if owned_media is not None:
        doc = {"pages": [{"blocks": [{"type": "custom", "root": data}]}]}
        if referenced_media(doc) - owned_media:
            raise WebAppError("Ba'zi rasmlar topilmadi — ularni qayta yuklang")
    return data
