"""📚 Bot jadvallari: egasi chatda yuritadigan ma'lumot (mahsulot, vakansiya, kurs, uy-joy, tadbir...) va uni foydalanuvchiga
ko'rsatish (sahifa moduli «table»).

    • Egasi: /admin → 🧩 Modullar → 📚 Jadvallar (`tl:*`): jadval yaratish, yozuv qo'shish (maydonma-maydon), ro'yxat/tahrir/o'chirish,
      📥 CSV import (faylni botga yuboradi), 📤 CSV eksport, «📄 Sahifa yaratish» — bosh menyuga ro'yxat bo'limi qo'shiladi.
    • Foydalanuvchi: ro'yxat (sahifalash) → yozuvni bosib batafsil ko'radi (`tb:*`). Rasm maydoni bo'lsa — rasm bilan.
    • Oqim amali `add_record`: oqim ichida jadvalga yozuv qo'shish (ariza, lid, buyurtma qoldiqlari...).
Shablonlar: {maydon_kaliti} — yozuv qiymatlari, {id} — yozuv raqami."""

import csv
import html
import io
import re
from typing import TYPE_CHECKING

from sqlalchemy import func, select

from core.botapi import BotApiError
from core.botbuilder import fill, new_page_id, page_by_id
from core.db.base import async_session
from core.db.models import BotRecord

if TYPE_CHECKING:
    from main import RunningBot

MAX_RECORDS = 2000
PER_PAGE = 6


def esc(t) -> str:
    return html.escape(str(t or ""), quote=False)


def _table(bot: "RunningBot", tid: str) -> dict | None:
    return next((t for t in bot.menu.get("tables") or [] if t["id"] == tid), None)


def slug(label: str, taken: set[str]) -> str:
    base = re.sub(r"[^a-z0-9]+", "_", label.lower().replace("'", "").replace("‘", "").replace("’", "").replace("o‘", "o").replace("g‘", "g")).strip("_")[:24]
    if not base or not base[0].isalpha():
        base = "m_" + base if base else "maydon"
    key, n = base, 2
    while key in taken:
        key = f"{base}_{n}"
        n += 1
    return key


def default_template(table: dict) -> str:
    first = table["fields"][0]["key"]
    rest = [f for f in table["fields"][1:] if f["type"] in ("text", "number")][:2]
    return f"<b>{{{first}}}</b>" + "".join(f" · {{{f['key']}}}" for f in rest)


def _fmt(table: dict, rec: dict, template: str, vals: dict | None = None) -> str:
    data = {f["key"]: str(rec["data"].get(f["key"], "")) for f in table["fields"]}
    data["id"] = str(rec["id"])
    return fill(template, {**(vals or {}), **data}, escape=True)


def _detail_default(table: dict) -> str:
    lines = [f"<b>{{{table['fields'][0]['key']}}}</b>", ""]
    for f in table["fields"][1:]:
        if f["type"] != "photo":
            lines.append(f"{esc(f['label'])}: {{{f['key']}}}")
    return "\n".join(lines)


async def _records(bot: "RunningBot", tid: str, n: int, per: int = PER_PAGE) -> tuple[list[dict], int]:
    async with async_session() as db:
        total = int(await db.scalar(select(func.count(BotRecord.id)).where(BotRecord.bot_id == bot.bot_id, BotRecord.table_id == tid, BotRecord.active == True)) or 0)  # noqa: E712
        rows = (
            await db.scalars(
                select(BotRecord).where(BotRecord.bot_id == bot.bot_id, BotRecord.table_id == tid, BotRecord.active == True)  # noqa: E712
                .order_by(BotRecord.id.desc()).offset(n * per).limit(per)
            )
        ).all()
    return [{"id": r.id, "data": r.data} for r in rows], total


async def _record(bot: "RunningBot", rid: int) -> dict | None:
    async with async_session() as db:
        r = await db.get(BotRecord, rid)
    return {"id": r.id, "data": r.data, "table": r.table_id} if r and r.bot_id == bot.bot_id else None


