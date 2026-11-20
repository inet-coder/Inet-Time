"""🎮 O'yin va jalb qilish: viktorina, reyting, kunlik bonus, konkurs, kapcha.

Foydalanuvchi callbacklari: `qz:*` viktorina, `bn:c` bonus, `cn:*` konkurs, `cap:*` kapcha. Egasi: `gm:*`.
Ballar — foydalanuvchining o'zgaruvchisida (standart `ball`); u matnlarda {ball} bo'lib chiqadi, reyting shundan tuziladi."""

import datetime
import html
import json
import random
from typing import TYPE_CHECKING

from sqlalchemy import Numeric, cast, func, select, update

from core.botapi import BotApiError
from core.botbuilder import new_page_id
from core.db.base import async_session
from core.db.models import BotContestEntry, BotSubscriber

import stats

if TYPE_CHECKING:
    from main import RunningBot

TTL = 3600 * 6


def esc(t) -> str:
    return html.escape(str(t or ""), quote=False)


async def _show(runner, bot, chat_id: int, text: str, rows: list, message: dict | None) -> None:
    import shop

    await shop._edit_or_send(runner, bot, chat_id, text, rows, message)


def _quiz(bot: "RunningBot", qid: str) -> dict | None:
    return next((q for q in bot.menu.get("quizzes") or [] if q["id"] == qid), None)


def _contest(bot: "RunningBot", cid: str) -> dict | None:
    return next((c for c in bot.menu.get("contests") or [] if c["id"] == cid), None)


async def _add_points(runner, bot, user_id: int, var: str, points: int) -> int:
    sub = await runner.subscriber(bot, user_id)
    try:
        cur = int(float(sub["data"].get(var) or 0))
    except ValueError:
        cur = 0
    await runner.set_vars(bot, user_id, {var: str(cur + points)})
    return cur + points


# ============================================================
# Sahifa modullari
# ============================================================


async def render_module(runner, bot, chat_id: int, page: dict, vals: dict, *, message: dict | None = None) -> bool:
    mod = page.get("module") or {}
    kind = mod.get("type")
    if kind == "quiz":
        quiz = _quiz(bot, mod.get("ref") or "")
        if quiz is None:
            return False
        done = (await runner.subscriber(bot, chat_id))["data"].get(f"qz_{quiz['id']}")
        extra = f"\n\n📊 Oxirgi natijangiz: <b>{esc(done)}</b>" if done else ""
        head = f"🧠 <b>{esc(quiz['title'])}</b>\n\n{len(quiz['questions'])} ta savol · har biri uchun javob variantlari tanlanadi.{extra}"
        await _show(runner, bot, chat_id, head, [[{"text": "▶️ Boshlash" if not done else "🔁 Qayta topshirish", "callback_data": f"qz:s:{quiz['id']}"}]], message)
    elif kind == "top":
        await render_top(runner, bot, chat_id, mod.get("var") or "ball", message)
    elif kind == "bonus":
        await render_bonus(runner, bot, chat_id, message)
    elif kind == "contest":
        await render_contest(runner, bot, chat_id, mod.get("ref") or "", message)
    else:
        return False
    return True


# ============================================================
# Viktorina
# ============================================================


def _qkey(bot: "RunningBot", chat_id: int) -> str:
    return f"ub:{bot.bot_id}:qz:{chat_id}"


async def _ask_q(runner, bot, chat_id: int, quiz: dict, st: dict, message: dict | None) -> None:
    q = quiz["questions"][st["i"]]
    rows = [[{"text": o, "callback_data": f"qz:a:{quiz['id']}:{st['i']}:{c}"}] for c, o in enumerate(q["options"])]
    await _show(runner, bot, chat_id, f"🧠 <b>{esc(quiz['title'])}</b> · {st['i'] + 1}/{len(quiz['questions'])}\n\n<b>{esc(q['q'])}</b>", rows, message)


