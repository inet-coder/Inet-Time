"""Bot egasining boshqaruv paneli — foydalanuvchi yaratgan botning O'ZIDA (/admin).

Asosiy bot faqat botni yaratadi va ishlatib turadi; sozlash shu yerda:
    🧩 Menyu va tugmalar — muharrir (Mini App) shu botning o'zida ochiladi
    📨 Xabar tarqatish   — egasi istalgan xabar (matn, rasm, video, fayl, ovoz) yuboradi → hammaga nusxalanadi
    💬 Murojaatlar       — menyuda yo'q har qanday xabar egasiga keladi (yoqish/o'chirish)
    📊 Statistika        — obunachilar, faollar, bloklaganlar
"""

import datetime
from typing import TYPE_CHECKING

from sqlalchemy import func, select, update

from core.botbuilder import page_by_id
from core.db.base import async_session
from core.db.models import BotBroadcast, BotSubscriber, UserBot
from core.webapp_url import discover_webapp_url

if TYPE_CHECKING:
    from main import RunningBot, Runner

STATE_KEY = "ub:{bot}:ast:{chat}"  # egasining panel holati ("bc" — tarqatiladigan xabar kutilmoqda)
OWNER_HINT_KEY = "ub:{bot}:ownerhint"

OWNER_COMMANDS = [
    {"command": "start", "description": "Bosh menyu"},
    {"command": "admin", "description": "Boshqaruv paneli"},
]

HELP = (
    "❓ Botni boshqarish\n\n"
    "🧩 Menyu va tugmalar — sahifalar, matnlar, rasmlar va tugmalarni tahrirlash. "
    "O'zgarishlar «Saqlash» bosilishi bilan kuchga kiradi.\n\n"
    "📨 Xabar tarqatish — botga istalgan xabar yuborasiz (matn, rasm, video, fayl, ovozli xabar), "
    "u barcha obunachilarga nusxalanadi.\n\n"
    "💬 Murojaatlar — foydalanuvchilar yozgan xabarlar sizga keladi. Javob berish uchun xabarga "
    "«Reply» qiling — javob o'sha odamga boradi.\n\n"
    "Botni to'xtatish, o'chirish yoki tokenni yangilash — Inet-Time asosiy botida: 🤖 Botlarim."
)


def _state_key(bot: "RunningBot", chat_id: int) -> str:
    return STATE_KEY.format(bot=bot.bot_id, chat=chat_id)


async def _stats(bot_id: int) -> dict:
    now = datetime.datetime.now(datetime.timezone.utc)
    async with async_session() as db:
        base = select(func.count(BotSubscriber.id)).where(BotSubscriber.bot_id == bot_id)
        return {
            "total": await db.scalar(base.where(BotSubscriber.blocked == False)),  # noqa: E712
            "active": await db.scalar(base.where(BotSubscriber.last_active_at >= now - datetime.timedelta(days=1))),
            "today": await db.scalar(base.where(BotSubscriber.started_at >= now - datetime.timedelta(days=1))),
            "blocked": await db.scalar(base.where(BotSubscriber.blocked == True)),  # noqa: E712
        }


async def panel(runner: "Runner", bot: "RunningBot", chat_id: int, message: dict | None = None) -> None:
    stats = await _stats(bot.bot_id)
    forward = bool(bot.menu.get("forward_all"))
    forward_text = "yoqilgan" if forward else "o'chiq"
    text = (
        f"⚙️ Boshqaruv paneli · @{bot.username}\n\n"
        f"👥 Obunachilar: {stats['total']}\n"
        f"🟢 24 soatda faol: {stats['active']}\n"
        f"🆕 Bugun qo'shildi: {stats['today']}\n"
        f"🚫 Bloklaganlar: {stats['blocked']}\n\n"
        f"💬 Murojaatlar rejimi: {forward_text}"
    )
    rows = []
    url = await discover_webapp_url()
    if url:
        rows.append([{"text": "🧩 Menyu va tugmalar", "web_app": {"url": f"{url.split('?')[0]}?bot={bot.bot_id}"}}])
    rows += [
        [{"text": "📨 Xabar tarqatish", "callback_data": "adm:bc"}],
        [{"text": f"💬 Murojaatlar: {'✅' if forward else '❌'} {forward_text}", "callback_data": "adm:fwd"}],
        [{"text": "👁 Foydalanuvchi ko'rinishi", "callback_data": "adm:view"}, {"text": "🔄 Yangilash", "callback_data": "adm:st"}],
        [{"text": "❓ Yordam", "callback_data": "adm:help"}],
    ]
    markup = {"inline_keyboard": rows}
    if message is not None:
        try:
            await runner.api(bot, "editMessageText", {"chat_id": chat_id, "message_id": message["message_id"], "text": text, "reply_markup": markup})
            return
        except Exception:  # noqa: BLE001 — eski xabar (rasm/boshqa) — yangisini yuboramiz
            pass
    await runner.api(bot, "sendMessage", {"chat_id": chat_id, "text": text, "reply_markup": markup})


async def set_owner_commands(runner: "Runner", bot: "RunningBot") -> None:
    if not bot.owner_chat_id:
        return
    try:
        await runner.api(bot, "setMyCommands", {"commands": OWNER_COMMANDS, "scope": {"type": "chat", "chat_id": bot.owner_chat_id}})
    except Exception:  # noqa: BLE001 — egasi botga hali kirmagan bo'lishi mumkin
        pass