def clean_value(field: dict, raw) -> str:
    """Maydon qiymatini tekshiradi/tozalaydi. Xato — ValueError (o'zbekcha)."""
    v = str(raw if raw is not None else "").strip()
    if field["type"] == "number":
        try:
            n = float(v.replace(",", ".").replace(" ", ""))
        except ValueError as exc:
            raise ValueError(f"«{field['label']}»: son kiriting") from exc
        return str(int(n)) if n.is_integer() else str(n)
    if field["type"] == "link" and v and not re.match(r"^(https?://|tg://|t\.me/)\S+$", v):
        raise ValueError(f"«{field['label']}»: havola https:// bilan boshlansin")
    return v[:1000]


async def add_record(bot: "RunningBot", tid: str, values: dict) -> int | None:
    table = _table(bot, tid)
    if table is None:
        return None
    data = {}
    for f in table["fields"]:
        if f["key"] in values and str(values[f["key"]]).strip() != "":
            data[f["key"]] = clean_value(f, values[f["key"]])
    if not data:
        return None
    async with async_session() as db:
        if int(await db.scalar(select(func.count(BotRecord.id)).where(BotRecord.bot_id == bot.bot_id, BotRecord.table_id == tid)) or 0) >= MAX_RECORDS:
            raise ValueError(f"jadvalda {MAX_RECORDS} tadan ko'p yozuv bo'lmasin")
        rec = BotRecord(bot_id=bot.bot_id, table_id=tid, data=data)
        db.add(rec)
        await db.commit()
        return rec.id


# ============================================================
# Foydalanuvchi: ro'yxat va batafsil
# ============================================================


