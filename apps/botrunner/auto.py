"""⚡ Avtomatik xabarlar: start'dan keyin, faol bo'lmaganga, savat tashlab ketilsa, jadval bo'yicha.

Dvigatel (tick) leader runnerda har daqiqada ishlaydi. Takror yubormaslik — bot_auto_log (bot, qoida, foydalanuvchi,
davr) ustidagi UNIQUE: avval «band qilinadi», keyin yuboriladi. Egasi boshqaruvi: /admin → ⚡ Avtomatik xabarlar (`au:*`)."""

import asyncio
import datetime
import html
import re
import time
from typing import TYPE_CHECKING

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert

from core.botapi import BotApiError
from core.botbuilder import AUTO_SEGMENTS, entities_to_html, fill, html_to_plain, new_page_id, page_by_id
from core.db.base import async_session
from core.db.models import BotAutoLog, BotSubscriber
from core.segments import SEGMENTS, conditions

import stats

if TYPE_CHECKING:
    from main import Runner, RunningBot

WINDOW_H = 72  # to'xtab qolgandan keyin shuncha soat ichida yetib olinadi
PER_TICK = 100
TRIGGERS = {
    "start_delay": "👋 Start'dan keyin",
    "inactive": "😴 Faol bo'lmaganlarga",
    "cart": "🛒 Savat tashlab ketilsa",
    "schedule": "📅 Jadval bo'yicha",
}
DAYS = ["Du", "Se", "Chor", "Pay", "Ju", "Sha", "Ya"]


def esc(t) -> str:
    return html.escape(str(t or ""), quote=False)


def cartat_key(bot_id: int, chat_id) -> str:
    return f"ub:{bot_id}:cartat:{chat_id}"


def describe(rule: dict) -> str:
    t = rule["trigger"]
    if t == "start_delay":
        return f"botga kirgandan {_dur(rule['hours'])} keyin"
    if t == "inactive":
        return f"{_dur(rule['hours'])} kirmaganlarga"
    if t == "cart":
        return f"savat {_dur(rule['hours'])} tashlab ketilsa"
    days = "har kuni" if len(rule["days"]) == 7 else ", ".join(DAYS[d] for d in rule["days"])
    return f"{days} {rule['at']} da"


def _dur(h: int) -> str:
    return f"{h // 24} kun" if h % 24 == 0 and h >= 24 else f"{h} soat"


# ============================================================
# Yuborish
# ============================================================


async def deliver(runner: "Runner", bot: "RunningBot", rule: dict, uid: int, first_name: str | None = None, username: str | None = None) -> bool:
    user = {"id": uid, "first_name": first_name, "username": username}
    vals = await runner.values(bot, user)
    data = {"chat_id": uid, "text": fill(rule["text"], vals, escape=True)[:4096], "parse_mode": "HTML", "disable_web_page_preview": True}
    page = page_by_id(bot.menu, rule.get("page")) if rule.get("page") else None
    if page is not None:
        data["reply_markup"] = {"inline_keyboard": [[{"text": f"👉 {page['title']}"[:64], "callback_data": f"p:{page['id']}"}]]}
    try:
        await runner.api(bot, "sendMessage", data)
    except BotApiError as exc:
        if exc.user_blocked:
            await runner._set_blocked(bot, uid, True)
        return False
    await stats.track(runner, bot, f"auto:{rule['id']}")
    return True


async def _claim(db, bot_id: int, rule_id: str, uid: int, period: str) -> bool:
    res = await db.execute(
        pg_insert(BotAutoLog).values(bot_id=bot_id, rule_id=rule_id, tg_user_id=uid, period=period[:32]).on_conflict_do_nothing().returning(BotAutoLog.id)
    )
    return res.scalar() is not None


