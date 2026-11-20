"""📣 Kanalga post: egasi botga xabar yuboradi → tugmalar qo'shiladi → hozir yoki rejalashtirilgan vaqtda kanalga chiqadi.

Bot kanalda admin bo'lishi (post yuborish huquqi bilan) kerak. Xabar egasining chatidan nusxalanadi (copyMessage) —
istalgan turdagi kontent (matn, rasm, video, so'rovnoma...) formatlash bilan saqlanadi. Rejalashtirilgan postlar daqiqalik
siklda yuboriladi (bot_posts). Do'kon mahsulotini kanalga «🛒 Buyurtma» tugmasi bilan chiqarish ham bor (pc:item)."""

import datetime
import html
import re
from typing import TYPE_CHECKING

from sqlalchemy import func, select

from core.botapi import BotApiError
from core.db.base import async_session
from core.db.models import BotPost

if TYPE_CHECKING:
    from main import Runner, RunningBot


def esc(t) -> str:
    return html.escape(str(t or ""), quote=False)


def tz(bot: "RunningBot") -> int:
    return int(bot.menu.get("tz", 5))


def parse_when(text: str, bot: "RunningBot", now: datetime.datetime | None = None) -> datetime.datetime | None:
    """«18:30» (bugun, o'tgan bo'lsa ertaga) · «25.12 18:30» · «2026-12-25 18:30» → UTC."""
    now = now or datetime.datetime.now(datetime.timezone.utc)
    local = now + datetime.timedelta(hours=tz(bot))
    t = (text or "").strip()
    try:
        if m := re.fullmatch(r"(\d{1,2})[:.](\d{2})", t):
            when = local.replace(hour=int(m.group(1)), minute=int(m.group(2)), second=0, microsecond=0, tzinfo=None)
            if when <= local.replace(tzinfo=None):
                when += datetime.timedelta(days=1)
        elif m := re.fullmatch(r"(\d{1,2})\.(\d{1,2})\s+(\d{1,2})[:.](\d{2})", t):
            when = datetime.datetime(local.year, int(m.group(2)), int(m.group(1)), int(m.group(3)), int(m.group(4)))
            if when <= local.replace(tzinfo=None):
                when = when.replace(year=when.year + 1)
        elif m := re.fullmatch(r"(\d{4})-(\d{2})-(\d{2})\s+(\d{1,2})[:.](\d{2})", t):
            when = datetime.datetime(int(m.group(1)), int(m.group(2)), int(m.group(3)), int(m.group(4)), int(m.group(5)))
        else:
            return None
    except ValueError:
        return None
    return (when - datetime.timedelta(hours=tz(bot))).replace(tzinfo=datetime.timezone.utc)


def parse_buttons(text: str) -> list[list[dict]] | None:
    """Har qator — bitta tugma: «Matn | https://havola». Bo'sh/«-» — tugmasiz."""
    rows = []
    for line in (text or "").splitlines():
        line = line.strip()
        if not line or line == "-":
            continue
        if "|" not in line:
            return None
        label, url = (x.strip() for x in line.split("|", 1))
        if not label or not re.fullmatch(r"(https?://|tg://)\S{3,300}", url):
            return None
        rows.append([{"text": label[:60], "url": url}])
    return rows[:8]


async def send_post(runner: "Runner", bot: "RunningBot", post: BotPost) -> tuple[bool, str]:
    data = {"chat_id": post.channel_id, "from_chat_id": post.from_chat_id, "message_id": post.message_id}
    if post.buttons:
        data["reply_markup"] = {"inline_keyboard": post.buttons}
    try:
        await runner.api(bot, "copyMessage", data)
        return True, ""
    except BotApiError as exc:
        return False, exc.description[:180]


