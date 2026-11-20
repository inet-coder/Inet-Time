"""📅 Yozilish moduli: xizmat → xodim → kun → vaqt → ma'lumot → tasdiq → eslatma.

Bo'sh vaqtlar core/booking.py da hisoblanadi (ish jadvali, xizmat davomiyligi, band intervallar). Ikki kishi bir vaqtga
yozilib qolmasligi uchun yaratish tranzaksiyada (pg_advisory_xact_lock) qayta tekshiriladi.

Foydalanuvchi callbacklari `bk:*`, egasiniki `bm:*` (faqat adminlarga).
Sahifa moduli (page.module): booking — yozilish ustasi; mybookings — «Yozilishlarim»."""

import datetime
import html
import json
import re
from typing import TYPE_CHECKING

from sqlalchemy import func, select, text

from core import booking as bk
from core.botapi import BotApiError
from core.botbuilder import fill, money, new_page_id
from core.db.base import async_session
from core.db.models import BotBooking

import integrations
import stats

if TYPE_CHECKING:
    from main import Runner, RunningBot

BOOKING_ID = "__booking"
TTL = 3600
MONTHS = ["yanvar", "fevral", "mart", "aprel", "may", "iyun", "iyul", "avgust", "sentabr", "oktabr", "noyabr", "dekabr"]
STATUS = {"pending": "⏳ Tasdiq kutilmoqda", "confirmed": "✅ Tasdiqlangan", "cancelled": "❌ Bekor qilingan", "done": "✔️ Bajarilgan"}
ACTIVE = ("pending", "confirmed")


def esc(t) -> str:
    return html.escape(str(t or ""), quote=False)


def cfg(bot: "RunningBot") -> dict:
    return bot.menu.get("booking") or {}


def fmt_day(d: datetime.date) -> str:
    return f"{bk.SHORT_DAYS[d.weekday()]}, {d.day}-{MONTHS[d.month - 1]}"


def fmt_when(b: dict, when: datetime.datetime) -> str:
    local = bk.to_local(b, when)
    return f"{fmt_day(local.date())}, {local:%H:%M}"


def _sk(bot: "RunningBot", chat_id: int) -> str:
    return f"ub:{bot.bot_id}:bks:{chat_id}"


async def _state(runner: "Runner", bot: "RunningBot", chat_id: int) -> dict:
    raw = await runner.redis.get(_sk(bot, chat_id))
    return json.loads(raw) if raw else {}


async def _save(runner: "Runner", bot: "RunningBot", chat_id: int, st: dict) -> None:
    await runner.redis.set(_sk(bot, chat_id), json.dumps(st), ex=TTL)


def _service(bot: "RunningBot", sid: str | None) -> dict | None:
    return next((s for s in cfg(bot).get("services") or [] if s["id"] == sid), None)


def _staff_list(bot: "RunningBot") -> list[dict]:
    return cfg(bot).get("staff") or []


# ============================================================
# Bo'sh vaqtlar
# ============================================================


async def _busy(db, bot_id: int, b: dict, day: datetime.date, staff_ids: list[str]) -> dict[str, list[tuple[int, int]]]:
    lo = bk.to_utc(b, day, 0) - datetime.timedelta(hours=12)
    hi = bk.to_utc(b, day, 24 * 60) + datetime.timedelta(hours=12)
    rows = (
        await db.execute(
            select(BotBooking.staff_id, BotBooking.starts_at, BotBooking.minutes).where(
                BotBooking.bot_id == bot_id, BotBooking.status.in_(ACTIVE), BotBooking.starts_at >= lo, BotBooking.starts_at < hi
            )
        )
    ).all()
    out: dict[str, list[tuple[int, int]]] = {s: [] for s in staff_ids}
    for staff_id, starts, minutes in rows:
        local = bk.to_local(b, starts)
        if local.date() == day and staff_id in out:
            m = local.hour * 60 + local.minute
            out[staff_id].append((m, m + minutes))
    return out


async def slots_for(bot: "RunningBot", service: dict, staff_id: str, day: datetime.date) -> list[tuple[int, str]]:
    """[(daqiqa, xodim id)]. staff_id "*" — farqi yo'q: istalgan bo'sh xodim."""
    b = cfg(bot)
    staff = _staff_list(bot)
    ids = [s["id"] for s in staff] or ["main"]
    wanted = ids if staff_id == "*" else [staff_id]
    now = bk.local_now(b)
    async with async_session() as db:
        busy = await _busy(db, bot.bot_id, b, day, wanted)
    seen: dict[int, str] = {}
    for sid in wanted:
        for t in bk.free_slots(b, service["minutes"], day, busy.get(sid, []), now):
            seen.setdefault(t, sid)
    return sorted(seen.items())


async def free_days(bot: "RunningBot", service: dict, staff_id: str) -> list[datetime.date]:
    b = cfg(bot)
    out = []
    for day in bk.open_days(b, bk.local_now(b)):
        if await slots_for(bot, service, staff_id, day):
            out.append(day)
    return out


# ============================================================
# Foydalanuvchi: ustaning qadamlari
# ============================================================


async def _show(runner, bot, chat_id: int, text_: str, rows: list, message: dict | None) -> None:
    import shop

    await shop._edit_or_send(runner, bot, chat_id, text_, rows, message)


