from aiogram.types import InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder


def main_menu() -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.button(text="➕ Akkaunt qo'shish", callback_data="menu:add_account")
    kb.button(text="📱 Mening akkauntlarim", callback_data="menu:accounts")
    kb.button(text="⚙️ Xizmatlarim", callback_data="menu:services")
    kb.button(text="💰 Balans", callback_data="menu:balance")
    kb.button(text="📦 Tariflar", callback_data="menu:plans")
    kb.button(text="🤝 Referral", callback_data="menu:referral")
    kb.button(text="🔧 Sozlamalar", callback_data="menu:settings")
    kb.adjust(1)
    return kb.as_markup()


def back_to_menu() -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.button(text="⬅️ Orqaga", callback_data="menu:root")
    return kb.as_markup()


def cancel_only() -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.button(text="❌ Bekor qilish", callback_data="menu:root")
    return kb.as_markup()


def add_account_methods() -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.button(text="📷 QR orqali", callback_data="add:qr")
    kb.button(text="📞 Telefon raqam orqali", callback_data="add:phone")
    kb.button(text="⬅️ Orqaga", callback_data="menu:root")
    kb.adjust(1)
    return kb.as_markup()


def qr_status_actions(login_id: str) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.button(text="🔄 Holatni tekshirish", callback_data=f"qr:check:{login_id}")
    kb.button(text="❌ Bekor qilish", callback_data="menu:root")
    kb.adjust(1)
    return kb.as_markup()


def accounts_list(accounts: list[dict]) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    for acc in accounts:
        label = acc["username"] or acc["first_name"] or str(acc["telegram_user_id"])
        kb.button(text=f"{label} ({acc['status']})", callback_data=f"acc:view:{acc['id']}")
    kb.button(text="⬅️ Orqaga", callback_data="menu:root")
    kb.adjust(1)
    return kb.as_markup()


def account_detail_actions(account_id: int, status: str) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    if status != "REVOKED":
        kb.button(text="🚫 Uzish (Revoke)", callback_data=f"acc:revoke:{account_id}")
    kb.button(text="⬅️ Orqaga", callback_data="menu:accounts")
    kb.adjust(1)
    return kb.as_markup()