async def tick(runner: "Runner") -> None:
    now = datetime.datetime.now(datetime.timezone.utc)
    async with async_session() as db:
        due = (await db.scalars(select(BotPost).where(BotPost.status == "scheduled", BotPost.publish_at <= now).order_by(BotPost.publish_at).limit(50))).all()
    for post in due:
        bot = runner.bots.get(post.bot_id)
        if bot is None:
            continue
        ok, error = await send_post(runner, bot, post)
        async with async_session() as db:
            row = await db.get(BotPost, post.id)
            if row is None or row.status != "scheduled":
                continue
            row.status = "sent" if ok else "failed"
            row.error = error
            row.sent_at = now if ok else None
            await db.commit()
        if not ok:
            try:
                await runner.api(bot, "sendMessage", {"chat_id": post.from_chat_id, "text": f"⚠️ Rejalashtirilgan post «{post.channel_title}» kanaliga chiqmadi: {error}"})
            except BotApiError:
                pass


# ============================================================
# Egasi: /admin → 📣 Kanal postlari
# ============================================================


async def admin_home(runner, bot, chat_id: int, message: dict | None = None) -> None:
    import editor

    channels = bot.menu.get("post_channels") or []
    async with async_session() as db:
        scheduled = await db.scalar(select(func.count(BotPost.id)).where(BotPost.bot_id == bot.bot_id, BotPost.status == "scheduled"))
    text = (
        "📣 <b>Kanal postlari</b>\n\nBot orqali kanalingizga post chiqaring — hozir yoki rejalashtirilgan vaqtda, inline tugmalar bilan.\n\n"
        + ("📡 Kanallar:\n" + "\n".join(f"• {esc(c['title'] or c['chat_id'])}" for c in channels) if channels else "<i>Avval kanal ulang: botni kanalga admin qiling (post yuborish huquqi bilan).</i>")
        + f"\n\n🗓 Rejalashtirilgan: <b>{scheduled or 0}</b>"
    )
    rows = []
    if channels:
        rows.append([{"text": "✍️ Post yaratish", "callback_data": "pc:new"}, {"text": f"🗓 Rejalashtirilgan ({scheduled or 0})", "callback_data": "pc:l:s"}])
        rows.append([{"text": "🕘 Oxirgi yuborilganlar", "callback_data": "pc:l:h"}])
    rows.append([{"text": "📡 Kanallar", "callback_data": "pc:ch"}, {"text": "⬅️ Panel", "callback_data": "adm:st"}])
    await editor.send(runner, bot, chat_id, text, rows, message=message)