async def quiz_callback(runner, bot, chat_id: int, data: str, message: dict, user: dict, query_id: str) -> None:
    parts = data.split(":")
    cmd = parts[1]
    quiz = _quiz(bot, parts[2]) if len(parts) > 2 else None
    if quiz is None:
        await runner.answer(bot, query_id, "Viktorina topilmadi")
        return
    await runner.answer(bot, query_id)
    key = _qkey(bot, chat_id)
    raw = await runner.redis.get(key)
    st = json.loads(raw) if raw else None
    if cmd == "s":
        await stats.track(runner, bot, f"quiz:{quiz['id']}")
        st = {"qid": quiz["id"], "i": 0, "score": 0, "correct": 0, "answered": False}
        await runner.redis.set(key, json.dumps(st), ex=TTL)
        await _ask_q(runner, bot, chat_id, quiz, st, message)
    elif cmd == "a" and st and st["qid"] == quiz["id"] and not st["answered"] and int(parts[3]) == st["i"]:
        q = quiz["questions"][st["i"]]
        choice = int(parts[4])
        ok = choice == q["answer"]
        st["answered"] = True
        if ok:
            st["score"] += q["points"]
            st["correct"] += 1
        await runner.redis.set(key, json.dumps(st), ex=TTL)
        last = st["i"] == len(quiz["questions"]) - 1
        text = (f"✅ <b>To'g'ri!</b> +{q['points']}" if ok else f"❌ <b>Noto'g'ri.</b> To'g'ri javob: <b>{esc(q['options'][q['answer']])}</b>") + (f"\n\n💡 {esc(q['explain'])}" if q.get("explain") else "")
        await _show(runner, bot, chat_id, f"<b>{esc(q['q'])}</b>\n\n{text}", [[{"text": "🏁 Natijani ko'rish" if last else "➡️ Keyingi savol", "callback_data": f"qz:n:{quiz['id']}"}]], message)
    elif cmd == "n" and st and st["qid"] == quiz["id"] and st["answered"]:
        st["i"] += 1
        st["answered"] = False
        if st["i"] < len(quiz["questions"]):
            await runner.redis.set(key, json.dumps(st), ex=TTL)
            await _ask_q(runner, bot, chat_id, quiz, st, message)
            return
        await runner.redis.delete(key)
        await _finish_quiz(runner, bot, chat_id, quiz, st, user, message)


async def _finish_quiz(runner, bot, chat_id: int, quiz: dict, st: dict, user: dict, message: dict) -> None:
    total = len(quiz["questions"])
    sub = await runner.subscriber(bot, user["id"])
    first_time = f"qz_{quiz['id']}" not in sub["data"]
    awarded = st["score"] if (first_time or quiz.get("repeat")) else 0
    total_points = None
    if awarded:
        total_points = await _add_points(runner, bot, user["id"], quiz.get("var") or "ball", awarded)
    await runner.set_vars(bot, user["id"], {f"qz_{quiz['id']}": f"{st['correct']}/{total}"})
    percent = round(st["correct"] / total * 100)
    medal = "🏆" if percent >= 80 else "👍" if percent >= 50 else "💪"
    lines = [f"{medal} <b>Natija: {st['correct']}/{total}</b> ({percent}%)"]
    if awarded:
        lines.append(f"💎 +{awarded} ball · jami: <b>{total_points}</b>")
    elif not first_time:
        lines.append("<i>Ball faqat birinchi topshirishda beriladi.</i>")
    await _show(runner, bot, chat_id, "\n".join(lines), [[{"text": "🔁 Qayta topshirish", "callback_data": f"qz:s:{quiz['id']}"}]], message)


# ============================================================
# Reyting
# ============================================================


