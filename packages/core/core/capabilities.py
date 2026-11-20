"""Imkoniyat reyestri: Telegram Bot API imkoniyatlari bitta joyda (sxema + tavsif + qaysi Bot API metodlari).

Bitta e'lon (pydantic sxema) AVTOMATIK ravishda hosil qiladi:
    • menyu hujjatini tekshirish (oqim qadamlari/triggerlari — core/botbuilder.Flow),
    • egasi interfeysidagi so'rovlar ketma-ketligi (maydon nomi, turi, tanlovlar — chatdagi oqim muharriri),
    • AI uchun hujjat (ai_doc) — yangi imkoniyat qo'shilishi bilan AI uni o'zi biladi,
    • API qamrov matritsasi (tools/api_coverage.py): bot_api maydonidan «qaysi metod qoplangan».

Yangi imkoniyat qo'shish: sxema sinfini yozing, @action / @trigger bilan e'lon qiling, runner'da (apps/botrunner/flows.py)
handler yozing. Interfeys, AI va qamrov hisoboti o'zi yangilanadi."""

import re
import typing
from dataclasses import dataclass, field
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator

_KEY = re.compile(r"^[a-z][a-z0-9_]{0,31}$")


class _P(BaseModel):
    model_config = ConfigDict(extra="ignore")


def _ui(kind: str, example: str = "") -> dict:
    return {"ui": kind, "example": example}


@dataclass(frozen=True)
class Capability:
    id: str
    kind: str  # "action" | "trigger"
    schema: type[BaseModel]
    title: str
    icon: str
    group: str
    bot_api: tuple = ()
    help: str = ""
    # runner: bu amal oqimni to'xtatib foydalanuvchi javobini kutadimi (ask)
    waits: bool = False


REGISTRY: dict[str, Capability] = {}


def _register(kind: str, id_: str, title: str, icon: str, group: str, bot_api: tuple = (), help_: str = "", waits: bool = False):
    def deco(cls):
        REGISTRY[f"{kind}:{id_}"] = Capability(id_, kind, cls, title, icon, group, bot_api, help_, waits)
        return cls

    return deco


def action(*a, **k):
    return _register("action", *a, **k)


def trigger(*a, **k):
    return _register("trigger", *a, **k)


# ============================================================
# Amallar
# ============================================================


@action("send_text", "Xabar yuborish", "💬", "Xabarlar", ("sendMessage",), "Matn (HTML, {o'zgaruvchi} bilan)")
class SendText(_P):
    text: str = Field(min_length=1, max_length=4096, description="Xabar matni", json_schema_extra=_ui("long", "Salom, {name}! 👋"))
    preview: bool = Field(default=False, description="Havola ko'rinishi (preview) bo'lsinmi?", json_schema_extra=_ui("bool"))
    silent: bool = Field(default=False, description="Ovozsiz (jim) yuborilsinmi?", json_schema_extra=_ui("bool"))
    protect: bool = Field(default=False, description="Ulashish/saqlashni taqiqlash?", json_schema_extra=_ui("bool"))


@action("send_location", "Joylashuv yuborish", "📍", "Xabarlar", ("sendLocation", "sendVenue"), "Xaritadagi nuqta (nom/manzil bo'lsa — joy kartasi)")
class SendLocation(_P):
    latitude: float = Field(ge=-90, le=90, description="Kenglik (latitude)", json_schema_extra=_ui("float", "41.311081"))
    longitude: float = Field(ge=-180, le=180, description="Uzunlik (longitude)", json_schema_extra=_ui("float", "69.240562"))
    title: str = Field(default="", max_length=100, description="Joy nomi (ixtiyoriy)", json_schema_extra=_ui("text", "Bizning ofis"))
    address: str = Field(default="", max_length=200, description="Manzil (ixtiyoriy)", json_schema_extra=_ui("text", "Toshkent, Amir Temur 1"))


