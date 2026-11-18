"""🤖 InetTime AI — botning o'zida AI bilan suhbatlashib bot tuzish (quruvchi v2).

Dasturchi kabi bosqichma-bosqich:
    1) reja — AI biznesni tushunadi; muhim ma'lumot yetishmasa 2-5 ta savol beradi («🤖 O'zing hal qil» ham bor)
    2) arxitektura — bo'limlar daraxti (egasiga darhol ko'rsatiladi)
    3) mazmun — har bir bo'lim uchun professional matnlar (parallel)
    4) yig'ish — navigatsiya va uslub kod bilan kafolatlanadi, linter tekshiradi va tuzatadi
    5) 🧪 sinov — egasi yangi botni foydalanuvchilarga ko'rsatmasdan o'zi sinab ko'radi → ✅ qo'llash / ↩️ qaytarish
Mavjud botni o'zgartirish so'ralsa — joriy hujjatning faqat kerakli qismi o'zgaradi.

AI chaqiruvi fon vazifasida — bot boshqa foydalanuvchilarga javob berishda davom etadi.
Holat (redis): aihist — suhbat, aiprop — taklif, aiundo — oldingi holat, aibusy — ishlayapti, aiq — savol berilgan so'rov."""

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
    "• <i>Restoran boti: menyu kategoriyalar bilan, narxlar, yetkazib berish, buyurtma formasi, manzil. Aralash uslubda.</i>\n"
    "• <i>Ingliz tili o'quv markazi: kurslar, o'qituvchilar, narxlar, ro'yxatdan o'tish. Faqat inline tugmalar.</i>\n"
    "• <i>Kanal uchun konkurs boti: referal havola, har taklif uchun 5 ball, profil.</i>\n"
    "• <i>Hozirgi botga «Aksiyalar» bo'limini qo'sh va menyularni klaviatura tugmalariga o'tkaz.</i>"
)
STAGES = {
    "plan": "🧭 Biznesingizni tahlil qilyapman va bot arxitekturasini loyihalayapman…",
    "write": "✍️ Har bir bo'lim uchun matnlar yozilmoqda…",
    "edit": "🛠 Botingizga o'zgartirish kiritilyapti…",
}


def _k(bot: "RunningBot", kind: str, chat_id: int) -> str:
    return f"ub:{bot.bot_id}:{kind}:{chat_id}"


def esc(text) -> str:
    return html.escape(str(text or ""), quote=False)


def real_bot(runner: "Runner", bot: "RunningBot") -> "RunningBot":
    """Sinov rejimidagi nusxa emas — haqiqiy bot."""
    return getattr(bot, "origin", None) or bot