async def _send_to(runner, bot, rule: dict, rows: list[tuple[int, str | None, str | None, str]]) -> int:
    """rows: (uid, first_name, username, period). Avval band qilinadi, keyin yuboriladi."""
    sent = 0
    for uid, first, username, period in rows:
        async with async_session() as db:
            ok = await _claim(db, bot.bot_id, rule["id"], uid, period)
            await db.commit()
        if not ok:
            continue
        if await deliver(runner, bot, rule, uid, first, username):
            sent += 1
        await asyncio.sleep(0.04)
    return sent


# ============================================================
# Dvigatel
# ============================================================


async def tick(runner: "Runner") -> None:
    for bot in list(runner.bots.values()):
        if getattr(bot, "sandbox", False):
            continue
        for rule in bot.menu.get("auto") or []:
            if not rule.get("enabled", True):
                continue
            try:
                await _run_rule(runner, bot, rule)
            except Exception:  # noqa: BLE001 — bitta qoida boshqalarni to'xtatmasin
                import logging

                logging.getLogger(__name__).exception("avtomatik xabar xatosi: %s", rule.get("id"))


async def _run_rule(runner, bot, rule: dict) -> None:
    now = datetime.datetime.now(datetime.timezone.utc)
    h = int(rule.get("hours") or 24)
    trigger = rule["trigger"]
    seg = rule.get("segment") or "all"
    if trigger in ("start_delay", "inactive"):
        col = BotSubscriber.started_at if trigger == "start_delay" else BotSubscriber.last_active_at
        q = (
            select(BotSubscriber.tg_user_id, BotSubscriber.first_name, BotSubscriber.username, col)
            .where(*conditions(seg, bot.bot_id, bot.menu), col <= now - datetime.timedelta(hours=h), col >= now - datetime.timedelta(hours=h + WINDOW_H))
            .limit(PER_TICK)
        )
        async with async_session() as db:
            found = (await db.execute(q)).all()
        owner = bot.owner_chat_id
        rows = [(u, f, n, "once" if trigger == "start_delay" else f"{c:%Y%m%d%H}") for u, f, n, c in found if u != owner]
        await _send_to(runner, bot, rule, rows)
    elif trigger == "cart":
        await _run_cart(runner, bot, rule, now)
    elif trigger == "schedule":
        await _run_schedule(runner, bot, rule, now)


async def _run_cart(runner, bot, rule: dict, now: datetime.datetime) -> None:
    h = int(rule.get("hours") or 3)
    due = []
    async for key in runner.redis.scan_iter(match=cartat_key(bot.bot_id, "*"), count=200):
        raw = await runner.redis.get(key)
        if not raw:
            continue
        ts = float(raw)
        age = (now.timestamp() - ts) / 3600
        if h <= age <= h + WINDOW_H:
            chat = int((key.decode() if isinstance(key, bytes) else key).rsplit(":", 1)[1])
            if await runner.redis.hlen(f"ub:{bot.bot_id}:cart:{chat}"):
                due.append((chat, int(ts)))
        if len(due) >= PER_TICK:
            break
    if not due:
        return
    async with async_session() as db:
        subs = {r.tg_user_id: r for r in (await db.scalars(select(BotSubscriber).where(*conditions(rule.get("segment") or "all", bot.bot_id, bot.menu), BotSubscriber.tg_user_id.in_([c for c, _ in due])))).all()}
    await _send_to(runner, bot, rule, [(c, subs[c].first_name, subs[c].username, str(ts)) for c, ts in due if c in subs])


