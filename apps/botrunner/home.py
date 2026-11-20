"""Boshqaruv panelining «uy» qismi: statistika, modullar, «Boshlash» ro'yxati, sozlash ustasi.

Panel modullarga qarab chiziladi (core/botmodules.py) — botda qaysi modul bo'lsa, shu bo'lim chiqadi."""

import html
from typing import TYPE_CHECKING

from sqlalchemy import func, select

from core import botmodules
from core.botbuilder import money
from core.db.base import async_session
from core.db.models import BotOrder, BotSubscriber

import admin
import editor
import stats

if TYPE_CHECKING:
    from main import RunningBot, Runner

FLAGS_KEY = "ub:{bot}:flags"


def esc(text) -> str:
    return html.escape(str(text or ""), quote=False)


async def flags(runner: "Runner", bot: "RunningBot") -> set[str]:
    raw = await runner.redis.smembers(FLAGS_KEY.format(bot=bot.bot_id))
    return {x.decode() if isinstance(x, bytes) else x for x in raw}


async def set_flag(runner: "Runner", bot: "RunningBot", flag: str) -> None:
    await runner.redis.sadd(FLAGS_KEY.format(bot=bot.bot_id), flag)


# --- Panel qatorlari (modullarga qarab) ---


async def module_rows(runner: "Runner", bot: "RunningBot") -> list[list[dict]]:
    rows: list[list[dict]] = []
    mods = botmodules.active(bot.menu)
    line: list[dict] = []
    for mod in mods:
        line.append({"text": f"{mod['icon']} {mod['title']}", "callback_data": mod["cb"]})
        if len(line) == 2:
            rows.append(line)
            line = []
    if line:
        rows.append(line)
    items = botmodules.checklist(bot.menu, bot.globals, await flags(runner, bot))
    done = sum(1 for i in items if i["done"])
    first = []
    if done < len(items):
        first.append([{"text": f"🚀 Boshlash · {done}/{len(items)}", "callback_data": "adm:todo"}])
    return first + rows + [[{"text": "📊 Statistika", "callback_data": "adm:stats"}, {"text": "🧩 Modullar", "callback_data": "adm:mods"}]]


# --- Statistika ---


async def stats_view(runner: "Runner", bot: "RunningBot") -> tuple[str, list]:
    import datetime

    now = datetime.datetime.now(datetime.timezone.utc)
    async with async_session() as db:
        base = select(func.count(BotSubscriber.id)).where(BotSubscriber.bot_id == bot.bot_id)
        total = await db.scalar(base.where(BotSubscriber.blocked == False))  # noqa: E712
        new7 = await db.scalar(base.where(BotSubscriber.started_at >= now - datetime.timedelta(days=7)))
        act7 = await db.scalar(base.where(BotSubscriber.last_active_at >= now - datetime.timedelta(days=7)))
        orders7 = await db.scalar(select(func.count(BotOrder.id)).where(BotOrder.bot_id == bot.bot_id, BotOrder.created_at >= now - datetime.timedelta(days=7)))
        revenue7 = await db.scalar(
            select(func.coalesce(func.sum(BotOrder.total), 0)).where(
                BotOrder.bot_id == bot.bot_id, BotOrder.created_at >= now - datetime.timedelta(days=7), BotOrder.status != "cancelled"
            )
        )
    ev = await stats.collect(runner, bot, 7)
    starts = await stats.per_day(runner, bot, "start", 7)
    lines = [
        "📊 <b>Statistika</b> · so'nggi 7 kun",
        "",
        f"👥 Obunachilar: <b>{total}</b> · 🆕 yangi: {new7} · 🟢 faol: {act7}",
        f"▶️ Start bosishlar: <b>{ev.get('start', 0)}</b>  <code>{stats.bar(starts)}</code>",
    ]
    pages = {p["id"]: p["title"] for p in bot.menu.get("pages") or []}
    top = sorted(((k[5:], v) for k, v in ev.items() if k.startswith("page:") and k[5:] in pages), key=lambda x: -x[1])[:6]
    if top:
        lines += ["", "🔥 <b>Eng ko'p ochilgan bo'limlar</b>"] + [f"{i}. {esc(pages[pid])} — {n}" for i, (pid, n) in enumerate(top, 1)]
    if botmodules._shop(bot.menu):
        a, c, o = ev.get("cart_add", 0), ev.get("checkout", 0), orders7 or 0
        lines += [
            "",
            "🛒 <b>Savdo voronkasi</b>",
            f"🛍 Savatga qo'shish: {a}\n📝 Rasmiylashtirishni boshladi: {c}\n✅ Buyurtma: <b>{o}</b>"
            + (f" · konversiya {round(o / c * 100)}%" if c else ""),
            f"💰 Tushum: <b>{money(int(revenue7 or 0), (bot.menu.get('shop') or {}).get('currency') or 'so‘m')}</b>",
        ]
    forms = sorted(((k[5:], v) for k, v in ev.items() if k.startswith("form:")), key=lambda x: -x[1])
    names = {f["id"]: f["title"] for f in bot.menu.get("forms") or []}
    if forms:
        lines += ["", "📝 <b>Arizalar</b>"] + [f"{esc(names.get(fid, fid))} — {n}" for fid, n in forms[:5] if fid in names]
    if not any(ev.values()):
        lines += ["", "<i>Hali ma'lumot yo'q — foydalanuvchilar botni ishlata boshlagach shu yerda ko'rinadi.</i>"]
    return "\n".join(lines), [[{"text": "🔄 Yangilash", "callback_data": "adm:stats"}, {"text": "⬅️ Panel", "callback_data": "adm:st"}]]


