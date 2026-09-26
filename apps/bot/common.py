from aiogram.exceptions import TelegramBadRequest
from aiogram.types import CallbackQuery, InlineKeyboardMarkup
from aiogram.types import User as TgUser

from api_client import api_client
from core.settings import settings

# Bir nechta akkaunti bor foydalanuvchi qaysi birini boshqarayotgani (telegram_id -> account_id).
# Faqat xotirada: restartdan keyin birinchi akkaunt tanlanadi — bu yetarli.
_selected_account: dict[int, int] = {}

# Mini App manzili — main.py'dagi watcher yangilab turadi (quick tunnel har restartda yangi URL beradi).
_webapp = {"url": None}


def webapp_url() -> str | None:
    return _webapp["url"]


def set_webapp_url(url: str | None) -> None:
    _webapp["url"] = url


def is_admin(telegram_user_id: int) -> bool:
    return telegram_user_id in settings.admin_telegram_id_set


def money(amount: float) -> str:
    return f"{amount:,.0f}".replace(",", " ") + " so'm"


async def db_user_id(tg_user: TgUser) -> int:
    user = await api_client.get_or_create_user(tg_user)
    return user["id"]


def select_account(telegram_user_id: int, account_id: int) -> None:
    _selected_account[telegram_user_id] = account_id


def current_account(overview: dict, telegram_user_id: int) -> dict | None:
    accounts = overview["accounts"]
    if not accounts:
        return None
    selected = _selected_account.get(telegram_user_id)
    return next((a for a in accounts if a["id"] == selected), accounts[0])


async def safe_edit(callback: CallbackQuery, text: str, reply_markup: InlineKeyboardMarkup | None = None) -> None:
    """edit_text rasm xabarida yoki matn o'zgarmaganda xato beradi — unda yangi xabar yuboriladi."""
    try:
        await callback.message.edit_text(text, reply_markup=reply_markup)
    except TelegramBadRequest as exc:
        if "message is not modified" in str(exc):
            return
        try:
            await callback.message.delete()
        except TelegramBadRequest:
            pass
        await callback.message.answer(text, reply_markup=reply_markup)


async def safe_answer(callback: CallbackQuery, text: str | None = None, show_alert: bool = False) -> None:
    try:
        await callback.answer(text, show_alert=show_alert)
    except TelegramBadRequest:
        pass
