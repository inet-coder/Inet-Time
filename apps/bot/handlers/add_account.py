import asyncio
import io
import logging
import re

import qrcode
from aiogram import Bot, F, Router
from aiogram.exceptions import TelegramBadRequest
from aiogram.fsm.context import FSMContext
from aiogram.types import BufferedInputFile, CallbackQuery, Message

import keyboards as kb
from api_client import ApiError, api_client
from common import db_user_id, safe_answer, safe_edit
from handlers.home import send_home
from states import PhoneLogin, QrLogin

router = Router(name="add_account")
logger = logging.getLogger(__name__)

QR_POLL_INTERVAL_SECONDS = 3
QR_POLL_TIMEOUT_SECONDS = 90
CONNECT_FAILED = "Ulab bo'lmadi."
WRONG_CODE = "Kod noto'g'ri."


def _render_qr_png(url: str) -> bytes:
    buf = io.BytesIO()
    qrcode.make(url).save(buf, format="PNG")
    return buf.getvalue()


async def _delete(message: Message) -> None:
    try:
        await message.delete()
    except TelegramBadRequest:
        pass


async def _limit_reached(callback: CallbackQuery, exc: ApiError) -> None:
    await safe_edit(callback, f"🔒 {exc.message}\n\nKo'proq akkaunt uchun tarifni oshiring.", kb.upsell())


async def _on_connected(bot: Bot, chat_id: int, tg_user_id: int, user_id: int, result: dict) -> None:
    label = f"@{result['username']}" if result.get("username") else "akkauntingiz"
    await bot.send_message(chat_id, f"✅ {label} ulandi! Endi xizmatlarni yoqishingiz mumkin.")
    await send_home(bot, chat_id, tg_user_id, user_id)


# --- QR ---


@router.callback_query(F.data == "login_qr")
async def start_qr_login(callback: CallbackQuery, state: FSMContext) -> None:
    user_id = await db_user_id(callback.from_user)
    try:
        login = await api_client.qr_login_start(user_id)
    except ApiError as exc:
        if exc.status_code == 402:
            await _limit_reached(callback, exc)
            await safe_answer(callback)
            return
        raise

    await _delete(callback.message)
    qr_message = await callback.message.answer_photo(
        BufferedInputFile(_render_qr_png(login["qr_url"]), filename="qr.png"),
        caption=(
            "📷 Ulanmoqchi bo'lgan akkaunt telefonida oching:\n"
            "Telegram → Sozlamalar → Qurilmalar → «Kompyuterni ulash» va shu QR kodni skanerlang.\n\n"
            "⏳ Skanerlashingizni kutyapman (90 soniya)..."
        ),
        reply_markup=kb.qr_waiting(),
    )
    await safe_answer(callback)
    asyncio.create_task(
        _poll_qr(callback.bot, qr_message, login["login_id"], callback.from_user.id, user_id, state)
    )