async def render_top(runner, bot, chat_id: int, var: str, message: dict | None) -> None:
    num = cast(BotSubscriber.data[var].astext, Numeric)
    base = [BotSubscriber.bot_id == bot.bot_id, BotSubscriber.blocked == False, BotSubscriber.banned == False, BotSubscriber.data[var].astext.op("~")(r"^-?\d+(\.\d+)?$")]  # noqa: E712
    async with async_session() as db:
        rows = (await db.execute(select(BotSubscriber.tg_user_id, BotSubscriber.first_name, num.label("v")).where(*base).order_by(num.desc(), BotSubscriber.id).limit(10))).all()
        mine = (await runner.subscriber(bot, chat_id))["data"].get(var)
        rank = None
        try:
            if mine is not None:
                rank = (await db.scalar(select(func.count(BotSubscriber.id)).where(*base, num > float(mine)))) + 1
        except ValueError:
            pass
    medals = ["🥇", "🥈", "🥉"]
    lines = ["🏆 <b>Reyting</b> · TOP-10", ""]
    for i, (uid, name, v) in enumerate(rows):
        mark = " 👈" if uid == chat_id else ""
        lines.append(f"{medals[i] if i < 3 else f'{i + 1}.'} {esc(name or 'Foydalanuvchi')} — <b>{int(v) if float(v).is_integer() else v}</b>{mark}")
    if not rows:
        lines.append("<i>Hozircha hech kim ball to'plamagan.</i>")
    if rank:
        lines += ["", f"📍 Sizning o'rningiz: <b>{rank}</b> · ball: <b>{esc(mine)}</b>"]
    await _show(runner, bot, chat_id, "\n".join(lines), [[{"text": "🔄 Yangilash", "callback_data": "bn:t"}]], message)


# ============================================================
# Kunlik bonus
# ============================================================


def _today(bot: "RunningBot") -> datetime.date:
    return (datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(hours=int(bot.menu.get("tz", 5)))).date()


async def render_bonus(runner, bot, chat_id: int, message: dict | None) -> None:
    cfg = bot.menu.get("bonus") or {}
    data = (await runner.subscriber(bot, chat_id))["data"]
    claimed = data.get("bonus_last") == str(_today(bot))
    streak = int(data.get("streak") or 0)
    text = f"🎁 <b>Kunlik bonus</b>\n\nHar kuni kirib <b>+{cfg.get('points', 5)}</b> ball oling" + (f"; ketma-ket har kun uchun qo'shimcha +{cfg['streak_bonus']} (7 kungacha)." if cfg.get("streak_bonus") else ".") + f"\n\n🔥 Ketma-ket kunlar: <b>{streak}</b>"
    rows = [[{"text": "✅ Bugun olingan — ertaga qaytib keling" if claimed else "🎁 Bonusni olish", "callback_data": "bn:c"}]]
    await _show(runner, bot, chat_id, text, rows, message)


async def bonus_callback(runner, bot, chat_id: int, data: str, message: dict, user: dict, query_id: str) -> None:
    cmd = data.split(":")[1]
    if cmd == "t":
        await runner.answer(bot, query_id)
        page = next((p for p in bot.menu["pages"] if (p.get("module") or {}).get("type") == "top"), None)
        await render_top(runner, bot, chat_id, (page or {}).get("module", {}).get("var") or "ball", message)
        return
    cfg = bot.menu.get("bonus") or {}
    sub = await runner.subscriber(bot, user["id"])
    today = _today(bot)
    if sub["data"].get("bonus_last") == str(today):
        await runner.answer(bot, query_id, "Bugungi bonus olingan ✅ Ertaga qaytib keling", alert=True)
        return
    last = sub["data"].get("bonus_last")
    streak = int(sub["data"].get("streak") or 0)
    streak = streak + 1 if last == str(today - datetime.timedelta(days=1)) else 1
    points = int(cfg.get("points", 5)) + int(cfg.get("streak_bonus", 0)) * (min(streak, 7) - 1)
    await runner.set_vars(bot, user["id"], {"bonus_last": str(today), "streak": str(streak)})
    total = await _add_points(runner, bot, user["id"], cfg.get("var") or "ball", points)
    await runner.answer(bot, query_id, f"🎁 +{points} ball! Jami: {total}", alert=True)
    await stats.track(runner, bot, "bonus")
    await render_bonus(runner, bot, chat_id, message)


