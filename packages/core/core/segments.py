"""Obunachilar segmentlari: tarqatish, avtomatik xabar va oqimlar auditoriyasi (hammasi SQL shartlari).

Segment turlari:
    all, new7, active7, inactive30, ordered, booked, referrers   — tayyor
    t:<teg>                                                        — shu tegli foydalanuvchilar
    s:<id>                                                         — egasi yaratgan segment (menu["segments"]): shartlar «va» bilan"""

import datetime
import re

from sqlalchemy import Numeric, cast, exists, literal, select
from sqlalchemy.dialects.postgresql import JSONB

from core.db.models import BotBooking, BotOrder, BotSubscriber

SEGMENTS: dict[str, str] = {
    "all": "👥 Hammasi",
    "new7": "🆕 Yangilar (7 kun)",
    "active7": "🟢 Faollar (7 kun)",
    "inactive30": "😴 30 kundan beri jim",
    "ordered": "🛒 Buyurtma berganlar",
    "booked": "📅 Yozilganlar",
    "referrers": "👥 Do'st taklif qilganlar",
}
SEGMENT_RE = re.compile(r"^(all|new7|active7|inactive30|ordered|booked|referrers|t:[a-z0-9_]{1,12}|s:[A-Za-z0-9_-]{1,24})$")
TAG_RE = re.compile(r"[^a-z0-9_]")


def normalize_tag(text: str) -> str:
    """Teg nomi: kichik lotin harf/raqam/_, 12 belgigacha."""
    return TAG_RE.sub("", (text or "").strip().lower().replace(" ", "_").replace("'", ""))[:12]


def tags_of(data: dict | None) -> list[str]:
    raw = (data or {}).get("_tags")
    return [t for t in raw if isinstance(t, str)] if isinstance(raw, list) else []


def cond_sql(cond: dict):
    """Cond (var op value) → BotSubscriber.data bo'yicha SQL sharti."""
    var, op, value = cond["var"], cond.get("op", "eq"), str(cond.get("value", ""))
    col = BotSubscriber.data[var].astext
    if var.startswith("tag_"):
        has = BotSubscriber.data["_tags"].op("@>")(literal([var[4:]], type_=JSONB))
        return has if op in ("set", "eq", "ge") else ~has
    if op == "set":
        return (col.is_not(None)) & (col != "")
    if op == "unset":
        return (col.is_(None)) | (col == "")
    if op in ("gt", "lt", "ge", "le"):
        num = cast(col, Numeric)
        try:
            v = float(value.replace(",", ".").replace(" ", ""))
        except ValueError:
            return BotSubscriber.id < 0
        guard = col.op("~")(r"^-?\d+(\.\d+)?$")
        return guard & {"gt": num > v, "lt": num < v, "ge": num >= v, "le": num <= v}[op]
    if op == "contains":
        return col.ilike(f"%{value.replace('%', '').replace('_', '')}%")
    if op == "ne":
        return (col.is_(None)) | (col != value)
    return col == value


def label(segment: str, menu: dict | None = None) -> str:
    if segment in SEGMENTS:
        return SEGMENTS[segment]
    if segment.startswith("t:"):
        return f"🏷 {segment[2:]}"
    if segment.startswith("s:"):
        s = next((x for x in (menu or {}).get("segments") or [] if x["id"] == segment[2:]), None)
        return f"🎯 {s['title']}" if s else "🎯 segment"
    return segment


def conditions(segment: str, bot_id: int, menu: dict | None = None) -> list:
    """BotSubscriber uchun SQLAlchemy shartlari (bloklanmaganlar doim)."""
    now = datetime.datetime.now(datetime.timezone.utc)
    base = [BotSubscriber.bot_id == bot_id, BotSubscriber.blocked == False, BotSubscriber.banned == False]  # noqa: E712
    if segment == "new7":
        base.append(BotSubscriber.started_at >= now - datetime.timedelta(days=7))
    elif segment == "active7":
        base.append(BotSubscriber.last_active_at >= now - datetime.timedelta(days=7))
    elif segment == "inactive30":
        base.append(BotSubscriber.last_active_at < now - datetime.timedelta(days=30))
    elif segment == "ordered":
        base.append(exists(select(BotOrder.id).where(BotOrder.bot_id == bot_id, BotOrder.tg_user_id == BotSubscriber.tg_user_id, BotOrder.status != "cancelled")))
    elif segment == "booked":
        base.append(exists(select(BotBooking.id).where(BotBooking.bot_id == bot_id, BotBooking.tg_user_id == BotSubscriber.tg_user_id, BotBooking.status != "cancelled")))
    elif segment == "referrers":
        base.append(BotSubscriber.ref_count > 0)
    elif segment.startswith("t:"):
        base.append(BotSubscriber.data["_tags"].op("@>")(literal([segment[2:]], type_=JSONB)))
    elif segment.startswith("s:"):
        seg = next((x for x in (menu or {}).get("segments") or [] if x["id"] == segment[2:]), None)
        if seg is None:
            base.append(BotSubscriber.id < 0)  # o'chirilgan segment — hech kim
        else:
            base.extend(cond_sql(c) for c in seg.get("conds") or [])
    return base