def _nav(back: str | None) -> list[list[dict]]:
    row = []
    if back:
        row.append({"text": "⬅️ Orqaga", "callback_data": back})
    row.append({"text": "📋 Yozilishlarim", "callback_data": "bk:m"})
    return [row]


async def render_start(runner, bot, chat_id: int, *, message: dict | None = None, header: str | None = None) -> None:
    await stats.track(runner, bot, "book_start")
    await _save(runner, bot, chat_id, {})
    await step(runner, bot, chat_id, {}, message, header=header)


async def step(runner, bot, chat_id: int, st: dict, message: dict | None, *, header: str | None = None) -> None:
    b = cfg(bot)
    services = b.get("services") or []
    head = (header + "\n\n") if header else ""
    if not services:
        await _show(runner, bot, chat_id, head + "📅 Hozircha yozilish uchun xizmatlar kiritilmagan.", _nav(None)[:0], message)
        return
    if not st.get("svc"):
        if len(services) == 1:
            st["svc"] = services[0]["id"]
            await _save(runner, bot, chat_id, st)
        else:
            rows = [[{"text": f"{s['title']} · {s['minutes']} daq" + (f" · {money(s['price'], 'so‘m')}" if s["price"] else ""), "callback_data": f"bk:v:{s['id']}"[:64]}] for s in services]
            await _show(runner, bot, chat_id, head + "📅 <b>Yozilish</b>\n\nQaysi xizmat kerak?", rows + _nav(None), message)
            return
    service = _service(bot, st["svc"])
    if service is None:
        await render_start(runner, bot, chat_id, message=message)
        return
    staff = _staff_list(bot)
    if staff and not st.get("staff"):
        rows = [[{"text": f"👤 {s['title']}", "callback_data": f"bk:f:{s['id']}"}] for s in staff]
        if len(staff) > 1:
            rows.append([{"text": "🔀 Farqi yo'q (eng yaqin vaqt)", "callback_data": "bk:f:*"}])
        back = "bk:s" if len(b.get("services") or []) > 1 else None
        await _show(runner, bot, chat_id, head + f"✨ <b>{esc(service['title'])}</b>\n\nKim qabul qilsin?", rows + _nav(back), message)
        return
    staff_id = st.get("staff") or "main"
    if not st.get("date"):
        days = await free_days(bot, service, staff_id)
        if not days:
            await _show(runner, bot, chat_id, head + "😔 Yaqin kunlarda bo'sh vaqt qolmagan. Keyinroq qayta urinib ko'ring yoki biz bilan bog'laning.", _nav("bk:s"), message)
            return
        page = int(st.get("dp", 0))
        per = 8
        chunk = days[page * per : (page + 1) * per]
        rows = []
        for i in range(0, len(chunk), 2):
            rows.append([{"text": fmt_day(d), "callback_data": f"bk:d:{d:%Y%m%d}"} for d in chunk[i : i + 2]])
        nav = []
        if page > 0:
            nav.append({"text": "◀️", "callback_data": f"bk:g:{page - 1}"})
        if (page + 1) * per < len(days):
            nav.append({"text": "▶️", "callback_data": f"bk:g:{page + 1}"})
        if nav:
            rows.append(nav)
        await _show(runner, bot, chat_id, head + f"✨ <b>{esc(service['title'])}</b> · {service['minutes']} daqiqa\n\n📅 Qaysi kun qulay?", rows + _nav("bk:s" if len(staff) or len(services) > 1 else None), message)
        return
    day = datetime.datetime.strptime(st["date"], "%Y%m%d").date()
    if not st.get("time"):
        slots = await slots_for(bot, service, staff_id, day)
        if not slots:
            st.pop("date", None)
            await _save(runner, bot, chat_id, st)
            await step(runner, bot, chat_id, st, message, header="😔 Bu kunga bo'sh vaqt qolmadi — boshqa kun tanlang")
            return
        buttons = [{"text": bk.hm(t), "callback_data": f"bk:t:{t // 60:02d}{t % 60:02d}"} for t, _ in slots[:36]]
        rows = [buttons[i : i + 4] for i in range(0, len(buttons), 4)]
        await _show(runner, bot, chat_id, head + f"✨ <b>{esc(service['title'])}</b>\n📅 {fmt_day(day)}\n\n🕘 Vaqtni tanlang:", rows + _nav("bk:g:0"), message)
        return
    # sana va vaqt tanlandi — ma'lumotlarni so'raymiz
    await runner.redis.set(_sk(bot, chat_id), json.dumps(st), ex=TTL)
    user = st.get("user") or {"id": chat_id}
    await runner.start_form(bot, chat_id, BOOKING_ID, user)


def booking_form(bot: "RunningBot") -> dict:
    steps = [{"key": f["key"], "question": f["label"], "type": f.get("type", "text"), "options": f.get("options") or []} for f in cfg(bot).get("fields") or []]
    return {"id": BOOKING_ID, "title": "📅 Yozilish", "steps": steps, "done_text": "", "target": None, "notify": False}