# ============================================================
# Konkurs
# ============================================================


async def _entries(bot: "RunningBot", cid: str) -> int:
    async with async_session() as db:
        return int(await db.scalar(select(func.count(BotContestEntry.id)).where(BotContestEntry.bot_id == bot.bot_id, BotContestEntry.contest_id == cid)) or 0)


async def render_contest(runner, bot, chat_id: int, cid: str, message: dict | None) -> None:
    c = _contest(bot, cid)
    if c is None:
        return
    async with async_session() as db:
        joined = await db.scalar(select(BotContestEntry.id).where(BotContestEntry.bot_id == bot.bot_id, BotContestEntry.contest_id == cid, BotContestEntry.tg_user_id == chat_id))
    text = f"🎉 <b>{esc(c['title'])}</b>\n\n" + (f"🎁 Sovg'a: <b>{esc(c['prize'])}</b>\n" if c.get("prize") else "") + f"🏆 G'oliblar: {c['winners']} ta\n👥 Ishtirokchilar: <b>{await _entries(bot, cid)}</b>"
    if not c.get("active"):
        text += "\n\n🏁 Konkurs yakunlangan."
        rows = []
    else:
        rows = [[{"text": "✅ Siz qatnashyapsiz" if joined else "🙌 Qatnashish", "callback_data": f"cn:j:{cid}"}]]
    await _show(runner, bot, chat_id, text, rows, message)


async def contest_callback(runner, bot, chat_id: int, data: str, message: dict, user: dict, query_id: str) -> None:
    parts = data.split(":")
    c = _contest(bot, parts[2]) if len(parts) > 2 else None
    if c is None or not c.get("active"):
        await runner.answer(bot, query_id, "Konkurs yakunlangan", alert=True)
        return
    from sqlalchemy.dialects.postgresql import insert as pg_insert

    async with async_session() as db:
        res = await db.execute(pg_insert(BotContestEntry).values(bot_id=bot.bot_id, contest_id=c["id"], tg_user_id=chat_id).on_conflict_do_nothing().returning(BotContestEntry.id))
        new = res.scalar() is not None
        await db.commit()
    await runner.answer(bot, query_id, "🎉 Siz ro'yxatdasiz! Omad!" if new else "Siz allaqachon qatnashyapsiz ✅", alert=True)
    if new:
        await stats.track(runner, bot, f"contest:{c['id']}")
    await render_contest(runner, bot, chat_id, c["id"], message)


async def draw(runner, bot, chat_id: int, cid: str) -> list[int]:
    """G'oliblarni tasodifiy tanlaydi, xabar beradi va konkursni yakunlaydi."""
    import editor

    c = _contest(bot, cid)
    if c is None:
        return []
    async with async_session() as db:
        ids = list(await db.scalars(select(BotContestEntry.tg_user_id).where(BotContestEntry.bot_id == bot.bot_id, BotContestEntry.contest_id == cid)))
    winners = random.sample(ids, min(c["winners"], len(ids)))
    for w in winners:
        try:
            await runner.api(bot, "sendMessage", {"chat_id": w, "text": f"🎉 <b>Tabriklaymiz!</b> Siz «{esc(c['title'])}» konkursida g'olib bo'ldingiz!" + (f"\n🎁 {esc(c['prize'])}" if c.get("prize") else ""), "parse_mode": "HTML"})
        except BotApiError:
            pass

    def close(m: dict) -> None:
        for x in m.get("contests") or []:
            if x["id"] == cid:
                x["active"] = False

    await editor.save(runner, bot, close)
    return winners


# ============================================================
# Kapcha
# ============================================================


