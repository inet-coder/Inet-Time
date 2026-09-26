import asyncio

from aiogram import Bot, F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, Message

import keyboards as kb
from api_client import ApiError, api_client
from catalog import (
    BASIC_SERVICES,
    PRO_SERVICES,
    SERVICES,
    STATUS_ICONS,
    TEMPLATE_HELP,
    UPDATE_INTERVAL_SECONDS,
    plan_features,
    plan_status_lines,
    pro_unlocked,
)
from common import current_account, db_user_id, is_admin, money, safe_answer, safe_edit, select_account
from core.settings import settings
from core.templates import TemplateContext, render
from states import EditTemplate

router = Router(name="home")

WELCOME = (
    "Salom! 👋\n\n"
    "Bu bot Telegram profilingizni avtomatik yangilab turadi:\n"
    "• 🕐 ismingiz yonida joriy soat\n"
    "• 📝 o'zgarib turadigan bio\n"
    "• ✏️ avto ism, 🟢 24/7 online\n\n"
    "Boshlash uchun akkauntingizni ulang 👇\n"
    "(Telefon raqam orqali ulash eng qulay usul.)"
)

# Telegram cheklovlari: ism 64, bio 70 belgi (Premium'da 140).
_MAX_LEN = {"name": 64, "bio": 70}


def _account_label(account: dict) -> str:
    return f"@{account['username']}" if account["username"] else (account["first_name"] or f"#{account['id']}")


def _preview(template: str, account: dict) -> str:
    ctx = TemplateContext(
        first_name=account["first_name"], last_name=None, username=account["username"], timezone=settings.default_timezone
    )
    return render(template, ctx)


async def _plan_block(overview: dict) -> str:
    lines = plan_status_lines(overview)
    if not overview["plan"]["expires_at"]:
        # Pullik tarifi yo'q foydalanuvchiga eng yuqori tarif nima berishini ko'rsatamiz.
        plans = await api_client.list_plans()
        if plans:
            best = max(plans, key=lambda p: p["price"])
            lines.append(f"   💡 {best['name']} bilan: " + ", ".join(plan_features(best["flags"])))
    return "\n".join(lines)


async def build_home(tg_user_id: int, user_id: int) -> tuple[str, InlineKeyboardMarkup | None]:
    overview = await api_client.get_overview(user_id)
    if overview["user"]["is_banned"]:
        return "⛔ Hisobingiz bloklangan. Savollar bo'lsa admin bilan bog'laning.", None

    admin = is_admin(tg_user_id)
    plan_block = await _plan_block(overview)
    balance_line = f"💰 Balans: {money(overview['user']['balance'])}"
    account = current_account(overview, tg_user_id)
    if account is None:
        return f"{WELCOME}\n\n{plan_block}\n{balance_line}", kb.home_no_account(admin)

    live = {a["service_code"]: a for a in account["automations"]}
    flags = overview["plan"]["flags"]
    lines = [f"👤 Akkaunt: {_account_label(account)}", plan_block, balance_line, "", "Xizmatlar:"]
    for code in BASIC_SERVICES:
        meta, automation = SERVICES[code], live.get(code)
        if automation is not None:
            status = STATUS_ICONS.get(automation["status"], "✅")
            lines.append(f"{status} {meta['title']} → «{_preview(automation['template'], account)}»")
        else:
            lines.append(f"❌ {meta['title']}")

    active_pro = [f"{STATUS_ICONS.get(live[c]['status'], '✅')} {m['title']}" for c, m in PRO_SERVICES.items() if c in live]
    if active_pro:
        lines.append("\n⭐ Pro xizmatlar:\n" + "\n".join(active_pro))
    elif pro_unlocked(flags):
        lines.append("\n⭐ Pro xizmatlar: hali yoqilmagan")
    else:
        lines.append("\n⭐ Pro xizmatlar: 🔒 Pro tarifda (playlist, jadval, emoji, rasm, 24/7 online)")
    lines.append("\nYoqish/o'chirish uchun tugmani bosing 👇")
    return "\n".join(lines), kb.home(live, len(overview["accounts"]) > 1, admin)


async def send_home(bot: Bot, chat_id: int, tg_user_id: int, user_id: int) -> None:
    text, markup = await build_home(tg_user_id, user_id)
    await bot.send_message(chat_id, text, reply_markup=markup)


async def _load(callback: CallbackQuery) -> tuple[dict, dict | None]:
    user_id = await db_user_id(callback.from_user)
    overview = await api_client.get_overview(user_id)
    return overview, current_account(overview, callback.from_user.id)


async def edit_home(callback: CallbackQuery) -> None:
    user_id = await db_user_id(callback.from_user)
    text, markup = await build_home(callback.from_user.id, user_id)
    await safe_edit(callback, text, markup)


