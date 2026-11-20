"""🏷 Teglar va 🎯 segmentlar (mini-CRM asosi).

Teg — foydalanuvchiga yorliq (data["_tags"]); shartlarda `tag_<nom> bor`, matnda `{tags}`; tegga ko'ra tarqatish va avto-xabar.
Segment — o'zgaruvchilar shartlari («va» bilan): `ball >= 10`, `shahar = Toshkent`, `tag_vip bor` — saqlanadi va auditoriya sifatida tanlanadi."""

import html
from typing import TYPE_CHECKING

from sqlalchemy import func, literal, select, text, update
from sqlalchemy.dialects.postgresql import JSONB

from core.botbuilder import describe_cond, new_page_id, parse_cond
from core.db.base import async_session
from core.db.models import BotSubscriber
from core.segments import SEGMENTS, conditions, normalize_tag, tags_of

if TYPE_CHECKING:
    from main import Runner, RunningBot


def esc(t) -> str:
    return html.escape(str(t or ""), quote=False)


async def _write_tags(bot: "RunningBot", user_id: int, tags: list[str]) -> None:
    async with async_session() as db:
        await db.execute(
            update(BotSubscriber).where(BotSubscriber.bot_id == bot.bot_id, BotSubscriber.tg_user_id == user_id).values(data=BotSubscriber.data.op("||")(literal({"_tags": tags}, type_=JSONB)))
        )
        await db.commit()


async def _current(runner: "Runner", bot: "RunningBot", user_id: int) -> list[str]:
    return tags_of((await runner.subscriber(bot, user_id))["data"])


async def add_tag(runner: "Runner", bot: "RunningBot", user_id: int, tag: str) -> bool:
    tag = normalize_tag(tag)
    tags = await _current(runner, bot, user_id)
    if not tag or tag in tags or len(tags) >= 20:
        return False
    await _write_tags(bot, user_id, tags + [tag])
    return True


async def remove_tag(runner: "Runner", bot: "RunningBot", user_id: int, tag: str) -> bool:
    tag = normalize_tag(tag)
    tags = await _current(runner, bot, user_id)
    if tag not in tags:
        return False
    await _write_tags(bot, user_id, [t for t in tags if t != tag])
    return True


async def top_tags(bot: "RunningBot", limit: int = 6) -> list[tuple[str, int]]:
    async with async_session() as db:
        rows = (
            await db.execute(
                text(
                    "SELECT t AS tag, count(*) AS n FROM bot_subscribers, jsonb_array_elements_text(data->'_tags') AS t "
                    "WHERE bot_id = :b AND jsonb_typeof(data->'_tags') = 'array' GROUP BY t ORDER BY n DESC, t LIMIT :l"
                ),
                {"b": bot.bot_id, "l": limit},
            )
        ).all()
    return [(r[0], r[1]) for r in rows]


async def segment_options(bot: "RunningBot") -> list[str]:
    """Tarqatish uchun tanlanadigan auditoriyalar: tayyor + eng ko'p teglar + egasining segmentlari."""
    return list(SEGMENTS) + [f"t:{t}" for t, _ in await top_tags(bot)] + [f"s:{s['id']}" for s in (bot.menu.get("segments") or [])[:8]]


# ============================================================
# Egasi: /admin → 🎯 Segmentlar
# ============================================================


async def _count(bot: "RunningBot", segment: str) -> int:
    async with async_session() as db:
        return int(await db.scalar(select(func.count(BotSubscriber.id)).where(*conditions(segment, bot.bot_id, bot.menu))) or 0)


