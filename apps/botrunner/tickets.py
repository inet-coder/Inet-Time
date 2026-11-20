"""🎫 Murojaatlar (tiketlar), operatorlar va shablon javoblar.

Tiket yoqilganda (menu.tickets.enabled) qayta aloqa xabarlari raqamli murojaatga (#1, #2...) aylanadi:
    • foydalanuvchining ochiq murojaati bo'lsa — yangi xabar shunga qo'shiladi, yo'q bo'lsa — yangisi ochiladi;
    • mas'ul bo'lmasa — hamma xodimga (egasi, adminlar, operatorlar) tushadi; «🙋 Meniki» bosgan yoki birinchi javob bergan
      xodim mas'ul bo'ladi, keyingi xabarlar faqat unga boradi;
    • xodim xabarga «Reply» qiladi yoki «📝 Shablon» dan tayyor javob yuboradi; «✅ Yopish» — mijozga baho so'rovi.
Xodim callbacklari `tk:*`, mijoz bahosi `tr:*`. Operatorlar (menu.operators) panelni ko'rmaydi — faqat murojaatlar."""

import datetime
import html
from typing import TYPE_CHECKING

from sqlalchemy import func, select

from core.botapi import BotApiError
from core.botbuilder import fill, new_page_id
from core.db.base import async_session
from core.db.models import BotTicket

import integrations
import stats

if TYPE_CHECKING:
    from main import Runner, RunningBot

TTL = 90 * 24 * 3600


def esc(t) -> str:
    return html.escape(str(t or ""), quote=False)


def enabled(bot: "RunningBot") -> bool:
    return bool((bot.menu.get("tickets") or {}).get("enabled"))


def operators(bot: "RunningBot") -> list[int]:
    return list(bot.menu.get("operators") or [])


def staff_chats(runner: "Runner", bot: "RunningBot") -> list[int]:
    return runner.admin_chats(bot) + [o for o in operators(bot) if o not in runner.admin_chats(bot)]


def is_staff(runner: "Runner", bot: "RunningBot", chat_id: int) -> bool:
    return runner.is_admin(bot, chat_id) or chat_id in operators(bot)


def _who(user: dict, anonymous: bool) -> str:
    if anonymous:
        return "Anonim"
    name = esc(user.get("first_name") or "Foydalanuvchi")
    return name + (f" (@{esc(user['username'])})" if user.get("username") else "")


def rows_for(t: BotTicket) -> list:
    if t.status == "closed":
        return [[{"text": "♻️ Qayta ochish", "callback_data": f"tk:re:{t.id}"}]]
    return [
        [{"text": "🙋 Meniki" if t.assignee is None else "🙋 O'zimga olish", "callback_data": f"tk:take:{t.id}"}, {"text": "📝 Shablon", "callback_data": f"tk:tpl:{t.id}"}],
        [{"text": "✅ Yopish", "callback_data": f"tk:close:{t.id}"}],
    ]


def head_text(t: BotTicket, who: str, *, fresh: bool, operator_name: str | None = None) -> str:
    state = "🆕 Yangi murojaat" if fresh else "💬 Yangi xabar"
    owner = f"\n👤 Mas'ul: {esc(operator_name)}" if operator_name else ("\n👤 Mas'ul: yo'q" if t.assignee is None else "")
    return f"🎫 <b>#{t.number}</b> · {state}\n{who} · <code>{t.tg_user_id}</code>{owner}\n\n↩️ Javob uchun shu xabarlarga «Reply» qiling."


# ============================================================
# Qabul qilish
# ============================================================


