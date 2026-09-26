import datetime
import decimal

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select, text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.ext.asyncio import AsyncSession

from admin_deps import require_permission
from core.audit import record_audit
from core.billing import FREE_CODE, PromoError, paid_plans, plan_price, plan_public, quote
from core.db.base import async_session
from core.db.enums import ActorType, PaymentMethod, PaymentStatus, SubscriptionStatus, TransactionType
from core.db.models import AdminUser, Payment, Plan, PromoRedemption, Subscription, Transaction, User
from deps import get_db
from schemas import PaymentOut, PurchaseCreate, RejectPaymentAdmin, SubscriptionOut, TopupCreate

router = APIRouter(prefix="/payments", tags=["payments"])
plans_router = APIRouter(prefix="/plans", tags=["payments"])
subscriptions_router = APIRouter(prefix="/subscriptions", tags=["payments"])


@plans_router.get("")
async def list_plans(db: AsyncSession = Depends(get_db)) -> list[dict]:
    """Sotib olinadigan (pullik, faol) tariflar; final_price — aksiya chegirmasi bilan."""
    return [{"id": p.id, **plan_public(p)} for p in await paid_plans(db)]


@subscriptions_router.get("", response_model=list[SubscriptionOut])
async def list_subscriptions(user_id: int, db: AsyncSession = Depends(get_db)) -> list[Subscription]:
    result = await db.scalars(select(Subscription).where(Subscription.user_id == user_id))
    return list(result)


_MAX_SERIALIZATION_RETRIES = 3


def _is_serialization_failure(exc: DBAPIError) -> bool:
    return "could not serialize access" in str(exc.orig).lower()


async def _extend_or_create_subscription(
    db: AsyncSession, user_id: int, plan: Plan, now: datetime.datetime, days: int | None = None
) -> Subscription:
    days = plan.duration_days if days is None else days
    subscription = await db.scalar(
        select(Subscription).where(
            Subscription.user_id == user_id,
            Subscription.plan_id == plan.id,
            Subscription.status == SubscriptionStatus.ACTIVE,
        )
    )
    if subscription is not None and subscription.expires_at > now:
        subscription.expires_at += datetime.timedelta(days=days)
    else:
        subscription = Subscription(
            user_id=user_id,
            plan_id=plan.id,
            status=SubscriptionStatus.ACTIVE,
            started_at=now,
            expires_at=now + datetime.timedelta(days=days),
        )
        db.add(subscription)
    await db.flush()
    return subscription


@subscriptions_router.post("/buy", response_model=SubscriptionOut)
async def buy_with_balance(payload: PurchaseCreate) -> Subscription:
    """Tarifni hamyon balansidan darhol sotib olish (admin tasdig'isiz)."""
    for attempt in range(_MAX_SERIALIZATION_RETRIES):
        async with async_session() as db:
            try:
                await db.execute(text("SET TRANSACTION ISOLATION LEVEL SERIALIZABLE"))

                user = await db.get(User, payload.user_id)
                if user is None:
                    raise HTTPException(404, "Foydalanuvchi topilmadi")
                plan = await db.scalar(
                    select(Plan).where(Plan.code == payload.plan_code, Plan.is_active == True)  # noqa: E712
                )
                if plan is None or plan.code == FREE_CODE:
                    raise HTTPException(404, f"Faol tarif topilmadi: {payload.plan_code}")

                now = datetime.datetime.now(datetime.timezone.utc)
                # Narx shu tranzaksiya ichida hisoblanadi: aksiya/promokod o'zgarsa ham eskisi qo'llanmaydi.
                try:
                    q = await quote(db, user.id, plan, payload.promo_code, now)
                except PromoError as exc:
                    raise HTTPException(400, str(exc)) from exc

                balance = await _current_balance(db, user.id)
                if balance < q.final:
                    raise HTTPException(402, f"Balans yetarli emas: {balance:.0f} / {q.final:.0f} so'm")

                subscription = await _extend_or_create_subscription(db, user.id, plan, now)
                balance -= q.final
                db.add(
                    Transaction(
                        user_id=user.id,
                        type=TransactionType.PURCHASE,
                        amount=-q.final,
                        balance_after=balance,
                        reference_subscription_id=subscription.id,
                    )
                )
                user.balance = balance
                if q.promo is not None:
                    q.promo.used_count += 1
                    db.add(
                        PromoRedemption(
                            promo_id=q.promo.id, user_id=user.id, subscription_id=subscription.id,
                            plan_code=plan.code, discount=q.promo_discount,
                        )
                    )
                await record_audit(
                    db, actor_type=ActorType.USER, actor_id=user.id, action="plan_purchased",
                    entity_type="subscription", entity_id=subscription.id,
                    meta={"plan": plan.code, "paid": str(q.final), "promo": q.promo.code if q.promo else None},
                )
                await db.commit()
                await db.refresh(subscription)
                return subscription
            except DBAPIError as exc:
                await db.rollback()
                if _is_serialization_failure(exc) and attempt < _MAX_SERIALIZATION_RETRIES - 1:
                    continue
                raise HTTPException(409, "Bir vaqtda ko'p yangilanish — qaytadan urinib ko'ring") from exc

    raise HTTPException(409, "Bir vaqtda ko'p yangilanish — qaytadan urinib ko'ring")


