"""Telegram sessiyasi tugatilganda (foydalanuvchi «Qurilmalar» bo'limidan chiqarib yuborsa) nima qilinadi.

Avval: har bir xizmat o'z navbatida 4 marta qayta urinib, keyin «xatolik» bo'lib qolardi, foydalanuvchi esa
nima bo'lganini bilmasdi. Endi: akkaunt bir marta EXPIRED deb belgilanadi, xizmatlar aniq sabab bilan to'xtaydi,
egasiga bot orqali xabar boriladi. Akkaunt qayta ulanganda shu xizmatlar o'zi qayta yoqiladi."""

import datetime
import logging

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from core.db.enums import AutomationStatus, TelegramAccountStatus
from core.db.models import Automation, AutomationAction, EncryptedSession, Service, TelegramAccount, User
from core.entitlements import LIVE_ACCOUNT_STATUSES, get_entitlement, missing_flag
from core.notify import send_telegram

logger = logging.getLogger(__name__)

# error_message shu matn bilan boshlansa — sabab sessiya tugaganligi (bot/Mini App alohida maslahat ko'rsatadi,
# qayta ulanganda shu xizmatlar avtomatik tiklanadi).
SESSION_DEAD_MESSAGE = "Telegram sessiyasi tugatilgan — akkauntni qayta ulang"

SESSION_DEAD_NOTICE = (
    "🔌 {who} akkauntingiz sessiyasi Telegram'da tugatildi\n"
    "(«Qurilmalar» bo'limidan chiqarilgan yoki Telegram uni bekor qilgan).\n\n"
    "Shu sabab xizmatlar vaqtincha to'xtadi. Akkauntni qayta ulang: /start → ➕ Akkaunt qo'shish — "
    "yoqilgan xizmatlaringiz o'zi qayta ishga tushadi."
)

_STOPPABLE = (AutomationStatus.ACTIVE, AutomationStatus.STARTING, AutomationStatus.WAITING, AutomationStatus.ERROR)


def is_session_dead_message(message: str | None) -> bool:
    return bool(message) and message.startswith(SESSION_DEAD_MESSAGE)


async def handle_session_dead(db: AsyncSession, account_id: int, reason: str = "") -> bool:
    """Akkauntni EXPIRED qiladi, xizmatlarini to'xtatadi, egasini ogohlantiradi.
    Bir nechta worker/listener bir vaqtda aniqlasa ham xabar faqat bir marta ketadi. True — shu chaqiriq belgiladi."""
    await db.rollback()  # oldingi xato tranzaksiyani buzgan bo'lishi mumkin
    now = datetime.datetime.now(datetime.timezone.utc)
    marked = (
        await db.execute(
            update(TelegramAccount)
            # Faqat «tirik» akkaunt: allaqachon EXPIRED (boshqasi aniqlagan) yoki egasi o'chirgan (REVOKED) — tegilmaydi.
            .where(TelegramAccount.id == account_id, TelegramAccount.status.in_(LIVE_ACCOUNT_STATUSES))
            .values(status=TelegramAccountStatus.EXPIRED)
            .returning(TelegramAccount.user_id, TelegramAccount.username, TelegramAccount.first_name)
        )
    ).first()
    if marked is None:
        await db.commit()
        return False

    await db.execute(
        update(EncryptedSession)
        .where(EncryptedSession.telegram_account_id == account_id, EncryptedSession.revoked_at.is_(None))
        .values(revoked_at=now)
    )
    message = f"{SESSION_DEAD_MESSAGE} ({reason})" if reason else SESSION_DEAD_MESSAGE
    await db.execute(
        update(Automation)
        .where(Automation.telegram_account_id == account_id, Automation.status.in_(_STOPPABLE))
        .values(status=AutomationStatus.ERROR, error_message=message[:1000])
    )
    await db.commit()
    logger.warning("akkaunt %s sessiyasi tugatilgan: %s", account_id, reason)

    user_id, username, first_name = marked
    user = await db.get(User, user_id)
    if user is not None and user.telegram_user_id:
        who = f"@{username}" if username else (first_name or "Telegram")
        await send_telegram(user.telegram_user_id, SESSION_DEAD_NOTICE.format(who=who))
    return True


async def reactivate_after_relogin(db: AsyncSession, account_id: int, user_id: int) -> int:
    """Akkaunt qayta ulanganda sessiya tugagani sabab to'xtagan xizmatlarni yana yoqadi (snapshotlar saqlangan).
    Tarif limiti va ruxsatlari hisobga olinadi. Commit chaqiruvchida. Qayta yoqilganlar soni."""
    rows = (
        await db.execute(
            select(Automation, Service.code)
            .join(Service, Service.id == Automation.service_id)
            .where(
                Automation.telegram_account_id == account_id,
                Automation.status == AutomationStatus.ERROR,
                Automation.error_message.startswith(SESSION_DEAD_MESSAGE),
            )
            .order_by(Automation.started_at)
        )
    ).all()
    if not rows:
        return 0
    ent = await get_entitlement(db, user_id)
    free_slots = ent.scheduler_limit - ent.automations_used
    reactivated = 0
    for automation, service_code in rows:
        if reactivated >= free_slots:
            break
        fields = set(await db.scalars(select(AutomationAction.field).where(AutomationAction.automation_id == automation.id)))
        if missing_flag(ent, service_code, fields):
            continue
        automation.status = AutomationStatus.ACTIVE
        automation.error_message = None
        reactivated += 1
    return reactivated
