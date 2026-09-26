"""🎂 Tug'ilgan kun (bio'da qancha qolgani) va 👁 Faollik holati (onlayn / yaqinda / kontaktlar / standart)."""

import asyncio
import re

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

import keyboards as kb
from api_client import ApiError, api_client
from catalog import UPDATE_INTERVAL_SECONDS
from common import current_account, db_user_id, safe_answer, safe_edit
from states import BirthdayAsk

router = Router(name="profile")

_DATE = re.compile(r"^\s*(\d{1,2})[./\-](\d{1,2})(?:[./\-](\d{4}))?\s*$")

PRESENCE = {
    "online": ("🟢 Doim onlayn", "online"),
    "recently": ("🕶 Yaqinda onlayn edi", "yaqinda onlayn edi"),
    "contacts": ("👥 Faqat kontaktlarga", "kontaktlarga — aniq vaqt, boshqalarga — «yaqinda»"),
    "default": ("🕐 Standart", "bugun 14:05 da onlayn edi"),
}


async def _load(tg_user) -> tuple[int, dict | None]:
    user_id = await db_user_id(tg_user)
    overview = await api_client.get_overview(user_id)
    return user_id, current_account(overview, tg_user.id)


# --- 🎂 Tug'ilgan kun ---


def _birthday_text(data: dict, note: str = "") -> str:
    if data["birthday"]:
        date = f"{data['day']:02d}.{data['month']:02d}" + (f".{data['year']}" if data["year"] else "")
        head = f"🎂 Tug'ilgan kun: {date}\n\nBio uchun tayyor shablonlar — bosing, Avto bio bo'lib yoqiladi 👇"
    else:
        head = "🎂 Tug'ilgan kun\n\nSanani yuboring: 08.10 yoki 08.10.2001\n(yil — faqat yoshni ko'rsatish uchun)"
    return head + note


async def _show_birthday(target: CallbackQuery | Message, state: FSMContext, note: str = "") -> None:
    user_id, account = await _load(target.from_user)
    if account is None:
        text, markup = "Avval akkauntni ulang 👇", kb.login_methods()
    else:
        data = await api_client.get_birthday(user_id, account["id"])
        await state.set_state(BirthdayAsk.waiting_date)
        text, markup = _birthday_text(data, note), kb.birthday_menu(data)
    if isinstance(target, CallbackQuery):
        await safe_edit(target, text, markup)
    else:
        await target.answer(text, reply_markup=markup)


@router.callback_query(F.data == "bday")
async def show_birthday(callback: CallbackQuery, state: FSMContext) -> None:
    await _show_birthday(callback, state)
    await safe_answer(callback)


@router.message(BirthdayAsk.waiting_date)
async def date_received(message: Message, state: FSMContext) -> None:
    match = _DATE.match(message.text or "")
    if not match:
        await message.answer("🤔 Sanani shunday yozing: 08.10 yoki 08.10.2001", reply_markup=kb.cancel_to("pro"))
        return
    day, month = int(match.group(1)), int(match.group(2))
    year = int(match.group(3)) if match.group(3) else None
    user_id, account = await _load(message.from_user)
    try:
        await api_client.save_birthday(user_id, account["id"], day, month, year)
    except ApiError as exc:
        await message.answer(f"🤔 {exc.message}. Qaytadan yuboring.", reply_markup=kb.cancel_to("pro"))
        return
    await _show_birthday(message, state, "\n\n✅ Saqlandi.")


@router.callback_query(F.data == "bday_import")
async def import_birthday(callback: CallbackQuery, state: FSMContext) -> None:
    user_id, account = await _load(callback.from_user)
    try:
        await api_client.import_birthday(user_id, account["id"])
    except ApiError as exc:
        await safe_answer(callback, exc.message, show_alert=True)
        return
    await safe_answer(callback, "✅ Telegram'dan olindi")
    await _show_birthday(callback, state)


@router.callback_query(F.data.startswith("bday_use:"))
async def use_template(callback: CallbackQuery, state: FSMContext) -> None:
    user_id, account = await _load(callback.from_user)
    data = await api_client.get_birthday(user_id, account["id"])
    template = data["templates"][int(callback.data.split(":", 1)[1])]["template"]
    try:
        await api_client.enable_service(account["id"], "auto_bio", [{"field": "bio", "template": template}], UPDATE_INTERVAL_SECONDS)
    except ApiError as exc:
        await safe_answer(callback, exc.message, show_alert=True)
        return
    await state.clear()
    await safe_answer(callback, "🎂 Bio'ga qo'yildi — har kuni o'zi yangilanadi", show_alert=True)
    await asyncio.sleep(1)
    await _show_birthday(callback, state, "\n\n✅ Avto bio yoqildi.")


# --- 👁 Faollik holati ---


async def _show_presence(callback: CallbackQuery, note: str = "") -> None:
    user_id, account = await _load(callback.from_user)
    if account is None:
        await safe_edit(callback, "Avval akkauntni ulang 👇", kb.login_methods())
        return
    try:
        data = await api_client.get_presence(user_id, account["id"])
    except ApiError as exc:
        await safe_edit(callback, f"⚠️ {exc.message}", kb.back_home())
        return
    title, shows = PRESENCE[data["mode"]]
    text = (
        f"👁 Faollik holati: {title}\n"
        f"Boshqalar ko'radi: «{shows}»\n\n"
        "ℹ️ Vaqtingizni yashirsangiz, siz ham boshqalarning aniq vaqtini ko'rmaysiz (Telegram qoidasi)."
        + note
    )
    await safe_edit(callback, text, kb.presence_menu(data["mode"], data["online_unlocked"]))


@router.callback_query(F.data == "presence")
async def show_presence(callback: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    await _show_presence(callback)
    await safe_answer(callback)


@router.callback_query(F.data.startswith("presence:"))
async def set_presence(callback: CallbackQuery) -> None:
    mode = callback.data.split(":", 1)[1]
    user_id, account = await _load(callback.from_user)
    try:
        await api_client.save_presence(user_id, account["id"], mode)
    except ApiError as exc:
        await safe_answer(callback, exc.message, show_alert=True)
        return
    await safe_answer(callback, f"✅ {PRESENCE[mode][0]}")
    await _show_presence(callback)