async def on_callback(runner, bot, chat_id: int, data: str, message: dict, user: dict, query_id: str) -> None:
    parts = data.split(":")
    cmd = parts[1] if len(parts) > 1 else ""
    arg = parts[2] if len(parts) > 2 else ""
    await runner.answer(bot, query_id)
    if cmd == "s":
        st = {}
        await _save(runner, bot, chat_id, st)
        await step(runner, bot, chat_id, st, message)
        return
    if cmd == "m":
        await render_mine(runner, bot, chat_id, message=message)
        return
    if cmd == "c":
        await _cancel_ask(runner, bot, chat_id, int(arg), message)
        return
    if cmd == "y":
        await _cancel_do(runner, bot, chat_id, int(arg), user, message)
        return
    st = await _state(runner, bot, chat_id)
    st["user"] = {k: user.get(k) for k in ("id", "first_name", "username") if user.get(k) is not None}
    if cmd == "v" and _service(bot, arg):
        st = {"svc": arg, "user": st["user"]}
    elif cmd == "f" and (arg == "*" or any(s["id"] == arg for s in _staff_list(bot))):
        st.update(staff=arg)
        st.pop("date", None)
    elif cmd == "g":
        st.update(dp=int(arg) if arg.isdigit() else 0)
        st.pop("date", None)
        st.pop("time", None)
    elif cmd == "d" and re.fullmatch(r"\d{8}", arg):
        st.update(date=arg)
        st.pop("time", None)
    elif cmd == "t" and re.fullmatch(r"\d{4}", arg):
        st.update(time=arg)
    await _save(runner, bot, chat_id, st)
    await step(runner, bot, chat_id, st, message)


# ============================================================
# Yaratish (forma tugagach)
# ============================================================


async def finish(runner, bot, chat_id: int, user: dict, data: dict) -> None:
    st = await _state(runner, bot, chat_id)
    service = _service(bot, st.get("svc"))
    if service is None or not st.get("date") or not st.get("time"):
        await runner.api(bot, "sendMessage", {"chat_id": chat_id, "text": "⚠️ Yozilish ma'lumotlari eskirgan — qaytadan boshlang.", "reply_markup": {"remove_keyboard": True}})
        return
    b = cfg(bot)
    day = datetime.datetime.strptime(st["date"], "%Y%m%d").date()
    minute = int(st["time"][:2]) * 60 + int(st["time"][2:])
    staff = _staff_list(bot)
    staff_id = st.get("staff") or "main"
    if getattr(bot, "sandbox", False):
        await runner.redis.delete(_sk(bot, chat_id))
        await runner.api(bot, "sendMessage", {"chat_id": chat_id, "text": "🧪 Sinov rejimi: yozilish to'g'ri yig'ildi, lekin saqlanmadi.", "reply_markup": {"remove_keyboard": True}})
        return
    starts = bk.to_utc(b, day, minute)
    created: BotBooking | None = None
    async with async_session() as db:
        await db.execute(text("select pg_advisory_xact_lock(:a, 7)"), {"a": bot.bot_id})
        candidates = [s["id"] for s in staff] if staff_id == "*" else [staff_id]
        chosen = None
        for sid in candidates:
            busy = (await _busy(db, bot.bot_id, b, day, [sid]))[sid]
            if minute in bk.free_slots({**b, "min_notice": 0}, service["minutes"], day, busy, datetime.datetime.min):
                chosen = sid
                break
        if chosen is not None:
            number = int(await db.scalar(select(func.coalesce(func.max(BotBooking.number), 0)).where(BotBooking.bot_id == bot.bot_id)) or 0) + 1
            title = next((s["title"] for s in staff if s["id"] == chosen), "")
            created = BotBooking(
                bot_id=bot.bot_id, number=number, tg_user_id=chat_id, service_id=service["id"], service_title=service["title"], staff_id=chosen, staff_title=title,
                starts_at=starts, minutes=service["minutes"], price=service["price"], data=data, reminded=[],
                status="confirmed" if b.get("confirm") == "auto" else "pending",
            )
            db.add(created)
            await db.commit()
            await db.refresh(created)
    await runner.redis.delete(_sk(bot, chat_id))
    if created is None:
        await runner.api(bot, "sendMessage", {"chat_id": chat_id, "text": "😔 Afsuski, bu vaqtni boshqa mijoz band qilib qo'ydi. Boshqa vaqt tanlang 👇", "reply_markup": {"remove_keyboard": True}})
        await render_start(runner, bot, chat_id)
        return
    await stats.track(runner, bot, "book")
    integrations.emit(runner, bot, "booking.created", {"number": created.number, "service": service["title"], "staff": created.staff_title, "starts_at": fmt_when(b, created.starts_at), "minutes": created.minutes, "price": created.price, "status": created.status, "customer_id": chat_id, "answers": data})
    await runner.set_vars(bot, user["id"], {k: v for k, v in data.items() if k})
    vals = await runner.values(bot, user)
    when = fmt_when(b, created.starts_at)
    vals.update({"booking": str(created.number), "service": service["title"], "when": when, "staff": created.staff_title})
    done = fill(b.get("done_text") or "", vals, escape=True)
    if created.status == "pending":
        done += "\n\n⏳ Administrator tez orada tasdiqlaydi."
    cur_page = await runner.current_page(bot, chat_id)
    markup = await runner.menu_markup(bot, chat_id, cur_page, vals) if cur_page else None
    await runner.api(bot, "sendMessage", {"chat_id": chat_id, "text": done, "parse_mode": "HTML", "reply_markup": markup or {"remove_keyboard": True}})
    who = esc(user.get("first_name") or "Mijoz") + (f" (@{esc(user['username'])})" if user.get("username") else "") + f" · <code>{chat_id}</code>"
    body = booking_text(bot, created, who)
    for admin_chat in runner.admin_chats(bot):
        try:
            sent = await runner.api(
                bot, "sendMessage", {"chat_id": admin_chat, "text": "🆕 Yangi yozilish\n\n" + body, "parse_mode": "HTML", "reply_markup": {"inline_keyboard": admin_rows(created)}}
            )
            await runner.redis.set(f"ub:{bot.bot_id}:fb:{admin_chat}:{sent['message_id']}", chat_id, ex=TTL * 24 * 30)
        except BotApiError:
            pass