async def is_verified(runner, bot, user_id: int) -> bool:
    if await runner.redis.get(f"ub:{bot.bot_id}:cap:{user_id}"):
        return True
    if (await runner.subscriber(bot, user_id))["data"].get("_cap"):
        await runner.redis.set(f"ub:{bot.bot_id}:cap:{user_id}", "1", ex=30 * 86400)
        return True
    return False


async def challenge(runner, bot, chat_id: int) -> None:
    a, b = random.randint(2, 9), random.randint(2, 9)
    options = {a + b}
    while len(options) < 3:
        options.add(a + b + random.choice([-3, -2, -1, 1, 2, 3]))
    shuffled = random.sample(sorted(options), 3)
    await runner.redis.set(f"ub:{bot.bot_id}:capq:{chat_id}", a + b, ex=900)
    await runner.api(
        bot, "sendMessage",
        {"chat_id": chat_id, "text": f"🛡 Botdan foydalanish uchun robot emasligingizni tasdiqlang:\n\n<b>{a} + {b} = ?</b>", "parse_mode": "HTML",
         "reply_markup": {"inline_keyboard": [[{"text": str(o), "callback_data": f"cap:{o}"} for o in shuffled]]}},
    )


async def captcha_callback(runner, bot, chat_id: int, data: str, message: dict, user: dict, query_id: str) -> bool:
    """True — to'g'ri javob (bot ishlashda davom etadi)."""
    right = await runner.redis.get(f"ub:{bot.bot_id}:capq:{chat_id}")
    if right is not None and data.split(":")[1] == right.decode():
        await runner.redis.delete(f"ub:{bot.bot_id}:capq:{chat_id}")
        async with async_session() as db:
            await db.execute(update(BotSubscriber).where(BotSubscriber.bot_id == bot.bot_id, BotSubscriber.tg_user_id == chat_id).values(data=BotSubscriber.data.op("||")({"_cap": "1"})))
            await db.commit()
        await runner.redis.set(f"ub:{bot.bot_id}:cap:{chat_id}", "1", ex=30 * 86400)
        await runner.answer(bot, query_id, "✅ Rahmat!")
        try:
            await runner.api(bot, "deleteMessage", {"chat_id": chat_id, "message_id": message["message_id"]})
        except BotApiError:
            pass
        return True
    await runner.answer(bot, query_id, "❌ Noto'g'ri, qayta urinib ko'ring")
    await challenge(runner, bot, chat_id)
    return False


async def callback(runner, bot, chat_id: int, data: str, message: dict, user: dict, query_id: str) -> None:
    kind = data.split(":")[0]
    if kind == "qz":
        await quiz_callback(runner, bot, chat_id, data, message, user, query_id)
    elif kind == "bn":
        await bonus_callback(runner, bot, chat_id, data, message, user, query_id)
    elif kind == "cn":
        await contest_callback(runner, bot, chat_id, data, message, user, query_id)


def new_id() -> str:
    return new_page_id()


# ============================================================
# Egasi: /admin → 🎮 O'yinlar
# ============================================================


def _add_page(m: dict, title: str, module: dict) -> str:
    pid = new_page_id()
    m["pages"].append(
        {"id": pid, "title": title[:64], "text": title[:64], "messages": [{"type": "text", "text": f"<b>{esc(title)}</b>", "buttons": []}], "keyboard": "inline", "buttons": [], "module": module}
    )
    start = next(p for p in m["pages"] if p["id"] == m["start"])
    start.setdefault("buttons", []).append([{"text": title[:64], "action": "page", "target": pid}])
    return pid


def _has_module(menu: dict, kind: str) -> bool:
    return any((p.get("module") or {}).get("type") == kind for p in menu.get("pages") or [])


