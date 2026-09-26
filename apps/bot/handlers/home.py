import asyncio

from aiogram import Bot, F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, Message

import keyboards as kb
from api_client import ApiError, api_client
from catalog import (
    BASIC_SERVICES,
    ERROR_HINT,
    PRO_SERVICES,
    SERVICES,
    STATUS_ICONS,
    STATUS_TEXT,
    STUDIO,
    TEMPLATE_HELP,
    UPDATE_INTERVAL_SECONDS,
    plan_features,
    plan_line,
    unlocking_plan,
    usage_line,
)
from common import current_account, db_user_id, is_admin, money, safe_answer, safe_edit, select_account
from core.settings import settings
from core.templates import TemplateContext, render
from states import EditTemplate

router = Router(name="home")


def _welcome(first_name: str | None) -> str:
    return (
        f"👋 Salom{', ' + first_name if first_name else ''}!\n\n"
        "Men Telegram profilingizni o'zim yangilab turaman:\n"
        "🕐 ismda soat · 📝 avto bio · 🗓 jadval\n"
        "🟢 24/7 online · 🖼 rasm · 😀 emoji status\n\n"
        "Boshlash uchun akkauntingizni ulang — 1 daqiqa 👇"
    )


HELP = (
    "❓ Qanday ishlaydi\n\n"
    "1️⃣ Akkauntni ulang — 📞 raqam yoki 📷 QR orqali.\n"
    "2️⃣ Xizmatni yoqing — profilingiz o'zi yangilanadi.\n"
    f"3️⃣ {STUDIO}da natijani oldindan ko'ring va tahrirlang.\n\n"
    "⏹ Xizmatni o'chirsangiz — profil asl holiga qaytadi.\n"
    "🚫 Akkauntni istalgan vaqtda uzasiz: ⚙️ Akkaunt.\n"
    "🔒 Sessiya shifrlangan holda saqlanadi.\n\n"
    "Savol bo'lsa — shu chatga yozing yoki /start bosing."
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


async def _upgrade_hint(overview: dict) -> str | None:
    """Pullik tarifi yo'q foydalanuvchiga eng yuqori tarif nima berishini bir qatorda."""
    if overview["plan"]["expires_at"]:
        return None
    plans = await api_client.list_plans()
    if not plans:
        return None
    best = max(plans, key=lambda p: p["price"])
    return f"💡 {best['name']}: {plan_features(best['flags'])}"


async def build_home(tg_user_id: int, user_id: int, first_name: str | None = None) -> tuple[str, InlineKeyboardMarkup | None]:
    overview = await api_client.get_overview(user_id)
    if overview["user"]["is_banned"]:
        return "⛔ Hisobingiz bloklangan. Savol bo'lsa — admin bilan bog'laning.", None

    admin = is_admin(tg_user_id)
    account = current_account(overview, tg_user_id)
    if account is None:
        return _welcome(first_name), kb.home_no_account(admin)

    live = {a["service_code"]: a for a in account["automations"]}
    if overview["plan"]["flags"].get("ai_service"):
        ai_state = await api_client.get_ai(user_id, account["id"])
        if ai_state["settings"]["enabled"]:
            live["ai"] = {"status": "ACTIVE", "service_code": "ai"}
    lines = [
        f"👤 {_account_label(account)}",
        f"{plan_line(overview)} · 💰 {money(overview['user']['balance'])}",
        usage_line(overview),
        "",
    ]
    active = []
    for code, automation in live.items():
        meta = SERVICES.get(code) or PRO_SERVICES.get(code)
        if meta is None:
            continue
        icon = STATUS_ICONS.get(automation["status"], "✅")
        if code in BASIC_SERVICES:
            active.append(f"{icon} {meta['title']} → «{_preview(automation['template'], account)}»")
        else:
            active.append(f"{icon} {meta['title']}")
    if active:
        lines += ["Ishlayapti:", *active]
    else:
        lines += ["Hozircha hech narsa yoqilmagan.", "🕐 Soat ismda'dan boshlang — bir bosishda yoqiladi."]
    if hint := await _upgrade_hint(overview):
        lines += ["", hint]
    lines += ["", "Xizmatni tanlang 👇"]
    return "\n".join(lines), kb.home(live, len(overview["accounts"]) > 1, admin)


async def send_home(bot: Bot, chat_id: int, tg_user_id: int, user_id: int, first_name: str | None = None) -> None:
    text, markup = await build_home(tg_user_id, user_id, first_name)
    await bot.send_message(chat_id, text, reply_markup=markup)


async def _load(callback: CallbackQuery) -> tuple[dict, dict | None]:
    user_id = await db_user_id(callback.from_user)
    overview = await api_client.get_overview(user_id)
    return overview, current_account(overview, callback.from_user.id)


async def edit_home(callback: CallbackQuery) -> None:
    user_id = await db_user_id(callback.from_user)
    text, markup = await build_home(callback.from_user.id, user_id, callback.from_user.first_name)
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
        text = f"{meta['title']} · {STATUS_TEXT.get(automation['status'], automation['status'])}\n\n{meta['desc']}"
        if meta["field"] != "online":
            text += f"\n\nHozir: «{_preview(automation['template'], account)}»\nShablon: {automation['template']}"
        if automation["status"] == "ERROR":
            text += f"\n\n{ERROR_HINT}"
        markup = kb.service_on(code, automation["id"])
    else:
        flag = meta.get("pro_flag")
        locked = bool(flag) and not overview["plan"]["flags"].get(flag)
        text = f"{meta['title']}\n\n{meta['desc']}"
        if meta["field"] != "online":
            text += f"\n\nKo'rinishi: «{_preview(meta['default'], account)}»"
        plan_name = None
        if locked:
            unlock = unlocking_plan(await api_client.list_plans(), flag)
            plan_name = unlock["name"] if unlock else None
            text += f"\n\n🔒 {plan_name or 'Yuqoriroq'} tarifida ochiladi."
        markup = kb.service_off(code, locked, plan_name)

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
                f"🔒 {exc.message}\n\nBoshqa xizmatni o'chiring yoki tarifni yangilang.",
                kb.upsell(),
            )
            return None
        raise
    if replaced:
        old = replaced[0]["service_code"]
        title = (SERVICES.get(old) or PRO_SERVICES.get(old, {})).get("title", old)
        return f"\n\nℹ️ {title} o'chirildi — ikkalasi bir joyni o'zgartiradi."
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
        f"✏️ {meta['title']} uchun matn yuboring.\n\n{TEMPLATE_HELP}\n\nMasalan: {meta['default']}",
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
        await message.answer("🤔 Noma'lum o'zgaruvchi bor. Qaytadan yuboring.\n\n" + TEMPLATE_HELP, reply_markup=kb.cancel())
        return
    limit = _MAX_LEN[meta["field"]] * (2 if meta["field"] == "bio" and account["is_premium"] else 1)
    if not preview or len(preview) > limit:
        await message.answer(f"✂️ Juda uzun: {len(preview)}/{limit} belgi. Qisqaroq yuboring.", reply_markup=kb.cancel())
        return

    try:
        await api_client.enable_service(
            account["id"], code, [{"field": meta["field"], "template": template}], UPDATE_INTERVAL_SECONDS
        )
    except ApiError as exc:
        if exc.status_code == 402:
            await state.clear()
            await message.answer(f"🔒 {exc.message}\n\nBoshqa xizmatni o'chiring yoki tarifni yangilang.", reply_markup=kb.upsell())
            return
        raise
    await state.clear()
    await message.answer(f"✅ {meta['title']} yoqildi!\nKo'rinishi: «{preview}»")
    await send_home(message.bot, message.chat.id, message.from_user.id, user_id)