async def intake(runner: "Runner", bot: "RunningBot", message: dict, user: dict) -> None:
    chat_id = message["chat"]["id"]
    anonymous = bool(bot.menu.get("feedback_anonymous"))
    preview = (message.get("text") or message.get("caption") or "[media]").strip()[:200]
    async with async_session() as db:
        t = await db.scalar(select(BotTicket).where(BotTicket.bot_id == bot.bot_id, BotTicket.tg_user_id == chat_id, BotTicket.status == "open").order_by(BotTicket.id.desc()))
        fresh = t is None
        if fresh:
            number = int(await db.scalar(select(func.coalesce(func.max(BotTicket.number), 0)).where(BotTicket.bot_id == bot.bot_id)) or 0) + 1
            t = BotTicket(bot_id=bot.bot_id, number=number, tg_user_id=chat_id, preview=preview, messages=1)
            db.add(t)
        else:
            t.messages += 1
        await db.commit()
        await db.refresh(t)
    who = _who(user, anonymous)
    targets = [t.assignee] if t.assignee else staff_chats(runner, bot)
    delivered = False
    for chat in targets:
        try:
            head = await runner.api(bot, "sendMessage", {"chat_id": chat, "text": head_text(t, who, fresh=fresh), "parse_mode": "HTML", "reply_markup": {"inline_keyboard": rows_for(t)}})
            copied = await runner.api(bot, "copyMessage", {"chat_id": chat, "from_chat_id": chat_id, "message_id": message["message_id"]})
        except BotApiError:
            continue
        delivered = True
        for msg_id in (head["message_id"], copied["message_id"]):
            await runner.redis.set(f"ub:{bot.bot_id}:fb:{chat}:{msg_id}", chat_id, ex=TTL)
            await runner.redis.set(f"ub:{bot.bot_id}:tkm:{chat}:{msg_id}", t.id, ex=TTL)
    if not delivered and t.assignee:  # mas'ul xodimga yetmadi — hammaga
        for chat in staff_chats(runner, bot):
            try:
                head = await runner.api(bot, "sendMessage", {"chat_id": chat, "text": head_text(t, who, fresh=fresh), "parse_mode": "HTML", "reply_markup": {"inline_keyboard": rows_for(t)}})
                copied = await runner.api(bot, "copyMessage", {"chat_id": chat, "from_chat_id": chat_id, "message_id": message["message_id"]})
            except BotApiError:
                continue
            delivered = True
            for msg_id in (head["message_id"], copied["message_id"]):
                await runner.redis.set(f"ub:{bot.bot_id}:fb:{chat}:{msg_id}", chat_id, ex=TTL)
                await runner.redis.set(f"ub:{bot.bot_id}:tkm:{chat}:{msg_id}", t.id, ex=TTL)
    if not delivered:
        await runner.api(bot, "sendMessage", {"chat_id": chat_id, "text": "⚠️ Xabar yetkazilmadi, keyinroq urinib ko'ring."})
        return
    if fresh:
        await stats.track(runner, bot, "ticket")
        integrations.emit(runner, bot, "ticket.created", {"number": t.number, "customer_id": chat_id, "customer_name": user.get("first_name"), "customer_username": user.get("username"), "message": preview})
        done = (bot.menu.get("feedback_done") or "✅ Murojaatingiz qabul qilindi.").rstrip()
        await runner.api(bot, "sendMessage", {"chat_id": chat_id, "text": f"{done}\n🎫 Murojaat raqami: <b>#{t.number}</b>", "parse_mode": "HTML"})


async def on_staff_reply(runner: "Runner", bot: "RunningBot", staff_id: int, reply_msg_id: int, user: dict) -> None:
    """Xodim «Reply» bilan javob berdi: mas'ul belgilanadi, birinchi javob vaqti yoziladi."""
    raw = await runner.redis.get(f"ub:{bot.bot_id}:tkm:{staff_id}:{reply_msg_id}")
    if not raw:
        return
    async with async_session() as db:
        t = await db.get(BotTicket, int(raw))
        if t is None or t.bot_id != bot.bot_id:
            return
        if t.assignee is None:
            t.assignee = staff_id
        if t.first_reply_at is None:
            t.first_reply_at = datetime.datetime.now(datetime.timezone.utc)
        await db.commit()


# ============================================================
# Xodim callbacklari
# ============================================================


async def _get(bot: "RunningBot", tid: int) -> BotTicket | None:
    async with async_session() as db:
        t = await db.get(BotTicket, tid)
    return t if t and t.bot_id == bot.bot_id else None


def _name(bot: "RunningBot", staff_id: int | None, user: dict | None = None) -> str:
    if staff_id is None:
        return ""
    if user and user.get("id") == staff_id:
        return user.get("first_name") or str(staff_id)
    return f"ID {staff_id}"


