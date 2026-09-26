import datetime
import decimal

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select, text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.ext.asyncio import AsyncSession

from admin_deps import require_permission
from core.admin_auth import hash_password
from core.audit import record_audit
from core.db.base import async_session
from core.db.enums import ActorType, TransactionType
from core.db.models import (
    AdminRole,
    AdminUser,
    AuditLog,
    Referral,
    Service,
    Subscription,
    SystemSetting,
    TelegramAccount,
    Transaction,
    User,
    WorkerJob,
)
from deps import get_db
from jobs import enqueue
from redis_client import get_redis
from schemas import (
    AccountOut,
    AdminUserView,
    AuditLogOut,
    BalanceAdjust,
    JobQueuedOut,
    JobStatusOut,
    ServiceOut,
    ServiceToggle,
    SubscriptionExtend,
    SubscriptionOut,
    SystemSettingIn,
    SystemSettingOut,
    WorkerLeaseOut,
)

router = APIRouter(prefix="/admin", tags=["admin"])

_MAX_SERIALIZATION_RETRIES = 3


# --- Admin foydalanuvchilarini boshqarish (faqat "admin.manage") ---


@router.post("/admins")
async def create_admin(
    username: str,
    password: str,
    role_name: str,
    admin: AdminUser = Depends(require_permission("admin.manage")),
    db: AsyncSession = Depends(get_db),
) -> dict:
    role = await db.scalar(select(AdminRole).where(AdminRole.name == role_name))
    if role is None:
        raise HTTPException(404, f"Rol topilmadi: {role_name}")
    existing = await db.scalar(select(AdminUser).where(AdminUser.username == username))
    if existing is not None:
        raise HTTPException(409, "Bu username band")

    new_admin = AdminUser(username=username, password_hash=hash_password(password), role_id=role.id)
    db.add(new_admin)
    await db.flush()
    await record_audit(
        db, actor_type=ActorType.ADMIN, actor_id=admin.id, action="admin_created",
        entity_type="admin_user", entity_id=new_admin.id,
    )
    await db.commit()
    return {"id": new_admin.id, "username": new_admin.username}


# --- Foydalanuvchilar ---


@router.get("/users", response_model=list[AdminUserView])
async def list_users(admin: AdminUser = Depends(require_permission("users")), db: AsyncSession = Depends(get_db)) -> list[User]:
    result = await db.scalars(select(User).order_by(User.id))
    return list(result)


@router.post("/users/{user_id}/ban", response_model=AdminUserView)
async def ban_user(user_id: int, admin: AdminUser = Depends(require_permission("users")), db: AsyncSession = Depends(get_db)) -> User:
    user = await db.get(User, user_id)
    if user is None:
        raise HTTPException(404, "Foydalanuvchi topilmadi")
    user.is_banned = True
    await record_audit(db, actor_type=ActorType.ADMIN, actor_id=admin.id, action="user_banned", entity_type="user", entity_id=user.id)
    await db.commit()
    await db.refresh(user)
    return user


@router.post("/users/{user_id}/unban", response_model=AdminUserView)
async def unban_user(user_id: int, admin: AdminUser = Depends(require_permission("users")), db: AsyncSession = Depends(get_db)) -> User:
    user = await db.get(User, user_id)
    if user is None:
        raise HTTPException(404, "Foydalanuvchi topilmadi")
    user.is_banned = False
    await record_audit(db, actor_type=ActorType.ADMIN, actor_id=admin.id, action="user_unbanned", entity_type="user", entity_id=user.id)
    await db.commit()
    await db.refresh(user)
    return user


