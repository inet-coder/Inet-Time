"""Referal tizimi.

Hisoblanish rejimi (admin tanlaydi):
- "start"   — do'st havola orqali botni ochishi bilan hisoblanadi;
- "account" — do'st o'z Telegram akkauntini ulagandagina (yangi, ilgari hech kim ulamagan akkaunt) hisoblanadi.

Sovg'alar: bosqichlar (masalan 3 ta → Starter 7 kun, 10 ta → Pro 30 kun), ixtiyoriy har referal uchun balans
bonusi va taklif qilingan do'stga sovg'a. Har bosqich sovg'asi bir marta beriladi (referral_rewards)."""

import datetime
import decimal

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from core.billing import extend_subscription
from core.db.enums import TransactionType
from core.db.models import Plan, Referral, ReferralReward, ReferralTransaction, SystemSetting, Transaction, User

SETTING_KEY = "referral"
MODES = ("start", "account")

DEFAULT_SETTINGS: dict = {
    "enabled": True,
    "mode": "account",
    "bonus_per_referral": 0,
    "milestones": [
        {"count": 3, "plan_code": "starter", "days": 7},
        {"count": 10, "plan_code": "pro", "days": 30},
        {"count": 25, "plan_code": "pro", "days": 90},
    ],
    "friend_plan_code": "starter",
    "friend_days": 3,
}


async def get_settings(db: AsyncSession) -> dict:
    row = await db.scalar(select(SystemSetting).where(SystemSetting.key == SETTING_KEY))
    value = row.value if row is not None and isinstance(row.value, dict) else {}
    return {**DEFAULT_SETTINGS, **value}


async def qualified_count(db: AsyncSession, user_id: int) -> int:
    return await db.scalar(
        select(func.count(Referral.id)).where(Referral.referrer_user_id == user_id, Referral.status == "qualified")
    )


def _who(user: User | None) -> str:
    if user is None:
        return "Do'stingiz"
    return f"@{user.username}" if user.username else (user.first_name or "Do'stingiz")


async def _plan_name(db: AsyncSession, code: str) -> str:
    plan = await db.scalar(select(Plan).where(Plan.code == code))
    return plan.name if plan else code


async def _grant_plan(db: AsyncSession, user_id: int, plan_code: str, days: int) -> bool:
    plan = await db.scalar(select(Plan).where(Plan.code == plan_code))
    if plan is None or days <= 0:
        return False
    await extend_subscription(db, user_id, plan, datetime.datetime.now(datetime.timezone.utc), days=days)
    return True


async def _add_bonus(db: AsyncSession, referral: Referral, amount: int) -> None:
    current = await db.scalar(
        select(func.coalesce(func.sum(Transaction.amount), 0)).where(Transaction.user_id == referral.referrer_user_id)
    )
    balance = decimal.Decimal(current) + amount
    tx = Transaction(
        user_id=referral.referrer_user_id, type=TransactionType.REFERRAL_BONUS, amount=decimal.Decimal(amount),
        balance_after=balance,
    )
    db.add(tx)
    await db.flush()
    db.add(ReferralTransaction(referral_id=referral.id, transaction_id=tx.id, amount=decimal.Decimal(amount)))
    referrer = await db.get(User, referral.referrer_user_id)
    referrer.balance = balance