async def admin_callback(runner, bot, chat_id: int, data: str, message: dict, user: dict) -> None:
    import admin
    import editor

    parts = data.split(":")
    cmd = parts[1] if len(parts) > 1 else ""
    arg = parts[2] if len(parts) > 2 else ""
    channels = bot.menu.get("post_channels") or []

    async def save(fn) -> bool:
        error = await editor.save(runner, bot, fn)
        if error:
            await runner.api(bot, "sendMessage", {"chat_id": chat_id, "text": f"⚠️ {error}"})
            return False
        return True

    if cmd == "home":
        await admin.set_state(runner, bot, chat_id, None)
        await admin_home(runner, bot, chat_id, message)
    elif cmd == "ch":
        rows = [[{"text": f"📡 {c['title'] or c['chat_id']}  🗑", "callback_data": f"pc:chx:{c['chat_id']}"}] for c in channels]
        rows.append([{"text": "➕ Kanal ulash", "callback_data": "pc:cha"}, {"text": "⬅️ Postlar", "callback_data": "pc:home"}])
        await editor.send(runner, bot, chat_id, "📡 <b>Kanallar</b>\n\nBotni kanalga <b>administrator</b> qiling (post yuborish huquqi bilan), keyin kanalni ulang.", rows, message=message)
    elif cmd == "cha":
        await admin.ask(runner, bot, chat_id, {"k": "pc_ch"}, "📡 Kanal manzilini (<code>@kanal_nomi</code>) yuboring yoki kanaldan bitta postni shu yerga forward qiling.")
    elif cmd == "chx":
        if await save(lambda m: m.update(post_channels=[c for c in m.get("post_channels") or [] if str(c["chat_id"]) != arg])):
            await admin_callback(runner, bot, chat_id, "pc:ch", message, user)
    elif cmd == "new":
        await admin.ask(
            runner, bot, chat_id, {"k": "pc_msg"},
            "✍️ Postni yuboring — matn, rasm, video, so'rovnoma... qanday bo'lsa shunday kanalga chiqadi (formatlash saqlanadi).",
        )
    elif cmd == "pick":
        # pc:pick:<channel_id> — kanal tanlandi, endi vaqt
        st = await admin.get_state(runner, bot, chat_id) or {}
        if st.get("k") == "pc_chan":
            await _ask_when(runner, bot, chat_id, {**st, "channel": int(arg)})
    elif cmd == "now" or cmd == "at":
        st = await admin.get_state(runner, bot, chat_id) or {}
        if st.get("k") not in ("pc_when",):
            return
        if cmd == "now":
            await _create(runner, bot, chat_id, st, datetime.datetime.now(datetime.timezone.utc))
        else:
            await admin.ask(runner, bot, chat_id, {**st, "k": "pc_time"}, "🗓 Qachon? <code>18:30</code> (bugun/ertaga) · <code>25.12 18:30</code> · <code>2026-12-25 18:30</code>")
    elif cmd == "l":
        async with async_session() as db:
            if arg == "s":
                q = select(BotPost).where(BotPost.bot_id == bot.bot_id, BotPost.status == "scheduled").order_by(BotPost.publish_at).limit(20)
            else:
                q = select(BotPost).where(BotPost.bot_id == bot.bot_id, BotPost.status.in_(("sent", "failed"))).order_by(BotPost.id.desc()).limit(15)
            posts = (await db.scalars(q)).all()
        rows = []
        for p in posts:
            when = (p.publish_at + datetime.timedelta(hours=tz(bot))).strftime("%d.%m %H:%M")
            rows.append([{"text": f"{'⏳' if p.status == 'scheduled' else ('✅' if p.status == 'sent' else '⚠️')} {when} · {p.channel_title[:20]}", "callback_data": f"pc:v:{p.id}"}])
        rows.append([{"text": "⬅️ Postlar", "callback_data": "pc:home"}])
        await editor.send(runner, bot, chat_id, ("🗓 <b>Rejalashtirilgan postlar</b>" if arg == "s" else "🕘 <b>Oxirgi postlar</b>") + ("" if posts else "\n\nYo'q."), rows, message=message)
    elif cmd == "v":
        async with async_session() as db:
            p = await db.get(BotPost, int(arg))
        if p and p.bot_id == bot.bot_id:
            when = (p.publish_at + datetime.timedelta(hours=tz(bot))).strftime("%d.%m.%Y %H:%M")
            rows = ([[{"text": "❌ Bekor qilish", "callback_data": f"pc:x:{p.id}"}]] if p.status == "scheduled" else []) + [[{"text": "⬅️ Postlar", "callback_data": "pc:home"}]]
            await editor.send(runner, bot, chat_id, f"📣 <b>{esc(p.channel_title)}</b>\n🕘 {when}\n📌 {p.status}" + (f"\n⚠️ {esc(p.error)}" if p.error else ""), rows, message=message)
            try:
                await runner.api(bot, "copyMessage", {"chat_id": chat_id, "from_chat_id": p.from_chat_id, "message_id": p.message_id, **({"reply_markup": {"inline_keyboard": p.buttons}} if p.buttons else {})})
            except BotApiError:
                pass
    elif cmd == "x":
        async with async_session() as db:
            p = await db.get(BotPost, int(arg))
            if p and p.bot_id == bot.bot_id and p.status == "scheduled":
                p.status = "cancelled"
                await db.commit()
        await admin_callback(runner, bot, chat_id, "pc:l:s", message, user)
    elif cmd == "item":
        await _post_item(runner, bot, chat_id, arg, parts[3] if len(parts) > 3 else None, message)


