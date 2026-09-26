from aiogram import Router
from aiogram.filters import CommandObject, CommandStart
from aiogram.types import Message

from api_client import api_client
from keyboards import main_menu

router = Router(name="start")


@router.message(CommandStart())
async def cmd_start(message: Message, command: CommandObject) -> None:
    referral_code = None
    if command.args and command.args.startswith("ref_"):
        referral_code = command.args.removeprefix("ref_")

    await api_client.get_or_create_user(
        telegram_user_id=message.from_user.id,
        username=message.from_user.username,
        first_name=message.from_user.first_name,
        last_name=message.from_user.last_name,
        language_code=message.from_user.language_code,
        referral_code=referral_code,
    )
    await message.answer(
        f"Salom, {message.from_user.first_name or ''}! 👋\n\nUserbots platformasiga xush kelibsiz.",
        reply_markup=main_menu(),
    )