async def _run_schedule(runner, bot, rule: dict, now: datetime.datetime) -> None:
    local = now + datetime.timedelta(hours=int(bot.menu.get("tz", 5)))
    if local.weekday() not in rule["days"] or f"{local:%H:%M}" < rule["at"]:
        return
    if (local.hour * 60 + local.minute) - (int(rule["at"][:2]) * 60 + int(rule["at"][3:])) > 180:
        return  # 3 soatdan ko'p kechikkan bo'lsa — bugun o'tkazib yuboriladi
    period = f"{local:%Y%m%d}"
    async with async_session() as db:
        if not await _claim(db, bot.bot_id, rule["id"], 0, period):
            return
        await db.commit()
        audience = (await db.execute(select(BotSubscriber.tg_user_id, BotSubscriber.first_name, BotSubscriber.username).where(*conditions(rule.get("segment") or "all", bot.bot_id, bot.menu)).limit(5000))).all()
    # Tarqatish fonda: daqiqalik sikl kutib qolmasin
    asyncio.create_task(_broadcast(runner, bot, rule, [(u, f, n) for u, f, n in audience if u != bot.owner_chat_id]))


async def _broadcast(runner, bot, rule: dict, audience: list) -> None:
    for uid, first, username in audience:
        await deliver(runner, bot, rule, uid, first, username)
        await asyncio.sleep(0.05)


# ============================================================
# Egasi: /admin → ⚡ Avtomatik xabarlar
# ============================================================


def _rule(bot: "RunningBot", rid: str) -> dict | None:
    return next((r for r in bot.menu.get("auto") or [] if r["id"] == rid), None)


def _short(rule: dict) -> str:
    return f"{'✅' if rule.get('enabled', True) else '⏸'} {TRIGGERS[rule['trigger']][:2]} {html_to_plain(rule['text'])[:28]}"


async def admin_home(runner, bot, chat_id: int, message: dict | None = None) -> None:
    import editor

    rules = bot.menu.get("auto") or []
    text = (
        "⚡ <b>Avtomatik xabarlar</b>\n\nBot o'zi yozadi: yangi foydalanuvchiga salom, uzoq kirmaganni qaytarish, "
        "savatini tashlab ketganga eslatma, har kuni «kun taklifi».\n\n"
        + ("\n".join(f"• {esc(_short(r))}\n   <i>{esc(describe(r))}</i>" for r in rules) if rules else "<i>Hozircha qoida yo'q — birinchisini qo'shing 👇</i>")
    )
    rows = [[{"text": _short(r)[:60], "callback_data": f"au:r:{r['id']}"}] for r in rules]
    rows.append([{"text": "➕ Yangi qoida", "callback_data": "au:new"}, {"text": "⬅️ Panel", "callback_data": "adm:st"}])
    await editor.send(runner, bot, chat_id, text, rows, message=message)


def _parse_time(text: str) -> str | None:
    m = re.match(r"^\s*(\d{1,2})[:.](\d{2})\s*$", text or "")
    if not m or int(m.group(1)) > 23 or int(m.group(2)) > 59:
        return None
    return f"{int(m.group(1)):02d}:{m.group(2)}"


async def _rule_view(runner, bot, chat_id: int, rid: str, message: dict | None) -> None:
    import editor

    rule = _rule(bot, rid)
    if rule is None:
        await admin_home(runner, bot, chat_id, message)
        return
    page = page_by_id(bot.menu, rule.get("page")) if rule.get("page") else None
    text = (
        f"{TRIGGERS[rule['trigger']]} — <b>{'yoqilgan' if rule.get('enabled', True) else 'to‘xtatilgan'}</b>\n"
        f"🕘 {esc(describe(rule))}\n🎯 Kimga: {SEGMENTS.get(rule.get('segment') or 'all')}\n"
        f"🔗 Tugma: {esc(page['title']) if page else 'yo‘q'}\n\n{rule['text']}"
    )
    rows = [
        [{"text": "✏️ Matn", "callback_data": f"au:e:{rid}"}, {"text": "🎯 Auditoriya", "callback_data": f"au:s:{rid}"}, {"text": "🔗 Tugma", "callback_data": f"au:p:{rid}"}],
        [{"text": "🧪 Menga yuborish", "callback_data": f"au:ts:{rid}"}, {"text": "⏸ To'xtatish" if rule.get("enabled", True) else "▶️ Yoqish", "callback_data": f"au:o:{rid}"}],
        [{"text": "🗑 O'chirish", "callback_data": f"au:x:{rid}"}, {"text": "⬅️ Qoidalar", "callback_data": "au:home"}],
    ]
    await editor.send(runner, bot, chat_id, text, rows, message=message)