async def render_module(runner, bot, chat_id: int, page: dict, vals: dict, *, message: dict | None = None, n: int = 0) -> bool:
    mod = page.get("module") or {}
    if mod.get("type") != "table":
        return False
    table = _table(bot, mod.get("ref") or "")
    if table is None:
        return False
    import shop

    n = max(0, n)
    recs, total = await _records(bot, table["id"], n)
    pages = max(1, (total + PER_PAGE - 1) // PER_PAGE)
    n = min(n, pages - 1)
    if n * PER_PAGE >= total and total:
        recs, total = await _records(bot, table["id"], n)
    first = next((m for m in page.get("messages") or [] if m.get("type") == "text"), None)
    head = fill(first["text"], vals, escape=True) if first else f"<b>{esc(table['title'])}</b>"
    if not recs:
        await shop._edit_or_send(runner, bot, chat_id, head + "\n\n<i>Hozircha ma'lumot yo'q.</i>", [], message)
        return True
    template = mod.get("template") or default_template(table)
    lines = [head, ""] + [f"{i}. {_fmt(table, r, template, vals)}" for i, r in enumerate(recs, n * PER_PAGE + 1)]
    rows = []
    title_key = table["fields"][0]["key"]
    for r in recs:
        rows.append([{"text": (str(r["data"].get(title_key) or f"#{r['id']}"))[:50] + " ➜", "callback_data": f"tb:d:{page['id']}:{r['id']}"}])
    if pages > 1:
        rows.append([
            {"text": "◀️", "callback_data": f"tb:p:{page['id']}:{(n - 1) % pages}"},
            {"text": f"{n + 1}/{pages}", "callback_data": f"tb:p:{page['id']}:{n}"},
            {"text": "▶️", "callback_data": f"tb:p:{page['id']}:{(n + 1) % pages}"},
        ])
    await shop._edit_or_send(runner, bot, chat_id, "\n".join(lines)[:4096], rows, message)
    return True


async def on_callback(runner, bot, chat_id: int, data: str, message: dict, user: dict, query_id: str) -> None:
    parts = data.split(":")
    page = page_by_id(bot.menu, parts[2]) if len(parts) > 2 else None
    await runner.answer(bot, query_id)
    if page is None or (page.get("module") or {}).get("type") != "table":
        return
    table = _table(bot, page["module"].get("ref") or "")
    if table is None:
        return
    if parts[1] == "p":
        vals = await runner.values(bot, user)
        await render_module(runner, bot, chat_id, page, vals, message=message, n=int(parts[3]))
        return
    rec = await _record(bot, int(parts[3]))
    if rec is None or rec["table"] != table["id"]:
        return
    vals = await runner.values(bot, user)
    text = _fmt(table, rec, page["module"].get("detail") or _detail_default(table), vals)
    back = [[{"text": "⬅️ Ro'yxatga", "callback_data": f"tb:p:{page['id']}:0"}]]
    photo = next((rec["data"].get(f["key"]) for f in table["fields"] if f["type"] == "photo" and rec["data"].get(f["key"])), None)
    if photo:
        try:
            await runner.api(bot, "sendPhoto", {"chat_id": chat_id, "photo": photo, "caption": text[:1024], "parse_mode": "HTML", "reply_markup": {"inline_keyboard": back}})
            return
        except BotApiError:
            pass
    import shop

    await shop._edit_or_send(runner, bot, chat_id, text[:4096], back, message)


# ============================================================
# Egasi: /admin → 📚 Jadvallar
# ============================================================


async def _count(bot: "RunningBot", tid: str) -> int:
    async with async_session() as db:
        return int(await db.scalar(select(func.count(BotRecord.id)).where(BotRecord.bot_id == bot.bot_id, BotRecord.table_id == tid)) or 0)


async def admin_home(runner, bot, chat_id: int, message: dict | None = None) -> None:
    import editor

    tables = bot.menu.get("tables") or []
    lines = [f"📚 <b>{esc(t['title'])}</b> — {await _count(bot, t['id'])} yozuv · {', '.join(esc(f['label']) for f in t['fields'])[:80]}" for t in tables]
    text = "📚 <b>Jadvallar</b>\n\nO'z ma'lumotlaringizni (mahsulotlar, vakansiyalar, kurslar, uy-joylar, tadbirlar...) shu yerda yuriting — foydalanuvchiga ro'yxat sifatida ko'rsatiladi.\n\n" + ("\n".join(lines) if lines else "<i>Hozircha jadval yo'q.</i>")
    rows = [[{"text": f"📚 {t['title']}"[:50], "callback_data": f"tl:v:{t['id']}"}] for t in tables]
    rows.append([{"text": "➕ Yangi jadval", "callback_data": "tl:new"}, {"text": "⬅️ Panel", "callback_data": "adm:st"}])
    await editor.send(runner, bot, chat_id, text, rows, message=message)


async def _view(runner, bot, chat_id: int, tid: str, message: dict | None) -> None:
    import editor

    t = _table(bot, tid)
    if t is None:
        await admin_home(runner, bot, chat_id, message)
        return
    has_page = any((p.get("module") or {}).get("ref") == tid for p in bot.menu["pages"] if (p.get("module") or {}).get("type") == "table")
    labels = {"text": "matn", "number": "son", "photo": "rasm", "link": "havola"}
    text = f"📚 <b>{esc(t['title'])}</b> — {await _count(bot, tid)} yozuv\n\n" + "\n".join(f"• {esc(f['label'])} <i>({labels[f['type']]})</i>" for f in t["fields"])
    rows = [
        [{"text": "➕ Yozuv qo'shish", "callback_data": f"tl:ra:{tid}"}, {"text": "📋 Yozuvlar", "callback_data": f"tl:rl:{tid}:0"}],
        [{"text": "📥 CSV import", "callback_data": f"tl:im:{tid}"}, {"text": "📤 CSV eksport", "callback_data": f"tl:ex:{tid}"}],
        [{"text": "✅ Sahifa bor" if has_page else "📄 Menyuga sahifa qo'shish", "callback_data": f"tl:pg:{tid}"}, {"text": "🗑 Jadvalni o'chirish", "callback_data": f"tl:x:{tid}"}],
        [{"text": "⬅️ Jadvallar", "callback_data": "tl:home"}],
    ]
    await editor.send(runner, bot, chat_id, text, rows, message=message)


async def _record_list(runner, bot, chat_id: int, tid: str, n: int, message: dict | None) -> None:
    import editor

    t = _table(bot, tid)
    if t is None:
        return
    recs, total = await _records(bot, tid, n, 8)
    key = t["fields"][0]["key"]
    rows = [[{"text": f"#{r['id']} · {str(r['data'].get(key, ''))[:34]}", "callback_data": f"tl:r:{r['id']}"}] for r in recs]
    nav = []
    if n > 0:
        nav.append({"text": "◀️", "callback_data": f"tl:rl:{tid}:{n - 1}"})
    if (n + 1) * 8 < total:
        nav.append({"text": "▶️", "callback_data": f"tl:rl:{tid}:{n + 1}"})
    if nav:
        rows.append(nav)
    rows.append([{"text": "⬅️ Jadval", "callback_data": f"tl:v:{tid}"}])
    await editor.send(runner, bot, chat_id, f"📋 <b>{esc(t['title'])}</b> · {total} yozuv", rows, message=message)


async def _ask_field(runner, bot, chat_id: int, st: dict) -> None:
    import admin

    t = _table(bot, st["table"])
    f = t["fields"][st["i"]]
    hint = {"photo": "🖼 rasm yuboring", "number": "🔢 son yozing", "link": "🔗 havola (https://...)", "text": "✍️ matn yozing"}[f["type"]]
    await admin.set_state(runner, bot, chat_id, {**st, "k": "tl_rec"})
    await runner.api(
        bot, "sendMessage",
        {"chat_id": chat_id, "parse_mode": "HTML", "text": f"➕ <b>{esc(t['title'])}</b> · {st['i'] + 1}/{len(t['fields'])}\n\n<b>{esc(f['label'])}</b> — {hint}\n<code>-</code> — o'tkazib yuborish · /cancel — bekor"},
    )


async def download(runner, bot, file_id: str, limit: int = 2_000_000) -> bytes | None:
    info = await runner.api(bot, "getFile", {"file_id": file_id})
    path = (info or {}).get("file_path")
    if not path:
        return None
    resp = await runner.http.get(f"https://api.telegram.org/file/bot{bot.token}/{path}", timeout=30)
    return resp.content if resp.status_code == 200 and len(resp.content) <= limit else None


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

    if cmd == "home":
        await admin.set_state(runner, bot, chat_id, None)
        await admin_home(runner, bot, chat_id, message)
    elif cmd == "new":
        await admin.ask(runner, bot, chat_id, {"k": "tl_title"}, "📚 Jadval nomini yuboring (masalan: <code>Vakansiyalar</code>).")
    elif cmd == "v":
        await _view(runner, bot, chat_id, arg, message)
    elif cmd == "ra":
        t = _table(bot, arg)
        if t:
            await _ask_field(runner, bot, chat_id, {"table": arg, "i": 0, "values": {}})
    elif cmd == "rl":
        await _record_list(runner, bot, chat_id, arg, int(parts[3]), message)
    elif cmd == "r":
        rec = await _record(bot, int(arg))
        t = _table(bot, rec["table"]) if rec else None
        if rec and t:
            body = "\n".join(f"• {esc(f['label'])}: {esc(str(rec['data'].get(f['key'], '—'))[:200])}" for f in t["fields"])
            rows = [[{"text": f"✏️ {f['label'][:18]}", "callback_data": f"tl:ed:{arg}:{k}"}] for k, f in enumerate(t["fields"][:6])]
            rows.append([{"text": "🗑 O'chirish", "callback_data": f"tl:rx:{arg}"}, {"text": "⬅️ Yozuvlar", "callback_data": f"tl:rl:{t['id']}:0"}])
            await editor.send(runner, bot, chat_id, f"📚 #{arg}\n\n{body}", rows, message=message)
    elif cmd == "ed":
        rec = await _record(bot, int(arg))
        t = _table(bot, rec["table"]) if rec else None
        if rec and t:
            f = t["fields"][int(parts[3])]
            await admin.ask(runner, bot, chat_id, {"k": "tl_edit", "rid": rec["id"], "field": f["key"]}, f"✏️ «{esc(f['label'])}» uchun yangi qiymat ({'rasm yuboring' if f['type'] == 'photo' else 'yozing'}). <code>-</code> — tozalash.")
    elif cmd == "rx":
        rec = await _record(bot, int(arg))
        if rec:
            async with async_session() as db:
                row = await db.get(BotRecord, rec["id"])
                await db.delete(row)
                await db.commit()
            await _record_list(runner, bot, chat_id, rec["table"], 0, message)
    elif cmd == "im":
        t = _table(bot, arg)
        if t:
            cols = ",".join(f["label"] for f in t["fields"])
            await admin.ask(
                runner, bot, chat_id, {"k": "tl_csv", "table": arg},
                f"📥 CSV faylni (.csv) shu yerga yuboring. Birinchi qator — sarlavha:\n<code>{esc(cols)}</code>\n\nExcel/Google Sheets'dan «CSV (UTF-8)» sifatida saqlang. {MAX_RECORDS} tagacha yozuv.",
            )
    elif cmd == "ex":
        t = _table(bot, arg)
        if t:
            async with async_session() as db:
                rows_db = (await db.scalars(select(BotRecord).where(BotRecord.bot_id == bot.bot_id, BotRecord.table_id == arg).order_by(BotRecord.id))).all()
            buf = io.StringIO()
            w = csv.writer(buf)
            w.writerow([f["label"] for f in t["fields"]])
            for r in rows_db:
                w.writerow([r.data.get(f["key"], "") for f in t["fields"]])
            await runner.api(bot, "sendDocument", {"chat_id": chat_id, "caption": f"📤 {t['title']} — {len(rows_db)} yozuv"}, {"document": (f"{arg}.csv", ("﻿" + buf.getvalue()).encode(), "text/csv")})
    elif cmd == "pg":
        t = _table(bot, arg)
        if t and not any((p.get("module") or {}).get("ref") == arg for p in bot.menu["pages"] if (p.get("module") or {}).get("type") == "table"):
            def add(m: dict) -> None:
                pid = new_page_id()
                m["pages"].append({"id": pid, "title": f"📚 {t['title']}"[:64], "text": t["title"], "messages": [{"type": "text", "text": f"<b>{esc(t['title'])}</b>", "buttons": []}], "keyboard": "inline", "buttons": [], "module": {"type": "table", "ref": arg}})
                start = next(p for p in m["pages"] if p["id"] == m["start"])
                start.setdefault("buttons", []).append([{"text": f"📚 {t['title']}"[:64], "action": "page", "target": pid}])

            if await save(add):
                await runner.api(bot, "sendMessage", {"chat_id": chat_id, "text": "✅ Bosh menyuga qo'shildi."})
        await _view(runner, bot, chat_id, arg, message)
    elif cmd == "x":
        async with async_session() as db:
            await db.execute(BotRecord.__table__.delete().where(BotRecord.bot_id == bot.bot_id, BotRecord.table_id == arg))
            await db.commit()
        if await save(lambda m: m.update(tables=[t for t in m.get("tables") or [] if t["id"] != arg])):
            await admin_home(runner, bot, chat_id, message)


async def admin_input(runner, bot, chat_id: int, message: dict, state: dict) -> bool:
    import admin
    import editor

    kind = state.get("k", "")
    if not kind.startswith("tl_"):
        return False
    text = (message.get("text") or "").strip()

    async def say(t: str) -> None:
        await runner.api(bot, "sendMessage", {"chat_id": chat_id, "text": t, "parse_mode": "HTML"})

    if kind == "tl_title":
        if not text:
            return True
        await admin.ask(
            runner, bot, chat_id, {"k": "tl_fields", "title": text[:40]},
            "📚 Maydonlarni yozing, har qatorga bittadan. Tur ixtiyoriy — nomdan keyin ikki nuqta bilan:\n\n<code>Lavozim\nMaosh: son\nRasm: rasm\nBatafsil: havola\nTalablar</code>\n\nTurlar: matn (standart), son, rasm, havola. Birinchi maydon — sarlavha. 10 tagacha.",
        )
        return True
    if kind == "tl_fields":
        fields, taken = [], set()
        tmap = {"matn": "text", "text": "text", "son": "number", "number": "number", "rasm": "photo", "photo": "photo", "havola": "link", "link": "link"}
        for line in text.splitlines():
            if not line.strip():
                continue
            label, _, typ = line.partition(":")
            ftype = tmap.get(typ.strip().lower(), "text") if typ.strip() else "text"
            key = slug(label.strip(), taken)
            taken.add(key)
            fields.append({"key": key, "label": label.strip()[:40], "type": ftype})
        if not fields or len(fields) > 10:
            await say("⚠️ 1 dan 10 gacha maydon yozing")
            return True
        table = {"id": new_page_id(), "title": state["title"], "fields": fields}
        error = await editor.save(runner, bot, lambda m: m.setdefault("tables", []).append(table))
        if error:
            await say(f"⚠️ {esc(error)}")
            return True
        await admin.set_state(runner, bot, chat_id, None)
        await _view(runner, bot, chat_id, table["id"], None)
        return True
    if kind == "tl_rec":
        t = _table(bot, state["table"])
        f = t["fields"][state["i"]]
        if text == "-":
            value = None
        elif f["type"] == "photo":
            if not message.get("photo"):
                await say("⚠️ Rasm yuboring (yoki <code>-</code>)")
                return True
            value = message["photo"][-1]["file_id"]
        else:
            try:
                value = clean_value(f, text)
            except ValueError as exc:
                await say(f"⚠️ {esc(str(exc))}")
                return True
        values = {**state["values"], **({f["key"]: value} if value is not None else {})}
        if state["i"] + 1 < len(t["fields"]):
            await _ask_field(runner, bot, chat_id, {"table": state["table"], "i": state["i"] + 1, "values": values})
            return True
        await admin.set_state(runner, bot, chat_id, None)
        try:
            rid = await add_record(bot, state["table"], values)
        except ValueError as exc:
            await say(f"⚠️ {esc(str(exc))}")
            return True
        await runner.api(bot, "sendMessage", {"chat_id": chat_id, "text": "✅ Qo'shildi" if rid else "⚠️ Bo'sh yozuv saqlanmadi", "reply_markup": {"inline_keyboard": [[{"text": "➕ Yana", "callback_data": f"tl:ra:{state['table']}"}, {"text": "📚 Jadval", "callback_data": f"tl:v:{state['table']}"}]]}})
        return True
    if kind == "tl_edit":
        rec = await _record(bot, state["rid"])
        t = _table(bot, rec["table"]) if rec else None
        if not rec or not t:
            await admin.set_state(runner, bot, chat_id, None)
            return True
        f = next(x for x in t["fields"] if x["key"] == state["field"])
        try:
            if text == "-":
                new = None
            elif f["type"] == "photo":
                if not message.get("photo"):
                    await say("⚠️ Rasm yuboring")
                    return True
                new = message["photo"][-1]["file_id"]
            else:
                new = clean_value(f, text)
        except ValueError as exc:
            await say(f"⚠️ {esc(str(exc))}")
            return True
        async with async_session() as db:
            row = await db.get(BotRecord, rec["id"])
            data = dict(row.data)
            if new is None:
                data.pop(f["key"], None)
            else:
                data[f["key"]] = new
            row.data = data
            await db.commit()
        await admin.set_state(runner, bot, chat_id, None)
        await say("✅ Yangilandi")
        return True
    if kind == "tl_csv":
        doc = message.get("document")
        t = _table(bot, state["table"])
        if not doc or not t:
            await say("⚠️ .csv faylni yuboring (yoki /cancel)")
            return True
        raw = await download(runner, bot, doc["file_id"])
        if raw is None:
            await say("⚠️ Faylni o'qib bo'lmadi (2 MB dan oshmasin)")
            return True
        try:
            content = raw.decode("utf-8-sig")
        except UnicodeDecodeError:
            content = raw.decode("cp1251", errors="replace")
        reader = csv.reader(io.StringIO(content), delimiter=";" if content.count(";") > content.count(",") else ",")
        rows = list(reader)
        if len(rows) < 2:
            await say("⚠️ Fayl bo'sh yoki sarlavhadan boshqa qator yo'q")
            return True
        header = [h.strip().lower() for h in rows[0]]
        index = {}
        for f in t["fields"]:
            for name in (f["label"].lower(), f["key"]):
                if name in header:
                    index[f["key"]] = header.index(name)
                    break
        if not index:
            await say("⚠️ Sarlavhalar jadval maydonlariga mos kelmadi: " + ", ".join(f["label"] for f in t["fields"]))
            return True
        added, bad = 0, 0
        for r in rows[1:]:
            values = {k: (r[i] if i < len(r) else "") for k, i in index.items()}
            try:
                if await add_record(bot, t["id"], values):
                    added += 1
            except ValueError:
                bad += 1
        await admin.set_state(runner, bot, chat_id, None)
        await say(f"✅ {added} ta yozuv import qilindi" + (f", {bad} tasi noto'g'ri (o'tkazib yuborildi)" if bad else ""))
        return True
    return False
