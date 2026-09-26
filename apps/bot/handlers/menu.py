from aiogram import F, Router
from aiogram.types import CallbackQuery

from api_client import api_client
from common import db_user_id
from keyboards import account_detail_actions, accounts_list, add_account_methods, back_to_menu, main_menu

router = Router(name="menu")

_STUB_LABELS = {
    "menu:services": "Xizmatlar",
    "menu:balance": "Balans",
    "menu:plans": "Tariflar",
    "menu:referral": "Referral",
    "menu:settings": "Sozlamalar",
}


@router.callback_query(F.data == "menu:root")
async def show_root(callback: CallbackQuery) -> None:
    await callback.message.edit_text("Bosh menyu:", reply_markup=main_menu())
    await callback.answer()


@router.callback_query(F.data == "menu:add_account")
async def show_add_account(callback: CallbackQuery) -> None:
    await callback.message.edit_text("Akkaunt qo'shish usulini tanlang:", reply_markup=add_account_methods())
    await callback.answer()


@router.callback_query(F.data == "menu:accounts")
async def show_accounts(callback: CallbackQuery) -> None:
    user_id = await db_user_id(callback.from_user)
    accounts = await api_client.list_accounts(user_id)
    if not accounts:
        await callback.message.edit_text("Hali ulangan akkauntlar yo'q.", reply_markup=back_to_menu())
    else:
        await callback.message.edit_text("Mening akkauntlarim:", reply_markup=accounts_list(accounts))
    await callback.answer()


@router.callback_query(F.data.startswith("acc:view:"))
async def view_account(callback: CallbackQuery) -> None:
    account_id = int(callback.data.split(":")[2])
    user_id = await db_user_id(callback.from_user)
    accounts = await api_client.list_accounts(user_id)
    account = next((a for a in accounts if a["id"] == account_id), None)
    if account is None:
        await callback.answer("Akkaunt topilmadi", show_alert=True)
        return
    premium_label = "ha" if account["is_premium"] else "yo'q"
    text = (
        f"👤 {account['first_name'] or ''} (@{account['username'] or '-'})\n"
        f"Holat: {account['status']}\n"
        f"Premium: {premium_label}"
    )
    await callback.message.edit_text(text, reply_markup=account_detail_actions(account_id, account["status"]))
    await callback.answer()


@router.callback_query(F.data.startswith("acc:revoke:"))
async def revoke_account(callback: CallbackQuery) -> None:
    account_id = int(callback.data.split(":")[2])
    try:
        await api_client.revoke_account(account_id)
    except Exception:  # noqa: BLE001 — foydalanuvchiga texnik xatoni ko'rsatmaymiz
        await callback.answer("Telegram bilan vaqtinchalik aloqa muammosi. Keyinroq urinib ko'ring.", show_alert=True)
        return
    await callback.answer("Akkaunt uzildi ✅", show_alert=True)
    await show_accounts(callback)


@router.callback_query(F.data.in_(_STUB_LABELS.keys()))
async def stub_section(callback: CallbackQuery) -> None:
    await callback.message.edit_text(
        f"{_STUB_LABELS[callback.data]} bo'limi hali ishlab chiqilmoqda.", reply_markup=back_to_menu()
    )
    await callback.answer()