@router.post("/topup", response_model=PaymentOut)
async def create_topup(payload: TopupCreate, db: AsyncSession = Depends(get_db)) -> Payment:
    user = await db.get(User, payload.user_id)
    if user is None:
        raise HTTPException(404, "Foydalanuvchi topilmadi")
    if payload.amount <= 0:
        raise HTTPException(400, "Summa musbat bo'lishi kerak")

    payment = Payment(
        user_id=user.id,
        plan_id=None,
        amount=decimal.Decimal(str(payload.amount)),
        currency="UZS",
        method=PaymentMethod.MANUAL_ADMIN,
        status=PaymentStatus.PENDING,
    )
    db.add(payment)
    await db.commit()
    await db.refresh(payment)
    return payment


@router.post("/purchase", response_model=PaymentOut)
async def create_purchase(payload: PurchaseCreate, db: AsyncSession = Depends(get_db)) -> Payment:
    user = await db.get(User, payload.user_id)
    if user is None:
        raise HTTPException(404, "Foydalanuvchi topilmadi")
    plan = await db.scalar(select(Plan).where(Plan.code == payload.plan_code, Plan.is_active == True))  # noqa: E712
    if plan is None or plan.code == FREE_CODE:
        raise HTTPException(404, f"Faol tarif topilmadi: {payload.plan_code}")

    payment = Payment(
        user_id=user.id,
        plan_id=plan.id,
        amount=plan_price(plan),
        currency="UZS",
        method=PaymentMethod.MANUAL_ADMIN,
        status=PaymentStatus.PENDING,
    )
    db.add(payment)
    await db.commit()
    await db.refresh(payment)
    return payment


@router.get("", response_model=list[PaymentOut])
async def list_payments(status: str | None = None, user_id: int | None = None, db: AsyncSession = Depends(get_db)) -> list[Payment]:
    query = select(Payment)
    if status is not None:
        query = query.where(Payment.status == PaymentStatus(status))
    if user_id is not None:
        query = query.where(Payment.user_id == user_id)
    result = await db.scalars(query.order_by(Payment.created_at))
    return list(result)


async def _current_balance(db: AsyncSession, user_id: int) -> decimal.Decimal:
    total = await db.scalar(
        select(func.coalesce(func.sum(Transaction.amount), 0)).where(Transaction.user_id == user_id)
    )
    return decimal.Decimal(total)