async def callback(runner: "Runner", bot: "RunningBot", chat_id: int, data: str, message: dict, user: dict) -> None:
    import admin
    import editor

    parts = data.split(":")
    cmd = parts[1] if len(parts) > 1 else ""
    arg = parts[2] if len(parts) > 2 else ""
    is_admin = runner.is_admin(bot, chat_id)
    if cmd in ("ops", "opa", "opx", "cnl", "cna", "cnx", "cfg") and not is_admin:
        return

    async def refresh_head(t: BotTicket) -> None:
        try:
            await runner.api(
                bot, "editMessageReplyMarkup",
                {"chat_id": message["chat"]["id"], "message_id": message["message_id"], "reply_markup": {"inline_keyboard": rows_for(t)}},
            )
        except BotApiError:
            pass

    if cmd == "home":
        await home(runner, bot, chat_id, message)
    elif cmd == "l":
        await _list(runner, bot, chat_id, arg, message, user)
    elif cmd == "v":
        t = await _get(bot, int(arg))
        if t:
            await editor.send(runner, bot, chat_id, _detail(bot, t), rows_for(t) + [[{"text": "⬅️ Murojaatlar", "callback_data": "tk:home"}]], message=message)
    elif cmd == "take":
        async with async_session() as db:
            t = await db.get(BotTicket, int(arg))
            if t is None or t.bot_id != bot.bot_id or t.status != "open":
                return
            t.assignee = chat_id
            await db.commit()
            await db.refresh(t)
        await refresh_head(t)
        await runner.api(bot, "sendMessage", {"chat_id": chat_id, "text": f"🙋 #{t.number} murojaati sizga biriktirildi. Mijozga javob uchun xabarga «Reply» qiling."})
    elif cmd == "close":
        async with async_session() as db:
            t = await db.get(BotTicket, int(arg))
            if t is None or t.bot_id != bot.bot_id or t.status != "open":
                return
            t.status = "closed"
            t.closed_at = datetime.datetime.now(datetime.timezone.utc)
            await db.commit()
            await db.refresh(t)
        await refresh_head(t)
        rating = (bot.menu.get("tickets") or {}).get("rating", True)
        note = f"✅ Murojaatingiz <b>#{t.number}</b> yopildi." + ("\n\nXizmatimizni baholang 👇" if rating else "\nYana savol bo'lsa — yozing.")
        try:
            data_ = {"chat_id": t.tg_user_id, "text": note, "parse_mode": "HTML"}
            if rating:
                data_["reply_markup"] = {"inline_keyboard": [[{"text": f"{n}⭐", "callback_data": f"tr:{t.id}:{n}"} for n in range(1, 6)]]}
            await runner.api(bot, "sendMessage", data_)
        except BotApiError:
            pass
    elif cmd == "re":
        async with async_session() as db:
            t = await db.get(BotTicket, int(arg))
            if t is None or t.bot_id != bot.bot_id:
                return
            t.status = "open"
            t.closed_at = None
            await db.commit()
            await db.refresh(t)
        await refresh_head(t)
    elif cmd == "tpl":
        canned = bot.menu.get("canned") or []
        if not canned:
            await runner.api(bot, "sendMessage", {"chat_id": chat_id, "text": "📝 Shablon javoblar yo'q. Admin: /admin → 🎫 Murojaatlar → 📝 Shablonlar."})
            return
        rows = [[{"text": c["title"][:40], "callback_data": f"tk:ts:{arg}:{c['id']}"}] for c in canned]
        await runner.api(bot, "sendMessage", {"chat_id": chat_id, "text": "📝 Qaysi tayyor javobni yuboramiz?", "reply_markup": {"inline_keyboard": rows}})
    elif cmd == "ts":
        t = await _get(bot, int(arg))
        canned = next((c for c in bot.menu.get("canned") or [] if c["id"] == (parts[3] if len(parts) > 3 else "")), None)
        if t is None or canned is None:
            return
        from core.db.models import BotSubscriber

        async with async_session() as db:
            row = await db.scalar(select(BotSubscriber).where(BotSubscriber.bot_id == bot.bot_id, BotSubscriber.tg_user_id == t.tg_user_id))
        vals = await runner.values(bot, {"id": t.tg_user_id, "first_name": row.first_name if row else None, "username": row.username if row else None})
        try:
            await runner.api(bot, "sendMessage", {"chat_id": t.tg_user_id, "text": fill(canned["text"], vals, escape=True), "parse_mode": "HTML"})
        except BotApiError as exc:
            await runner.api(bot, "sendMessage", {"chat_id": chat_id, "text": f"⚠️ Yuborilmadi: {exc.description}"})
            return
        async with async_session() as db:
            tt = await db.get(BotTicket, t.id)
            if tt.assignee is None:
                tt.assignee = chat_id
            if tt.first_reply_at is None:
                tt.first_reply_at = datetime.datetime.now(datetime.timezone.utc)
            await db.commit()
        await runner.api(bot, "sendMessage", {"chat_id": chat_id, "text": f"✅ #{t.number} ga «{canned['title']}» yuborildi"})
    elif cmd == "ops":
        await _operators_view(runner, bot, chat_id, message)
    elif cmd == "opa":
        await admin.ask(runner, bot, chat_id, {"k": "tk_op"}, "👥 Operatorning Telegram ID raqamini yuboring (yoki uning xabarini shu yerga forward qiling).\n\n<i>Operator avval shu botga /start bosgan bo'lishi kerak.</i>")
    elif cmd == "opx":
        op = int(arg)
        error = await editor.save(runner, bot, lambda m: m.update(operators=[o for o in m.get("operators") or [] if o != op]))
        if error:
            await runner.api(bot, "sendMessage", {"chat_id": chat_id, "text": f"⚠️ {error}"})
        await _operators_view(runner, bot, chat_id, message)
    elif cmd == "cnl":
        await _canned_view(runner, bot, chat_id, message)
    elif cmd == "cna":
        await admin.ask(runner, bot, chat_id, {"k": "tk_cn"}, "📝 Shablon javobni yuboring:\n\n<code>Salomlashish\nAssalomu alaykum, {name}! Murojaatingiz ustida ishlayapmiz.</code>\n\n1-qator — nomi, qolgani — matn.")
    elif cmd == "cnx":
        error = await editor.save(runner, bot, lambda m: m.update(canned=[c for c in m.get("canned") or [] if c["id"] != arg]))
        if error:
            await runner.api(bot, "sendMessage", {"chat_id": chat_id, "text": f"⚠️ {error}"})
        await _canned_view(runner, bot, chat_id, message)
    elif cmd == "cfg":
        def toggle(m: dict) -> None:
            t = m.setdefault("tickets", {})
            t["enabled"] = not t.get("enabled")

        error = await editor.save(runner, bot, toggle)
        if error:
            await runner.api(bot, "sendMessage", {"chat_id": chat_id, "text": f"⚠️ {error}"})
        await home(runner, bot, chat_id, message)