async def _ask_when(runner, bot, chat_id: int, st: dict) -> None:
    import admin

    ch = next((c for c in bot.menu.get("post_channels") or [] if c["chat_id"] == st["channel"]), None)
    await admin.set_state(runner, bot, chat_id, {**st, "k": "pc_when", "channel": st["channel"], "title": (ch or {}).get("title", "")})
    await runner.api(
        bot, "sendMessage",
        {"chat_id": chat_id, "text": "🕘 Qachon chiqaramiz?", "reply_markup": {"inline_keyboard": [[{"text": "🚀 Hozir", "callback_data": "pc:now"}, {"text": "🗓 Vaqt tanlash", "callback_data": "pc:at"}]]}},
    )


async def _create(runner, bot, chat_id: int, st: dict, when: datetime.datetime) -> None:
    import admin

    async with async_session() as db:
        post = BotPost(
            bot_id=bot.bot_id, channel_id=st["channel"], channel_title=st.get("title", ""), from_chat_id=chat_id, message_id=st["mid"],
            buttons=st.get("buttons") or [], publish_at=when, status="scheduled",
        )
        db.add(post)
        await db.commit()
        await db.refresh(post)
    await admin.set_state(runner, bot, chat_id, None)
    if when <= datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(seconds=5):
        ok, error = await send_post(runner, bot, post)
        async with async_session() as db:
            row = await db.get(BotPost, post.id)
            row.status = "sent" if ok else "failed"
            row.error = error
            row.sent_at = datetime.datetime.now(datetime.timezone.utc) if ok else None
            await db.commit()
        await runner.api(bot, "sendMessage", {"chat_id": chat_id, "text": f"✅ «{esc(st.get('title'))}» kanaliga yuborildi" if ok else f"⚠️ Yuborilmadi: {esc(error)}\n\nBot kanalda admin va post yuborish huquqiga egami?", "parse_mode": "HTML"})
        return
    local = (when + datetime.timedelta(hours=tz(bot))).strftime("%d.%m.%Y %H:%M")
    await runner.api(bot, "sendMessage", {"chat_id": chat_id, "text": f"🗓 Rejalashtirildi: <b>{local}</b> · {esc(st.get('title'))}", "parse_mode": "HTML", "reply_markup": {"inline_keyboard": [[{"text": "🗓 Ro'yxat", "callback_data": "pc:l:s"}]]}})


async def _post_item(runner, bot, chat_id: int, item_id: str, channel: str | None, message: dict | None) -> None:
    """Do'kon mahsulotini kanalga «🛒 Buyurtma berish» tugmasi bilan chiqaradi."""
    import shop

    item = shop.shop_item(bot.menu, item_id)
    channels = bot.menu.get("post_channels") or []
    if item is None:
        return
    if not channels:
        await runner.api(bot, "sendMessage", {"chat_id": chat_id, "text": "📡 Avval kanal ulang: /admin → 📣 Kanal postlari → 📡 Kanallar"})
        return
    if channel is None and len(channels) > 1:
        rows = [[{"text": c["title"] or str(c["chat_id"]), "callback_data": f"pc:item:{item_id}:{c['chat_id']}"}] for c in channels]
        await runner.api(bot, "sendMessage", {"chat_id": chat_id, "text": "📣 Qaysi kanalga?", "reply_markup": {"inline_keyboard": rows}})
        return
    target = next((c for c in channels if channel is None or str(c["chat_id"]) == channel), channels[0])
    markup = {"inline_keyboard": [[{"text": "🛒 Buyurtma berish", "url": f"https://t.me/{bot.username}?start=p_{item['category']}"}]]}
    text = shop.card_text(bot, item)
    try:
        if item.get("file_id"):
            await runner.api(bot, "sendPhoto", {"chat_id": target["chat_id"], "photo": item["file_id"], "caption": text[:1024], "parse_mode": "HTML", "reply_markup": markup})
        else:
            await runner.api(bot, "sendMessage", {"chat_id": target["chat_id"], "text": text, "parse_mode": "HTML", "reply_markup": markup})
        await runner.api(bot, "sendMessage", {"chat_id": chat_id, "text": f"✅ «{item['title']}» {target['title'] or ''} kanaliga chiqdi"})
    except BotApiError as exc:
        await runner.api(bot, "sendMessage", {"chat_id": chat_id, "text": f"⚠️ Yuborilmadi: {exc.description}"})


