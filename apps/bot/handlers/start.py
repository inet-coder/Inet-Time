from aiogram import Router
from aiogram.filters import Command, CommandObject, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.types import Message

from api_client import api_client
from handlers.home import send_home

router = Router(name="start")


@router.message(CommandStart())
async def cmd_start(message: Message, command: CommandObject, state: FSMContext) -> None:
    await state.clear()
    referral_code = None
    if command.args and command.args.startswith("ref_"):
        referral_code = command.args.removeprefix("ref_")
    user = await api_client.get_or_create_user(message.from_user, referral_code=referral_code)
    await send_home(message.bot, message.chat.id, message.from_user.id, user["id"])


@router.message(Command("menu"))
async def cmd_menu(message: Message, state: FSMContext) -> None:
    await state.clear()
    user = await api_client.get_or_create_user(message.from_user)
    await send_home(message.bot, message.chat.id, message.from_user.id, user["id"])