async def rate(runner: "Runner", bot: "RunningBot", chat_id: int, data: str, message: dict, query_id: str) -> None:
    _, tid, n = data.split(":")
    async with async_session() as db:
        t = await db.get(BotTicket, int(tid))
        if t is None or t.bot_id != bot.bot_id or t.tg_user_id != chat_id or t.rating is not None:
            await runner.answer(bot, query_id)
            return
        t.rating = max(1, min(5, int(n)))
        await db.commit()
    await runner.answer(bot, query_id, "🙏 Rahmat!")
    try:
        await runner.api(bot, "editMessageText", {"chat_id": chat_id, "message_id": message["message_id"], "text": f"🙏 Bahoyingiz uchun rahmat! {'⭐' * int(n)}"})
    except BotApiError:
        pass


# ============================================================
# Ro'yxatlar va panel
# ============================================================


def _detail(bot: "RunningBot", t: BotTicket) -> str:
    return (
        f"🎫 <b>#{t.number}</b> · {'🟢 ochiq' if t.status == 'open' else '⚪️ yopilgan'}\n"
        f"👤 <code>{t.tg_user_id}</code> · xabarlar: {t.messages}\n"
        f"🙋 Mas'ul: {('ID ' + str(t.assignee)) if t.assignee else 'yo‘q'}"
        + (f"\n⭐ Baho: {t.rating}" if t.rating else "")
        + f"\n\n«{esc(t.preview)}»"
    )