async def say(runner: "Runner", bot: "RunningBot", chat_id: int, text: str, rows: list | None = None, markup: dict | None = None, message: dict | None = None):
    return await editor.send(runner, bot, chat_id, text, rows, markup=markup, message=message)


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
        status = "\n\n⚠️ AI hozircha sozlanmagan — platforma administratori OpenAI kalitini kiritishi kerak."
    elif limit <= 0:
        status = "\n\n⚠️ Tarifingizda InetTime AI yo'q — tarifni yangilang."
    await say(
        runner,
        bot,
        chat_id,
        "🤖 <b>InetTime AI</b> — botingizni dasturchi kabi loyihalayman\n\n"
        "Biznesingiz va qanday bot kerakligini oddiy so'z bilan yozing. Qancha batafsil (nomi, nima sotasiz, narxlar, manzil, "
        "uslub) — shuncha sifatli. Kerak bo'lsa, aniqlashtiruvchi savol beraman.\n\n"
        "Natijani avval 🧪 <b>sinab ko'rasiz</b> (foydalanuvchilar ko'rmaydi), keyin ✅ qo'llaysiz.\n\n"
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
        await runner.redis.delete(_k(bot, "aihist", chat_id), _k(bot, "aiprop", chat_id), _k(bot, "aiq", chat_id))
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
    asked = await runner.redis.get(_k(bot, "aiq", chat_id))
    if asked:
        await runner.redis.delete(_k(bot, "aiq", chat_id))
        text = f"{asked.decode()}\n\nSavollaringizga javoblarim:\n{text}"
        allow_questions = False
    else:
        # Aniqlashtiruvchi savollar faqat yangi (deyarli bo'sh) bot uchun — tayyor botni o'zgartirishda emas
        allow_questions = len(bot.menu.get("pages") or []) <= 3
    await launch(runner, bot, chat_id, user, text, allow_questions)
    return True


async def launch(runner: "Runner", bot: "RunningBot", chat_id: int, user: dict, text: str, allow_questions: bool) -> None:
    if not await runner.redis.set(_k(bot, "aibusy", chat_id), "1", nx=True, ex=600):
        await say(runner, bot, chat_id, "⏳ Oldingi so'rovingiz ustida ishlayapman — biroz kuting.")
        return
    async with async_session() as db:
        ent = await get_entitlement(db, bot.user_id)
        config = await ai.get_config(db)
    if not config["configured"] or not config["enabled"]:
        await runner.redis.delete(_k(bot, "aibusy", chat_id))
        await say(runner, bot, chat_id, "⚠️ AI hozircha sozlanmagan — platforma administratori OpenAI kalitini kiritishi kerak.")
        return
    limit = bot_ai.daily_limit(ent.flags)
    if not await bot_ai.take_quota(runner.redis, bot.user_id, limit):
        await runner.redis.delete(_k(bot, "aibusy", chat_id))
        await say(runner, bot, chat_id, f"⚠️ Bugungi InetTime AI limiti tugadi ({limit} ta). Ertaga davom etamiz yoki tarifni yangilang.")
        return
    max_pages = max(ent.bot_pages_limit, len(bot.menu.get("pages", [])))
    status = await say(runner, bot, chat_id, f"⏳ <b>InetTime AI ishlayapti</b>\n\n{STAGES['plan']}")
    task = asyncio.create_task(_job(runner, bot, chat_id, user, text, config.get("builder_model") or config["model"], max_pages, allow_questions, status))
    bot.pending.add(task)
    task.add_done_callback(bot.pending.discard)


async def _typing(runner: "Runner", bot: "RunningBot", chat_id: int) -> None:
    try:
        while True:
            await runner.api(bot, "sendChatAction", {"chat_id": chat_id, "action": "typing"})
            await asyncio.sleep(5)
    except asyncio.CancelledError:
        pass
    except Exception:  # noqa: BLE001
        pass


def report_text(report: dict) -> str:
    lines = [f"✅ {esc(x)}" for x in report.get("ok") or []] + [f"⚠️ {esc(x)}" for x in report.get("warn") or []]
    verify = report.get("verify") or []
    if verify:
        lines.append("📝 <b>Tekshirib, o'zingiznikiga almashtiring:</b> " + esc(", ".join(verify[:8])))
    return "\n".join(lines)


async def _job(runner, bot, chat_id, user, text, model, max_pages, allow_questions, status) -> None:
    typing = asyncio.create_task(_typing(runner, bot, chat_id))
    results: list = []

    async def stage(name: str, extra: str = "") -> None:
        if status:
            try:
                await say(runner, bot, chat_id, f"⏳ <b>InetTime AI ishlayapti</b>\n\n{extra}{STAGES[name]}", message=status)
            except Exception:  # noqa: BLE001
                pass

    try:
        raw = await runner.redis.get(_k(bot, "aihist", chat_id))
        history = json.loads(raw) if raw else []
        try:
            data, res = await bot_ai.plan_request(model, bot.menu, history, text, allow_questions=allow_questions, max_pages=max_pages)
            results += res
            mode = data["mode"]
            reply = str(data.get("reply") or "").strip()
            report: dict = {}
            menu = None
            if mode == "ask":
                questions = [str(q) for q in data.get("questions") or [] if str(q).strip()][:5]
                await runner.redis.set(_k(bot, "aiq", chat_id), text, ex=TTL)
                qs = "\n".join(f"{i + 1}. {esc(q)}" for i, q in enumerate(questions))
                await say(
                    runner,
                    bot,
                    chat_id,
                    f"🤖 {esc(reply) or 'Sifatli bot qilish uchun bir necha savol:'}\n\n{qs}\n\n"
                    "Bitta xabarda javob yozing (raqam bilan). Yoki men o'zim hal qilaman 👇",
                    [[{"text": "🤖 O'zing hal qil", "callback_data": "ai:auto"}]],
                )
                history += [{"role": "user", "content": text[:2000]}, {"role": "assistant", "content": (reply + "\n" + qs)[:1500]}]
            elif mode == "answer":
                await say(runner, bot, chat_id, f"🤖 {esc(reply)}")
                history += [{"role": "user", "content": text[:2000]}, {"role": "assistant", "content": reply[:1500]}]
            elif mode == "new":
                plan = data["plan"]
                n = len(plan["sections"])
                await stage("write", f"📐 Arxitektura tayyor: {n} bo'lim\n<pre>{esc(bot_ai.summary_tree_plan(plan))}</pre>\n")
                menu, report, res = await bot_ai.build_new(model, bot.menu, data.get("brief") or {}, plan, max_pages)
                results += res
            else:  # edit
                await stage("edit")
                reply2, menu, res, report = await bot_ai.build_bot(model, bot.menu, history, text, max_pages)
                results += res
                reply = reply2 or reply
        except ai.AIError as exc:
            await bot_ai.refund_quota(runner.redis, bot.user_id)
            await say(runner, bot, chat_id, f"⚠️ {esc(exc)}")
            return
        finally:
            if results:
                async with async_session() as db:
                    for r in results:
                        await ai.log_usage(db, bot.user_id, "bot_builder", r)
        if menu is None:
            await runner.redis.set(_k(bot, "aihist", chat_id), json.dumps(history[-12:]), ex=TTL)
            return
        history += [{"role": "user", "content": text[:2000]}, {"role": "assistant", "content": (reply or "Bot tayyorlandi")[:1500]}]
        await runner.redis.set(_k(bot, "aihist", chat_id), json.dumps(history[-12:]), ex=TTL)
        await runner.redis.set(_k(bot, "aiprop", chat_id), json.dumps(menu), ex=TTL)
        await say(
            runner,
            bot,
            chat_id,
            (f"🤖 {esc(reply)}\n\n" if reply else "")
            + f"<b>Natija:</b> {esc(bot_ai.summary(menu))}\n\n<pre>{esc(bot_ai.tree(menu))}</pre>\n\n"
            + f"<b>Sifat tekshiruvi:</b>\n{report_text(report)}\n\n"
            "🧪 Avval sinab ko'ring — yangi botni faqat siz ko'rasiz, foydalanuvchilar eskisini ko'rishda davom etadi.",
            [
                [{"text": "🧪 Sinab ko'rish", "callback_data": "ai:try"}],
                [{"text": "✅ Qo'llash", "callback_data": "ai:ok"}, {"text": "❌ Bekor", "callback_data": "ai:no"}],
            ],
        )
    except Exception:  # noqa: BLE001
        logger.exception("bot %s: InetTime AI xatosi", bot.bot_id)
        await say(runner, bot, chat_id, "⚠️ Kutilmagan xato — qaytadan urinib ko'ring.")
    finally:
        typing.cancel()
        await runner.redis.delete(_k(bot, "aibusy", chat_id))


async def apply(runner: "Runner", bot: "RunningBot", chat_id: int, user: dict, message: dict | None = None) -> None:
    bot = real_bot(runner, bot)
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
    await runner.redis.delete(*(f"ub:{bot.bot_id}:{k}:{chat_id}" for k in ("nav", "inav", "leaf", "epage", "estack", "esel")))
    await runner.redis.set(f"ub:{bot.bot_id}:cur:{chat_id}", bot.menu["start"], ex=30 * 24 * 3600)
    await editor.set_mode(runner, bot, chat_id, "ai")
    if message is not None:
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


async def try_proposal(runner: "Runner", bot: "RunningBot", chat_id: int, user: dict) -> None:
    bot = real_bot(runner, bot)
    raw = await runner.redis.get(_k(bot, "aiprop", chat_id))
    if not raw:
        await say(runner, bot, chat_id, "⚠️ Taklif eskirgan — so'rovni qayta yozing.")
        return
    await editor.set_mode(runner, bot, chat_id, "sandbox")
    proposal = json.loads(raw)
    sandbox = runner.sandbox_copy(bot, proposal)
    for k in ("nav", "inav", "leaf", "cur"):
        await runner.redis.delete(f"ub:{bot.bot_id}:{k}:{chat_id}")
    await say(
        runner,
        bot,
        chat_id,
        "🧪 <b>Sinov rejimi</b> — yangi botni faqat siz ko'ryapsiz. Tugmalarni bosib, formalarni to'ldirib sinab ko'ring.\n"
        f"Yoqsa — «{editor.SBX_APPLY}», yoqmasa — «{editor.SBX_EXIT}» va AI'ga nima o'zgarishi kerakligini yozing.",
    )
    start = editor.page_by_id(proposal, proposal["start"])
    await runner.send_page(sandbox, chat_id, start, user, with_branding=False)


async def exit_sandbox(runner: "Runner", bot: "RunningBot", chat_id: int, user: dict) -> None:
    bot = real_bot(runner, bot)
    await editor.set_mode(runner, bot, chat_id, "ai")
    for k in ("nav", "inav", "leaf", "q", "form", "ask"):
        await runner.redis.delete(f"ub:{bot.bot_id}:{k}:{chat_id}")
    await runner.redis.set(f"ub:{bot.bot_id}:cur:{chat_id}", bot.menu["start"], ex=30 * 24 * 3600)
    await say(
        runner,
        bot,
        chat_id,
        "🚪 Sinovdan chiqdingiz — hozirgi (eski) bot ko'rinishidasiz. Nimani o'zgartirish kerakligini yozing yoki taklifni qo'llang.",
        [[{"text": "✅ Taklifni qo'llash", "callback_data": "ai:ok"}, {"text": "🧪 Yana sinash", "callback_data": "ai:try"}]],
        markup=None,
    )
    await editor.show_menu(runner, bot, chat_id, editor.page_by_id(bot.menu, bot.menu["start"]), "🤖 InetTime AI")


async def on_callback(runner: "Runner", bot: "RunningBot", chat_id: int, data: str, message: dict, user: dict) -> None:
    action = data.split(":", 1)[1] if ":" in data else ""
    if action == "ok":
        await apply(runner, bot, chat_id, user, message)
    elif action == "try":
        await try_proposal(runner, bot, chat_id, user)
    elif action == "auto":
        asked = await runner.redis.get(_k(bot, "aiq", chat_id))
        if not asked:
            return
        await runner.redis.delete(_k(bot, "aiq", chat_id))
        await launch(runner, real_bot(runner, bot), chat_id, user, asked.decode() + "\n\n(Qolgan hamma narsani o'zing hal qil — savol berma.)", False)
    elif action == "no":
        await runner.redis.delete(_k(bot, "aiprop", chat_id))
        await editor.send(runner, bot, chat_id, "❌ Bekor qilindi. Boshqacha qilib yozib ko'ring.", message=message)
    elif action == "undo":
        bot = real_bot(runner, bot)
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