def booking_text(bot: "RunningBot", row: BotBooking, who: str | None = None) -> str:
    b = cfg(bot)
    lines = [f"📅 <b>Yozilish #{row.number}</b> · {STATUS.get(row.status, row.status)}"]
    if who:
        lines.append(f"👤 {who}")
    lines.append(f"✨ {esc(row.service_title)} · {row.minutes} daq" + (f" · {money(row.price, 'so‘m')}" if row.price else ""))
    if row.staff_title:
        lines.append(f"👨‍⚕️ {esc(row.staff_title)}")
    lines.append(f"🕘 <b>{fmt_when(b, row.starts_at)}</b>")
    for f in b.get("fields") or []:
        v = (row.data or {}).get(f["key"])
        if v:
            lines.append(f"• {esc(f['label'][:30])} {esc(v)}")
    return "\n".join(lines)


def admin_rows(row: BotBooking) -> list:
    rows = []
    if row.status == "pending":
        rows.append([{"text": "✅ Tasdiqlash", "callback_data": f"bm:st:{row.id}:confirmed"}, {"text": "❌ Rad etish", "callback_data": f"bm:st:{row.id}:cancelled"}])
    elif row.status == "confirmed":
        rows.append([{"text": "✔️ Bajarildi", "callback_data": f"bm:st:{row.id}:done"}, {"text": "❌ Bekor", "callback_data": f"bm:st:{row.id}:cancelled"}])
    return rows


async def set_status(runner, bot, booking_id: int, status: str, message: dict | None) -> None:
    if status not in STATUS:
        return
    async with async_session() as db:
        row = await db.get(BotBooking, booking_id)
        if row is None or row.bot_id != bot.bot_id:
            return
        changed = row.status != status
        row.status = status
        await db.commit()
        await db.refresh(row)
    if message is not None:
        try:
            await runner.api(
                bot, "editMessageText",
                {"chat_id": message["chat"]["id"], "message_id": message["message_id"], "text": booking_text(bot, row), "parse_mode": "HTML", "reply_markup": {"inline_keyboard": admin_rows(row)}},
            )
        except BotApiError:
            pass
    if changed:
        integrations.emit(runner, bot, "booking.status", {"number": row.number, "status": row.status, "service": row.service_title, "starts_at": fmt_when(cfg(bot), row.starts_at), "customer_id": row.tg_user_id})
        b = cfg(bot)
        note = {"confirmed": "✅ Yozilishingiz tasdiqlandi!", "cancelled": "❌ Afsuski, yozilishingiz bekor qilindi.", "done": "🙏 Tashrifingiz uchun rahmat!"}.get(status)
        if note:
            try:
                await runner.api(
                    bot, "sendMessage",
                    {"chat_id": row.tg_user_id, "text": f"{note}\n\n<b>#{row.number}</b> · {esc(row.service_title)}\n📅 {fmt_when(b, row.starts_at)}", "parse_mode": "HTML"},
                )
            except BotApiError:
                pass


# ============================================================
# Yozilishlarim
# ============================================================


async def _upcoming(bot: "RunningBot", chat_id: int) -> list[BotBooking]:
    async with async_session() as db:
        return list(
            (
                await db.scalars(
                    select(BotBooking)
                    .where(BotBooking.bot_id == bot.bot_id, BotBooking.tg_user_id == chat_id, BotBooking.status.in_(ACTIVE), BotBooking.starts_at >= datetime.datetime.now(datetime.timezone.utc))
                    .order_by(BotBooking.starts_at)
                    .limit(10)
                )
            ).all()
        )


async def render_mine(runner, bot, chat_id: int, *, message: dict | None = None) -> None:
    rows_db = await _upcoming(bot, chat_id)
    b = cfg(bot)
    if not rows_db:
        await _show(runner, bot, chat_id, "📋 <b>Yozilishlarim</b>\n\nYaqin kunlarga yozilishingiz yo'q.", [[{"text": "📅 Yozilish", "callback_data": "bk:s"}]], message)
        return
    lines = ["📋 <b>Yozilishlarim</b>", ""]
    rows = []
    for r in rows_db:
        lines.append(f"<b>#{r.number}</b> · {esc(r.service_title)}\n📅 {fmt_when(b, r.starts_at)} · {STATUS[r.status]}")
        rows.append([{"text": f"❌ #{r.number} ni bekor qilish", "callback_data": f"bk:c:{r.id}"}])
    rows.append([{"text": "📅 Yangi yozilish", "callback_data": "bk:s"}])
    await _show(runner, bot, chat_id, "\n\n".join([lines[0], "\n\n".join(lines[2:])]), rows, message)


async def _cancel_ask(runner, bot, chat_id: int, booking_id: int, message: dict) -> None:
    await _show(
        runner, bot, chat_id, "Yozilishni bekor qilamizmi?",
        [[{"text": "✅ Ha, bekor qilish", "callback_data": f"bk:y:{booking_id}"}, {"text": "↩️ Yo'q", "callback_data": "bk:m"}]], message,
    )