@router.callback_query(F.data == "home")
async def show_home(callback: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    await edit_home(callback)
    await safe_answer(callback)


# --- Xizmatlar ---


async def _render_service(callback: CallbackQuery, code: str, note: str = "") -> None:
    overview, account = await _load(callback)
    if account is None:
        await edit_home(callback)
        return
    meta = SERVICES[code]
    automation = next((a for a in account["automations"] if a["service_code"] == code), None)

    if automation is not None:
        status_text = {"ACTIVE": "✅ yoqilgan", "STARTING": "⏳ ishga tushmoqda", "ERROR": "⚠️ xatolik"}.get(
            automation["status"], automation["status"]
        )
        text = f"{meta['title']} — {status_text}\n\n{meta['desc']}"
        if meta["field"] != "online":
            text += f"\n\nShablon: {automation['template']}\nHozir: «{_preview(automation['template'], account)}»"
        if automation["status"] == "ERROR":
            text += "\n\n⚠️ Telegram bilan muammo yuz berdi. Xizmatni o'chirib, qayta yoqib ko'ring."
        markup = kb.service_on(code, automation["id"])
    else:
        locked = bool(meta.get("pro_flag")) and not overview["plan"]["flags"].get(meta["pro_flag"])
        text = f"{meta['title']} — ❌ o'chiq\n\n{meta['desc']}"
        if meta["field"] != "online":
            text += f"\n\nNamuna: «{_preview(meta['default'], account)}»"
        if locked:
            text += "\n\n🔒 Bu xizmat faqat Pro tarifda mavjud."
        markup = kb.service_off(code, locked)

    await safe_edit(callback, text + note, markup)


@router.callback_query(F.data.startswith("svc:"))
async def show_service(callback: CallbackQuery) -> None:
    await _render_service(callback, callback.data.split(":", 1)[1])
    await safe_answer(callback)


async def _enable(callback: CallbackQuery, code: str, template: str) -> str | None:
    """Xizmatni yoqadi. Limit oshsa foydalanuvchiga upsell ko'rsatib None qaytaradi, aks holda izoh matni."""
    overview, account = await _load(callback)
    meta = SERVICES[code]
    replaced = [a for a in account["automations"] if a["field"] == meta["field"] and a["service_code"] != code]
    try:
        await api_client.enable_service(
            account["id"], code, [{"field": meta["field"], "template": template}], UPDATE_INTERVAL_SECONDS
        )
    except ApiError as exc:
        if exc.status_code == 402:
            await safe_edit(
                callback,
                f"🔒 {exc.message}\n\nBoshqa xizmatni o'chiring yoki tarifni oshiring.",
                kb.upsell(),
            )
            return None
        raise
    if replaced:
        return f"\n\nℹ️ {SERVICES[replaced[0]['service_code']]['title']} o'chirildi — ikkalasi ham bir xil maydonni o'zgartiradi."
    return ""


@router.callback_query(F.data.startswith("svc_on:"))
async def enable_service(callback: CallbackQuery) -> None:
    code = callback.data.split(":", 1)[1]
    note = await _enable(callback, code, SERVICES[code]["default"])
    if note is None:
        await safe_answer(callback)
        return
    await safe_answer(callback, "✅ Yoqildi")
    await asyncio.sleep(1.5)  # worker faollashtirishga ulgursin
    await _render_service(callback, code, note)


@router.callback_query(F.data.startswith("svc_tpl:"))
async def ask_template(callback: CallbackQuery, state: FSMContext) -> None:
    code = callback.data.split(":", 1)[1]
    meta = SERVICES[code]
    await state.set_state(EditTemplate.waiting_text)
    await state.update_data(code=code)
    await safe_edit(
        callback,
        f"{meta['title']} uchun shablon yuboring.\n\n{TEMPLATE_HELP}\n\nNamuna: {meta['default']}",
        kb.cancel(),
    )
    await safe_answer(callback)


@router.message(EditTemplate.waiting_text)
async def template_received(message: Message, state: FSMContext) -> None:
    code = (await state.get_data())["code"]
    meta = SERVICES[code]
    template = (message.text or "").strip()
    user_id = await db_user_id(message.from_user)
    overview = await api_client.get_overview(user_id)
    account = current_account(overview, message.from_user.id)

    try:
        preview = _preview(template, account)
    except ValueError:
        await message.answer("Shablonda noma'lum o'zgaruvchi bor. Qaytadan yuboring.\n\n" + TEMPLATE_HELP, reply_markup=kb.cancel())
        return
    limit = _MAX_LEN[meta["field"]] * (2 if meta["field"] == "bio" and account["is_premium"] else 1)
    if not preview or len(preview) > limit:
        await message.answer(f"Natija bo'sh yoki juda uzun ({len(preview)}/{limit} belgi). Qisqaroq yuboring.", reply_markup=kb.cancel())
        return

    try:
        await api_client.enable_service(
            account["id"], code, [{"field": meta["field"], "template": template}], UPDATE_INTERVAL_SECONDS
        )
    except ApiError as exc:
        if exc.status_code == 402:
            await state.clear()
            await message.answer(f"🔒 {exc.message}\n\nBoshqa xizmatni o'chiring yoki tarifni oshiring.", reply_markup=kb.upsell())
            return
        raise
    await state.clear()
    await message.answer(f"✅ {meta['title']} yoqildi.\nKo'rinishi: «{preview}»")
    await send_home(message.bot, message.chat.id, message.from_user.id, user_id)


@router.callback_query(F.data.startswith("svc_off:"))
async def disable_service(callback: CallbackQuery) -> None:
    automation_id = int(callback.data.split(":", 1)[1])
    try:
        await api_client.stop_service(automation_id, restore=True)
    except ApiError as exc:
        await safe_answer(callback, exc.message, show_alert=True)
        return
    await safe_answer(callback, "⏹ O'chirildi. Profilingiz asl holiga qaytariladi.", show_alert=True)
    await asyncio.sleep(1.5)
    await edit_home(callback)


# --- Akkaunt ---


@router.callback_query(F.data == "acc")
async def show_account(callback: CallbackQuery) -> None:
    overview, account = await _load(callback)
    if account is None:
        await safe_edit(callback, "Hali akkaunt ulanmagan.", kb.login_methods())
        await safe_answer(callback)
        return
    flags = overview["plan"]["flags"]
    premium = "ha" if account["is_premium"] else "yo'q"
    text = (
        f"⚙️ Akkaunt\n\n"
        f"👤 {account['first_name'] or ''} ({_account_label(account)})\n"
        f"Premium: {premium}\n"
        f"Ulangan akkauntlar: {overview['usage']['accounts']}/{flags['account_limit']}"
    )
    await safe_edit(callback, text, kb.account_menu(len(overview["accounts"]) > 1))
    await safe_answer(callback)


@router.callback_query(F.data == "acc_add")
async def add_account(callback: CallbackQuery) -> None:
    await safe_edit(
        callback,
        "Qaysi usulda ulaymiz?\n\n"
        "📞 Telefon raqam — telefonda eng qulay.\n"
        "📷 QR kod — botni kompyuterda ochgan bo'lsangiz, telefoningiz bilan skanerlaysiz.",
        kb.login_methods(),
    )
    await safe_answer(callback)


@router.callback_query(F.data == "acc_switch")
async def switch_account(callback: CallbackQuery) -> None:
    overview, _ = await _load(callback)
    await safe_edit(callback, "Qaysi akkauntni boshqaramiz?", kb.account_picker(overview["accounts"]))
    await safe_answer(callback)


@router.callback_query(F.data.startswith("acc_sel:"))
async def select_account_handler(callback: CallbackQuery, state: FSMContext) -> None:
    select_account(callback.from_user.id, int(callback.data.split(":", 1)[1]))
    await show_home(callback, state)


@router.callback_query(F.data == "acc_del")
async def confirm_revoke(callback: CallbackQuery) -> None:
    _, account = await _load(callback)
    if account is None:
        await safe_answer(callback)
        return
    await safe_edit(
        callback,
        f"{_account_label(account)} akkauntini uzasizmi?\n\n"
        "Barcha xizmatlar to'xtaydi, profilingiz asl holiga qaytariladi va bot bu akkauntga boshqa kira olmaydi.",
        kb.confirm_revoke(account["id"]),
    )
    await safe_answer(callback)


@router.callback_query(F.data.startswith("acc_del_yes:"))
async def revoke(callback: CallbackQuery) -> None:
    await api_client.revoke_account(int(callback.data.split(":", 1)[1]))
    await safe_answer(callback, "Akkaunt uzilmoqda...")
    await asyncio.sleep(2)
    await edit_home(callback)


# --- Referral ---


@router.callback_query(F.data == "ref")
async def show_referral(callback: CallbackQuery) -> None:
    user_id = await db_user_id(callback.from_user)
    user = await api_client.get_user(user_id)
    bot_username = (await callback.bot.get_me()).username
    link = f"https://t.me/{bot_username}?start=ref_{user['referral_code']}"
    await safe_edit(callback, f"🤝 Do'stlaringizni taklif qiling!\n\nSizning havolangiz:\n{link}", kb.back_home())
    await safe_answer(callback)


@router.message()
async def fallback(message: Message) -> None:
    """Holatsiz har qanday matn — bosh sahifani ko'rsatadi (bot jim qolmasin)."""
    user_id = await db_user_id(message.from_user)
    await send_home(message.bot, message.chat.id, message.from_user.id, user_id)