async def qualify(db: AsyncSession, referral: Referral) -> list[tuple[int, str]]:
    """Referalni hisoblangan qiladi va sovg'alarni beradi. Commit'dan keyin yuboriladigan xabarlar:
    [(telegram_user_id, matn)]. Commit'ni chaqiruvchi qiladi."""
    if referral.status == "qualified":
        return []
    settings = await get_settings(db)
    referral.status = "qualified"
    referral.qualified_at = datetime.datetime.now(datetime.timezone.utc)
    await db.flush()

    referrer = await db.get(User, referral.referrer_user_id)
    friend = await db.get(User, referral.referred_user_id)
    messages: list[tuple[int, str]] = []
    lines = [f"🎉 {_who(friend)} sizning havolangiz orqali qo'shildi!"]

    bonus = int(settings.get("bonus_per_referral") or 0)
    if bonus > 0:
        await _add_bonus(db, referral, bonus)
        lines.append(f"💰 Balansingizga +{bonus:,} so'm".replace(",", " "))

    count = await qualified_count(db, referral.referrer_user_id)
    lines.append(f"👥 Referallar: {count} ta")
    for milestone in sorted(settings.get("milestones") or [], key=lambda m: m["count"]):
        if count != milestone["count"]:
            continue
        exists = await db.scalar(
            select(ReferralReward.id).where(ReferralReward.user_id == referrer.id, ReferralReward.milestone == milestone["count"])
        )
        if exists is None and await _grant_plan(db, referrer.id, milestone["plan_code"], milestone["days"]):
            db.add(ReferralReward(user_id=referrer.id, milestone=milestone["count"], plan_code=milestone["plan_code"], days=milestone["days"]))
            lines.append(f"🏆 Sovg'a: {await _plan_name(db, milestone['plan_code'])} — {milestone['days']} kun!")
    upcoming = next((m for m in sorted(settings.get("milestones") or [], key=lambda m: m["count"]) if m["count"] > count), None)
    if upcoming:
        lines.append(
            f"🎯 Keyingi sovg'a ({await _plan_name(db, upcoming['plan_code'])} {upcoming['days']} kun) — yana {upcoming['count'] - count} ta do'st"
        )
    if referrer and referrer.telegram_user_id:
        messages.append((referrer.telegram_user_id, "\n".join(lines)))

    friend_days = int(settings.get("friend_days") or 0)
    if friend and friend_days > 0 and await _grant_plan(db, friend.id, settings.get("friend_plan_code") or "starter", friend_days):
        if friend.telegram_user_id:
            plan_name = await _plan_name(db, settings.get("friend_plan_code") or "starter")
            messages.append((friend.telegram_user_id, f"🎁 Taklif uchun sovg'a: {plan_name} — {friend_days} kun! Imkoniyatlar allaqachon ochiq."))
    return messages


async def on_signup(db: AsyncSession, referral: Referral) -> list[tuple[int, str]]:
    settings = await get_settings(db)
    if settings["enabled"] and settings["mode"] == "start":
        return await qualify(db, referral)
    return []


async def on_account_connected(db: AsyncSession, user_id: int) -> list[tuple[int, str]]:
    """Faqat yangi (ilgari hech kim ulamagan) akkaunt ulanganda chaqiriladi."""
    settings = await get_settings(db)
    if not settings["enabled"] or settings["mode"] != "account":
        return []
    referral = await db.scalar(select(Referral).where(Referral.referred_user_id == user_id, Referral.status == "pending"))
    if referral is None:
        return []
    return await qualify(db, referral)


async def summary(db: AsyncSession, user: User) -> dict:
    """Foydalanuvchi uchun: havola kodi, hisoblangan/kutilayotganlar, bosqichlar va keyingi sovg'a."""
    settings = await get_settings(db)
    qualified = await qualified_count(db, user.id)
    pending = await db.scalar(
        select(func.count(Referral.id)).where(Referral.referrer_user_id == user.id, Referral.status == "pending")
    )
    got = set(await db.scalars(select(ReferralReward.milestone).where(ReferralReward.user_id == user.id)))
    milestones = []
    for m in sorted(settings.get("milestones") or [], key=lambda m: m["count"]):
        milestones.append({**m, "plan_name": await _plan_name(db, m["plan_code"]), "reached": qualified >= m["count"], "rewarded": m["count"] in got})
    upcoming = next((m for m in milestones if m["count"] > qualified), None)
    friend_plan = await _plan_name(db, settings.get("friend_plan_code") or "starter")
    return {
        "enabled": settings["enabled"],
        "mode": settings["mode"],
        "code": user.referral_code,
        "qualified": qualified,
        "pending": pending,
        "bonus_per_referral": int(settings.get("bonus_per_referral") or 0),
        "friend_reward": {"plan_name": friend_plan, "days": int(settings.get("friend_days") or 0)},
        "milestones": milestones,
        "next": upcoming,
    }