async def _cancel_do(runner, bot, chat_id: int, booking_id: int, user: dict, message: dict) -> None:
    async with async_session() as db:
        row = await db.get(BotBooking, booking_id)
        if row is None or row.bot_id != bot.bot_id or row.tg_user_id != chat_id or row.status not in ACTIVE:
            await render_mine(runner, bot, chat_id, message=message)
            return
        row.status = "cancelled"
        await db.commit()
        await db.refresh(row)
    who = esc(user.get("first_name") or "Mijoz") + f" · <code>{chat_id}</code>"
    for admin_chat in runner.admin_chats(bot):
        try:
            await runner.api(bot, "sendMessage", {"chat_id": admin_chat, "text": "🚫 Mijoz yozilishni bekor qildi\n\n" + booking_text(bot, row, who), "parse_mode": "HTML"})
        except BotApiError:
            pass
    await render_mine(runner, bot, chat_id, message=message)


async def render_module(runner, bot, chat_id: int, page: dict, vals: dict, *, message: dict | None = None) -> bool:
    kind = (page.get("module") or {}).get("type")
    if kind == "booking":
        first = next((m for m in page.get("messages") or [] if m.get("type") == "text"), None)
        header = fill(first["text"], vals, escape=True) if first else None
        await render_start(runner, bot, chat_id, message=message, header=header)
    elif kind == "mybookings":
        await render_mine(runner, bot, chat_id, message=message)
    else:
        return False
    return True


# ============================================================
# Eslatmalar
# ============================================================


async def reminder_tick(runner: "Runner") -> None:
    now = datetime.datetime.now(datetime.timezone.utc)
    for bot in list(runner.bots.values()):
        b = cfg(bot)
        if not b.get("enabled") or not b.get("remind"):
            continue
        horizon = now + datetime.timedelta(hours=max(b["remind"]))
        async with async_session() as db:
            rows = (
                await db.scalars(
                    select(BotBooking).where(BotBooking.bot_id == bot.bot_id, BotBooking.status == "confirmed", BotBooking.starts_at > now, BotBooking.starts_at <= horizon)
                )
            ).all()
            for row in rows:
                left = (row.starts_at - now).total_seconds() / 3600
                due = [h for h in b["remind"] if left <= h and h not in (row.reminded or []) and row.created_at <= row.starts_at - datetime.timedelta(hours=h)]
                if not due:
                    continue
                # eng yaqin (kichik) soat — bitta xabar; kattalari ham belgilanadi
                row.reminded = sorted(set((row.reminded or []) + [h for h in b["remind"] if h >= min(due)]))
                try:
                    await runner.api(
                        bot, "sendMessage",
                        {
                            "chat_id": row.tg_user_id,
                            "text": f"⏰ <b>Eslatma</b>\n\n{esc(row.service_title)}\n📅 {fmt_when(b, row.starts_at)}\n\nKelolmasangiz — oldindan bekor qiling.",
                            "parse_mode": "HTML",
                            "reply_markup": {"inline_keyboard": [[{"text": "📋 Yozilishlarim", "callback_data": "bk:m"}]]},
                        },
                    )
                except BotApiError:
                    pass
            await db.commit()


# ============================================================
# Egasi: /admin → 📅 Yozilishlar
# ============================================================

PRESETS = {
    "1": "Du-Sha 09:00-18:00\nYa yopiq",
    "2": "Du-Ya 09:00-21:00",
    "3": "Du-Ju 10:00-19:00\nSha 10:00-15:00\nYa yopiq",
}
CYCLES = {"days": ("days_ahead", [7, 14, 30, 60]), "step": ("step", [15, 30, 60]), "notice": ("min_notice", [0, 1, 2, 4, 12, 24])}


def _b(m: dict) -> dict:
    from core.botbuilder import Booking

    return m.setdefault("booking", Booking().model_dump())


def _new_id(existing: list[dict]) -> str:
    ids = {x["id"] for x in existing}
    while True:
        i = new_page_id()
        if i not in ids:
            return i


async def _counts(bot: "RunningBot") -> dict:
    b = cfg(bot)
    now = datetime.datetime.now(datetime.timezone.utc)
    day = bk.local_now(b).date()
    lo, hi = bk.to_utc(b, day, 0), bk.to_utc(b, day, 24 * 60)
    async with async_session() as db:
        base = select(func.count(BotBooking.id)).where(BotBooking.bot_id == bot.bot_id)
        pending = await db.scalar(base.where(BotBooking.status == "pending", BotBooking.starts_at >= now))
        today = await db.scalar(base.where(BotBooking.status.in_(ACTIVE), BotBooking.starts_at >= lo, BotBooking.starts_at < hi))
        upcoming = await db.scalar(base.where(BotBooking.status.in_(ACTIVE), BotBooking.starts_at >= now))
    return {"pending": pending or 0, "today": today or 0, "upcoming": upcoming or 0}


