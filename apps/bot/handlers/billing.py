import logging
import re

from aiogram import Bot, F, Router
from aiogram.exceptions import TelegramAPIError
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

import keyboards as kb
from api_client import ApiError, api_client
from catalog import expiry_text, plan_features, plan_status_lines, pro_unlocked
from common import db_user_id, money, safe_answer, safe_edit
from core.entitlements import FREE_PLAN
from core.settings import settings
from states import Topup

router = Router(name="billing")
logger = logging.getLogger(__name__)

PLAN_ICONS = {"free": "🆓", "starter": "⭐", "pro": "🚀"}


def _plan_card(code: str, name: str, price_text: str, flags: dict, is_current: bool) -> str:
    title = f"{PLAN_ICONS.get(code, '💎')} {name} — {price_text}" + ("   ✅ sizda" if is_current else "")
    return title + "\n" + "\n".join(f"   • {f}" for f in plan_features(flags))


@router.callback_query(F.data == "plans")
async def show_plans(callback: CallbackQuery) -> None:
    user_id = await db_user_id(callback.from_user)
    overview = await api_client.get_overview(user_id)
    plans = await api_client.list_plans()
    current_code = overview["plan"]["code"]

    cards = [_plan_card("free", FREE_PLAN["name"], "tekin", FREE_PLAN["flags"], current_code == "free")]
    cards += [
        _plan_card(p["code"], p["name"], f"{money(p['price'])} / {p['duration_days']} kun", p["flags"], current_code == p["code"])
        for p in plans
    ]
    text = (
        "\n".join(plan_status_lines(overview))
        + f"\n💰 Balans: {money(overview['user']['balance'])}\n\n"
        + "\n\n".join(cards)
        + "\n\nTarif balansdan sotib olinadi. Muddat tugasa Bepul tarifga qaytasiz va ortiqcha xizmatlar to'xtaydi."
    )
    await safe_edit(callback, text, kb.plans(plans, current_code))
    await safe_answer(callback)


@router.callback_query(F.data.startswith("buy:"))
async def ask_buy(callback: CallbackQuery) -> None:
    code = callback.data.split(":", 1)[1]
    user_id = await db_user_id(callback.from_user)
    overview = await api_client.get_overview(user_id)
    plans = await api_client.list_plans()
    plan = next(p for p in plans if p["code"] == code)
    current = next((p for p in plans if p["code"] == overview["plan"]["code"]), None)
    balance = overview["user"]["balance"]

    if current is not None and current["code"] != code and current["price"] > plan["price"]:
        await safe_edit(
            callback,
            f"Sizda yuqoriroq {current['name']} tarifi faol — {expiry_text(overview['plan']['expires_at'])}.\n"
            f"{plan['name']} olish hozir hech narsa qo'shmaydi.",
            kb.plans(plans, current["code"]),
        )
    elif balance < plan["price"]:
        await safe_edit(
            callback,
            f"Balans yetarli emas.\n\n{plan['name']}: {money(plan['price'])}\nSizda: {money(balance)}\n\n"
            "Avval balansni to'ldiring.",
            kb.need_topup(),
        )
    else:
        extend = "Muddati" if current is not None and current["code"] == code else "Tarif"
        await safe_edit(
            callback,
            f"{PLAN_ICONS.get(code, '💎')} {plan['name']} — {plan['duration_days']} kun\n"
            + "\n".join(f"   • {f}" for f in plan_features(plan["flags"]))
            + f"\n\n{extend} {plan['duration_days']} kunga {'uzayadi' if extend == 'Muddati' else 'faollashadi'}.\n"
            f"Balansingizdan {money(plan['price'])} yechiladi (qoladi: {money(balance - plan['price'])}).\n\n"
            "Tasdiqlaysizmi?",
            kb.confirm_buy(code),
        )
    await safe_answer(callback)


@router.callback_query(F.data.startswith("buy_yes:"))
async def buy(callback: CallbackQuery) -> None:
    code = callback.data.split(":", 1)[1]
    user_id = await db_user_id(callback.from_user)
    try:
        await api_client.buy_plan(user_id, code)
    except ApiError as exc:
        await safe_edit(callback, f"⚠️ {exc.message}", kb.need_topup())
        await safe_answer(callback)
        return

    overview = await api_client.get_overview(user_id)
    plan, flags = overview["plan"], overview["plan"]["flags"]
    unlocked = [f"{flags['account_limit']} ta akkaunt ulash", f"bir vaqtda {flags['scheduler_limit']} ta xizmat"]
    unlocked += pro_unlocked(flags)
    await safe_edit(
        callback,
        f"🎉 {plan['name']} tarifi faollashdi!\n⏳ {expiry_text(plan['expires_at'])}\n\n"
        "Endi sizda:\n" + "\n".join(f"✅ {u}" for u in unlocked) + "\n\n"
        "Xizmatlarni bosh sahifada yoqing 👇\nMuddat tugashidan 1 kun oldin eslataman.",
        kb.after_purchase(bool(flags.get("online_service"))),
    )
    await safe_answer(callback, "🎉 Tarif faollashdi")


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
