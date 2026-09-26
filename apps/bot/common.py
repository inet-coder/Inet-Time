from aiogram.types import User as TgUser

from api_client import api_client


async def db_user_id(tg_user: TgUser) -> int:
    """Har chaqiriqda idempotent: mavjud bo'lsa API darhol qaytaradi, referral /start'da yozilgan."""
    user = await api_client.get_or_create_user(
        telegram_user_id=tg_user.id,
        username=tg_user.username,
        first_name=tg_user.first_name,
        last_name=tg_user.last_name,
        language_code=tg_user.language_code,
        referral_code=None,
    )
    return user["id"]