async def owner_started(runner: "Runner", bot: "RunningBot", chat_id: int) -> None:
    """Egasi /start bosdi: buyruqlar menyusi va (haftada bir) panel haqida eslatma."""
    await set_owner_commands(runner, bot)
    if await runner.redis.set(OWNER_HINT_KEY.format(bot=bot.bot_id), "1", nx=True, ex=7 * 24 * 3600):
        await runner.api(
            bot,
            "sendMessage",
            {
                "chat_id": chat_id,
                "text": "ℹ️ Siz ushbu botning egasisiz. Botni sozlash va boshqarish: /admin",
                "reply_markup": {"inline_keyboard": [[{"text": "⚙️ Boshqaruv paneli", "callback_data": "adm:st"}]]},
            },
        )


async def on_callback(runner: "Runner", bot: "RunningBot", chat_id: int, data: str, message: dict, user: dict) -> None:
    action = data.removeprefix("adm:")
    if action == "st":
        await panel(runner, bot, chat_id, message)
    elif action == "help":
        await runner.api(
            bot,
            "editMessageText",
            {
                "chat_id": chat_id,
                "message_id": message["message_id"],
                "text": HELP,
                "reply_markup": {"inline_keyboard": [[{"text": "⬅️ Panel", "callback_data": "adm:st"}]]},
            },
        )
    elif action == "view":
        start = page_by_id(bot.menu, bot.menu.get("start"))
        if start is not None:
            await runner.redis.set(f"ub:{bot.bot_id}:cur:{chat_id}", start["id"])
            await runner.send_page(bot, chat_id, start, user, with_branding=True)
    elif action == "fwd":
        bot.menu["forward_all"] = not bot.menu.get("forward_all")
        async with async_session() as db:
            row = await db.get(UserBot, bot.bot_id)
            if row is not None:
                row.menu = {**row.menu, "forward_all": bot.menu["forward_all"]}
                await db.commit()
        await panel(runner, bot, chat_id, message)
    elif action == "bc":
        await runner.redis.set(_state_key(bot, chat_id), "bc", ex=1800)
        await runner.api(
            bot,
            "sendMessage",
            {
                "chat_id": chat_id,
                "text": "📨 Tarqatiladigan xabarni yuboring.\n\nMatn, rasm, video, fayl yoki ovozli xabar bo'lishi mumkin — "
                "u barcha obunachilarga aynan shu ko'rinishda boradi.\n\nBekor qilish: /cancel",
            },
        )
    elif action.startswith("bcok:"):
        await _start_broadcast(runner, bot, chat_id, int(action.split(":", 1)[1]), message)
    elif action == "bcno":
        await runner.api(bot, "editMessageText", {"chat_id": chat_id, "message_id": message["message_id"], "text": "❌ Bekor qilindi."})


async def on_message(runner: "Runner", bot: "RunningBot", message: dict) -> bool:
    """Egasining xabari panelga tegishli bo'lsa — qayta ishlab True qaytaradi."""
    chat_id = message["chat"]["id"]
    text = (message.get("text") or "").strip()
    if text in ("/admin", "/start admin"):
        await runner.redis.delete(_state_key(bot, chat_id))
        await set_owner_commands(runner, bot)
        await panel(runner, bot, chat_id)
        return True
    state = await runner.redis.get(_state_key(bot, chat_id))
    if state != b"bc":
        return False
    await runner.redis.delete(_state_key(bot, chat_id))
    if text == "/cancel":
        await runner.api(bot, "sendMessage", {"chat_id": chat_id, "text": "❌ Bekor qilindi."})
        return True
    stats = await _stats(bot.bot_id)
    await runner.api(
        bot,
        "sendMessage",
        {
            "chat_id": chat_id,
            "text": f"☝️ Shu xabar {stats['total']} ta obunachiga yuborilsinmi?",
            "reply_to_message_id": message["message_id"],
            "reply_markup": {
                "inline_keyboard": [
                    [{"text": "✅ Yuborish", "callback_data": f"adm:bcok:{message['message_id']}"}, {"text": "❌ Bekor", "callback_data": "adm:bcno"}]
                ]
            },
        },
    )
    return True


async def _start_broadcast(runner: "Runner", bot: "RunningBot", chat_id: int, message_id: int, confirm: dict) -> None:
    async with async_session() as db:
        running = await db.scalar(select(BotBroadcast.id).where(BotBroadcast.bot_id == bot.bot_id, BotBroadcast.status == "sending"))
        if running:
            await runner.api(bot, "sendMessage", {"chat_id": chat_id, "text": "⏳ Oldingi xabar hali tarqatilmoqda — tugashini kuting."})
            return
        item = BotBroadcast(bot_id=bot.bot_id, text="", from_chat_id=chat_id, message_id=message_id)
        db.add(item)
        await db.commit()
        broadcast_id = item.id
    try:
        pool = await runner.arq()
        await pool.enqueue_job("user_bot_broadcast_job", broadcast_id=broadcast_id, _job_id=f"userbot_broadcast:{broadcast_id}")
    except Exception:  # noqa: BLE001
        async with async_session() as db:
            await db.execute(update(BotBroadcast).where(BotBroadcast.id == broadcast_id).values(status="done"))
            await db.commit()
        await runner.api(bot, "sendMessage", {"chat_id": chat_id, "text": "⚠️ Tarqatishni boshlab bo'lmadi, birozdan keyin qayta urinib ko'ring."})
        return
    await runner.api(
        bot,
        "editMessageText",
        {"chat_id": chat_id, "message_id": confirm["message_id"], "text": "🚀 Tarqatish boshlandi. Tugagach, natijani shu yerga yuboraman."},
    )