async def admin_callback(runner, bot, chat_id: int, data: str, message: dict, user: dict) -> None:
    import admin
    import editor

    parts = data.split(":")
    cmd = parts[1] if len(parts) > 1 else ""
    arg = parts[2] if len(parts) > 2 else ""

    async def save(fn) -> bool:
        error = await editor.save(runner, bot, fn)
        if error:
            await runner.api(bot, "sendMessage", {"chat_id": chat_id, "text": f"⚠️ {error}"})
            return False
        return True

    def edit(rid: str, **changes):
        def fn(m: dict) -> None:
            for r in m.get("auto") or []:
                if r["id"] == rid:
                    r.update(changes)

        return fn

    if cmd == "home":
        await admin.set_state(runner, bot, chat_id, None)
        await admin_home(runner, bot, chat_id, message)
    elif cmd == "new":
        triggers = [t for t in TRIGGERS if t != "cart" or (bot.menu.get("shop") or {}).get("enabled")]
        rows = [[{"text": TRIGGERS[t], "callback_data": f"au:t:{t}"}] for t in triggers] + [[{"text": "⬅️ Qoidalar", "callback_data": "au:home"}]]
        await editor.send(
            runner, bot, chat_id,
            "➕ <b>Qachon yuborilsin?</b>\n\n👋 Yangi foydalanuvchiga — kirgandan keyin\n😴 Anchadan beri kirmaganlarga — qaytarish\n🛒 Savatga qo'yib ketganlarga — eslatma\n📅 Hammaga — jadval bo'yicha (kun taklifi, yangilik)",
            rows, message=message,
        )
    elif cmd == "t":
        if arg == "schedule":
            await admin.ask(runner, bot, chat_id, {"k": "au_time"}, "🕘 Soat nechada yuborilsin? <code>10:00</code> ko'rinishida yozing.")
            return
        options = {"start_delay": [1, 3, 24, 72], "inactive": [72, 168, 336, 720], "cart": [1, 3, 24]}.get(arg)
        if options:
            rows = [[{"text": _dur(h), "callback_data": f"au:h:{arg}:{h}"} for h in options], [{"text": "⬅️ Orqaga", "callback_data": "au:new"}]]
            await editor.send(runner, bot, chat_id, f"{TRIGGERS[arg]}\n\n⏱ Qancha vaqtdan keyin?", rows, message=message)
    elif cmd == "h":
        await admin.ask(runner, bot, chat_id, {"k": "au_text", "trigger": arg, "hours": int(parts[3])}, _text_prompt())
    elif cmd == "d":
        days = {"all": list(range(7)), "wk": [0, 1, 2, 3, 4], "we": [5, 6]}.get(parts[3], list(range(7)))
        await admin.ask(runner, bot, chat_id, {"k": "au_text", "trigger": "schedule", "at": f"{arg[:2]}:{arg[2:]}", "days": days}, _text_prompt())
    elif cmd == "r":
        await _rule_view(runner, bot, chat_id, arg, message)
    elif cmd == "e":
        await admin.ask(runner, bot, chat_id, {"k": "au_edit", "id": arg}, _text_prompt())
    elif cmd == "s":
        rule = _rule(bot, arg)
        if rule:
            order = list(AUTO_SEGMENTS)
            nxt = order[(order.index(rule.get("segment") or "all") + 1) % len(order)]
            if await save(edit(arg, segment=nxt)):
                await _rule_view(runner, bot, chat_id, arg, message)
    elif cmd == "p":
        pages = [p for p in bot.menu.get("pages") or [] if p["id"] != bot.menu.get("start")][:12]
        rows = [[{"text": "🚫 Tugmasiz", "callback_data": f"au:pp:{arg}:-"}]] + [[{"text": p["title"][:40], "callback_data": f"au:pp:{arg}:{p['id']}"}] for p in pages]
        rows.append([{"text": "⬅️ Orqaga", "callback_data": f"au:r:{arg}"}])
        await editor.send(runner, bot, chat_id, "🔗 Xabar ostida qaysi bo'limni ochadigan tugma bo'lsin?", rows, message=message)
    elif cmd == "pp":
        target = parts[3] if len(parts) > 3 and parts[3] != "-" else None
        if await save(edit(arg, page=target)):
            await _rule_view(runner, bot, chat_id, arg, message)
    elif cmd == "o":
        rule = _rule(bot, arg)
        if rule and await save(edit(arg, enabled=not rule.get("enabled", True))):
            await _rule_view(runner, bot, chat_id, arg, message)
    elif cmd == "x":
        if await save(lambda m: m.update(auto=[r for r in m.get("auto") or [] if r["id"] != arg])):
            await admin_home(runner, bot, chat_id, message)
    elif cmd == "ts":
        rule = _rule(bot, arg)
        if rule:
            await deliver(runner, bot, rule, chat_id, user.get("first_name"), user.get("username"))


