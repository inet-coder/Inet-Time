import asyncio
import logging

from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import BotCommand, ErrorEvent

from api_client import api_client
from core.settings import settings
from handlers import add_account, admin, billing, home, pro, start

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger("bot")

dp = Dispatcher(storage=MemoryStorage())
dp.include_router(start.router)
dp.include_router(add_account.router)
dp.include_router(billing.router)
dp.include_router(admin.router)
dp.include_router(pro.router)
dp.include_router(home.router)  # oxirida: holatsiz xabarlar uchun fallback shu yerda


@dp.errors()
async def on_error(event: ErrorEvent) -> None:
    # Foydalanuvchiga texnik xato ko'rsatilmaydi (BUILD.md: Error UX) — to'liq xato faqat logda.
    logger.exception("update qayta ishlanmadi", exc_info=event.exception)
    update = event.update
    text = "⚠️ Vaqtinchalik xatolik. Qaytadan urinib ko'ring yoki /start bosing."
    try:
        if update.callback_query:
            await update.callback_query.answer(text, show_alert=True)
        elif update.message:
            await update.message.answer(text)
    except Exception:  # noqa: BLE001
        pass


async def main() -> None:
    if not settings.bot_token:
        # Token yo'q bo'lsa ham konteyner qulamasin.
        logger.warning("BOT_TOKEN yo'q, bot kutish rejimida.")
        await asyncio.Event().wait()
        return
    bot = Bot(token=settings.bot_token)
    await bot.set_my_commands([BotCommand(command="start", description="Bosh sahifa")])
    try:
        await dp.start_polling(bot)
    finally:
        await api_client.close()


if __name__ == "__main__":
    asyncio.run(main())