async def admin_home(runner, bot, chat_id: int, message: dict | None = None) -> None:
    import editor

    b = cfg(bot)
    c = await _counts(bot)
    text_ = (
        f"📅 <b>Yozilishlar</b> — {'✅ ishlayapti' if b.get('enabled') else '❌ o‘chiq'}\n\n"
        f"⏳ Tasdiq kutayotgan: <b>{c['pending']}</b>\n📆 Bugun: <b>{c['today']}</b> · yaqin kunlarda: {c['upcoming']}\n\n"
        f"✨ Xizmatlar: {len(b.get('services') or [])} · 👤 Xodimlar: {len(b.get('staff') or []) or 'yo‘q (bitta)'}\n"
        f"🕘 Tasdiqlash: {'avtomatik' if b.get('confirm') == 'auto' else 'siz tasdiqlaysiz'}"
    )
    rows = [
        [{"text": f"⏳ Kutayotganlar ({c['pending']})", "callback_data": "bm:l:p"}, {"text": f"📆 Bugun ({c['today']})", "callback_data": "bm:l:t"}],
        [{"text": "📋 Yaqin yozilishlar", "callback_data": "bm:l:u"}],
        [{"text": "✨ Xizmatlar", "callback_data": "bm:svc"}, {"text": "👤 Xodimlar", "callback_data": "bm:stf"}],
        [{"text": "🕘 Ish jadvali", "callback_data": "bm:hrs"}, {"text": "⚙️ Sozlamalar", "callback_data": "bm:cfg"}],
        [{"text": "⬅️ Panel", "callback_data": "adm:st"}],
    ]
    await editor.send(runner, bot, chat_id, text_, rows, message=message)


async def _list(runner, bot, chat_id: int, kind: str, message: dict | None) -> None:
    import editor

    b = cfg(bot)
    now = datetime.datetime.now(datetime.timezone.utc)
    q = select(BotBooking).where(BotBooking.bot_id == bot.bot_id)
    title = "📋 Yaqin yozilishlar"
    if kind == "p":
        q = q.where(BotBooking.status == "pending", BotBooking.starts_at >= now)
        title = "⏳ Tasdiq kutayotganlar"
    elif kind == "t":
        day = bk.local_now(b).date()
        q = q.where(BotBooking.status.in_(ACTIVE), BotBooking.starts_at >= bk.to_utc(b, day, 0), BotBooking.starts_at < bk.to_utc(b, day, 24 * 60))
        title = "📆 Bugungi yozilishlar"
    else:
        q = q.where(BotBooking.status.in_(ACTIVE), BotBooking.starts_at >= now)
    async with async_session() as db:
        rows_db = (await db.scalars(q.order_by(BotBooking.starts_at).limit(20))).all()
    rows = [
        [{"text": f"{'⏳' if r.status == 'pending' else '✅'} {bk.to_local(b, r.starts_at):%d.%m %H:%M} · {r.service_title}"[:64], "callback_data": f"bm:o:{r.id}"}] for r in rows_db
    ]
    rows.append([{"text": "⬅️ Yozilishlar", "callback_data": "bm:home"}])
    await editor.send(runner, bot, chat_id, f"{title}\n\n" + ("Hozircha yo'q." if not rows_db else "Batafsil uchun bosing."), rows, message=message)


def _parse_service(text_: str) -> tuple[str, int, int] | None:
    parts = [p.strip() for p in re.split(r"[\n|;]|,(?=\s*\d)", text_ or "") if p.strip()]
    if not parts:
        return None
    name = parts[0]
    nums = []
    for p in parts[1:]:
        digits = re.sub(r"[^\d]", "", p)
        if digits:
            mult = 1000 if re.search(r"\bming\b|\bk\b", p, re.I) else 1
            nums.append(int(digits) * mult)
    if len(parts) == 1:
        m = re.match(r"^(.*?)\s+(\d{1,3})\s*(?:daq\w*|min\w*)?\s+(\d[\d\s]*?)\s*(ming|k|so'?m|sum)?\.?$", name, re.I)
        if m:
            mult = 1000 if (m.group(4) or "").lower() in ("ming", "k") else 1
            name, nums = m.group(1).strip(), [int(m.group(2)), int(re.sub(r"\s", "", m.group(3))) * mult]
    minutes = nums[0] if nums and 5 <= nums[0] <= 720 else 30
    price = nums[1] if len(nums) > 1 else 0
    return name[:64], minutes, price


