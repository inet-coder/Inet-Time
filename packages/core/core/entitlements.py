import datetime
from dataclasses import dataclass

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from core.db.enums import AutomationStatus, ProfileField, SubscriptionStatus, TelegramAccountStatus
from core.db.models import Automation, AutomationAction, Plan, Service, Subscription, TelegramAccount

# Zaxira: bazada "free" tarif qatori bo'lmasa (migratsiyadan oldin). Asl qiymatlar admin paneldan sozlanadi.
FREE_PLAN = {
    "code": "free",
    "name": "Bepul",
    "flags": {
        "account_limit": 1,
        "scheduler_limit": 1,
        "online_service": False,
        "emoji_service": False,
    },
}

# Limitga kiradigan holatlar.
LIVE_AUTOMATION_STATUSES = (AutomationStatus.ACTIVE, AutomationStatus.STARTING)
LIVE_ACCOUNT_STATUSES = (TelegramAccountStatus.CONNECTED, TelegramAccountStatus.ACTIVE, TelegramAccountStatus.PAUSED)


class EntitlementError(Exception):
    """Tarif limiti oshib ketdi — foydalanuvchiga ko'rsatiladigan xabar bilan."""


@dataclass
class Entitlement:
    plan_code: str
    plan_name: str
    expires_at: datetime.datetime | None
    flags: dict
    accounts_used: int
    automations_used: int

    @property
    def account_limit(self) -> int:
        return int(self.flags.get("account_limit", 1))

    @property
    def scheduler_limit(self) -> int:
        return int(self.flags.get("scheduler_limit", 1))


async def get_entitlement(db: AsyncSession, user_id: int) -> Entitlement:
    now = datetime.datetime.now(datetime.timezone.utc)
    # Bir nechta faol obuna bo'lsa — eng qimmat tarif amal qiladi.
    row = (
        await db.execute(
            select(Plan, Subscription.expires_at)
            .join(Subscription, Subscription.plan_id == Plan.id)
            .where(
                Subscription.user_id == user_id,
                Subscription.status == SubscriptionStatus.ACTIVE,
                Subscription.expires_at > now,
                Plan.code != FREE_PLAN["code"],
            )
            .order_by(Plan.price.desc())
            .limit(1)
        )
    ).first()

    # EXPIRED/ERROR/REVOKED hisobga kirmaydi — foydalanuvchi o'sha akkauntni qayta ulay olishi kerak.
    accounts_used = await db.scalar(
        select(func.count(TelegramAccount.id)).where(
            TelegramAccount.user_id == user_id, TelegramAccount.status.in_(LIVE_ACCOUNT_STATUSES)
        )
    )
    automations_used = await db.scalar(
        select(func.count(Automation.id))
        .join(TelegramAccount, TelegramAccount.id == Automation.telegram_account_id)
        .where(TelegramAccount.user_id == user_id, Automation.status.in_(LIVE_AUTOMATION_STATUSES))
    )

    if row is None:
        free = await db.scalar(select(Plan).where(Plan.code == FREE_PLAN["code"]))
        return Entitlement(
            plan_code=FREE_PLAN["code"],
            plan_name=free.name if free else FREE_PLAN["name"],
            expires_at=None,
            flags=free.flags if free else FREE_PLAN["flags"],
            accounts_used=accounts_used,
            automations_used=automations_used,
        )
    plan, expires_at = row
    return Entitlement(
        plan_code=plan.code,
        plan_name=plan.name,
        expires_at=expires_at,
        flags=plan.flags,
        accounts_used=accounts_used,
        automations_used=automations_used,
    )


# Xizmat kodi -> uni ochadigan tarif flag'i (va foydalanuvchiga ko'rsatiladigan nomi).
SERVICE_FLAGS = {
    "online": ("online_service", "24/7 Online"),
    "playlist": ("playlist_service", "Bio playlist"),
    "schedule": ("schedule_service", "Jadval"),
    "emoji": ("emoji_service", "Emoji status"),
    "photo": ("photo_service", "Rasm almashtirish"),
}
# Boshqa xizmat kodi orqali yaratilsa ham (masalan API'dan "combo") shu fieldlar Pro'siz ishlamaydi.
FIELD_FLAGS = {
    ProfileField.ONLINE: SERVICE_FLAGS["online"],
    ProfileField.EMOJI_STATUS: SERVICE_FLAGS["emoji"],
    ProfileField.PHOTO: SERVICE_FLAGS["photo"],
}


def missing_flag(ent: Entitlement, service_code: str, fields: set[ProfileField]) -> str | None:
    """Tarif bu xizmatga ruxsat bermasa — xizmat nomini qaytaradi."""
    required = [SERVICE_FLAGS[service_code]] if service_code in SERVICE_FLAGS else []
    required += [FIELD_FLAGS[f] for f in fields if f in FIELD_FLAGS]
    for flag, title in required:
        if not ent.flags.get(flag):
            return title
    return None


async def check_can_activate(db: AsyncSession, user_id: int, automation_id: int) -> None:
    ent = await get_entitlement(db, user_id)
    if ent.automations_used >= ent.scheduler_limit:
        raise EntitlementError(
            f"{ent.plan_name} tarifida bir vaqtda {ent.scheduler_limit} ta xizmat ishlashi mumkin."
        )
    service_code = await db.scalar(
        select(Service.code).join(Automation, Automation.service_id == Service.id).where(Automation.id == automation_id)
    )
    fields = set(await db.scalars(select(AutomationAction.field).where(AutomationAction.automation_id == automation_id)))
    title = missing_flag(ent, service_code, fields)
    if title is not None:
        raise EntitlementError(f"{title} {ent.plan_name} tarifida yo'q — tarifni yangilang.")


async def check_can_add_account(db: AsyncSession, user_id: int) -> None:
    ent = await get_entitlement(db, user_id)
    if ent.accounts_used >= ent.account_limit:
        raise EntitlementError(f"{ent.plan_name} tarifida {ent.account_limit} ta akkaunt ulash mumkin.")