async def admin_input(runner, bot, chat_id: int, message: dict, state: dict) -> bool:
    import admin
    import editor

    kind = state.get("k", "")
    if not kind.startswith("pc_"):
        return False
    text = (message.get("text") or "").strip()

    async def say(t: str, rows: list | None = None) -> None:
        await editor.send(runner, bot, chat_id, t, rows)

    if kind == "pc_ch":
        fwd = message.get("forward_from_chat") or (message.get("forward_origin") or {}).get("chat")
        target = fwd["id"] if fwd else (text if re.fullmatch(r"@[A-Za-z0-9_]{4,32}", text) else None)
        if target is None:
            await say("⚠️ <code>@kanal_nomi</code> yuboring yoki kanaldan postni forward qiling")
            return True
        try:
            chat = await runner.api(bot, "getChat", {"chat_id": target})
            me = await runner.api(bot, "getMe")
            member = await runner.api(bot, "getChatMember", {"chat_id": chat["id"], "user_id": me["id"]})
        except BotApiError as exc:
            await say(f"⚠️ Kanalga ulanib bo'lmadi: {esc(exc.description)}\n\nBotni kanalga administrator qiling va qayta urining.")
            return True
        if chat.get("type") != "channel":
            await say("⚠️ Bu kanal emas (guruh yoki shaxsiy chat). Kanal ulang.")
            return True
        if member.get("status") not in ("administrator", "creator") or member.get("can_post_messages") is False:
            await say("⚠️ Bot kanalda <b>post yuborish huquqiga ega administrator</b> emas. Huquq bering va qayta urining.")
            return True
        item = {"chat_id": int(chat["id"]), "title": (chat.get("title") or chat.get("username") or "")[:64]}
        error = await editor.save(runner, bot, lambda m: m.setdefault("post_channels", []).append(item) if all(c["chat_id"] != item["chat_id"] for c in m.get("post_channels", [])) else None)
        if error:
            await say(f"⚠️ {esc(error)}")
            return True
        await admin.set_state(runner, bot, chat_id, None)
        await say(f"✅ «{esc(item['title'])}» ulandi.", [[{"text": "✍️ Post yaratish", "callback_data": "pc:new"}]])
        return True
    if kind == "pc_msg":
        await admin.ask(
            runner, bot, chat_id, {"k": "pc_btn", "mid": message["message_id"]},
            "🔘 Post ostiga tugma kerakmi? Har qatorga bittadan:\n\n<code>🛒 Buyurtma | https://t.me/bot_nomi\n📞 Aloqa | https://t.me/menejer</code>\n\nTugmasiz bo'lsa — <code>-</code> yuboring.",
        )
        return True
    if kind == "pc_btn":
        buttons = parse_buttons(text)
        if buttons is None:
            await say("⚠️ Format: <code>Matn | https://havola</code> (har qatorga bitta). Tugmasiz — <code>-</code>")
            return True
        st = {"mid": state["mid"], "buttons": buttons}
        channels = bot.menu.get("post_channels") or []
        if len(channels) > 1:
            await admin.set_state(runner, bot, chat_id, {**st, "k": "pc_chan"})
            await say("📡 Qaysi kanalga?", [[{"text": c["title"] or str(c["chat_id"]), "callback_data": f"pc:pick:{c['chat_id']}"}] for c in channels])
        else:
            await _ask_when(runner, bot, chat_id, {**st, "channel": channels[0]["chat_id"]})
        return True
    if kind == "pc_time":
        when = parse_when(text, bot)
        if when is None:
            await say("⚠️ Tushunmadim. Namuna: <code>18:30</code> yoki <code>25.12 18:30</code>")
            return True
        if when <= datetime.datetime.now(datetime.timezone.utc):
            await say("⚠️ Bu vaqt o'tib ketgan")
            return True
        await _create(runner, bot, chat_id, state, when)
        return True
    return False
