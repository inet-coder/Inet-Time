import asyncio

from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage

from api_client import api_client
from core.settings import settings
from handlers import add_account, menu, start

dp = Dispatcher(storage=MemoryStorage())
dp.include_router(start.router)
dp.include_router(add_account.router)
dp.include_router(menu.router)


async def main() -> None:
    if not settings.bot_token:
        # Skeleton bosqichida token yo'q bo'lsa ham konteyner qulamasin.
        print("BOT_TOKEN yo'q, bot kutish rejimida.")
        await asyncio.Event().wait()
        return
    bot = Bot(token=settings.bot_token)
    try:
        await dp.start_polling(bot)
    finally:
        await api_client.close()


if __name__ == "__main__":
    asyncio.run(main())