async def admin_home(runner, bot, chat_id: int, message: dict | None = None) -> None:
    import editor

    m = bot.menu
    bonus = (m.get("bonus") or {}).get("enabled")
    text = (
        "🎮 <b>O'yinlar va jalb qilish</b>\n\n"
        f"🧠 Viktorinalar: <b>{len(m.get('quizzes') or [])}</b>\n"
        f"🏆 Reyting: {'✅ bor' if _has_module(m, 'top') else '➕ yo‘q'}\n"
        f"🎁 Kunlik bonus: {'✅ yoqilgan' if bonus else '❌ o‘chiq'}\n"
        f"🎉 Konkurslar: <b>{len(m.get('contests') or [])}</b>\n"
        f"🛡 Kapcha (robotdan himoya): {'✅' if m.get('captcha') else '❌'}\n\n"
        "Ball — foydalanuvchining <code>{ball}</code> o'zgaruvchisida; viktorina, bonus, referal shu ballni oshiradi."
    )
    rows = [
        [{"text": "🧠 Viktorinalar", "callback_data": "gm:qz"}, {"text": "🎉 Konkurslar", "callback_data": "gm:cn"}],
        [{"text": "🏆 Reyting qo'shish" if not _has_module(m, "top") else "🏆 Reyting ✅", "callback_data": "gm:top"}, {"text": "🎁 Bonus " + ("✅" if bonus else "❌"), "callback_data": "gm:bn"}],
        [{"text": "🛡 Kapcha " + ("✅" if m.get("captcha") else "❌"), "callback_data": "gm:cap"}, {"text": "⬅️ Panel", "callback_data": "adm:st"}],
    ]
    await editor.send(runner, bot, chat_id, text, rows, message=message)


