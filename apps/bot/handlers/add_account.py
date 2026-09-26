import io

import qrcode
from aiogram import F, Router
from aiogram.exceptions import TelegramBadRequest
from aiogram.fsm.context import FSMContext
from aiogram.types import BufferedInputFile, CallbackQuery, Message

from api_client import api_client
from common import db_user_id
from keyboards import add_account_methods, cancel_only, main_menu, qr_status_actions
from states import PhoneLogin, QrLogin

router = Router(name="add_account")


def _render_qr_png(url: str) -> bytes:
    img = qrcode.make(url)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


async def _safe_delete(message: Message) -> None:
    try:
        await message.delete()
    except TelegramBadRequest:
        pass


def _success_text(result: dict) -> str:
    label = result.get("username") or result.get("telegram_user_id")
    return f"✅ Akkaunt ulandi: @{label}"


@router.callback_query(F.data == "add:qr")
async def start_qr_login(callback: CallbackQuery, state: FSMContext) -> None:
    user_id = await db_user_id(callback.from_user)
    login = await api_client.qr_login_start(user_id)
    await state.update_data(login_id=login["login_id"])

    qr_bytes = _render_qr_png(login["qr_url"])
    photo = BufferedInputFile(qr_bytes, filename="qr.png")
    await callback.message.delete()
    await callback.message.answer_photo(
        photo,
        caption=(
            "Telegram ilovasida: Sozlamalar → Qurilmalar → Qurilma ulash orqali "
            "shu QR kodni skanerlang."
        ),
        reply_markup=qr_status_actions(login["login_id"]),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("qr:check:"))
async def check_qr_status(callback: CallbackQuery, state: FSMContext) -> None:
    login_id = callback.data.split(":", 2)[2]
    result = await api_client.qr_login_status(login_id)
    status = result["status"]

    if status == "WAITING_SCAN":
        await callback.answer("Hali skanerlanmagan, kuting...")
        return

    if status == "NEED_PASSWORD":
        await state.set_state(QrLogin.waiting_password)
        await state.update_data(login_id=login_id)
        await callback.message.answer("Ikki bosqichli tasdiqlash (2FA) yoqilgan. Parolni yuboring:", reply_markup=cancel_only())
        await callback.answer()
        return

    if status == "SUCCESS":
        await state.clear()
        await callback.message.answer(_success_text(result), reply_markup=main_menu())
        await callback.answer()
        return

    if status == "EXPIRED":
        await callback.message.answer("QR kod muddati tugadi. Qaytadan urinib ko'ring.", reply_markup=add_account_methods())
        await callback.answer()
        return

    await callback.message.answer(
        "Telegram bilan vaqtinchalik aloqa muammosi. Qaytadan urinib ko'ring.",
        reply_markup=add_account_methods(),
    )
    await callback.answer()


@router.message(QrLogin.waiting_password)
async def qr_password_entered(message: Message, state: FSMContext) -> None:
    data = await state.get_data()
    result = await api_client.submit_password(data["login_id"], message.text or "")
    await _safe_delete(message)

    if result["status"] == "SUCCESS":
        await state.clear()
        await message.answer(_success_text(result), reply_markup=main_menu())
    else:
        await message.answer("Parol noto'g'ri. Qaytadan yuboring:", reply_markup=cancel_only())


@router.callback_query(F.data == "add:phone")
async def start_phone_login(callback: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(PhoneLogin.waiting_phone)
    await callback.message.edit_text(
        "Telefon raqamingizni xalqaro formatda yuboring (masalan +998901234567):",
        reply_markup=cancel_only(),
    )
    await callback.answer()


@router.message(PhoneLogin.waiting_phone)
async def phone_entered(message: Message, state: FSMContext) -> None:
    user_id = await db_user_id(message.from_user)
    phone = (message.text or "").strip()
    login = await api_client.phone_login_start(user_id, phone)
    await state.update_data(login_id=login["login_id"])
    await state.set_state(PhoneLogin.waiting_code)
    await message.answer("Tasdiqlash kodi yuborildi. Kodni kiriting:", reply_markup=cancel_only())


@router.message(PhoneLogin.waiting_code)
async def code_entered(message: Message, state: FSMContext) -> None:
    data = await state.get_data()
    code = (message.text or "").strip()
    result = await api_client.phone_login_code(data["login_id"], code)
    await _safe_delete(message)

    if result["status"] == "NEED_PASSWORD":
        await state.set_state(PhoneLogin.waiting_password)
        await message.answer("2FA parolini kiriting:", reply_markup=cancel_only())
        return
    if result["status"] == "SUCCESS":
        await state.clear()
        await message.answer(_success_text(result), reply_markup=main_menu())
        return

    await message.answer("Kod noto'g'ri. Qaytadan kiriting:", reply_markup=cancel_only())


@router.message(PhoneLogin.waiting_password)
async def phone_password_entered(message: Message, state: FSMContext) -> None:
    data = await state.get_data()
    result = await api_client.submit_password(data["login_id"], message.text or "")
    await _safe_delete(message)

    if result["status"] == "SUCCESS":
        await state.clear()
        await message.answer(_success_text(result), reply_markup=main_menu())
    else:
        await message.answer("Parol noto'g'ri. Qaytadan yuboring:", reply_markup=cancel_only())