async def _list(runner, bot, chat_id: int, kind: str, message: dict | None, user: dict) -> None:
    import editor

    q = select(BotTicket).where(BotTicket.bot_id == bot.bot_id, BotTicket.status == "open")
    title = "🟢 Ochiq murojaatlar"
    if kind == "m":
        q = q.where(BotTicket.assignee == chat_id)
        title = "🙋 Mening murojaatlarim"
    elif kind == "u":
        q = q.where(BotTicket.assignee.is_(None))
        title = "🆕 Mas'ulsiz murojaatlar"
    async with async_session() as db:
        rows_db = (await db.scalars(q.order_by(BotTicket.updated_at.desc()).limit(20))).all()
    rows = [[{"text": f"#{t.number} · {t.preview[:36]}", "callback_data": f"tk:v:{t.id}"}] for t in rows_db]
    rows.append([{"text": "⬅️ Murojaatlar", "callback_data": "tk:home"}])
    await editor.send(runner, bot, chat_id, f"{title}\n\n" + ("Yo'q." if not rows_db else "Batafsil uchun bosing."), rows, message=message)


async def home(runner, bot, chat_id: int, message: dict | None = None) -> None:
    import editor

    now = datetime.datetime.now(datetime.timezone.utc)
    async with async_session() as db:
        base = select(func.count(BotTicket.id)).where(BotTicket.bot_id == bot.bot_id)
        open_n = await db.scalar(base.where(BotTicket.status == "open"))
        unassigned = await db.scalar(base.where(BotTicket.status == "open", BotTicket.assignee.is_(None)))
        mine = await db.scalar(base.where(BotTicket.status == "open", BotTicket.assignee == chat_id))
        week = await db.scalar(base.where(BotTicket.created_at >= now - datetime.timedelta(days=7)))
        avg_rating = await db.scalar(select(func.avg(BotTicket.rating)).where(BotTicket.bot_id == bot.bot_id, BotTicket.rating.is_not(None)))
        resp = (
            await db.execute(
                select(BotTicket.created_at, BotTicket.first_reply_at).where(
                    BotTicket.bot_id == bot.bot_id, BotTicket.first_reply_at.is_not(None), BotTicket.created_at >= now - datetime.timedelta(days=30)
                )
            )
        ).all()
    avg_min = round(sum((r - c).total_seconds() for c, r in resp) / len(resp) / 60) if resp else None
    is_admin = runner.is_admin(bot, chat_id)
    on = enabled(bot)
    text = (
        f"🎫 <b>Murojaatlar</b> — {'✅ yoqilgan' if on else '❌ o‘chiq (oddiy qayta aloqa)'}\n\n"
        f"🟢 Ochiq: <b>{open_n or 0}</b> · 🆕 mas'ulsiz: <b>{unassigned or 0}</b> · 🙋 meniki: <b>{mine or 0}</b>\n"
        f"📈 7 kunda: {week or 0} ta"
        + (f"\n⏱ O'rtacha birinchi javob: <b>{avg_min} daq</b>" if avg_min is not None else "")
        + (f"\n⭐ O'rtacha baho: <b>{float(avg_rating):.1f}</b>" if avg_rating else "")
    )
    rows = [
        [{"text": f"🆕 Mas'ulsiz ({unassigned or 0})", "callback_data": "tk:l:u"}, {"text": f"🙋 Meniki ({mine or 0})", "callback_data": "tk:l:m"}],
        [{"text": f"🟢 Barcha ochiq ({open_n or 0})", "callback_data": "tk:l:o"}],
    ]
    if is_admin:
        rows.append([{"text": f"👥 Operatorlar ({len(operators(bot))})", "callback_data": "tk:ops"}, {"text": f"📝 Shablonlar ({len(bot.menu.get('canned') or [])})", "callback_data": "tk:cnl"}])
        rows.append([{"text": "⏸ O'chirish" if on else "▶️ Yoqish", "callback_data": "tk:cfg"}, {"text": "⬅️ Panel", "callback_data": "adm:st"}])
    await editor.send(runner, bot, chat_id, text, rows, message=message)