async def _poll_qr(bot: Bot, qr_message: Message, login_id: str, tg_user_id: int, user_id: int, state: FSMContext) -> None:
    """Foydalanuvchi "tekshirish" tugmasini bosishi shart emas — natijani bot o'zi kuzatadi."""
    chat_id = qr_message.chat.id
    try:
        for _ in range(QR_POLL_TIMEOUT_SECONDS // QR_POLL_INTERVAL_SECONDS):
            await asyncio.sleep(QR_POLL_INTERVAL_SECONDS)
            result = await api_client.qr_login_status(login_id)
            status = result["status"]
            if status == "WAITING_SCAN":
                continue

            await _delete(qr_message)
            if status == "SUCCESS":
                await _on_connected(bot, chat_id, tg_user_id, user_id, result)
            elif status == "LIMIT_REACHED":
                await bot.send_message(chat_id, f"🔒 {result['error']}", reply_markup=kb.upsell())
            elif status == "NEED_PASSWORD":
                await state.set_state(QrLogin.waiting_password)
                await state.update_data(login_id=login_id)
                await bot.send_message(
                    chat_id, "🔐 Akkauntda ikki bosqichli himoya (2FA) yoqilgan. Parolingizni yuboring:",
                    reply_markup=kb.cancel(),
                )
            elif status == "EXPIRED":
                await bot.send_message(chat_id, "⌛ QR kod muddati tugadi.", reply_markup=kb.qr_expired())
            else:
                await bot.send_message(chat_id, f"⚠️ {result.get('error') or CONNECT_FAILED}", reply_markup=kb.qr_expired())
            return

        await _delete(qr_message)
        await bot.send_message(chat_id, "⌛ QR kod muddati tugadi.", reply_markup=kb.qr_expired())
    except Exception:  # noqa: BLE001 — fon vazifasi: xato yutilmasin, lekin bot qulamasin
        logger.exception("QR polling failed")
        await bot.send_message(chat_id, "⚠️ Ulashda xatolik yuz berdi. Qaytadan urinib ko'ring.", reply_markup=kb.qr_expired())


@router.message(QrLogin.waiting_password)
async def qr_password(message: Message, state: FSMContext) -> None:
    await _submit_password(message, state)


# --- Telefon ---


@router.callback_query(F.data == "login_phone")
async def start_phone_login(callback: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(PhoneLogin.waiting_phone)
    await safe_edit(
        callback,
        "📞 Ulanmoqchi bo'lgan akkauntning telefon raqamini yuboring.\nMasalan: +998901234567",
        kb.cancel(),
    )
    await safe_answer(callback)


@router.message(PhoneLogin.waiting_phone)
async def phone_received(message: Message, state: FSMContext) -> None:
    phone = "+" + re.sub(r"\D", "", message.text or "")
    if len(phone) < 10:
        await message.answer("Raqam noto'g'ri. Masalan: +998901234567", reply_markup=kb.cancel())
        return

    user_id = await db_user_id(message.from_user)
    try:
        login = await api_client.phone_login_start(user_id, phone)
    except ApiError as exc:
        if exc.status_code == 402:
            await state.clear()
            await message.answer(f"🔒 {exc.message}\n\nKo'proq akkaunt uchun tarifni oshiring.", reply_markup=kb.upsell())
        else:
            await message.answer(exc.message, reply_markup=kb.cancel())
        return

    await state.update_data(login_id=login["login_id"])
    await state.set_state(PhoneLogin.waiting_code)
    await message.answer(
        "✉️ Telegram'ga kod yuborildi (Telegram ilovasidagi «Telegram» chatiga).\n\n"
        "❗️ Kodni raqamlar orasiga tire qo'yib yuboring, masalan: 1-2-3-4-5\n"
        "Aks holda Telegram kodni boshqa chatga yuborilgan deb hisoblab, bekor qiladi.",
        reply_markup=kb.cancel(),
    )


@router.message(PhoneLogin.waiting_code)
async def code_received(message: Message, state: FSMContext) -> None:
    code = re.sub(r"\D", "", message.text or "")
    await _delete(message)
    if len(code) < 5:
        await message.answer("Kod 5 xonali bo'lishi kerak. Masalan: 1-2-3-4-5", reply_markup=kb.cancel())
        return

    result = await api_client.phone_login_code((await state.get_data())["login_id"], code)
    status = result["status"]
    if status == "NEED_PASSWORD":
        await state.set_state(PhoneLogin.waiting_password)
        await message.answer("🔐 Ikki bosqichli himoya (2FA) parolingizni yuboring:", reply_markup=kb.cancel())
    elif status == "SUCCESS":
        await state.clear()
        await _on_connected(message.bot, message.chat.id, message.from_user.id, await db_user_id(message.from_user), result)
    elif status == "LIMIT_REACHED":
        await state.clear()
        await message.answer(f"🔒 {result['error']}", reply_markup=kb.upsell())
    else:
        await message.answer(f"⚠️ {WRONG_CODE} Qaytadan yuboring (masalan: 1-2-3-4-5):", reply_markup=kb.cancel())


@router.message(PhoneLogin.waiting_password)
async def phone_password(message: Message, state: FSMContext) -> None:
    await _submit_password(message, state)


async def _submit_password(message: Message, state: FSMContext) -> None:
    password = message.text or ""
    await _delete(message)  # parol chatda qolmasin
    result = await api_client.submit_password((await state.get_data())["login_id"], password)
    if result["status"] == "SUCCESS":
        await state.clear()
        await _on_connected(message.bot, message.chat.id, message.from_user.id, await db_user_id(message.from_user), result)
    elif result["status"] == "LIMIT_REACHED":
        await state.clear()
        await message.answer(f"🔒 {result['error']}", reply_markup=kb.upsell())
    else:
        await message.answer("❌ Parol noto'g'ri. Qaytadan yuboring:", reply_markup=kb.cancel())
