"""🤖 InetTime AI — botning o'zida AI bilan suhbatlashib bot tuzish.

Egasi «🤖 InetTime AI» ni bosadi va oddiy so'z bilan yozadi: «Go'zallik saloni uchun bot: xizmatlar, narxlar,
onlayn yozilish formasi, ustalar, manzil. Inline tugmalar bilan». AI to'liq botni loyihalaydi → egasi tuzilmani
ko'radi → «✅ Qo'llash» → bot darhol yangilanadi («↩️ Oldingi holat» bilan qaytarish mumkin). Keyin suhbatni
davom ettiradi: «narxlar bo'limiga chegirma qo'sh», «hammasini klaviatura tugmalariga o'tkaz»...

AI chaqiruvi fon vazifasida — bot boshqa foydalanuvchilarga javob berishda davom etadi.
Holat (redis): aihist — suhbat tarixi, aiprop — taklif qilingan hujjat, aiundo — oldingi holat, aibusy — ishlayapti."""

import asyncio
import copy
import html
import json
import logging
from typing import TYPE_CHECKING

from core import ai, bot_ai
from core.db.base import async_session
from core.entitlements import get_entitlement

import editor

if TYPE_CHECKING:
    from main import RunningBot, Runner

logger = logging.getLogger("botrunner.ai")

TTL = 24 * 3600
EXAMPLES = (
    "• <i>Restoran uchun bot: menyu kategoriyalar bilan, narxlar, yetkazib berish, buyurtma formasi, manzil. Aralash uslubda.</i>\n"
    "• <i>Ingliz tili o'quv markazi: kurslar, o'qituvchilar, test (5 savol, ball bilan), ro'yxatdan o'tish. Faqat inline tugmalar.</i>\n"
    "• <i>Kanal uchun konkurs boti: majburiy obuna, referal havola, har taklif uchun 1 ball, reyting sahifasi.</i>\n"
    "• <i>Hozirgi botga «Aloqa» bo'limini qo'sh va barcha menyularni klaviatura tugmalariga o'tkaz.</i>"
)


def _k(bot: "RunningBot", kind: str, chat_id: int) -> str:
    return f"ub:{bot.bot_id}:{kind}:{chat_id}"


def esc(text) -> str:
    return html.escape(str(text or ""), quote=False)


async def say(runner: "Runner", bot: "RunningBot", chat_id: int, text: str, rows: list | None = None, markup: dict | None = None) -> None:
    await editor.send(runner, bot, chat_id, text, rows, markup=markup)


async def keyboard(runner: "Runner", bot: "RunningBot", chat_id: int) -> dict | None:
    cur = await runner.current_page(bot, chat_id)
    vals = await runner.values(bot, {"id": chat_id, "first_name": "Admin"})
    return await runner.menu_markup(bot, chat_id, cur, vals) if cur else None


async def start(runner: "Runner", bot: "RunningBot", chat_id: int, user: dict) -> None:
    await editor.set_mode(runner, bot, chat_id, "ai")
    async with async_session() as db:
        ent = await get_entitlement(db, bot.user_id)
        config = await ai.get_config(db)
    limit = bot_ai.daily_limit(ent.flags)
    used = await bot_ai.used_today(runner.redis, bot.user_id)
    status = ""
    if not config["configured"] or not config["enabled"]:
        status = "\n\n⚠️ AI hozircha sozlanmagan — platforma administratori OpenAI kalitini qo'shishi kerak."
    elif limit <= 0:
        status = "\n\n⚠️ Tarifingizda InetTime AI yo'q — tarifni yangilang."
    await say(
        runner,
        bot,
        chat_id,
        "🤖 <b>InetTime AI</b> — botingizni suhbat orqali tuzamiz\n\n"
        "Qanday bot kerakligini oddiy so'z bilan yozing — men to'liq botni loyihalayman: bo'limlar, postlar, tugmalar "
        "(⌨️ klaviatura, 💬 inline yoki 🔀 aralash), formalar, o'zgaruvchilar, kalit so'zlar, referal...\n"
        "Natijani ko'rib, «✅ Qo'llash» ni bosasiz. Keyin suhbatni davom ettirib o'zgartirasiz.\n\n"
        f"Masalan:\n{EXAMPLES}\n\n"
        f"Bugun: {used}/{limit} so'rov" + status,
        markup=await keyboard(runner, bot, chat_id),
    )