async def _operators_view(runner, bot, chat_id: int, message: dict | None) -> None:
    import editor

    ops = operators(bot)
    rows = [[{"text": f"👤 {o}  🗑", "callback_data": f"tk:opx:{o}"}] for o in ops]
    rows.append([{"text": "➕ Operator qo'shish", "callback_data": "tk:opa"}, {"text": "⬅️ Murojaatlar", "callback_data": "tk:home"}])
    await editor.send(
        runner, bot, chat_id,
        "👥 <b>Operatorlar</b>\n\nOperator — panelni ko'rmaydi, faqat murojaatlarni oladi, javob beradi va yopadi. Operator botga /start bosgan bo'lishi kerak; keyin <code>/tickets</code> buyrug'i bilan ro'yxatni ko'radi.",
        rows, message=message,
    )


async def _canned_view(runner, bot, chat_id: int, message: dict | None) -> None:
    import editor

    canned = bot.menu.get("canned") or []
    rows = [[{"text": f"📝 {c['title']}  🗑", "callback_data": f"tk:cnx:{c['id']}"}] for c in canned]
    rows.append([{"text": "➕ Shablon qo'shish", "callback_data": "tk:cna"}, {"text": "⬅️ Murojaatlar", "callback_data": "tk:home"}])
    await editor.send(runner, bot, chat_id, "📝 <b>Shablon javoblar</b>\n\nOperator murojaat ostidagi «📝 Shablon» tugmasi bilan bir bosishda yuboradi. Matnda <code>{name}</code> ishlaydi.", rows, message=message)


async def staff_command(runner, bot, chat_id: int, user: dict) -> None:
    await home(runner, bot, chat_id, None)


async def admin_input(runner, bot, chat_id: int, message: dict, state: dict) -> bool:
    import admin
    import editor

    kind = state.get("k", "")
    if not kind.startswith("tk_"):
        return False
    text = (message.get("text") or "").strip()

    async def fail(msg: str) -> bool:
        await runner.api(bot, "sendMessage", {"chat_id": chat_id, "text": f"⚠️ {msg}"})
        return True

    if kind == "tk_op":
        fwd = message.get("forward_from") or (message.get("forward_origin") or {}).get("sender_user")
        if fwd:
            op = int(fwd["id"])
        elif text.lstrip("-").isdigit():
            op = int(text)
        else:
            return await fail("Telegram ID raqamini (masalan 123456789) yuboring yoki operatorning xabarini forward qiling")
        if op == bot.owner_chat_id or op in (bot.menu.get("admins") or []):
            return await fail("Bu odam allaqachon admin")
        error = await editor.save(runner, bot, lambda m: m.setdefault("operators", []).append(op) if op not in m.get("operators", []) else None)
        if error:
            return await fail(error)
        await admin.set_state(runner, bot, chat_id, None)
        await _operators_view(runner, bot, chat_id, None)
        try:
            await runner.api(bot, "sendMessage", {"chat_id": op, "text": "🎫 Siz operator etib tayinlandingiz. Murojaatlar shu yerga keladi; ro'yxat: /tickets"})
        except BotApiError:
            await runner.api(bot, "sendMessage", {"chat_id": chat_id, "text": "ℹ️ Operatorga xabar yuborilmadi — u botga /start bosishi kerak."})
        return True
    if kind == "tk_cn":
        lines = text.splitlines()
        if len(lines) < 2 or not lines[0].strip() or not "\n".join(lines[1:]).strip():
            return await fail("1-qator — nomi, keyingi qatorlar — matn")
        item = {"id": new_page_id(), "title": lines[0].strip()[:40], "text": "\n".join(lines[1:]).strip()[:1500]}
        error = await editor.save(runner, bot, lambda m: m.setdefault("canned", []).append(item))
        if error:
            return await fail(error)
        await admin.set_state(runner, bot, chat_id, None)
        await _canned_view(runner, bot, chat_id, None)
        return True
    return False