async def admin_callback(runner, bot, chat_id: int, data: str, message: dict, user: dict) -> None:
    import admin
    import editor

    parts = data.split(":")
    cmd = parts[1] if len(parts) > 1 else ""
    arg = parts[2] if len(parts) > 2 else ""
    m0 = bot.menu

    async def save(fn) -> bool:
        error = await editor.save(runner, bot, fn)
        if error:
            await runner.api(bot, "sendMessage", {"chat_id": chat_id, "text": f"⚠️ {error}"})
            return False
        return True

    if cmd == "home":
        await admin.set_state(runner, bot, chat_id, None)
        await admin_home(runner, bot, chat_id, message)
    elif cmd == "qz":
        rows = [[{"text": f"🧠 {q['title']} · {len(q['questions'])} savol"[:60], "callback_data": f"gm:q:{q['id']}"}] for q in m0.get("quizzes") or []]
        rows.append([{"text": "➕ Yangi viktorina", "callback_data": "gm:qn"}, {"text": "⬅️ O'yinlar", "callback_data": "gm:home"}])
        await editor.send(runner, bot, chat_id, "🧠 <b>Viktorinalar</b>\n\nHar bir to'g'ri javob uchun ball beriladi, natija reytingga tushadi.", rows, message=message)
    elif cmd == "qn":
        await admin.ask(runner, bot, chat_id, {"k": "gm_qt"}, "🧠 Viktorina nomini yuboring (masalan: <code>Umumiy bilimlar</code>).")
    elif cmd == "q":
        q = next((x for x in m0.get("quizzes") or [] if x["id"] == arg), None)
        if q:
            rows = [
                [{"text": "🔁 Ball har safar: " + ("✅" if q.get("repeat") else "❌"), "callback_data": f"gm:qr:{arg}"}],
                [{"text": "🗑 O'chirish", "callback_data": f"gm:qx:{arg}"}, {"text": "⬅️ Viktorinalar", "callback_data": "gm:qz"}],
            ]
            body = "\n".join(f"{i}. {esc(x['q'][:50])}" for i, x in enumerate(q["questions"][:15], 1))
            await editor.send(runner, bot, chat_id, f"🧠 <b>{esc(q['title'])}</b>\n\n{body}", rows, message=message)
    elif cmd == "qr":
        def flip(m):
            for q in m.get("quizzes") or []:
                if q["id"] == arg:
                    q["repeat"] = not q.get("repeat")

        if await save(flip):
            await admin_callback(runner, bot, chat_id, f"gm:q:{arg}", message, user)
    elif cmd == "qx":
        def drop(m):
            m["quizzes"] = [q for q in m.get("quizzes") or [] if q["id"] != arg]
            for p in m["pages"]:
                if (p.get("module") or {}).get("ref") == arg and p["module"].get("type") == "quiz":
                    p["module"] = None
                    p["messages"] = [{"type": "text", "text": "Bu viktorina o'chirilgan.", "buttons": []}]

        if await save(drop):
            await admin_callback(runner, bot, chat_id, "gm:qz", message, user)
    elif cmd == "top":
        if not _has_module(m0, "top"):
            await save(lambda m: _add_page(m, "🏆 Reyting", {"type": "top", "var": "ball"}) and None)
        await admin_home(runner, bot, chat_id, message)
    elif cmd == "bn":
        def toggle(m):
            b = m.setdefault("bonus", {})
            b["enabled"] = not b.get("enabled")
            if b["enabled"] and not any((p.get("module") or {}).get("type") == "bonus" for p in m["pages"]):
                _add_page(m, "🎁 Kunlik bonus", {"type": "bonus"})

        if await save(toggle):
            await admin_home(runner, bot, chat_id, message)
    elif cmd == "cap":
        if await save(lambda m: m.update(captcha=not m.get("captcha"))):
            await admin_home(runner, bot, chat_id, message)
    elif cmd == "cn":
        rows = [[{"text": f"{'🟢' if c.get('active') else '🏁'} {c['title']}"[:60], "callback_data": f"gm:c:{c['id']}"}] for c in m0.get("contests") or []]
        rows.append([{"text": "➕ Yangi konkurs", "callback_data": "gm:cnew"}, {"text": "⬅️ O'yinlar", "callback_data": "gm:home"}])
        await editor.send(runner, bot, chat_id, "🎉 <b>Konkurslar</b>\n\nIshtirokchilar «Qatnashish» tugmasini bosadi, siz bir bosishda g'oliblarni tasodifiy tanlaysiz.", rows, message=message)
    elif cmd == "cnew":
        await admin.ask(runner, bot, chat_id, {"k": "gm_cn"}, "🎉 Konkurs ma'lumotini 3 qatorda yuboring:\n\n<code>Bahorgi sovg'alar\niPhone 15\n3</code>\n\n1) nomi 2) sovg'a 3) g'oliblar soni")
    elif cmd == "c":
        c = _contest(bot, arg)
        if c:
            n = await _entries(bot, arg)
            rows = ([[{"text": f"🎲 G'oliblarni tanlash ({n} kishidan)", "callback_data": f"gm:cd:{arg}"}]] if c.get("active") and n else []) + [
                [{"text": "🗑 O'chirish", "callback_data": f"gm:cx:{arg}"}, {"text": "⬅️ Konkurslar", "callback_data": "gm:cn"}]
            ]
            await editor.send(runner, bot, chat_id, f"🎉 <b>{esc(c['title'])}</b> — {'faol' if c.get('active') else 'yakunlangan'}\n🎁 {esc(c.get('prize') or '—')}\n🏆 G'oliblar: {c['winners']}\n👥 Ishtirokchilar: <b>{n}</b>", rows, message=message)
    elif cmd == "cd":
        winners = await draw(runner, bot, chat_id, arg)
        if not winners:
            await runner.api(bot, "sendMessage", {"chat_id": chat_id, "text": "Ishtirokchi yo'q."})
            return
        names = []
        async with async_session() as db:
            for w in winners:
                row = await db.scalar(select(BotSubscriber).where(BotSubscriber.bot_id == bot.bot_id, BotSubscriber.tg_user_id == w))
                names.append(f"• {esc(row.first_name if row else '')} {('@' + row.username) if row and row.username else ''} <code>{w}</code>")
        await runner.api(bot, "sendMessage", {"chat_id": chat_id, "text": "🏆 <b>G'oliblar:</b>\n\n" + "\n".join(names) + "\n\nHar biriga xabar yuborildi. Konkurs yakunlandi.", "parse_mode": "HTML"})
    elif cmd == "cx":
        def drop(m):
            m["contests"] = [c for c in m.get("contests") or [] if c["id"] != arg]
            for p in m["pages"]:
                if (p.get("module") or {}).get("ref") == arg and p["module"].get("type") == "contest":
                    p["module"] = None
                    p["messages"] = [{"type": "text", "text": "Konkurs yakunlangan.", "buttons": []}]

        if await save(drop):
            await admin_callback(runner, bot, chat_id, "gm:cn", message, user)