@router.post("/users/{user_id}/balance-adjust")
async def balance_adjust(
    user_id: int,
    payload: BalanceAdjust,
    admin: AdminUser = Depends(require_permission("balance.adjust")),
) -> dict:
    # `db` (Depends(get_db)) auth tekshiruvi uchun allaqachon ishlatilgan bo'lardi, ya'ni uning
    # tranzaksiyasi boshlanib bo'lgan — SET TRANSACTION ISOLATION LEVEL esa birinchi buyruq
    # bo'lishi shart. Shu sabab pul harakati uchun butunlay yangi, "toza" session ochiladi.
    for attempt in range(_MAX_SERIALIZATION_RETRIES):
        async with async_session() as db:
            try:
                await db.execute(text("SET TRANSACTION ISOLATION LEVEL SERIALIZABLE"))

                user = await db.get(User, user_id)
                if user is None:
                    raise HTTPException(404, "Foydalanuvchi topilmadi")

                current = await db.scalar(
                    select(func.coalesce(func.sum(Transaction.amount), 0)).where(Transaction.user_id == user_id)
                )
                new_balance = decimal.Decimal(current) + decimal.Decimal(str(payload.amount))
                db.add(
                    Transaction(
                        user_id=user_id,
                        type=TransactionType.ADJUSTMENT,
                        amount=decimal.Decimal(str(payload.amount)),
                        balance_after=new_balance,
                    )
                )
                user.balance = new_balance
                await record_audit(
                    db, actor_type=ActorType.ADMIN, actor_id=admin.id, action="balance_adjusted",
                    entity_type="user", entity_id=user_id,
                    meta={"amount": str(payload.amount), "reason": payload.reason},
                )
                await db.commit()
                return {"user_id": user_id, "balance": float(new_balance)}
            except DBAPIError as exc:
                await db.rollback()
                if "could not serialize access" in str(exc.orig).lower() and attempt < _MAX_SERIALIZATION_RETRIES - 1:
                    continue
                raise HTTPException(409, "Bir vaqtda ko'p yangilanish — qaytadan urinib ko'ring") from exc

    raise HTTPException(409, "Bir vaqtda ko'p yangilanish — qaytadan urinib ko'ring")


# --- Telegram akkauntlar ---


@router.get("/accounts", response_model=list[AccountOut])
async def list_all_accounts(admin: AdminUser = Depends(require_permission("accounts")), db: AsyncSession = Depends(get_db)) -> list[TelegramAccount]:
    result = await db.scalars(select(TelegramAccount).order_by(TelegramAccount.id))
    return list(result)


@router.post("/accounts/{account_id}/revoke", response_model=JobQueuedOut)
async def admin_revoke_account(
    account_id: int, admin: AdminUser = Depends(require_permission("accounts")), db: AsyncSession = Depends(get_db)
) -> JobQueuedOut:
    account = await db.get(TelegramAccount, account_id)
    if account is None:
        raise HTTPException(404, "Akkaunt topilmadi")
    job_id = await enqueue(
        db, task_name="revoke_account_job", telegram_account_id=account.id, automation_id=None,
        task_kwargs={"account_id": account.id},
    )
    await record_audit(
        db, actor_type=ActorType.ADMIN, actor_id=admin.id, action="account_revoked",
        entity_type="telegram_account", entity_id=account.id,
    )
    await db.commit()
    return JobQueuedOut(job_id=job_id)


# --- Servislar ---


@router.get("/services", response_model=list[ServiceOut])
async def list_services(admin: AdminUser = Depends(require_permission("services")), db: AsyncSession = Depends(get_db)) -> list[Service]:
    result = await db.scalars(select(Service).order_by(Service.id))
    return list(result)


@router.post("/services/{code}/toggle", response_model=ServiceOut)
async def toggle_service(
    code: str, payload: ServiceToggle, admin: AdminUser = Depends(require_permission("services")), db: AsyncSession = Depends(get_db)
) -> Service:
    service = await db.scalar(select(Service).where(Service.code == code))
    if service is None:
        raise HTTPException(404, "Service topilmadi")
    service.is_active = payload.is_active
    await record_audit(
        db, actor_type=ActorType.ADMIN, actor_id=admin.id,
        action="service_enabled" if payload.is_active else "service_disabled",
        entity_type="service", entity_id=service.id,
    )
    await db.commit()
    await db.refresh(service)
    return service


# --- Obunalar ---


@router.post("/subscriptions/{subscription_id}/extend", response_model=SubscriptionOut)
async def extend_subscription(
    subscription_id: int, payload: SubscriptionExtend,
    admin: AdminUser = Depends(require_permission("subscriptions")), db: AsyncSession = Depends(get_db),
) -> Subscription:
    subscription = await db.get(Subscription, subscription_id)
    if subscription is None:
        raise HTTPException(404, "Obuna topilmadi")
    subscription.expires_at += datetime.timedelta(days=payload.days)
    await record_audit(
        db, actor_type=ActorType.ADMIN, actor_id=admin.id, action="subscription_extended",
        entity_type="subscription", entity_id=subscription.id, meta={"days": payload.days},
    )
    await db.commit()
    await db.refresh(subscription)
    return subscription


