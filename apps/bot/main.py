import asyncio
import logging

import httpx
from aiogram import Bot, Dispatcher
from aiogram.exceptions import TelegramAPIError
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import BotCommand, ErrorEvent, MenuButtonWebApp, WebAppInfo

from api_client import api_client
from catalog import STUDIO_SHORT
from common import set_webapp_url, webapp_url
from core.settings import settings
from handlers import add_account, admin, ai, billing, home, pro, start

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger("bot")

dp = Dispatcher(storage=MemoryStorage())
dp.include_router(start.router)
dp.include_router(add_account.router)
dp.include_router(billing.router)
dp.include_router(admin.router)
dp.include_router(ai.router)  # pro'dan oldin: "pro:ai" / "pro:stories" aniq mos kelsin
dp.include_router(pro.router)
dp.include_router(home.router)  # oxirida: holatsiz xabarlar uchun fallback shu yerda


@dp.errors()
async def on_error(event: ErrorEvent) -> None:
    # Foydalanuvchiga texnik xato ko'rsatilmaydi (BUILD.md: Error UX) — to'liq xato faqat logda.
    logger.exception("update qayta ishlanmadi", exc_info=event.exception)
    update = event.update
    text = "⚠️ Nimadir xato ketdi. Qaytadan urinib ko'ring yoki /start bosing."
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
                await bot.set_chat_menu_button(menu_button=MenuButtonWebApp(text=STUDIO_SHORT, web_app=WebAppInfo(url=url)))
                set_webapp_url(url)
                logger.info("Mini App manzili: %s", url)
            except TelegramAPIError:
                logger.exception("menu button o'rnatilmadi")
        await asyncio.sleep(WEBAPP_CHECK_SECONDS)


# /start bosilishidan oldin ko'rinadigan matnlar (bot profili va bo'sh chat).
DESCRIPTION = (
    "Telegram profilingiz o'zi yangilanib turadi:\n"
    "🕐 ismda soat · 📝 avto bio · 🗓 jadval\n"
    "🟢 24/7 online · 🖼 rasm · 😀 emoji status\n\n"
    "«Start» ni bosing — 1 daqiqada ulanadi."
)
SHORT_DESCRIPTION = "Profilingiz o'zi yangilanadi: ismda soat, avto bio, jadval, 24/7 online, rasm va emoji."


async def setup_profile(bot: Bot) -> None:
    try:
        await bot.set_my_commands(
            [BotCommand(command="start", description="🏠 Bosh sahifa"), BotCommand(command="help", description="❓ Qanday ishlaydi")]
        )
        await bot.set_my_description(DESCRIPTION)
        await bot.set_my_short_description(SHORT_DESCRIPTION)
    except TelegramAPIError:
        # Juda tez-tez chaqirilsa Telegram cheklaydi — bot ishlashiga ta'sir qilmaydi.
        logger.warning("bot tavsifi/komandalari yangilanmadi", exc_info=True)


async def main() -> None:
    if not settings.bot_token:
        # Token yo'q bo'lsa ham konteyner qulamasin.
        logger.warning("BOT_TOKEN yo'q, bot kutish rejimida.")
        await asyncio.Event().wait()
        return
    bot = Bot(token=settings.bot_token)
    await setup_profile(bot)
    watcher = asyncio.create_task(webapp_url_watcher(bot))
    try:
        await dp.start_polling(bot)
    finally:
        watcher.cancel()
        await api_client.close()


if __name__ == "__main__":
    asyncio.run(main())