# --- Modullar ---


def mods_view(bot: "RunningBot") -> tuple[str, list]:
    rows = []
    lines = ["🧩 <b>Modullar</b>\n\nBotga imkoniyat qo'shing — modul qo'shilgach panelda o'z bo'limi paydo bo'ladi.\n"]
    for mod, on in botmodules.listing(bot.menu):
        lines.append(f"{'✅' if on else '➕'} {mod['icon']} <b>{mod['title']}</b> — {mod['desc']}")
        rows.append([{"text": f"{'✅' if on else '➕'} {mod['icon']} {mod['title']}", "callback_data": mod["cb"]}])
    lines.append("\n🤖 Boshqa narsa kerakmi? InetTime AI'ga yozing: «yozilish qo'sh», «promokod qo'sh»...")
    rows.append([{"text": "⬅️ Panel", "callback_data": "adm:st"}])
    return "\n".join(lines), rows


# --- Boshlash ro'yxati ---


async def todo_view(runner: "Runner", bot: "RunningBot") -> tuple[str, list]:
    items = botmodules.checklist(bot.menu, bot.globals, await flags(runner, bot))
    lines = ["🚀 <b>Birinchi 5 daqiqa</b>\n"]
    rows = []
    for it in items:
        lines.append(f"{'✅' if it['done'] else '⬜️'} {it['text']}")
        if not it["done"]:
            rows.append([{"text": f"👉 {it['text'][:40]}", "callback_data": it["cb"]}])
    done = sum(1 for i in items if i["done"])
    lines.append(f"\nBajarildi: {done}/{len(items)}")
    rows.append([{"text": "⬅️ Panel", "callback_data": "adm:st"}])
    return "\n".join(lines), rows


async def share_view(runner: "Runner", bot: "RunningBot") -> tuple[str, list]:
    await set_flag(runner, bot, "shared")
    link = f"https://t.me/{bot.username}"
    return (
        f"📣 <b>Botingiz havolasi</b>\n\n<code>{link}</code>\n\nShuni Instagram profilingiz, Telegram kanalingiz, vizitka va "
        "chek (QR) ga qo'ying. Kanalga e'lon: «Endi bizda bot bor — buyurtma, narxlar, aksiyalar bir joyda 👇»",
        [[{"text": "📤 Ulashish", "url": f"https://t.me/share/url?url={link}"}], [{"text": "⬅️ Boshlash", "callback_data": "adm:todo"}]],
    )


# --- Sozlash ustasi ---


async def wizard_next(runner: "Runner", bot: "RunningBot", chat_id: int, *, intro: bool = False) -> None:
    """Keyingi savolni so'raydi; qadamlar tugagan bo'lsa — ustani yakunlaydi."""
    steps = bot.menu.get("setup") or []
    if not steps:
        await admin.set_state(runner, bot, chat_id, None)
        await runner.api(bot, "sendMessage", {"chat_id": chat_id, "text": "✅ Asosiy ma'lumotlar tayyor!", "parse_mode": "HTML"})
        text, rows = await todo_view(runner, bot)
        await editor.send(runner, bot, chat_id, text, rows)
        return
    step = steps[0]
    total = len(bot.menu.get("setup") or [])
    await admin.set_state(runner, bot, chat_id, {"k": "setup", "key": step["key"]})
    head = "🧰 <b>Botni sozlaymiz</b> — bir necha qisqa savol, javoblar botning matnlariga o'zi joylashadi.\n\n" if intro else ""
    example = f"\n<i>Masalan: {esc(step['example'])}</i>" if step.get("example") else ""
    await runner.api(
        bot,
        "sendMessage",
        {
            "chat_id": chat_id,
            "text": f"{head}<b>{esc(step['label'])}</b>{example}\n\nQolgan savollar: {total}",
            "parse_mode": "HTML",
            "reply_markup": {"inline_keyboard": [[{"text": "⏭ Keyinroq", "callback_data": "adm:suskip"}]]},
        },
    )


async def wizard_answer(runner: "Runner", bot: "RunningBot", chat_id: int, user: dict, state: dict, text: str | None) -> None:
    """text=None — qadam o'tkazib yuboriladi (qiymat standartligicha qoladi)."""
    key = state.get("key")
    if text is not None:
        await runner.set_vars(bot, user["id"], {key: text.strip()[:200]})
    error = await editor.save(runner, bot, lambda m: m.update(setup=[s for s in m.get("setup") or [] if s["key"] != key]))
    if error:
        await runner.api(bot, "sendMessage", {"chat_id": chat_id, "text": f"⚠️ {error}"})
        return
    await wizard_next(runner, bot, chat_id)


async def maybe_start_wizard(runner: "Runner", bot: "RunningBot", chat_id: int) -> bool:
    if not bot.menu.get("setup"):
        return False
    if await runner.redis.set(f"ub:{bot.bot_id}:wiz:{chat_id}", "1", nx=True, ex=6 * 3600):
        await wizard_next(runner, bot, chat_id, intro=True)
        return True
    return False