# --- Tranzaksiyalar / Referrallar ---


@router.get("/transactions")
async def list_transactions(
    user_id: int | None = None, admin: AdminUser = Depends(require_permission("transactions")), db: AsyncSession = Depends(get_db)
) -> list[dict]:
    query = select(Transaction).order_by(Transaction.id)
    if user_id is not None:
        query = query.where(Transaction.user_id == user_id)
    rows = await db.scalars(query)
    return [
        {
            "id": t.id, "user_id": t.user_id, "type": t.type.value, "amount": float(t.amount),
            "balance_after": float(t.balance_after), "created_at": t.created_at.isoformat(),
        }
        for t in rows
    ]


@router.get("/referrals")
async def list_referrals(admin: AdminUser = Depends(require_permission("referrals")), db: AsyncSession = Depends(get_db)) -> list[dict]:
    rows = await db.scalars(select(Referral).order_by(Referral.id))
    return [
        {"id": r.id, "referrer_user_id": r.referrer_user_id, "referred_user_id": r.referred_user_id, "code": r.code}
        for r in rows
    ]


# --- Workerlar / Jobs ---


@router.get("/jobs", response_model=list[JobStatusOut])
async def list_jobs(
    status: str | None = None, admin: AdminUser = Depends(require_permission("jobs")), db: AsyncSession = Depends(get_db)
) -> list[WorkerJob]:
    query = select(WorkerJob).order_by(WorkerJob.created_at.desc()).limit(200)
    if status is not None:
        query = query.where(WorkerJob.status == status)
    result = await db.scalars(query)
    return list(result)


# --- Audit log (faqat to'liq huquqli SUPER_ADMIN) ---


@router.get("/audit-logs", response_model=list[AuditLogOut])
async def list_audit_logs(admin: AdminUser = Depends(require_permission("audit")), db: AsyncSession = Depends(get_db)) -> list[AuditLog]:
    result = await db.scalars(select(AuditLog).order_by(AuditLog.id.desc()).limit(200))
    return list(result)


# --- Workerlar (Redis lease) ---


@router.get("/workers", response_model=list[WorkerLeaseOut])
async def list_worker_leases(admin: AdminUser = Depends(require_permission("workers"))) -> list[WorkerLeaseOut]:
    redis = get_redis()
    leases = []
    async for key in redis.scan_iter(match="lease:account:*"):
        key_str = key.decode() if isinstance(key, bytes) else key
        account_id = int(key_str.rsplit(":", 1)[1])
        worker_id_raw = await redis.get(key)
        ttl = await redis.ttl(key)
        worker_id = worker_id_raw.decode() if isinstance(worker_id_raw, bytes) else worker_id_raw
        leases.append(WorkerLeaseOut(telegram_account_id=account_id, worker_id=worker_id, ttl_seconds=max(ttl, 0)))
    return leases


# --- Tizim sozlamalari (faqat SUPER_ADMIN) ---


@router.get("/settings", response_model=list[SystemSettingOut])
async def list_settings(admin: AdminUser = Depends(require_permission("settings")), db: AsyncSession = Depends(get_db)) -> list[SystemSetting]:
    result = await db.scalars(select(SystemSetting).order_by(SystemSetting.key))
    return list(result)


@router.put("/settings/{key}", response_model=SystemSettingOut)
async def upsert_setting(
    key: str, payload: SystemSettingIn, admin: AdminUser = Depends(require_permission("settings")), db: AsyncSession = Depends(get_db)
) -> SystemSetting:
    setting = await db.scalar(select(SystemSetting).where(SystemSetting.key == key))
    if setting is None:
        setting = SystemSetting(key=key, value=payload.value)
        db.add(setting)
    else:
        setting.value = payload.value
    await record_audit(
        db, actor_type=ActorType.ADMIN, actor_id=admin.id, action="setting_updated",
        entity_type="system_setting", meta={"key": key, "value": payload.value},
    )
    await db.commit()
    await db.refresh(setting)
    return setting