async def on_message(runner: "Runner", bot: "RunningBot", message: dict) -> bool:
    chat_id = message["chat"]["id"]
    user = message["from"]
    text = (message.get("text") or message.get("caption") or "").strip()
    if text == editor.AI_EXIT:
        await editor.set_mode(runner, bot, chat_id, None)
        cur = await runner.current_page(bot, chat_id)
        await editor.show_menu(runner, bot, chat_id, cur, "👋 InetTime AI'dan chiqdingiz. Qayta kirish: 🤖 InetTime AI")
        return True
    if text == editor.AI_RESET:
        await runner.redis.delete(_k(bot, "aihist", chat_id), _k(bot, "aiprop", chat_id))
        await say(runner, bot, chat_id, "🧹 Suhbat tozalandi. Yangi bot g'oyasini yozing.")
        return True
    # Klaviaturadagi bot tugmalari AI rejimida ham oddiy ishlaydi (botni sinab ko'rish uchun)
    if text in ("⬅️ Orqaga", "🏠 Bosh menyu"):
        return False
    if text:
        vals = await runner.values(bot, user)
        button, _ = await runner._find_reply_button(bot, chat_id, text, vals)
        if button is not None:
            return False
    if not text or text.startswith("/"):
        await say(runner, bot, chat_id, "✍️ Nima qilish kerakligini matn ko'rinishida yozing. Chiqish: " + editor.AI_EXIT)
        return True
    if not await runner.redis.set(_k(bot, "aibusy", chat_id), "1", nx=True, ex=300):
        await say(runner, bot, chat_id, "⏳ Oldingi so'rovingiz ustida ishlayapman — biroz kuting.")
        return True
    async with async_session() as db:
        ent = await get_entitlement(db, bot.user_id)
        config = await ai.get_config(db)
    if not config["configured"] or not config["enabled"]:
        await runner.redis.delete(_k(bot, "aibusy", chat_id))
        await say(runner, bot, chat_id, "⚠️ AI hozircha sozlanmagan — platforma administratori OpenAI kalitini qo'shishi kerak.")
        return True
    limit = bot_ai.daily_limit(ent.flags)
    if not await bot_ai.take_quota(runner.redis, bot.user_id, limit):
        await runner.redis.delete(_k(bot, "aibusy", chat_id))
        await say(runner, bot, chat_id, f"⚠️ Bugungi InetTime AI limiti tugadi ({limit} ta). Ertaga davom etamiz yoki tarifni yangilang.")
        return True
    max_pages = max(ent.bot_pages_limit, len(bot.menu.get("pages", [])))
    await say(runner, bot, chat_id, "⏳ <b>InetTime AI loyihalayapti…</b>\nMurakkab bot uchun 20–60 soniya ketishi mumkin. Shu orada botingiz ishlashda davom etadi.")
    task = asyncio.create_task(_job(runner, bot, chat_id, user, text, config["model"], max_pages))
    bot.pending.add(task)
    task.add_done_callback(bot.pending.discard)
    return True


async def _typing(runner: "Runner", bot: "RunningBot", chat_id: int) -> None:
    try:
        while True:
            await runner.api(bot, "sendChatAction", {"chat_id": chat_id, "action": "typing"})
            await asyncio.sleep(5)
    except asyncio.CancelledError:
        pass
    except Exception:  # noqa: BLE001
        pass


