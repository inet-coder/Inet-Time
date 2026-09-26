import asyncio
import logging

import httpx
from aiogram import Bot, Dispatcher
from aiogram.exceptions import TelegramAPIError
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import BotCommand, ErrorEvent, MenuButtonWebApp, WebAppInfo

from api_client import api_client
from common import set_webapp_url, webapp_url
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


WEBAPP_CHECK_SECONDS = 60


async def _discover_webapp_url() -> str | None:
    if settings.webapp_url:
        return settings.webapp_url
    try:
        async with httpx.AsyncClient(timeout=5) as client:
            hostname = (await client.get(settings.tunnel_metrics_url)).json().get("hostname")
    except (httpx.HTTPError, ValueError):
        return None
    return f"https://{hostname}" if hostname else None


async def webapp_url_watcher(bot: Bot) -> None:
    """Quick tunnel har restartda yangi manzil beradi — menyu tugmasini doim joriy manzilga moslaymiz."""
    while True:
        url = await _discover_webapp_url()
        if url and url != webapp_url():
            try:
                await bot.set_chat_menu_button(menu_button=MenuButtonWebApp(text="📱 Ilova", web_app=WebAppInfo(url=url)))
                set_webapp_url(url)
                logger.info("Mini App manzili: %s", url)
            except TelegramAPIError:
                logger.exception("menu button o'rnatilmadi")
        await asyncio.sleep(WEBAPP_CHECK_SECONDS)


async def main() -> None:
    if not settings.bot_token:
        # Token yo'q bo'lsa ham konteyner qulamasin.
        logger.warning("BOT_TOKEN yo'q, bot kutish rejimida.")
        await asyncio.Event().wait()
        return
    bot = Bot(token=settings.bot_token)
    await bot.set_my_commands([BotCommand(command="start", description="Bosh sahifa")])
    watcher = asyncio.create_task(webapp_url_watcher(bot))
    try:
        await dp.start_polling(bot)
    finally:
        watcher.cancel()
        await api_client.close()


if __name__ == "__main__":
    asyncio.run(main())