@action("send_contact", "Kontakt yuborish", "📇", "Xabarlar", ("sendContact",), "Telefon raqamli kontakt kartasi")
class SendContact(_P):
    phone: str = Field(min_length=5, max_length=30, description="Telefon raqami", json_schema_extra=_ui("text", "+998901234567"))
    first_name: str = Field(min_length=1, max_length=64, description="Ism", json_schema_extra=_ui("text", "Menejer Aziza"))
    last_name: str = Field(default="", max_length=64, description="Familiya (ixtiyoriy)", json_schema_extra=_ui("text"))


@action("send_poll", "So'rovnoma / viktorina", "📊", "Xabarlar", ("sendPoll",), "Telegram so'rovnomasi; viktorina rejimida to'g'ri javob va izoh")
class SendPoll(_P):
    question: str = Field(min_length=1, max_length=300, description="Savol", json_schema_extra=_ui("text", "Qaysi taom yoqadi?"))
    options: list[str] = Field(min_length=2, max_length=10, description="Javob variantlari (har qatorga bittadan, 2–10 ta)", json_schema_extra=_ui("lines", "Osh\nLag'mon\nSomsa"))
    anonymous: bool = Field(default=True, description="Anonim bo'lsinmi? (javobni o'zgaruvchiga saqlash uchun «yo'q» tanlang)", json_schema_extra=_ui("bool"))
    multiple: bool = Field(default=False, description="Bir nechta javob tanlash mumkinmi?", json_schema_extra=_ui("bool"))
    quiz: bool = Field(default=False, description="Viktorina rejimi (bitta to'g'ri javob)?", json_schema_extra=_ui("bool"))
    correct: int = Field(default=1, ge=1, le=10, description="To'g'ri javob raqami (viktorinada, 1 dan boshlab)", json_schema_extra=_ui("int", "1"))
    explanation: str = Field(default="", max_length=200, description="Viktorina izohi (ixtiyoriy)", json_schema_extra=_ui("text"))
    var: str | None = Field(default=None, description="Tanlangan javob saqlanadigan o'zgaruvchi (ixtiyoriy)", json_schema_extra=_ui("var", "tanlov"))

    @field_validator("options")
    @classmethod
    def _opts(cls, v: list[str]) -> list[str]:
        out = [o.strip()[:100] for o in v if o.strip()]
        if len(out) < 2:
            raise ValueError("kamida 2 ta javob varianti kerak")
        return out

    @field_validator("var")
    @classmethod
    def _var(cls, v: str | None) -> str | None:
        v = (v or "").strip().lower().strip("{}")
        if v and not _KEY.match(v):
            raise ValueError("o'zgaruvchi nomi lotin kichik harf/raqam/_ bo'lsin")
        return v or None


@action("send_dice", "Dice (o'yin kubigi)", "🎲", "O'yinlar", ("sendDice",), "🎲🎯🏀⚽🎳🎰 — natija o'zgaruvchiga saqlanadi")
class SendDice(_P):
    emoji: Literal["🎲", "🎯", "🏀", "⚽", "🎳", "🎰"] = Field(default="🎲", description="Qaysi o'yin?", json_schema_extra=_ui("choice"))
    var: str | None = Field(default=None, description="Natija (tushgan son) saqlanadigan o'zgaruvchi", json_schema_extra=_ui("var", "dice"))

    @field_validator("var")
    @classmethod
    def _var(cls, v: str | None) -> str | None:
        v = (v or "").strip().lower().strip("{}")
        if v and not _KEY.match(v):
            raise ValueError("o'zgaruvchi nomi lotin kichik harf/raqam/_ bo'lsin")
        return v or None