def _text_prompt() -> str:
    return (
        "✍️ Xabar matnini yuboring (formatlash saqlanadi).\n\n"
        "Foydalanuvchi ismi: <code>{name}</code>, savat: <code>{cart_count}</code> / <code>{cart_total}</code>, "
        "havola: <code>{ref_link}</code>, o'zgaruvchilaringiz: <code>{ball}</code>..."
    )


async def admin_input(runner, bot, chat_id: int, message: dict, state: dict) -> bool:
    import admin
    import editor

    kind = state.get("k", "")
    if not kind.startswith("au_"):
        return False
    text = (message.get("text") or "").strip()

    async def say(t: str, rows: list | None = None) -> None:
        await editor.send(runner, bot, chat_id, t, rows)

    if kind == "au_time":
        at = _parse_time(text)
        if at is None:
            await say("⚠️ Soatni <code>10:00</code> ko'rinishida yozing")
            return True
        await admin.set_state(runner, bot, chat_id, None)
        key = at.replace(":", "")
        rows = [[{"text": "Har kuni", "callback_data": f"au:d:{key}:all"}], [{"text": "Du–Ju", "callback_data": f"au:d:{key}:wk"}, {"text": "Shanba–Yakshanba", "callback_data": f"au:d:{key}:we"}]]
        await say(f"🕘 {at}\n\nQaysi kunlari?", rows)
        return True
    html_text = entities_to_html(message.get("text") or "", message.get("entities"))[:1500]
    if not html_text.strip():
        await say("⚠️ Matn yuboring")
        return True
    if kind == "au_text":
        rid = new_page_id()
        rule = {"id": rid, "title": TRIGGERS[state["trigger"]], "trigger": state["trigger"], "text": html_text, "enabled": True}
        for k in ("hours", "at", "days"):
            if k in state:
                rule[k] = state[k]
        error = await editor.save(runner, bot, lambda m: m.setdefault("auto", []).append(rule))
        if error:
            await say(f"⚠️ {esc(error)}")
            return True
        await admin.set_state(runner, bot, chat_id, None)
        await _rule_view(runner, bot, chat_id, rid, None)
        return True
    if kind == "au_edit":
        rid = state["id"]

        def fn(m: dict) -> None:
            for r in m.get("auto") or []:
                if r["id"] == rid:
                    r["text"] = html_text

        error = await editor.save(runner, bot, fn)
        if error:
            await say(f"⚠️ {esc(error)}")
            return True
        await admin.set_state(runner, bot, chat_id, None)
        await _rule_view(runner, bot, chat_id, rid, None)
        return True
    return False


def now_ts() -> int:
    return int(time.time())
