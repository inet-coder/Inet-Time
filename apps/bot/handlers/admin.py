import logging

from aiogram import Bot, F, Router
from aiogram.exceptions import TelegramAPIError
from aiogram.types import CallbackQuery

import keyboards as kb
from api_client import ApiError, api_client
from common import is_admin, money, safe_answer, safe_edit

router = Router(name="admin")
logger = logging.getLogger(__name__)

# Bu router'dagi barcha callbacklar faqat adminlar uchun.
router.callback_query.filter(lambda c: is_admin(c.from_user.id))


async def _notify_user(bot: Bot, user_id: int, text: str) -> None:
    user = await api_client.get_user(user_id)
    try:
        await bot.send_message(user["telegram_user_id"], text, reply_markup=kb.back_home())
    except TelegramAPIError:
        logger.warning("user %s ga xabar yuborib bo'lmadi", user_id)


@router.callback_query(F.data == "adm")
async def admin_menu(callback: CallbackQuery) -> None:
    pending = await api_client.admin_list_payments(status="PENDING")
    await safe_edit(callback, "🛠 Admin panel", kb.admin_menu(len(pending)))
    await safe_answer(callback)


@router.callback_query(F.data == "adm_pays")
async def pending_payments(callback: CallbackQuery) -> None:
    pending = await api_client.admin_list_payments(status="PENDING")
    text = "Kutayotgan to'lovlar yo'q ✅" if not pending else "Kutayotgan to'lovlar:"
    await safe_edit(callback, text, kb.admin_payments(pending))
    await safe_answer(callback)


@router.callback_query(F.data.startswith("adm_pay:"))
async def payment_view(callback: CallbackQuery) -> None:
    payment_id = int(callback.data.split(":", 1)[1])
    payment = next((p for p in await api_client.admin_list_payments(status="PENDING") if p["id"] == payment_id), None)
    if payment is None:
        await safe_answer(callback, "Bu so'rov allaqachon ko'rib chiqilgan", show_alert=True)
        return
    user = await api_client.get_user(payment["user_id"])
    who = f"@{user['username']}" if user["username"] else (user["first_name"] or user["telegram_user_id"])
    kind = "tarif to'lovi" if payment["plan_id"] else "balansni to'ldirish"
    await safe_edit(
        callback,
        f"💳 So'rov #{payment['id']}\n👤 {who}\nSumma: {money(payment['amount'])}\nTuri: {kind}",
        kb.admin_payment_view(payment_id),
    )
    await safe_answer(callback)


@router.callback_query(F.data.startswith("adm_ok:"))
async def confirm_payment(callback: CallbackQuery) -> None:
    payment_id = int(callback.data.split(":", 1)[1])
    try:
        payment = await api_client.admin_confirm_payment(payment_id)
    except ApiError:
        await safe_answer(callback, "Bu so'rov allaqachon ko'rib chiqilgan", show_alert=True)
        return
    await safe_edit(callback, f"✅ So'rov #{payment_id} tasdiqlandi — {money(payment['amount'])}")
    await safe_answer(callback, "Tasdiqlandi")
    if payment["plan_id"]:
        text = "✅ To'lovingiz tasdiqlandi va tarifingiz faollashdi!"
    else:
        text = (
            f"✅ To'lovingiz tasdiqlandi! Balansingizga {money(payment['amount'])} qo'shildi.\n"
            "Endi 💎 Tariflar bo'limidan tarif olishingiz mumkin."
        )
    await _notify_user(callback.bot, payment["user_id"], text)


@router.callback_query(F.data.startswith("adm_no:"))
async def reject_payment(callback: CallbackQuery) -> None:
    payment_id = int(callback.data.split(":", 1)[1])
    try:
        payment = await api_client.admin_reject_payment(payment_id)
    except ApiError:
        await safe_answer(callback, "Bu so'rov allaqachon ko'rib chiqilgan", show_alert=True)
        return
    await safe_edit(callback, f"❌ So'rov #{payment_id} rad etildi")
    await safe_answer(callback, "Rad etildi")
    await _notify_user(
        callback.bot,
        payment["user_id"],
        f"❌ #{payment_id} to'lov so'rovingiz rad etildi. Savollar bo'lsa admin bilan bog'laning.",
    )


@router.callback_query(F.data == "adm_users")
async def users_list(callback: CallbackQuery) -> None:
    users = await api_client.admin_list_users()
    await safe_edit(callback, f"👥 Foydalanuvchilar ({len(users)}):", kb.admin_users(users))
    await safe_answer(callback)


@router.callback_query(F.data.startswith("adm_user:"))
async def user_view(callback: CallbackQuery) -> None:
    user_id = int(callback.data.split(":", 1)[1])
    user = next(u for u in await api_client.admin_list_users() if u["id"] == user_id)
    overview = await api_client.get_overview(user_id)
    banned = "ha" if user["is_banned"] else "yo'q"
    text = (
        f"👤 {user['first_name'] or ''} {('@' + user['username']) if user['username'] else ''}\n"
        f"Telegram ID: {user['telegram_user_id']}\n"
        f"Tarif: {overview['plan']['name']}\n"
        f"Balans: {money(user['balance'])}\n"
        f"Akkauntlar: {overview['usage']['accounts']}, faol xizmatlar: {overview['usage']['automations']}\n"
        f"Bloklangan: {banned}"
    )
    await safe_edit(callback, text, kb.admin_user_view(user_id, user["is_banned"]))
    await safe_answer(callback)


@router.callback_query(F.data.startswith("adm_ban:"))
async def ban(callback: CallbackQuery) -> None:
    await api_client.admin_ban_user(int(callback.data.split(":", 1)[1]))
    await safe_answer(callback, "🚫 Bloklandi")
    await users_list(callback)


@router.callback_query(F.data.startswith("adm_unban:"))
async def unban(callback: CallbackQuery) -> None:
    await api_client.admin_unban_user(int(callback.data.split(":", 1)[1]))
    await safe_answer(callback, "✅ Blokdan chiqarildi")
    await users_list(callback)