async def admin_input(runner, bot, chat_id: int, message: dict, state: dict) -> bool:
    import admin
    import editor
    from core.games import parse_quiz

    kind = state.get("k", "")
    if not kind.startswith("gm_"):
        return False
    text = (message.get("text") or "").strip()

    async def say(t: str, rows: list | None = None) -> None:
        await editor.send(runner, bot, chat_id, t, rows)

    if kind == "gm_qt":
        if not text:
            await say("⚠️ Nom yuboring")
            return True
        await admin.ask(
            runner, bot, chat_id, {"k": "gm_qq", "title": text[:64]},
            "📝 Savollarni yuboring — savollar orasida bo'sh qator:\n\n<code>Poytaxt qaysi shahar?\n+Toshkent\n-Samarqand\n-Buxoro\n? Toshkent 1930 yildan poytaxt\n\n2 + 2 nechta?\n-3\n+4</code>\n\n<b>+</b> to'g'ri javob, <b>-</b> noto'g'ri, <b>?</b> izoh (ixtiyoriy).",
        )
        return True
    if kind == "gm_qq":
        questions, error = parse_quiz(message.get("text") or "")
        if error:
            await say(f"⚠️ {esc(error)}")
            return True
        qid = new_id()
        quiz = {"id": qid, "title": state["title"], "questions": questions, "var": "ball", "repeat": False}

        def add(m):
            m.setdefault("quizzes", []).append(quiz)
            _add_page(m, f"🧠 {state['title']}", {"type": "quiz", "ref": qid})

        err = await editor.save(runner, bot, add)
        if err:
            await say(f"⚠️ {esc(err)}")
            return True
        await admin.set_state(runner, bot, chat_id, None)
        await say(f"✅ «{esc(state['title'])}» — {len(questions)} ta savol. Bosh menyuga qo'shildi.", [[{"text": "🏆 Reyting qo'shish", "callback_data": "gm:top"}, {"text": "⬅️ O'yinlar", "callback_data": "gm:home"}]])
        return True
    if kind == "gm_cn":
        lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
        if not lines:
            await say("⚠️ Kamida nomini yuboring")
            return True
        winners = int("".join(c for c in lines[2] if c.isdigit()) or 1) if len(lines) > 2 else 1
        cid = new_id()
        contest = {"id": cid, "title": lines[0][:64], "prize": (lines[1] if len(lines) > 1 else "")[:200], "winners": max(1, min(50, winners)), "active": True}

        def add(m):
            m.setdefault("contests", []).append(contest)
            _add_page(m, f"🎉 {contest['title']}", {"type": "contest", "ref": cid})

        err = await editor.save(runner, bot, add)
        if err:
            await say(f"⚠️ {esc(err)}")
            return True
        await admin.set_state(runner, bot, chat_id, None)
        await say(f"✅ Konkurs «{esc(contest['title'])}» boshlandi — bosh menyuga qo'shildi.", [[{"text": "🎉 Konkurslar", "callback_data": "gm:cn"}]])
        return True
    return False