@router.post("/{payment_id}/confirm", response_model=PaymentOut)
async def confirm_payment(
    payment_id: int,
    admin: AdminUser = Depends(require_permission("payments")),
) -> Payment:
    # `db` (Depends(get_db)) auth tekshiruvi uchun ishlatilgan bo'lardi — SET TRANSACTION
    # ISOLATION LEVEL esa tranzaksiyadagi birinchi buyruq bo'lishi shart, shuning uchun
    # pul harakati uchun butunlay yangi session ochiladi.
    for attempt in range(_MAX_SERIALIZATION_RETRIES):
        async with async_session() as db:
            try:
                await db.execute(text("SET TRANSACTION ISOLATION LEVEL SERIALIZABLE"))

                payment = await db.get(Payment, payment_id)
                if payment is None:
                    raise HTTPException(404, "To'lov topilmadi")
                if payment.status != PaymentStatus.PENDING:
                    raise HTTPException(400, "Faqat PENDING to'lov tasdiqlanishi mumkin")

                now = datetime.datetime.now(datetime.timezone.utc)
                balance = await _current_balance(db, payment.user_id)

                if payment.plan_id is not None:
                    plan = await db.get(Plan, payment.plan_id)
                    subscription = await _extend_or_create_subscription(db, payment.user_id, plan, now)

                    # Double-entry: tashqaridan pul kirdi (TOPUP), so'ng tarifga sarflandi (PURCHASE) — sof ta'sir 0.
                    balance += payment.amount
                    db.add(
                        Transaction(
                            user_id=payment.user_id,
                            type=TransactionType.TOPUP,
                            amount=payment.amount,
                            balance_after=balance,
                            reference_payment_id=payment.id,
                        )
                    )
                    balance -= payment.amount
                    db.add(
                        Transaction(
                            user_id=payment.user_id,
                            type=TransactionType.PURCHASE,
                            amount=-payment.amount,
                            balance_after=balance,
                            reference_payment_id=payment.id,
                            reference_subscription_id=subscription.id,
                        )
                    )
                    payment.subscription_id = subscription.id
                else:
                    balance += payment.amount
                    db.add(
                        Transaction(
                            user_id=payment.user_id,
                            type=TransactionType.TOPUP,
                            amount=payment.amount,
                            balance_after=balance,
                            reference_payment_id=payment.id,
                        )
                    )

                payment.status = PaymentStatus.PAID
                payment.confirmed_at = now
                payment.confirmed_by_admin_id = admin.id

                user = await db.get(User, payment.user_id)
                user.balance = balance

                await record_audit(
                    db, actor_type=ActorType.ADMIN, actor_id=admin.id, action="payment_confirmed",
                    entity_type="payment", entity_id=payment.id, meta={"amount": str(payment.amount)},
                )
                await db.commit()
                await db.refresh(payment)
                return payment
            except DBAPIError as exc:
                await db.rollback()
                if _is_serialization_failure(exc) and attempt < _MAX_SERIALIZATION_RETRIES - 1:
                    continue
                raise HTTPException(409, "Bir vaqtda ko'p yangilanish — qaytadan urinib ko'ring") from exc

    raise HTTPException(409, "Bir vaqtda ko'p yangilanish — qaytadan urinib ko'ring")


@router.post("/{payment_id}/reject", response_model=PaymentOut)
async def reject_payment(
    payment_id: int,
    payload: RejectPaymentAdmin,
    admin: AdminUser = Depends(require_permission("payments")),
    db: AsyncSession = Depends(get_db),
) -> Payment:
    payment = await db.get(Payment, payment_id)
    if payment is None:
        raise HTTPException(404, "To'lov topilmadi")
    if payment.status != PaymentStatus.PENDING:
        raise HTTPException(400, "Faqat PENDING to'lov rad etilishi mumkin")

    payment.status = PaymentStatus.CANCELLED
    payment.confirmed_at = datetime.datetime.now(datetime.timezone.utc)
    payment.confirmed_by_admin_id = admin.id
    await record_audit(
        db, actor_type=ActorType.ADMIN, actor_id=admin.id, action="payment_rejected",
        entity_type="payment", entity_id=payment.id, meta={"reason": payload.reason},
    )
    await db.commit()
    await db.refresh(payment)
    return payment
