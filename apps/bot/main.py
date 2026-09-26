import asyncio

from aiogram import Bot, Dispatcher

from core.settings import settings

dp = Dispatcher()


async def main() -> None:
    if not settings.bot_token:
        # Skeleton bosqichida token yo'q bo'lsa ham konteyner qulamasin.
        print("BOT_TOKEN yo'q, bot kutish rejimida.")
        await asyncio.Event().wait()
        return
    bot = Bot(token=settings.bot_token)
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