@action("typing", "«Yozmoqda…» indikatori", "⌨️", "Xabarlar", ("sendChatAction",), "Tabiiy kechikish: yozmoqda/rasm yuklamoqda...")
class Typing(_P):
    action: Literal["typing", "upload_photo", "record_video", "upload_video", "record_voice", "upload_voice", "upload_document", "choose_sticker", "find_location"] = Field(
        default="typing", description="Qaysi holat?", json_schema_extra=_ui("choice")
    )
    seconds: int = Field(default=2, ge=1, le=5, description="Necha soniya (1–5)", json_schema_extra=_ui("int", "2"))


@action("react", "Xabarga reaksiya", "👍", "Xabarlar", ("setMessageReaction",), "Foydalanuvchi xabariga emoji reaksiya qo'yadi")
class React(_P):
    emoji: Literal["👍", "❤", "🔥", "🎉", "👏", "😁", "🤔", "🙏", "👌", "💯", "⚡", "🏆"] = Field(default="👍", description="Qaysi emoji?", json_schema_extra=_ui("choice"))


@action("set_var", "O'zgaruvchini o'zgartirish", "🔢", "Ma'lumot", (), "Qo'yish, qo'shish, ayirish, tozalash")
class SetVar(_P):
    var: str = Field(description="O'zgaruvchi nomi", json_schema_extra=_ui("var", "ball"))
    op: Literal["set", "add", "sub", "clear"] = Field(default="set", description="Amal", json_schema_extra=_ui("choice"))
    value: str = Field(default="", max_length=200, description="Qiymat ({o'zgaruvchi} ishlatish mumkin)", json_schema_extra=_ui("text", "1"))

    @field_validator("var")
    @classmethod
    def _var(cls, v: str) -> str:
        v = v.strip().lower().strip("{}")
        if not _KEY.match(v):
            raise ValueError("o'zgaruvchi nomi lotin kichik harf/raqam/_ bo'lsin")
        return v


@action("notify_admin", "Adminga bildirish", "🔔", "Ma'lumot", ("sendMessage",), "Egasi va adminlarga xabar (foydalanuvchi ma'lumoti bilan)")
class NotifyAdmin(_P):
    text: str = Field(min_length=1, max_length=1000, description="Bildirish matni", json_schema_extra=_ui("long", "{name} yangi so'rov qoldirdi"))


@action("wait", "Kutish", "⏱", "Boshqaruv", (), "Keyingi qadamgacha qisqa pauza (1–10 soniya)")
class Wait(_P):
    seconds: int = Field(default=2, ge=1, le=10, description="Necha soniya (1–10)", json_schema_extra=_ui("int", "3"))


@action("open_page", "Bo'limni ochish", "📄", "Boshqaruv", ("sendMessage",), "Botdagi mavjud bo'limni foydalanuvchiga ko'rsatadi")
class OpenPage(_P):
    page: str = Field(description="Bo'lim", json_schema_extra=_ui("page"))


@action("ask", "Javob so'rash", "❓", "Boshqaruv", ("sendMessage",), "Savol beradi, foydalanuvchi javobini o'zgaruvchiga saqlab, oqimni davom ettiradi", waits=True)
class Ask(_P):
    question: str = Field(min_length=1, max_length=1000, description="Savol matni", json_schema_extra=_ui("long", "Ismingiz nima?"))
    var: str = Field(description="Javob saqlanadigan o'zgaruvchi", json_schema_extra=_ui("var", "ism"))
    input: Literal["text", "number", "phone", "email", "photo", "location", "choice", "document", "voice", "video", "sticker", "any"] = Field(
        default="text", description="Javob turi", json_schema_extra=_ui("choice")
    )
    options: list[str] = Field(default_factory=list, max_length=12, description="Variantlar (faqat «choice» uchun, har qatorga bittadan)", json_schema_extra=_ui("lines", "Ha\nYo'q"))

    @field_validator("var")
    @classmethod
    def _var(cls, v: str) -> str:
        v = v.strip().lower().strip("{}")
        if not _KEY.match(v):
            raise ValueError("o'zgaruvchi nomi lotin kichik harf/raqam/_ bo'lsin")
        return v

    @field_validator("options")
    @classmethod
    def _opts(cls, v: list[str]) -> list[str]:
        return [o.strip()[:64] for o in v if o.strip()][:12]


