"""Web App ma'lumotlar bazasi: to'plam (jadval) tavsifi va yozuvlarni tekshirish.

To'plam:  {key, name, read: public|own|none, create: bool,
           fields: [{key, label, type, required, private, options}]}
Yozuv:    {maydon_kaliti: qiymat, ...}  (app_records.data, JSONB)

Maydon turlari: text, longtext, number, money, image, date, bool, select, phone, url, email.
private — maydon ilovada boshqalarga ko'rsatilmaydi (masalan telefon); egasi va yozuv muallifi ko'radi."""

import csv
import datetime
import io
import re
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator

MAX_COLLECTIONS = 20
MAX_FIELDS = 40
MAX_RECORDS = 5000

FIELD_TYPES = ("text", "longtext", "number", "money", "image", "date", "bool", "select", "phone", "url", "email")
FieldType = Literal["text", "longtext", "number", "money", "image", "date", "bool", "select", "phone", "url", "email"]

_KEY = re.compile(r"^[a-z][a-z0-9_]{0,31}$")
_PHONE = re.compile(r"^\+?[0-9 ()-]{5,20}$")
_URL = re.compile(r"^https?://[^\s<>\"']{1,1000}$")
_EMAIL = re.compile(r"^[^@\s]{1,64}@[^@\s]{1,255}\.[A-Za-z]{2,}$")
_DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


class DataError(ValueError):
    """Foydalanuvchiga ko'rsatiladigan xato."""


class _M(BaseModel):
    model_config = ConfigDict(extra="ignore")


class FieldDef(_M):
    key: str
    label: str = Field(min_length=1, max_length=64)
    type: FieldType = "text"
    required: bool = False
    private: bool = False
    options: list[str] = Field(default_factory=list, max_length=50)

    @model_validator(mode="after")
    def _check(self):
        if not _KEY.match(self.key):
            raise ValueError(f"«{self.label}»: kalit faqat lotin kichik harf, raqam va _ (harf bilan boshlansin)")
        self.options = [o.strip()[:80] for o in self.options if o.strip()]
        if self.type == "select" and not self.options:
            raise ValueError(f"«{self.label}»: variantlar kiritilmagan")
        return self


class CollectionDef(_M):
    key: str
    name: str = Field(min_length=1, max_length=64)
    read: Literal["public", "own", "none"] = "public"
    create: bool = False
    fields: list[FieldDef] = Field(min_length=1, max_length=MAX_FIELDS)

    @model_validator(mode="after")
    def _check(self):
        if not _KEY.match(self.key):
            raise ValueError("to'plam kaliti faqat lotin kichik harf, raqam va _ bo'lsin")
        keys = [f.key for f in self.fields]
        if len(set(keys)) != len(keys):
            raise ValueError("maydon kalitlari takrorlanmasin")
        if "id" in keys:
            raise ValueError("«id» kaliti band — boshqa nom tanlang")
        return self


def validate_collection(raw: dict) -> dict:
    try:
        return CollectionDef.model_validate(raw).model_dump()
    except ValidationError as exc:
        err = exc.errors()[0]
        raise DataError(str(err.get("msg", "noto'g'ri to'plam")).removeprefix("Value error, ")) from exc


def _clean_value(f: dict, raw):
    t = f["type"]
    if t == "bool":
        return raw in (True, "true", "1", 1, "on", "ha", "Ha", "yes")
    if raw is None or (isinstance(raw, str) and raw.strip() == ""):
        return None
    if t in ("number", "money"):
        try:
            num = float(str(raw).replace(" ", "").replace(",", "."))
        except ValueError as exc:
            raise DataError(f"«{f['label']}»: son kiriting") from exc
        if t == "money":
            if num < 0:
                raise DataError(f"«{f['label']}»: manfiy bo'lmasin")
            return int(round(num))
        return int(num) if num.is_integer() else num
    if t == "image":
        try:
            return int(raw)
        except (TypeError, ValueError) as exc:
            raise DataError(f"«{f['label']}»: rasm noto'g'ri") from exc
    value = str(raw).strip()
    if t == "text" and len(value) > 500:
        raise DataError(f"«{f['label']}»: 500 belgidan oshmasin")
    if t == "longtext" and len(value) > 5000:
        raise DataError(f"«{f['label']}»: 5000 belgidan oshmasin")
    if t == "date":
        if not _DATE.match(value):
            raise DataError(f"«{f['label']}»: sana YYYY-MM-DD ko'rinishida bo'lsin")
        try:
            datetime.date.fromisoformat(value)
        except ValueError as exc:
            raise DataError(f"«{f['label']}»: sana noto'g'ri") from exc
    if t == "phone" and not _PHONE.match(value):
        raise DataError(f"«{f['label']}»: telefon raqami noto'g'ri")
    if t == "url" and not _URL.match(value):
        raise DataError(f"«{f['label']}»: havola https:// bilan boshlansin")
    if t == "email" and not _EMAIL.match(value):
        raise DataError(f"«{f['label']}»: email noto'g'ri")
    if t == "select" and value not in f.get("options", []):
        raise DataError(f"«{f['label']}»: variantlardan birini tanlang")
    return value[:5000]


def clean_record(fields: list[dict], data: dict, *, from_user: bool = False, owned_media: set[int] | None = None) -> dict:
    """Yozuvni maydonlar bo'yicha tekshiradi. from_user — ilova foydalanuvchisi (rasm yuklay olmaydi)."""
    out: dict = {}
    for f in fields:
        if from_user and f["type"] == "image":
            continue
        value = _clean_value(f, data.get(f["key"]))
        if value is None:
            if f.get("required"):
                raise DataError(f"«{f['label']}» to'ldirilmagan")
            continue
        if f["type"] == "image" and owned_media is not None and value not in owned_media:
            raise DataError(f"«{f['label']}»: rasm topilmadi — qayta yuklang")
        out[f["key"]] = value
    return out


def record_view(fields: list[dict], record_id: int, data: dict, *, show_private: bool) -> dict:
    out = {"id": record_id}
    for f in fields:
        if f.get("private") and not show_private:
            continue
        if f["key"] in data:
            out[f["key"]] = data[f["key"]]
    return out


def image_fields(fields: list[dict]) -> list[str]:
    return [f["key"] for f in fields if f["type"] == "image"]


# --- CSV ---


def to_csv(fields: list[dict], rows: list[tuple[int, dict]]) -> str:
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(["id", *[f["key"] for f in fields]])
    for rid, data in rows:
        writer.writerow([rid, *[("ha" if data.get(f["key"]) is True else "" if data.get(f["key"]) is None else data.get(f["key"])) for f in fields]])
    return "﻿" + buf.getvalue()  # Excel o'zbekcha harflarni to'g'ri ochsin


def from_csv(fields: list[dict], text: str, limit: int) -> list[dict]:
    """Sarlavha — maydon kaliti yoki nomi. Rasm maydonlari import qilinmaydi."""
    reader = csv.DictReader(io.StringIO(text.lstrip("﻿")))
    by_name = {}
    for f in fields:
        by_name[f["key"].lower()] = f["key"]
        by_name[f["label"].strip().lower()] = f["key"]
    rows = []
    for i, row in enumerate(reader, start=2):
        if len(rows) >= limit:
            break
        data = {by_name[k.strip().lower()]: v for k, v in row.items() if k and k.strip().lower() in by_name}
        if not any(str(v).strip() for v in data.values()):
            continue
        try:
            rows.append(clean_record([f for f in fields if f["type"] != "image"], data))
        except DataError as exc:
            raise DataError(f"{i}-qator: {exc}") from exc
    return rows