async def admin_home(runner, bot, chat_id: int, message: dict | None = None) -> None:
    import editor

    segs = bot.menu.get("segments") or []
    tags = await top_tags(bot, 10)
    seg_lines = [f"🎯 <b>{esc(s['title'])}</b> — {await _count(bot, 's:' + s['id'])} kishi\n   <i>{esc(' va '.join(describe_cond(c) for c in s['conds']))}</i>" for s in segs]
    text_ = (
        "🎯 <b>Segmentlar va teglar</b>\n\nSegment — shartlar bo'yicha foydalanuvchilar guruhi (masalan «ball ≥ 100 va shahar = Toshkent»). "
        "Tarqatish, avto xabarlar va oqimlarda auditoriya sifatida tanlanadi.\n\n"
        + ("\n".join(seg_lines) if segs else "<i>Segment yo'q.</i>")
        + ("\n\n🏷 <b>Teglar:</b> " + ", ".join(f"{esc(t)} ({n})" for t, n in tags) if tags else "\n\n<i>Teglar yo'q — foydalanuvchi kartasidan yoki oqimdagi «Teg qo'shish» qadami bilan qo'shiladi.</i>")
    )
    rows = [[{"text": f"🗑 {s['title']}"[:50], "callback_data": f"sn:x:{s['id']}"}] for s in segs]
    rows.append([{"text": "➕ Segment yaratish", "callback_data": "sn:new"}, {"text": "⬅️ Panel", "callback_data": "adm:st"}])
    await editor.send(runner, bot, chat_id, text_, rows, message=message)


async def admin_callback(runner, bot, chat_id: int, data: str, message: dict, user: dict) -> None:
    import admin
    import editor

    parts = data.split(":")
    cmd = parts[1] if len(parts) > 1 else ""
    arg = parts[2] if len(parts) > 2 else ""
    if cmd == "home":
        await admin.set_state(runner, bot, chat_id, None)
        await admin_home(runner, bot, chat_id, message)
    elif cmd == "new":
        await admin.ask(runner, bot, chat_id, {"k": "sg_title"}, "🎯 Segment nomini yuboring (masalan: <code>VIP mijozlar</code>).")
    elif cmd == "x":
        error = await editor.save(runner, bot, lambda m: m.update(segments=[s for s in m.get("segments") or [] if s["id"] != arg]))
        if error:
            await runner.api(bot, "sendMessage", {"chat_id": chat_id, "text": f"⚠️ {error}"})
        await admin_home(runner, bot, chat_id, message)


async def admin_input(runner, bot, chat_id: int, message: dict, state: dict) -> bool:
    import admin
    import editor

    kind = state.get("k", "")
    text_ = (message.get("text") or "").strip()
    if kind == "user_tag":
        tag = normalize_tag(text_)
        uid = int(state["id"])
        if not tag:
            await runner.api(bot, "sendMessage", {"chat_id": chat_id, "text": "⚠️ Teg nomi lotin harf/raqam bo'lsin"})
            return True
        removed = await remove_tag(runner, bot, uid, tag)
        if not removed:
            await add_tag(runner, bot, uid, tag)
        await admin.set_state(runner, bot, chat_id, None)
        card = await admin.user_card(bot, uid)
        await runner.api(bot, "sendMessage", {"chat_id": chat_id, "text": f"{'➖ Olib tashlandi' if removed else '➕ Qo`shildi'}: 🏷 {tag}"})
        if card:
            await editor.send(runner, bot, chat_id, card[0], card[1])
        return True
    if not kind.startswith("sg_"):
        return False
    if kind == "sg_title":
        if not text_:
            return True
        await admin.ask(
            runner, bot, chat_id, {"k": "sg_conds", "title": text_[:40]},
            "🎯 Shartlarni yozing, har qatorga bittadan (hammasi bajarilishi kerak):\n\n<code>ball >= 100</code>\n<code>shahar = Toshkent</code>\n<code>phone bor</code>\n<code>tag_vip bor</code>",
        )
        return True
    if kind == "sg_conds":
        conds = []
        for line in text_.splitlines():
            if not line.strip():
                continue
            c = parse_cond(line)
            if c is None:
                await runner.api(bot, "sendMessage", {"chat_id": chat_id, "text": f"⚠️ «{line[:40]}» tushunarsiz. Namuna: ball >= 100"})
                return True
            conds.append(c)
        if not conds:
            return True
        seg = {"id": new_page_id(), "title": state["title"], "conds": conds[:6]}
        error = await editor.save(runner, bot, lambda m: m.setdefault("segments", []).append(seg))
        if error:
            await runner.api(bot, "sendMessage", {"chat_id": chat_id, "text": f"⚠️ {error}"})
            return True
        await admin.set_state(runner, bot, chat_id, None)
        await runner.api(bot, "sendMessage", {"chat_id": chat_id, "text": f"✅ «{state['title']}» segmenti yaratildi — {await _count(bot, 's:' + seg['id'])} kishi mos."})
        await admin_home(runner, bot, chat_id, None)
        return True
    return False