@action("stop", "To'xtatish", "⛔", "Boshqaruv", (), "Oqimni shu yerda tugatadi (shartli qadam bilan birga ishlatiladi)")
class Stop(_P):
    pass


# ============================================================
# Triggerlar
# ============================================================


@trigger("command", "Buyruq", "⌨️", "Triggerlar", ("getUpdates",), "/buyruq yozilganda")
class TrCommand(_P):
    command: str = Field(min_length=1, max_length=32, description="Buyruq (slashsiz)", json_schema_extra=_ui("text", "narx"))

    @field_validator("command")
    @classmethod
    def _c(cls, v: str) -> str:
        v = v.strip().lstrip("/").lower()
        if not re.fullmatch(r"[a-z0-9_]{1,32}", v) or v in ("start", "admin", "cancel", "tickets"):
            raise ValueError("buyruq lotin harf/raqam/_ bo'lsin (start, admin, cancel, tickets band)")
        return v


@trigger("text", "Matn", "🔤", "Triggerlar", ("getUpdates",), "Foydalanuvchi shunday matn yozganda")
class TrText(_P):
    match: Literal["exact", "contains", "start", "regex"] = Field(default="contains", description="Qanday moslik?", json_schema_extra=_ui("choice"))
    text: str = Field(min_length=1, max_length=200, description="Matn yoki ibora", json_schema_extra=_ui("text", "narx"))

    @field_validator("text")
    @classmethod
    def _t(cls, v: str) -> str:
        return v.strip()


@trigger("new_user", "Yangi foydalanuvchi", "🆕", "Triggerlar", ("getUpdates",), "Botga birinchi marta /start bosganda")
class TrNewUser(_P):
    pass


@trigger("message_type", "Xabar turi", "📎", "Triggerlar", ("getUpdates",), "Foydalanuvchi rasm/ovoz/hujjat/joylashuv... yuborganda")
class TrMessageType(_P):
    kind: Literal["photo", "video", "voice", "audio", "document", "sticker", "animation", "video_note", "location", "contact", "poll", "dice"] = Field(
        default="photo", description="Qaysi tur?", json_schema_extra=_ui("choice")
    )


@trigger("poll_answer", "So'rovnomaga javob", "🗳", "Triggerlar", ("getUpdates",), "Foydalanuvchi oqim yuborgan so'rovnomada ovoz berganda ({poll_choice} o'zgaruvchisi)")
class TrPollAnswer(_P):
    pass


# ============================================================
# Yordamchilar
# ============================================================


def get(kind: str, id_: str) -> Capability | None:
    return REGISTRY.get(f"{kind}:{id_}")


def by_kind(kind: str) -> list[Capability]:
    return [c for c in REGISTRY.values() if c.kind == kind]


def validate(kind: str, id_: str, params: dict | None) -> dict:
    """Parametrlarni tekshiradi va tozalangan lug'atni qaytaradi. Xato — ValueError (o'zbekcha)."""
    cap = get(kind, id_)
    if cap is None:
        raise ValueError(f"noma'lum {'amal' if kind == 'action' else 'trigger'}: {id_}")
    try:
        return cap.schema.model_validate(params or {}).model_dump()
    except ValidationError as exc:
        err = exc.errors()[0]
        where = ".".join(str(x) for x in err.get("loc", ()))
        raise ValueError(f"«{cap.title}»: {where + ' — ' if where else ''}{str(err.get('msg', 'noto‘g‘ri')).removeprefix('Value error, ')}") from exc


@dataclass
class FieldSpec:
    name: str
    label: str
    ui: str  # text | long | int | float | bool | choice | lines | var | page
    required: bool
    default: object = None
    choices: list = field(default_factory=list)
    example: str = ""