@router.callback_query(F.data.startswith("svc_off:"))
async def disable_service(callback: CallbackQuery) -> None:
    automation_id = int(callback.data.split(":", 1)[1])
    try:
        await api_client.stop_service(automation_id, restore=True)
    except ApiError as exc:
        await safe_answer(callback, exc.message, show_alert=True)
        return
    await safe_answer(callback, "⏹ O'chirildi — profil asl holiga qaytadi.")
    await asyncio.sleep(1.5)
    await edit_home(callback)


# --- Akkaunt ---


@router.callback_query(F.data == "acc")
async def show_account(callback: CallbackQuery) -> None:
    overview, account = await _load(callback)
    if account is None:
        await safe_edit(callback, "Akkaunt hali ulanmagan. Qanday ulaymiz?", kb.login_methods())
        await safe_answer(callback)
        return
    flags = overview["plan"]["flags"]
    premium = " · ⭐ Premium" if account["is_premium"] else ""
    text = (
        f"⚙️ Akkaunt\n\n"
        f"👤 {account['first_name'] or ''} ({_account_label(account)}){premium}\n"
        f"Ulangan: {overview['usage']['accounts']}/{flags['account_limit']} akkaunt"
    )
    await safe_edit(callback, text, kb.account_menu(len(overview["accounts"]) > 1))
    await safe_answer(callback)


@router.callback_query(F.data == "acc_add")
async def add_account(callback: CallbackQuery) -> None:
    await safe_edit(
        callback,
        "Qanday ulaymiz?\n\n"
        "📞 Raqam — telefonda eng qulay.\n"
        "📷 QR — bot kompyuterda ochiq bo'lsa, telefon bilan skanerlaysiz.",
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
        f"🚫 {_account_label(account)} uzilsinmi?\n\n"
        "• barcha xizmatlar to'xtaydi\n"
        "• profil asl holiga qaytadi\n"
        "• bot bu akkauntga boshqa kira olmaydi",
        kb.confirm_revoke(account["id"]),
    )
    await safe_answer(callback)


@router.callback_query(F.data.startswith("acc_del_yes:"))
async def revoke(callback: CallbackQuery) -> None:
    await api_client.revoke_account(int(callback.data.split(":", 1)[1]))
    await safe_answer(callback, "🚫 Akkaunt uzilmoqda…")
    await asyncio.sleep(2)
    await edit_home(callback)


# --- Referral ---


@router.callback_query(F.data == "ref")
async def show_referral(callback: CallbackQuery) -> None:
    user_id = await db_user_id(callback.from_user)
    user = await api_client.get_user(user_id)
    bot_username = (await callback.bot.get_me()).username
    link = f"https://t.me/{bot_username}?start=ref_{user['referral_code']}"
    await safe_edit(callback, f"🎁 Do'stlaringizga ulashing\n\nSizning havolangiz:\n{link}", kb.back_home())
    await safe_answer(callback)


@router.callback_query(F.data == "help")
async def show_help(callback: CallbackQuery) -> None:
    await safe_edit(callback, HELP, kb.help_menu())
    await safe_answer(callback)


async def send_help(message: Message) -> None:
    await message.answer(HELP, reply_markup=kb.help_menu())


@router.message()
async def fallback(message: Message) -> None:
    """Holatsiz har qanday matn — bosh sahifani ko'rsatadi (bot jim qolmasin)."""
    user_id = await db_user_id(message.from_user)
    await send_home(message.bot, message.chat.id, message.from_user.id, user_id, message.from_user.first_name)