async def _job(runner: "Runner", bot: "RunningBot", chat_id: int, user: dict, text: str, model: str, max_pages: int) -> None:
    typing = asyncio.create_task(_typing(runner, bot, chat_id))
    try:
        raw = await runner.redis.get(_k(bot, "aihist", chat_id))
        history = json.loads(raw) if raw else []
        try:
            reply, menu, results = await bot_ai.build_bot(model, bot.menu, history, text, max_pages)
        except ai.AIError as exc:
            await bot_ai.refund_quota(runner.redis, bot.user_id)
            await say(runner, bot, chat_id, f"⚠️ {esc(exc)}")
            return
        async with async_session() as db:
            for r in results:
                await ai.log_usage(db, bot.user_id, "bot_builder", r)
        history += [{"role": "user", "content": text[:2000]}, {"role": "assistant", "content": reply[:1500]}]
        await runner.redis.set(_k(bot, "aihist", chat_id), json.dumps(history[-12:]), ex=TTL)
        if menu is None:
            await say(runner, bot, chat_id, f"🤖 {esc(reply)}")
            return
        await runner.redis.set(_k(bot, "aiprop", chat_id), json.dumps(menu), ex=TTL)
        await say(
            runner,
            bot,
            chat_id,
            f"🤖 {esc(reply)}\n\n<b>Natija:</b> {esc(bot_ai.summary(menu))}\n\n<pre>{esc(bot_ai.tree(menu))}</pre>",
            [
                [{"text": "✅ Qo'llash", "callback_data": "ai:ok"}, {"text": "❌ Bekor", "callback_data": "ai:no"}],
            ],
        )
    except Exception:  # noqa: BLE001
        logger.exception("bot %s: InetTime AI xatosi", bot.bot_id)
        await say(runner, bot, chat_id, "⚠️ Kutilmagan xato — qaytadan urinib ko'ring.")
    finally:
        typing.cancel()
        await runner.redis.delete(_k(bot, "aibusy", chat_id))


async def on_callback(runner: "Runner", bot: "RunningBot", chat_id: int, data: str, message: dict, user: dict) -> None:
    action = data.split(":", 1)[1] if ":" in data else ""
    if action == "ok":
        raw = await runner.redis.get(_k(bot, "aiprop", chat_id))
        if not raw:
            await say(runner, bot, chat_id, "⚠️ Taklif eskirgan — so'rovni qayta yozing.")
            return
        proposal = json.loads(raw)
        previous = copy.deepcopy(bot.menu)

        def replace(m: dict):
            m.clear()
            m.update(proposal)

        error = await editor.save(runner, bot, replace)
        if error:
            await say(runner, bot, chat_id, f"⚠️ Qo'llab bo'lmadi: {esc(error)}")
            return
        await runner.redis.set(_k(bot, "aiundo", chat_id), json.dumps(previous), ex=7 * TTL)
        await runner.redis.delete(_k(bot, "aiprop", chat_id))
        # Egasining joyi bosh sahifaga qaytadi
        await runner.redis.delete(*(f"ub:{bot.bot_id}:{k}:{chat_id}" for k in ("nav", "inav", "leaf", "epage", "estack", "esel")))
        await runner.redis.set(f"ub:{bot.bot_id}:cur:{chat_id}", bot.menu["start"], ex=30 * 24 * 3600)
        try:
            await runner.api(bot, "editMessageReplyMarkup", {"chat_id": chat_id, "message_id": message["message_id"], "reply_markup": {"inline_keyboard": []}})
        except Exception:  # noqa: BLE001
            pass
        await say(
            runner,
            bot,
            chat_id,
            "✅ <b>Bot yangilandi!</b> Foydalanuvchilar uni hozirdan shunday ko'radi 👇\n"
            "Keyingi o'zgarishni yozing yoki 🎛 / 📝 muharrirlarda qo'lda aniqlang.",
            [[{"text": "↩️ Oldingi holatga qaytarish", "callback_data": "ai:undo"}]],
        )
        start = editor.page_by_id(bot.menu, bot.menu["start"])
        await runner.send_page(bot, chat_id, start, user)
    elif action == "no":
        await runner.redis.delete(_k(bot, "aiprop", chat_id))
        await editor.send(runner, bot, chat_id, "❌ Bekor qilindi. Boshqacha qilib yozib ko'ring.", message=message)
    elif action == "undo":
        raw = await runner.redis.get(_k(bot, "aiundo", chat_id))
        if not raw:
            await say(runner, bot, chat_id, "⚠️ Qaytariladigan holat topilmadi.")
            return
        previous = json.loads(raw)

        def restore(m: dict):
            m.clear()
            m.update(previous)

        error = await editor.save(runner, bot, restore)
        if error:
            await say(runner, bot, chat_id, f"⚠️ {esc(error)}")
            return
        await runner.redis.delete(_k(bot, "aiundo", chat_id))
        await runner.redis.set(f"ub:{bot.bot_id}:cur:{chat_id}", bot.menu["start"], ex=30 * 24 * 3600)
        await editor.send(runner, bot, chat_id, "↩️ Oldingi holat tiklandi.", message=message)
        start = editor.page_by_id(bot.menu, bot.menu["start"])
        await runner.send_page(bot, chat_id, start, user)