async def admin_callback(runner, bot, chat_id: int, data: str, message: dict, user: dict) -> None:
    import admin
    import editor

    parts = data.split(":")
    cmd = parts[1] if len(parts) > 1 else ""
    arg = parts[2] if len(parts) > 2 else ""
    b = cfg(bot)

    async def save(fn) -> bool:
        error = await editor.save(runner, bot, fn)
        if error:
            await runner.api(bot, "sendMessage", {"chat_id": chat_id, "text": f"⚠️ {error}"})
            return False
        return True

    if cmd == "home":
        await admin.set_state(runner, bot, chat_id, None)
        await admin_home(runner, bot, chat_id, message)
    elif cmd == "l":
        await _list(runner, bot, chat_id, arg, message)
    elif cmd == "o":
        async with async_session() as db:
            row = await db.get(BotBooking, int(arg))
        if row and row.bot_id == bot.bot_id:
            who = f"<code>{row.tg_user_id}</code>"
            rows = admin_rows(row) + [[{"text": "⬅️ Yozilishlar", "callback_data": "bm:home"}]]
            await editor.send(runner, bot, chat_id, booking_text(bot, row, who), rows, message=message)
    elif cmd == "st":
        await set_status(runner, bot, int(arg), parts[3] if len(parts) > 3 else "", message)
    elif cmd == "svc":
        rows = [[{"text": f"{s['title']} · {s['minutes']} daq" + (f" · {money(s['price'], 'so‘m')}" if s["price"] else "")[:40], "callback_data": f"bm:sv:{s['id']}"}] for s in b.get("services") or []]
        rows.append([{"text": "➕ Xizmat qo'shish", "callback_data": "bm:sa"}, {"text": "⬅️ Yozilishlar", "callback_data": "bm:home"}])
        await editor.send(runner, bot, chat_id, "✨ <b>Xizmatlar</b>\n\nTahrirlash uchun xizmatni bosing.", rows, message=message)
    elif cmd == "sa":
        await admin.ask(
            runner, bot, chat_id, {"k": "bk_svc"},
            "✨ Xizmatni yuboring: nom, davomiyligi (daqiqa), narxi.\n\n<code>Soch olish\n45\n80000</code>\n\nyoki bir qatorda: <code>Manikyur 60 120000</code>. Bir nechta xizmatni ketma-ket yuborishingiz mumkin. Tugatish: /cancel",
        )
    elif cmd == "sv":
        s = next((x for x in b.get("services") or [] if x["id"] == arg), None)
        if s:
            rows = [
                [{"text": "💰 Narxi", "callback_data": f"bm:sp:{arg}"}, {"text": "⏱ Davomiyligi", "callback_data": f"bm:sm:{arg}"}],
                [{"text": "🗑 O'chirish", "callback_data": f"bm:sx:{arg}"}, {"text": "⬅️ Xizmatlar", "callback_data": "bm:svc"}],
            ]
            await editor.send(runner, bot, chat_id, f"✨ <b>{esc(s['title'])}</b>\n⏱ {s['minutes']} daqiqa\n💰 {money(s['price'], 'so‘m')}", rows, message=message)
    elif cmd in ("sp", "sm"):
        await admin.ask(runner, bot, chat_id, {"k": "bk_sedit", "f": cmd, "id": arg}, "💰 Yangi narxni yuboring (raqam)." if cmd == "sp" else "⏱ Yangi davomiylikni yuboring (daqiqada, masalan 45).")
    elif cmd == "sx":
        if await save(lambda m: _b(m).update(services=[s for s in _b(m)["services"] if s["id"] != arg])):
            await admin_callback(runner, bot, chat_id, "bm:svc", message, user)
    elif cmd == "stf":
        rows = [[{"text": f"👤 {s['title']}  🗑", "callback_data": f"bm:fx:{s['id']}"}] for s in b.get("staff") or []]
        rows.append([{"text": "➕ Xodim qo'shish", "callback_data": "bm:fa"}, {"text": "⬅️ Yozilishlar", "callback_data": "bm:home"}])
        await editor.send(
            runner, bot, chat_id,
            "👤 <b>Xodimlar</b> (mutaxassislar)\n\nXodim qo'shilsa, mijoz kimga yozilishni tanlaydi va har birining vaqti alohida hisoblanadi. Xodim bo'lmasa — bitta umumiy jadval.\n\n🗑 — o'chirish uchun bosing.",
            rows, message=message,
        )
    elif cmd == "fa":
        await admin.ask(runner, bot, chat_id, {"k": "bk_stf"}, "👤 Xodim ismini yuboring (bir nechta bo'lsa — har birini yangi qatordan). Tugatish: /cancel")
    elif cmd == "fx":
        if await save(lambda m: _b(m).update(staff=[s for s in _b(m)["staff"] if s["id"] != arg])):
            await admin_callback(runner, bot, chat_id, "bm:stf", message, user)
    elif cmd == "hrs":
        import home
        from core.botbuilder import DEFAULT_HOURS

        await home.set_flag(runner, bot, "hours")
        rows = [
            [{"text": "Du–Sha 09–18 · Ya dam", "callback_data": "bm:hp:1"}],
            [{"text": "Har kuni 09–21", "callback_data": "bm:hp:2"}],
            [{"text": "Du–Ju 10–19 · Sha 10–15 · Ya dam", "callback_data": "bm:hp:3"}],
            [{"text": "✍️ O'zim yozaman", "callback_data": "bm:hc"}, {"text": "⬅️ Yozilishlar", "callback_data": "bm:home"}],
        ]
        await editor.send(runner, bot, chat_id, "🕘 <b>Ish jadvali</b>\n\n" + esc(bk.hours_text(b.get("hours") or DEFAULT_HOURS)) + "\n\nTayyor variantni tanlang:", rows, message=message)
    elif cmd == "hp":
        hours = bk.parse_hours(PRESETS.get(arg, ""))
        if hours and await save(lambda m: _b(m).update(hours=hours)):
            await admin_callback(runner, bot, chat_id, "bm:hrs", message, user)
    elif cmd == "hc":
        await admin.ask(
            runner, bot, chat_id, {"k": "bk_hours"},
            "✍️ Jadvalni yozing, har qatorga bitta:\n\n<code>Du-Ju 09:00-18:00\nSha 10:00-14:00\nYa yopiq</code>\n\nKunlar: Du Se Chor Pay Ju Sha Ya",
        )
    elif cmd == "cfg":
        await _cfg_view(runner, bot, chat_id, message)
    elif cmd == "conf":
        if await save(lambda m: _b(m).update(confirm="auto" if _b(m).get("confirm") != "auto" else "manual")):
            await _cfg_view(runner, bot, chat_id, message)
    elif cmd == "cyc" and arg in CYCLES:
        field, values = CYCLES[arg]
        cur = b.get(field)
        nxt = values[(values.index(cur) + 1) % len(values)] if cur in values else values[0]
        if await save(lambda m: _b(m).update({field: nxt})):
            await _cfg_view(runner, bot, chat_id, message)
    elif cmd == "rem":
        options = [[24, 2], [2], [24], []]
        cur = b.get("remind") or []
        nxt = options[(options.index(cur) + 1) % len(options)] if cur in options else options[0]
        if await save(lambda m: _b(m).update(remind=nxt)):
            await _cfg_view(runner, bot, chat_id, message)
    elif cmd == "tog":
        if await save(lambda m: _b(m).update(enabled=not _b(m).get("enabled"))):
            await admin_home(runner, bot, chat_id, message)