def fields_of(cap: Capability) -> list[FieldSpec]:
    """Egasi interfeysi uchun maydonlar ro'yxati (sxemadan avtomatik)."""
    out = []
    for name, info in cap.schema.model_fields.items():
        extra = info.json_schema_extra or {}
        ann = info.annotation
        choices: list = []
        for arg in [ann, *typing.get_args(ann)]:
            if typing.get_origin(arg) is Literal:
                choices = list(typing.get_args(arg))
        ui = extra.get("ui") or ("choice" if choices else "text")
        out.append(FieldSpec(name, info.description or name, ui, info.is_required(), None if info.is_required() else info.get_default(call_default_factory=True), choices, extra.get("example", "")))
    return out


def parse_value(spec: FieldSpec, raw: str):
    """Egasi yozgan matnni maydon turiga aylantiradi. Xato — ValueError (o'zbekcha)."""
    text = (raw or "").strip()
    if spec.ui == "int":
        try:
            return int(float(text.replace(",", ".").replace(" ", "")))
        except ValueError as exc:
            raise ValueError("butun son kiriting") from exc
    if spec.ui == "float":
        try:
            return float(text.replace(",", ".").replace(" ", ""))
        except ValueError as exc:
            raise ValueError("son kiriting (masalan 41.311)") from exc
    if spec.ui == "bool":
        if text.lower() in ("ha", "yes", "true", "1", "✅", "bor"):
            return True
        if text.lower() in ("yo'q", "yoq", "no", "false", "0", "❌", "yo‘q"):
            return False
        raise ValueError("«Ha» yoki «Yo'q» deb javob bering")
    if spec.ui == "lines":
        return [ln.strip() for ln in text.splitlines() if ln.strip()]
    if spec.ui == "choice":
        for c in spec.choices:
            if text == str(c):
                return c
        raise ValueError("variantlardan birini tanlang")
    return text


def summary(kind: str, id_: str, params: dict) -> str:
    """Qisqa tavsif (ro'yxatlar uchun)."""
    cap = get(kind, id_)
    if cap is None:
        return id_
    parts = []
    for spec in fields_of(cap)[:2]:
        v = params.get(spec.name)
        if v not in (None, "", [], False):
            parts.append(str(v if not isinstance(v, list) else ", ".join(v))[:30])
    return f"{cap.icon} {cap.title}" + (f": {' · '.join(parts)}" if parts else "")


def ai_doc() -> str:
    """AI uchun oqimlar hujjati — reyestrdan avtomatik."""

    def line(cap: Capability) -> str:
        fields = []
        for s in fields_of(cap):
            t = {"int": "int", "float": "number", "bool": "true|false", "lines": "[str]", "var": "var-name", "page": "page-id", "long": "str", "text": "str"}.get(s.ui, "|".join(map(str, s.choices)) if s.choices else "str")
            fields.append(f'"{s.name}": {t}' + ("" if s.required else "?"))
        return f' - {cap.id}: {{{", ".join(fields)}}} — {cap.title}. {cap.help}'

    return (
        "FLOWS (custom automation, any logic the pages/modules do not cover):\n"
        ' "flows": [{"id": "<[a-z0-9_-]>", "title": "...", "enabled": true, "trigger": {"type": TRIGGER, "params": {...}},\n'
        '            "steps": [{"type": ACTION, "params": {...}, "when": {"var": "ball", "op": "ge", "value": "10"} (optional condition)}]}]\n'
        " Steps run top to bottom; a step with a failing \"when\" is skipped. Texts may use {variables}. An \"ask\" step pauses the flow until the user answers.\n"
        "TRIGGERS:\n" + "\n".join(line(c) for c in by_kind("trigger")) + "\nACTIONS:\n" + "\n".join(line(c) for c in by_kind("action"))
    )


def bot_api_methods() -> set[str]:
    """Reyestr qoplagan Bot API metodlari."""
    return {m for c in REGISTRY.values() for m in c.bot_api}
