"""Obunachilar segmentlari: tarqatish va avtomatik xabarlar auditoriyasi (hammasi SQL shartlari)."""

import datetime

from sqlalchemy import exists, select

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


def conditions(segment: str, bot_id: int) -> list:
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
    return base