async def _cfg_view(runner, bot, chat_id: int, message: dict | None) -> None:
    import editor

    b = cfg(bot)
    rem = ", ".join(f"{h} soat" for h in b.get("remind") or []) or "o'chiq"
    text_ = (
        "⚙️ <b>Yozilish sozlamalari</b>\n\n"
        f"✅ Tasdiqlash: {'avtomatik' if b.get('confirm') == 'auto' else 'siz tasdiqlaysiz'}\n"
        f"📅 Necha kun oldindan yozilish mumkin: {b.get('days_ahead')}\n"
        f"🕘 Vaqt oralig'i: {b.get('step')} daqiqa\n"
        f"⏳ Eng kamida: {b.get('min_notice')} soat oldin\n"
        f"⏰ Eslatma: {rem} oldin"
    )
    rows = [
        [{"text": "✅ Tasdiqlash usuli", "callback_data": "bm:conf"}, {"text": "⏰ Eslatma", "callback_data": "bm:rem"}],
        [{"text": "📅 Kunlar", "callback_data": "bm:cyc:days"}, {"text": "🕘 Oraliq", "callback_data": "bm:cyc:step"}, {"text": "⏳ Oldindan", "callback_data": "bm:cyc:notice"}],
        [{"text": "⏸ O'chirish" if b.get("enabled") else "▶️ Yoqish", "callback_data": "bm:tog"}, {"text": "⬅️ Yozilishlar", "callback_data": "bm:home"}],
    ]
    await editor.send(runner, bot, chat_id, text_, rows, message=message)


async def admin_input(runner, bot, chat_id: int, message: dict, state: dict) -> bool:
    import admin
    import editor

    kind = state.get("k", "")
    if not kind.startswith("bk_"):
        return False
    text_ = (message.get("text") or "").strip()

    async def say(t: str, rows: list | None = None) -> None:
        await editor.send(runner, bot, chat_id, t, rows)

    async def save(fn) -> bool:
        error = await editor.save(runner, bot, fn)
        if error:
            await say(f"⚠️ {esc(error)}")
            return False
        return True

    if kind == "bk_svc":
        parsed = _parse_service(text_)
        if not parsed:
            await say("⚠️ Xizmat nomini yuboring")
            return True
        name, minutes, price = parsed
        svc = {"id": _new_id(cfg(bot).get("services") or []), "title": name, "minutes": minutes, "price": price}
        if not await save(lambda m: _b(m).setdefault("services", []).append(svc)):
            return True
        await say(f"✅ «{esc(name)}» — {minutes} daq, {money(price, 'so‘m')}. Yana yuboring yoki tugating.", [[{"text": "✅ Tayyor", "callback_data": "bm:svc"}]])
        return True
    if kind == "bk_sedit":
        digits = re.sub(r"[^\d]", "", text_)
        if not digits:
            await say("⚠️ Raqam yuboring")
            return True
        value = int(digits) * (1000 if re.search(r"\bming\b|\bk\b", text_, re.I) else 1)
        field = "price" if state["f"] == "sp" else "minutes"
        sid = state["id"]
        if field == "minutes" and not 5 <= value <= 720:
            await say("⚠️ 5 dan 720 gacha daqiqa")
            return True
        if await save(lambda m: next(s for s in _b(m)["services"] if s["id"] == sid).update({field: value})):
            await admin.set_state(runner, bot, chat_id, None)
            await admin_callback(runner, bot, chat_id, f"bm:sv:{sid}", None, {})
        return True
    if kind == "bk_stf":
        names = [n.strip()[:64] for n in text_.splitlines() if n.strip()][:10]
        if not names:
            await say("⚠️ Ism yuboring")
            return True
        existing = list(cfg(bot).get("staff") or [])
        new = []
        for n in names:
            new.append({"id": _new_id(existing + new), "title": n})
        if await save(lambda m: _b(m).setdefault("staff", []).extend(new)):
            await admin.set_state(runner, bot, chat_id, None)
            await admin_callback(runner, bot, chat_id, "bm:stf", None, {})
        return True
    if kind == "bk_hours":
        hours = bk.parse_hours(text_)
        if hours is None:
            await say("⚠️ Tushunmadim. Namuna:\n<code>Du-Ju 09:00-18:00\nSha 10:00-14:00\nYa yopiq</code>")
            return True
        if await save(lambda m: _b(m).update(hours=hours)):
            await admin.set_state(runner, bot, chat_id, None)
            await admin_callback(runner, bot, chat_id, "bm:hrs", None, {})
        return True
    return False
