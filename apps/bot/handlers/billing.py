import datetime
import logging
import re

from aiogram import Bot, F, Router
from aiogram.exceptions import TelegramAPIError
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

import keyboards as kb
from api_client import ApiError, api_client
from common import db_user_id, money, safe_answer, safe_edit
from core.settings import settings
from states import Topup

router = Router(name="billing")
logger = logging.getLogger(__name__)

FREE_DESCRIPTION = "🆓 Bepul — 1 akkaunt, 1 ta xizmat"


def _plan_description(plan: dict) -> str:
    flags = plan["flags"]
    parts = [f"{flags.get('account_limit', 1)} akkaunt", f"bir vaqtda {flags.get('scheduler_limit', 1)} ta xizmat"]
    if flags.get("online_service"):
        parts.append("🟢 24/7 Online")
    return f"⭐ {plan['name']} — {money(plan['price'])} / {plan['duration_days']} kun\n    " + ", ".join(parts)


@router.callback_query(F.data == "plans")
async def show_plans(callback: CallbackQuery) -> None:
    user_id = await db_user_id(callback.from_user)
    overview = await api_client.get_overview(user_id)
    plans = await api_client.list_plans()
    current = overview["plan"]
    header = f"💎 Joriy tarif: {current['name']}"
    if current["expires_at"]:
        header += f" ({datetime.datetime.fromisoformat(current['expires_at']).strftime('%d.%m.%Y')} gacha)"
    text = "\n\n".join(
        [header, f"💰 Balans: {money(overview['user']['balance'])}", FREE_DESCRIPTION, *map(_plan_description, plans)]
    )
    text += "\n\nTarif balansdan sotib olinadi."
    await safe_edit(callback, text, kb.plans(plans, current["code"]))
    await safe_answer(callback)


@router.callback_query(F.data.startswith("buy:"))
async def ask_buy(callback: CallbackQuery) -> None:
    code = callback.data.split(":", 1)[1]
    user_id = await db_user_id(callback.from_user)
    overview = await api_client.get_overview(user_id)
    plan = next(p for p in await api_client.list_plans() if p["code"] == code)
    balance = overview["user"]["balance"]

    if balance < plan["price"]:
        await safe_edit(
            callback,
            f"Balans yetarli emas.\n\n{plan['name']}: {money(plan['price'])}\nSizda: {money(balance)}\n\n"
            "Avval balansni to'ldiring.",
            kb.need_topup(),
        )
    else:
        await safe_edit(
            callback,
            f"{plan['name']} tarifi — {plan['duration_days']} kun.\n"
            f"Balansingizdan {money(plan['price'])} yechiladi.\n\nTasdiqlaysizmi?",
            kb.confirm_buy(code),
        )
    await safe_answer(callback)


@router.callback_query(F.data.startswith("buy_yes:"))
async def buy(callback: CallbackQuery) -> None:
    code = callback.data.split(":", 1)[1]
    user_id = await db_user_id(callback.from_user)
    try:
        subscription = await api_client.buy_plan(user_id, code)
    except ApiError as exc:
        await safe_edit(callback, f"⚠️ {exc.message}", kb.need_topup())
        await safe_answer(callback)
        return
    until = datetime.datetime.fromisoformat(subscription["expires_at"]).strftime("%d.%m.%Y")
    await safe_edit(callback, f"🎉 Tarif faollashdi! {until} gacha amal qiladi.", kb.back_home())
    await safe_answer(callback)


# --- Balans ---


@router.callback_query(F.data == "bal")
async def show_balance(callback: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    user = await api_client.get_user(await db_user_id(callback.from_user))
    await safe_edit(
        callback,
        f"💰 Balansingiz: {money(user['balance'])}\n\nBalans orqali tariflarni sotib olasiz.",
        kb.balance(),
    )
    await safe_answer(callback)


@router.callback_query(F.data == "topup")
async def ask_topup_amount(callback: CallbackQuery) -> None:
    amounts = sorted({int(p["price"]) for p in await api_client.list_plans()})
    await safe_edit(callback, "Qancha summaga to'ldiramiz?", kb.topup_amounts(amounts))
    await safe_answer(callback)


@router.callback_query(F.data == "topup_custom")
async def ask_custom_amount(callback: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(Topup.waiting_amount)
    await safe_edit(callback, "Summani so'mda yuboring (masalan: 100000):", kb.cancel())
    await safe_answer(callback)


@router.message(Topup.waiting_amount)
async def custom_amount_received(message: Message, state: FSMContext) -> None:
    digits = re.sub(r"\D", "", message.text or "")
    if not digits or int(digits) < 1000:
        await message.answer("Kamida 1 000 so'm kiriting:", reply_markup=kb.cancel())
        return
    await state.clear()
    await _create_topup(message.bot, message.chat.id, message.from_user, int(digits))


@router.callback_query(F.data.startswith("topup_amt:"))
async def preset_amount(callback: CallbackQuery) -> None:
    await _create_topup(callback.bot, callback.message.chat.id, callback.from_user, int(callback.data.split(":", 1)[1]))
    await safe_answer(callback)


async def _create_topup(bot: Bot, chat_id: int, tg_user, amount: int) -> None:
    user_id = await db_user_id(tg_user)
    payment = await api_client.create_topup(user_id, amount)

    instructions = (
        f"To'lov uchun:\n{settings.payment_instructions}\n\nTo'lov izohiga #{payment['id']} raqamini yozing."
        if settings.payment_instructions
        else "Admin siz bilan bog'lanib, to'lovni tasdiqlaydi."
    )
    await bot.send_message(
        chat_id,
        f"✅ So'rov #{payment['id']} yaratildi: {money(amount)}\n\n{instructions}\n\n"
        "Tasdiqlangach balansingizga tushadi va sizga xabar beraman.",
        reply_markup=kb.back_home(),
    )

    who = f"@{tg_user.username}" if tg_user.username else tg_user.full_name
    for admin_id in settings.admin_telegram_id_set:
        try:
            await bot.send_message(
                admin_id,
                f"💳 Yangi to'ldirish so'rovi #{payment['id']}\n👤 {who} (id {tg_user.id})\nSumma: {money(amount)}",
                reply_markup=kb.admin_payment_decision(payment["id"]),
            )
        except TelegramAPIError:
            logger.warning("admin %s ga xabar yuborib bo'lmadi", admin_id)
