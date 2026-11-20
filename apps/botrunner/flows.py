"""⚙️ Oqimlar: trigger → (shartli) qadamlar. Imkoniyatlar core/capabilities.py reyestridan olinadi.

Dvigatel: oqim qadamlari yuqoridan pastga bajariladi; qadamning `when` sharti noto'g'ri bo'lsa — o'tkazib yuboriladi.
«ask» qadami oqimni to'xtatadi va foydalanuvchi javobini kutadi (holat Redis'da), javob kelgach oqim davom etadi.
Egasi boshqaruvi: /admin → ⚙️ Oqimlar (`fl:*`) — so'rovlar ketma-ketligi reyestr sxemasidan avtomatik yasaladi."""

import asyncio
import html
import json
import logging
import re
from typing import TYPE_CHECKING

from core import capabilities as caps
from core.botapi import BotApiError
from core.botbuilder import apply_op, check_cond, describe_cond, fill, html_to_plain, new_page_id, page_by_id, parse_cond

import stats

if TYPE_CHECKING:
    from main import Runner, RunningBot

logger = logging.getLogger(__name__)
STATE_TTL = 24 * 3600
MAX_STEPS = 60
CANCEL = "❌ Bekor qilish"


def esc(t) -> str:
    return html.escape(str(t or ""), quote=False)


def _skey(bot: "RunningBot", chat_id: int) -> str:
    return f"ub:{bot.bot_id}:flow:{chat_id}"


def _flow(bot: "RunningBot", fid: str) -> dict | None:
    return next((f for f in bot.menu.get("flows") or [] if f["id"] == fid), None)


# ============================================================
# Amallar (handlerlar)
# ============================================================


def inline_markup(bot: "RunningBot", vals: dict, lines: list[str]) -> dict | None:
    """«Matn | havola / page: / flow: / copy: / inline:» qatorlari → inline klaviatura."""
    rows = []
    for (b,) in caps.parse_buttons(lines or []):
        label, kind, value = fill(b["text"], vals, escape=False), b["kind"], b["value"]
        if kind == "url":
            rows.append([{"text": label, "url": fill(value, vals, escape=False)}])
        elif kind == "page" and page_by_id(bot.menu, value):
            rows.append([{"text": label, "callback_data": f"p:{value}"}])
        elif kind == "flow" and _flow(bot, value):
            rows.append([{"text": label, "callback_data": f"fx:{value}"}])
        elif kind == "copy":
            rows.append([{"text": label, "copy_text": {"text": fill(value, vals, escape=False)[:256]}}])
        elif kind == "inline":
            rows.append([{"text": label, "switch_inline_query": fill(value, vals, escape=False)}])
    return {"inline_keyboard": rows} if rows else None


async def _schedule_delete(runner, bot, chat_id: int, message_id: int | None, minutes: int) -> None:
    if message_id and minutes:
        import time

        await runner.redis.zadd(f"ub:{bot.bot_id}:autodel", {f"{chat_id}:{message_id}": time.time() + minutes * 60})


async def tick(runner: "Runner") -> None:
    """Avto-o'chirish: muddati kelgan xabarlarni o'chiradi."""
    import time

    for bot in list(runner.bots.values()):
        key = f"ub:{bot.bot_id}:autodel"
        due = await runner.redis.zrangebyscore(key, 0, time.time(), start=0, num=100)
        for member in due:
            chat, mid = (member.decode() if isinstance(member, bytes) else member).split(":")
            try:
                await runner.api(bot, "deleteMessage", {"chat_id": int(chat), "message_id": int(mid)})
            except BotApiError:
                pass
            await runner.redis.zrem(key, member)


async def _text(runner, bot, ctx, p):
    data = {"chat_id": ctx["chat_id"], "text": fill(p["text"], ctx["vals"], escape=True)[:4096], "parse_mode": "HTML", "disable_web_page_preview": not p.get("preview")}
    if p.get("silent"):
        data["disable_notification"] = True
    if p.get("protect"):
        data["protect_content"] = True
    if p.get("reply") and ctx.get("msg_id"):
        data["reply_parameters"] = {"message_id": ctx["msg_id"], "allow_sending_without_reply": True}
    markup = inline_markup(bot, ctx["vals"], p.get("buttons") or [])
    if markup:
        data["reply_markup"] = markup
    effect = caps.EFFECTS.get(p.get("effect", ""))
    if effect:
        data["message_effect_id"] = effect
    sent = None
    for attempt in range(3):
        try:
            sent = await runner.api(bot, "sendMessage", data)
            break
        except BotApiError as exc:
            if "message_effect_id" in data and ("effect" in exc.description.lower() or "EFFECT" in exc.description):
                data.pop("message_effect_id")
            elif "parse entities" in exc.description and "parse_mode" in data:
                data.pop("parse_mode")
                data["text"] = html_to_plain(fill(p["text"], ctx["vals"], escape=False))[:4096]
            elif "reply" in exc.description.lower() and "reply_parameters" in data:
                data.pop("reply_parameters")
            else:
                raise
    await _schedule_delete(runner, bot, ctx["chat_id"], (sent or {}).get("message_id"), int(p.get("delete_after") or 0))


_MEDIA = {"photo": "sendPhoto", "video": "sendVideo", "document": "sendDocument", "audio": "sendAudio", "voice": "sendVoice", "animation": "sendAnimation", "video_note": "sendVideoNote", "sticker": "sendSticker"}


async def _media(runner, bot, ctx, p):
    kind = p.get("kind", "photo")
    data = {"chat_id": ctx["chat_id"], kind: p["file"]}
    if kind not in ("sticker", "video_note") and p.get("caption"):
        data["caption"] = fill(p["caption"], ctx["vals"], escape=True)[:1024]
        data["parse_mode"] = "HTML"
        if p.get("caption_above") and kind in ("photo", "video", "animation"):
            data["show_caption_above_media"] = True
    if p.get("spoiler") and kind in ("photo", "video", "animation"):
        data["has_spoiler"] = True
    if p.get("silent"):
        data["disable_notification"] = True
    markup = inline_markup(bot, ctx["vals"], p.get("buttons") or [])
    if markup:
        data["reply_markup"] = markup
    sent = await runner.api(bot, _MEDIA[kind], data)
    await _schedule_delete(runner, bot, ctx["chat_id"], (sent or {}).get("message_id") if isinstance(sent, dict) else None, int(p.get("delete_after") or 0))


async def _album(runner, bot, ctx, p):
    media = [{"type": p.get("kind", "photo"), "media": f} for f in p["files"]]
    if p.get("caption"):
        media[0]["caption"] = fill(p["caption"], ctx["vals"], escape=True)[:1024]
        media[0]["parse_mode"] = "HTML"
    data = {"chat_id": ctx["chat_id"], "media": media}
    if p.get("silent"):
        data["disable_notification"] = True
    await runner.api(bot, "sendMediaGroup", data)


def _carousel_markup(bot, vals: dict, cid: str, i: int, total: int, lines: list[str]) -> dict:
    nav = [
        {"text": "◀️", "callback_data": f"cr:{cid}:{(i - 1) % total}"},
        {"text": f"{i + 1}/{total}", "callback_data": f"cr:{cid}:{i}"},
        {"text": "▶️", "callback_data": f"cr:{cid}:{(i + 1) % total}"},
    ]
    extra = (inline_markup(bot, vals, lines) or {}).get("inline_keyboard", [])
    return {"inline_keyboard": [nav] + extra}


async def _carousel(runner, bot, ctx, p):
    items = []
    for line in p["items"]:
        media, _, caption = line.partition("|")
        items.append({"media": media.strip(), "caption": fill(caption.strip(), ctx["vals"], escape=True)[:1024]})
    cid = new_page_id()
    await runner.redis.set(f"ub:{bot.bot_id}:car:{cid}", json.dumps({"items": items, "buttons": p.get("buttons") or [], "vals": {k: v for k, v in ctx["vals"].items() if isinstance(v, str) and len(v) < 200}}), ex=30 * 24 * 3600)
    first = items[0]
    await runner.api(
        bot, "sendPhoto",
        {"chat_id": ctx["chat_id"], "photo": first["media"], "caption": first["caption"], "parse_mode": "HTML", "reply_markup": _carousel_markup(bot, ctx["vals"], cid, 0, len(items), p.get("buttons") or [])},
    )


async def on_carousel(runner: "Runner", bot: "RunningBot", chat_id: int, data: str, message: dict, query_id: str) -> None:
    _, cid, n = data.split(":")
    raw = await runner.redis.get(f"ub:{bot.bot_id}:car:{cid}")
    if not raw:
        await runner.answer(bot, query_id, "Bu karusel eskirgan")
        return
    info = json.loads(raw)
    items = info["items"]
    i = max(0, min(len(items) - 1, int(n)))
    await runner.answer(bot, query_id)
    item = items[i]
    try:
        await runner.api(
            bot, "editMessageMedia",
            {"chat_id": chat_id, "message_id": message["message_id"], "media": {"type": "photo", "media": item["media"], "caption": item["caption"], "parse_mode": "HTML"},
             "reply_markup": _carousel_markup(bot, info.get("vals") or {}, cid, i, len(items), info.get("buttons") or [])},
        )
    except BotApiError as exc:
        if "not modified" not in exc.description:
            raise


async def on_button(runner: "Runner", bot: "RunningBot", chat_id: int, flow_id: str, user: dict, message: dict | None, query_id: str | None = None) -> None:
    """Tugma orqali oqimni ishga tushirish (fx:<oqim>)."""
    flow = _flow(bot, flow_id)
    await runner.answer(bot, query_id)
    if flow is None or not flow.get("enabled", True):
        return
    ctx = await _ctx(runner, bot, chat_id, user, None)
    await run(runner, bot, flow, ctx)


async def _location(runner, bot, ctx, p):
    base = {"chat_id": ctx["chat_id"], "latitude": p["latitude"], "longitude": p["longitude"]}
    if p.get("title") or p.get("address"):
        await runner.api(bot, "sendVenue", {**base, "title": p.get("title") or p["address"], "address": p.get("address") or p["title"]})
    else:
        await runner.api(bot, "sendLocation", base)


async def _contact(runner, bot, ctx, p):
    data = {"chat_id": ctx["chat_id"], "phone_number": fill(p["phone"], ctx["vals"], escape=False), "first_name": fill(p["first_name"], ctx["vals"], escape=False)}
    if p.get("last_name"):
        data["last_name"] = p["last_name"]
    await runner.api(bot, "sendContact", data)


async def _poll(runner, bot, ctx, p):
    quiz = bool(p.get("quiz"))
    data = {
        "chat_id": ctx["chat_id"], "question": fill(p["question"], ctx["vals"], escape=False)[:300],
        "options": [{"text": o} for o in p["options"]],
        "is_anonymous": bool(p.get("anonymous", True)) and not p.get("var"),
    }
    if quiz:
        data["type"] = "quiz"
        data["correct_option_id"] = min(len(p["options"]), max(1, p.get("correct", 1))) - 1
        if p.get("explanation"):
            data["explanation"] = p["explanation"]
    else:
        data["allows_multiple_answers"] = bool(p.get("multiple"))
    sent = await runner.api(bot, "sendPoll", data)
    poll = (sent or {}).get("poll") or {}
    if poll.get("id") and (p.get("var") or ctx.get("flow_id")):
        await runner.redis.set(
            f"ub:{bot.bot_id}:poll:{poll['id']}",
            json.dumps({"var": p.get("var"), "options": p["options"], "quiz": quiz, "correct": data.get("correct_option_id"), "chat": ctx["chat_id"]}),
            ex=30 * 24 * 3600,
        )


async def _dice(runner, bot, ctx, p):
    sent = await runner.api(bot, "sendDice", {"chat_id": ctx["chat_id"], "emoji": p.get("emoji", "🎲")})
    value = str(((sent or {}).get("dice") or {}).get("value", ""))
    ctx["vals"]["dice"] = value
    if p.get("var") and value:
        await runner.set_vars(bot, ctx["user"]["id"], {p["var"]: value})
        ctx["vals"][p["var"]] = value


async def _typing(runner, bot, ctx, p):
    try:
        await runner.api(bot, "sendChatAction", {"chat_id": ctx["chat_id"], "action": p.get("action", "typing")})
    except BotApiError:
        pass
    await asyncio.sleep(min(5, max(1, int(p.get("seconds", 2)))))


async def _react(runner, bot, ctx, p):
    if not ctx.get("msg_id"):
        return
    try:
        await runner.api(bot, "setMessageReaction", {"chat_id": ctx["chat_id"], "message_id": ctx["msg_id"], "reaction": [{"type": "emoji", "emoji": p.get("emoji", "👍")}]})
    except BotApiError:
        pass


async def _set_var(runner, bot, ctx, p):
    cur = ctx["vals"].get(p["var"])
    new = apply_op(cur, p.get("op", "set"), fill(p.get("value", ""), ctx["vals"], escape=False))
    await runner.set_vars(bot, ctx["user"]["id"], {p["var"]: new})
    ctx["vals"][p["var"]] = new


async def _notify(runner, bot, ctx, p):
    user = ctx["user"]
    who = esc(user.get("first_name") or "Foydalanuvchi") + (f" (@{esc(user['username'])})" if user.get("username") else "") + f" · <code>{user['id']}</code>"
    text = f"🔔 {fill(p['text'], ctx['vals'], escape=True)}\n\n👤 {who}"
    for admin_chat in runner.admin_chats(bot):
        try:
            sent = await runner.api(bot, "sendMessage", {"chat_id": admin_chat, "text": text[:4096], "parse_mode": "HTML"})
            await runner.redis.set(f"ub:{bot.bot_id}:fb:{admin_chat}:{sent['message_id']}", ctx["chat_id"], ex=30 * 24 * 3600)
        except BotApiError:
            pass


async def _wait(runner, bot, ctx, p):
    await asyncio.sleep(min(10, max(1, int(p.get("seconds", 2)))))


async def _open_page(runner, bot, ctx, p):
    page = page_by_id(bot.menu, p["page"])
    if page is not None:
        await runner.open_page(bot, ctx["chat_id"], page["id"], ctx["user"])


async def _ask(runner, bot, ctx, p):
    kind = p.get("input", "text")
    rows: list = []
    if kind == "choice":
        opts = p.get("options") or []
        rows = [[{"text": o} for o in opts[i : i + 2]] for i in range(0, len(opts), 2)]
    elif kind == "phone":
        rows = [[{"text": "📱 Raqamni yuborish", "request_contact": True}]]
    elif kind == "location":
        rows = [[{"text": "📍 Joylashuvni yuborish", "request_location": True}]]
    rows.append([{"text": CANCEL}])
    await runner.api(
        bot, "sendMessage",
        {"chat_id": ctx["chat_id"], "text": fill(p["question"], ctx["vals"], escape=True), "parse_mode": "HTML",
         "reply_markup": {"keyboard": rows, "resize_keyboard": True, "one_time_keyboard": kind == "choice", **({"input_field_placeholder": p["placeholder"][:64]} if p.get("placeholder") else {})}},
    )
    return "wait"


async def _stop(runner, bot, ctx, p):
    return "stop"


ACTIONS = {
    "send_text": _text, "send_media": _media, "send_album": _album, "send_carousel": _carousel, "send_location": _location, "send_contact": _contact, "send_poll": _poll, "send_dice": _dice, "typing": _typing,
    "react": _react, "set_var": _set_var, "notify_admin": _notify, "wait": _wait, "open_page": _open_page, "ask": _ask, "stop": _stop,
}


# ============================================================
# Dvigatel
# ============================================================


async def run(runner: "Runner", bot: "RunningBot", flow: dict, ctx: dict, start: int = 0) -> None:
    steps = flow["steps"]
    ctx["flow_id"] = flow["id"]
    pc = start
    executed = 0
    try:
        while pc < len(steps) and executed < MAX_STEPS:
            step = steps[pc]
            executed += 1
            if step.get("when") and not check_cond(step["when"], ctx["vals"]):
                pc += 1
                continue
            handler = ACTIONS.get(step["type"])
            result = await handler(runner, bot, ctx, step["params"]) if handler else None
            if result == "stop":
                return
            if result == "wait":
                p = step["params"]
                await runner.redis.set(_skey(bot, ctx["chat_id"]), json.dumps({"flow": flow["id"], "pc": pc, "input": p.get("input", "text"), "options": p.get("options") or [], "var": p["var"]}), ex=STATE_TTL)
                return
            pc += 1
    except BotApiError as exc:
        if exc.user_blocked:
            await runner._set_blocked(bot, ctx["chat_id"], True)
        else:
            logger.info("oqim %s: Telegram xatosi: %s", flow["id"], exc.description)
    except Exception:  # noqa: BLE001 — oqim xatosi botni to'xtatmasin
        logger.exception("oqim %s xatosi", flow["id"])
    finally:
        await stats.track(runner, bot, f"flow:{flow['id']}")


async def _ctx(runner, bot, chat_id: int, user: dict, message: dict | None, extra: dict | None = None) -> dict:
    vals = await runner.values(bot, user)
    if message:
        vals["msg_text"] = (message.get("text") or message.get("caption") or "")
        if message.get("location"):
            vals["lat"], vals["lon"] = str(message["location"]["latitude"]), str(message["location"]["longitude"])
        if message.get("contact"):
            vals["phone"] = message["contact"].get("phone_number", "")
    vals.update(extra or {})
    return {"chat_id": chat_id, "user": user, "vals": vals, "msg_id": (message or {}).get("message_id")}


def _kind(message: dict) -> str | None:
    if message.get("animation"):
        return "animation"
    for k in ("photo", "video", "voice", "audio", "document", "sticker", "video_note", "location", "contact", "poll", "dice"):
        if message.get(k):
            return k
    return None


def _text_match(p: dict, text: str) -> bool:
    t, want = text.strip().lower(), p["text"].lower()
    if p["match"] == "exact":
        return t == want
    if p["match"] == "start":
        return t.startswith(want)
    if p["match"] == "regex":
        try:
            return re.search(p["text"], text, re.I) is not None
        except re.error:
            return False
    return want in t


async def on_wait(runner: "Runner", bot: "RunningBot", message: dict, user: dict) -> bool:
    """Oqim «ask» qadamida javob kutayotgan bo'lsa — xabarni shu yerda ishlaydi."""
    chat_id = message["chat"]["id"]
    raw = await runner.redis.get(_skey(bot, chat_id))
    if not raw:
        return False
    state = json.loads(raw)
    flow = _flow(bot, state["flow"])
    text = (message.get("text") or "").strip()
    if flow is None or text in (CANCEL, "/cancel"):
        await runner.redis.delete(_skey(bot, chat_id))
        await runner.api(bot, "sendMessage", {"chat_id": chat_id, "text": "❌ Bekor qilindi.", "reply_markup": {"remove_keyboard": True}})
        return True
    value, error = runner._form_answer({"type": state["input"], "options": state["options"]}, message)
    if value is None:
        await runner.api(bot, "sendMessage", {"chat_id": chat_id, "text": error})
        return True
    await runner.redis.delete(_skey(bot, chat_id))
    await runner.set_vars(bot, user["id"], {state["var"]: value})
    ctx = await _ctx(runner, bot, chat_id, user, message)
    ctx["vals"][state["var"]] = value
    await runner.api(bot, "sendMessage", {"chat_id": chat_id, "text": "✅", "reply_markup": {"remove_keyboard": True}})
    await run(runner, bot, flow, ctx, state["pc"] + 1)
    return True


async def on_trigger(runner: "Runner", bot: "RunningBot", message: dict, user: dict, stage: str) -> bool:
    """stage: «command» — buyruqlar (menyu buyruqlaridan oldin) · «message» — matn/xabar turi (kalit so'zlardan keyin)."""
    flows = [f for f in bot.menu.get("flows") or [] if f.get("enabled", True)]
    if not flows:
        return False
    chat_id = message["chat"]["id"]
    text = (message.get("text") or "").strip()
    chosen = None
    if stage == "command" and text.startswith("/"):
        cmd = text[1:].split()[0].split("@")[0].lower()
        chosen = next((f for f in flows if f["trigger"]["type"] == "command" and f["trigger"]["params"]["command"] == cmd), None)
    elif stage == "message" and not text.startswith("/"):
        kind = _kind(message)
        for f in flows:
            t = f["trigger"]
            if text and t["type"] == "text" and _text_match(t["params"], text):
                chosen = f
            elif kind and t["type"] == "message_type" and t["params"]["kind"] == kind:
                chosen = f
            if chosen:
                break
    if chosen is None:
        return False
    ctx = await _ctx(runner, bot, chat_id, user, message)
    await run(runner, bot, chosen, ctx)
    return True


async def on_new_user(runner: "Runner", bot: "RunningBot", chat_id: int, user: dict) -> None:
    for f in bot.menu.get("flows") or []:
        if f.get("enabled", True) and f["trigger"]["type"] == "new_user":
            await run(runner, bot, f, await _ctx(runner, bot, chat_id, user, None))


async def on_poll_answer(runner: "Runner", bot: "RunningBot", answer: dict) -> None:
    raw = await runner.redis.get(f"ub:{bot.bot_id}:poll:{answer.get('poll_id')}")
    user = answer.get("user") or {}
    if not raw or not user.get("id") or not answer.get("option_ids"):
        return
    info = json.loads(raw)
    idx = int(answer["option_ids"][0])
    options = info.get("options") or []
    choice = options[idx] if idx < len(options) else ""
    extra = {"poll_choice": choice, "poll_choice_index": str(idx + 1), "poll_correct": "1" if info.get("quiz") and info.get("correct") == idx else "0"}
    if info.get("var"):
        await runner.set_vars(bot, user["id"], {info["var"]: choice})
    chat_id = int(info.get("chat") or user["id"])
    for f in bot.menu.get("flows") or []:
        if f.get("enabled", True) and f["trigger"]["type"] == "poll_answer":
            ctx = await _ctx(runner, bot, chat_id, user, None, extra)
            if info.get("var"):
                ctx["vals"][info["var"]] = choice
            await run(runner, bot, f, ctx)


# ============================================================
# Egasi: /admin → ⚙️ Oqimlar
# ============================================================


def _trigger_text(f: dict) -> str:
    return caps.summary("trigger", f["trigger"]["type"], f["trigger"]["params"])


async def admin_home(runner, bot, chat_id: int, message: dict | None = None) -> None:
    import editor

    flows = bot.menu.get("flows") or []
    text = (
        "⚙️ <b>Oqimlar</b>\n\nOqim — «agar shunday bo'lsa, shunday qil». Trigger (buyruq, matn, rasm yuborildi, yangi foydalanuvchi...) "
        "ishga tushirsa, qadamlar ketma-ket bajariladi: xabar, joylashuv, so'rovnoma, dice, savol, o'zgaruvchi... Hamma imkoniyatlar ro'yxatdan tanlanadi.\n\n"
        + ("\n".join(f"{'✅' if f.get('enabled', True) else '⏸'} <b>{esc(f['title'] or f['id'])}</b>\n   {esc(_trigger_text(f))} → {len(f['steps'])} qadam" for f in flows) if flows else "<i>Hozircha oqim yo'q.</i>")
    )
    rows = [[{"text": f"{'✅' if f.get('enabled', True) else '⏸'} {f['title'] or f['id']}"[:60], "callback_data": f"fl:v:{f['id']}"}] for f in flows]
    rows.append([{"text": "➕ Yangi oqim", "callback_data": "fl:new"}, {"text": "⬅️ Panel", "callback_data": "adm:st"}])
    await editor.send(runner, bot, chat_id, text, rows, message=message)


async def _view(runner, bot, chat_id: int, fid: str, message: dict | None) -> None:
    import editor

    f = _flow(bot, fid)
    if f is None:
        await admin_home(runner, bot, chat_id, message)
        return
    lines = [f"⚙️ <b>{esc(f['title'] or f['id'])}</b> — {'yoqilgan' if f.get('enabled', True) else 'to‘xtatilgan'}", f"🎯 Trigger: {esc(_trigger_text(f))}", ""]
    for i, s in enumerate(f["steps"], 1):
        cond = f"  <i>agar {esc(describe_cond(s['when']))}</i>" if s.get("when") else ""
        lines.append(f"{i}. {esc(caps.summary('action', s['type'], s['params']))}{cond}")
    rows = [[{"text": f"{i}. {caps.get('action', s['type']).icon} {caps.get('action', s['type']).title}"[:44], "callback_data": f"fl:s:{fid}:{i - 1}"}] for i, s in enumerate(f["steps"], 1)]
    rows.append([{"text": "➕ Qadam", "callback_data": f"fl:as:{fid}"}, {"text": "🧪 Menga yuborish", "callback_data": f"fl:run:{fid}"}])
    rows.append([{"text": "✏️ Nomi", "callback_data": f"fl:nm:{fid}"}, {"text": "⏸ To'xtatish" if f.get("enabled", True) else "▶️ Yoqish", "callback_data": f"fl:t:{fid}"}, {"text": "🗑", "callback_data": f"fl:x:{fid}"}])
    rows.append([{"text": "⬅️ Oqimlar", "callback_data": "fl:home"}])
    await editor.send(runner, bot, chat_id, "\n".join(lines), rows, message=message)


async def _picker(runner, bot, chat_id: int, kind: str, payload: str, message: dict | None, back: str) -> None:
    import editor

    groups: dict[str, list] = {}
    for cap in caps.by_kind(kind):
        groups.setdefault(cap.group, []).append(cap)
    rows = []
    for group, items in groups.items():
        for i in range(0, len(items), 2):
            rows.append([{"text": f"{c.icon} {c.title}"[:30], "callback_data": f"fl:{'ca' if kind == 'action' else 'ct'}:{payload}:{c.id}"} for c in items[i : i + 2]])
    rows.append([{"text": "⬅️ Orqaga", "callback_data": back}])
    title = "➕ <b>Qadam tanlang</b>" if kind == "action" else "🎯 <b>Qachon ishga tushsin?</b> (trigger)"
    legend = "\n\n" + "\n".join(f"{c.icon} <b>{c.title}</b> — {esc(c.help)}" for g in groups.values() for c in g if c.help)
    await editor.send(runner, bot, chat_id, title + legend[:3000], rows, message=message)


async def _ask_next(runner, bot, chat_id: int, st: dict) -> None:
    """Navbatdagi maydonni so'raydi (sxemadan avtomatik)."""
    import admin

    cap = caps.get(st["kind"], st["cap"])
    specs = caps.fields_of(cap)
    queue = st["queue"]
    if not queue:
        await _finish(runner, bot, chat_id, st)
        return
    spec = next(s for s in specs if s.name == queue[0])
    await admin.set_state(runner, bot, chat_id, {**st, "k": "fl_p"})
    hint = f"\n<i>Masalan: {esc(spec.example)}</i>" if spec.example else ""
    skip = "" if spec.required else "\n<code>-</code> — standart qiymat"
    head = f"{cap.icon} <b>{cap.title}</b> · {len(specs) - len(queue) + 1}/{len(specs)}\n\n<b>{esc(spec.label)}</b>{hint}{skip}"
    markup = None
    if spec.ui == "choice":
        markup = [[{"text": str(c), "callback_data": f"fl:pv:{c}"} for c in spec.choices[i : i + 3]] for i in range(0, len(spec.choices), 3)]
    elif spec.ui == "bool":
        markup = [[{"text": "✅ Ha", "callback_data": "fl:pv:ha"}, {"text": "❌ Yo'q", "callback_data": "fl:pv:yo'q"}]]
    elif spec.ui == "page":
        markup = [[{"text": p["title"][:40], "callback_data": f"fl:pv:{p['id']}"}] for p in (bot.menu.get("pages") or [])[:20]]
    data = {"chat_id": chat_id, "text": head + "\n\nBekor qilish: /cancel", "parse_mode": "HTML"}
    if markup:
        data["reply_markup"] = {"inline_keyboard": markup}
    await runner.api(bot, "sendMessage", data)


def _file_of(message: dict | None) -> tuple[str, str] | None:
    """Egasi yuborgan fayl → (tur, file_id)."""
    if not message:
        return None
    if message.get("photo"):
        return "photo", message["photo"][-1]["file_id"]
    for k in ("animation", "video", "document", "audio", "voice", "video_note", "sticker"):
        if message.get(k):
            return k, message[k]["file_id"]
    return None


async def _accept(runner, bot, chat_id: int, st: dict, raw: str, message: dict | None = None) -> None:
    cap = caps.get(st["kind"], st["cap"])
    spec = next(s for s in caps.fields_of(cap) if s.name == st["queue"][0])
    if spec.ui == "media":
        found = _file_of(message)
        if found:
            kind, fid = found
            values = {**st["values"], spec.name: fid}
            queue = st["queue"][1:]
            if "kind" in queue and any(f.name == "kind" for f in caps.fields_of(cap)):
                values["kind"] = kind
                queue = [q for q in queue if q != "kind"]
            await _ask_next(runner, bot, chat_id, {**st, "values": values, "queue": queue})
            return
        if not raw.strip().startswith(("https://", "http://")) and len(raw.strip()) < 20:
            await runner.api(bot, "sendMessage", {"chat_id": chat_id, "text": "⚠️ Faylni shu yerga yuboring (rasm, video, hujjat...) yoki https:// havola yozing"})
            return
    if raw.strip() == "-" and not spec.required:
        value = spec.default
    else:
        try:
            if spec.ui == "page":
                if page_by_id(bot.menu, raw.strip()) is None:
                    raise ValueError("bunday bo'lim yo'q")
                value = raw.strip()
            else:
                value = caps.parse_value(spec, raw)
        except ValueError as exc:
            await runner.api(bot, "sendMessage", {"chat_id": chat_id, "text": f"⚠️ {exc}"})
            return
    st = {**st, "values": {**st["values"], spec.name: value}, "queue": st["queue"][1:]}
    await _ask_next(runner, bot, chat_id, st)


async def _finish(runner, bot, chat_id: int, st: dict) -> None:
    import admin
    import editor

    try:
        params = caps.validate(st["kind"], st["cap"], st["values"])
    except ValueError as exc:
        await runner.api(bot, "sendMessage", {"chat_id": chat_id, "text": f"⚠️ {exc}\n\nQaytadan kiriting."})
        cap = caps.get(st["kind"], st["cap"])
        await _ask_next(runner, bot, chat_id, {**st, "values": {}, "queue": [s.name for s in caps.fields_of(cap)]})
        return
    if st["kind"] == "trigger":
        # keyingi: birinchi qadamni tanlash
        await admin.set_state(runner, bot, chat_id, {"k": "fl_trig", "trigger": {"type": st["cap"], "params": params}})
        await _picker(runner, bot, chat_id, "action", "new", None, "fl:home")
        return
    step = {"type": st["cap"], "params": params}
    fid = st.get("flow")
    if fid is None:  # yangi oqim
        trig = st["trigger"]
        cap = caps.get("trigger", trig["type"])
        fid = new_page_id()
        flow = {"id": fid, "title": cap.title, "enabled": True, "trigger": trig, "steps": [step]}
        error = await editor.save(runner, bot, lambda m: m.setdefault("flows", []).append(flow))
    else:
        def add(m: dict) -> None:
            for f in m.get("flows") or []:
                if f["id"] == fid:
                    f["steps"].append(step)

        error = await editor.save(runner, bot, add)
    await admin.set_state(runner, bot, chat_id, None)
    if error:
        await runner.api(bot, "sendMessage", {"chat_id": chat_id, "text": f"⚠️ {error}"})
        return
    await _view(runner, bot, chat_id, fid, None)


async def _begin(runner, bot, chat_id: int, kind: str, cap_id: str, base: dict) -> None:
    cap = caps.get(kind, cap_id)
    if cap is None:
        return
    specs = caps.fields_of(cap)
    await _ask_next(runner, bot, chat_id, {**base, "kind": kind, "cap": cap_id, "queue": [s.name for s in specs], "values": {}})


async def admin_callback(runner, bot, chat_id: int, data: str, message: dict, user: dict) -> None:
    import admin
    import editor

    parts = data.split(":", 4)
    cmd = parts[1] if len(parts) > 1 else ""
    arg = parts[2] if len(parts) > 2 else ""

    async def save(fn) -> bool:
        error = await editor.save(runner, bot, fn)
        if error:
            await runner.api(bot, "sendMessage", {"chat_id": chat_id, "text": f"⚠️ {error}"})
            return False
        return True

    def edit(fid: str, **changes):
        def fn(m: dict) -> None:
            for f in m.get("flows") or []:
                if f["id"] == fid:
                    f.update(changes)

        return fn

    if cmd == "home":
        await admin.set_state(runner, bot, chat_id, None)
        await admin_home(runner, bot, chat_id, message)
    elif cmd == "new":
        await admin.set_state(runner, bot, chat_id, None)
        await _picker(runner, bot, chat_id, "trigger", "new", message, "fl:home")
    elif cmd == "ct":  # fl:ct:<payload>:<trigger id>
        await _begin(runner, bot, chat_id, "trigger", parts[3], {"flow": None})
    elif cmd == "as":
        await _picker(runner, bot, chat_id, "action", arg, message, f"fl:v:{arg}")
    elif cmd == "ca":  # fl:ca:<flow|new>:<action id>
        st = await admin.get_state(runner, bot, chat_id) or {}
        base = {"flow": None if arg == "new" else arg}
        if arg == "new":
            if st.get("k") != "fl_trig":
                return
            base["trigger"] = st["trigger"]
        await _begin(runner, bot, chat_id, "action", parts[3], base)
    elif cmd == "pv":
        st = await admin.get_state(runner, bot, chat_id) or {}
        if st.get("k") == "fl_p" and st.get("queue"):
            await _accept(runner, bot, chat_id, st, data.split(":", 2)[2])
    elif cmd == "v":
        await admin.set_state(runner, bot, chat_id, None)
        await _view(runner, bot, chat_id, arg, message)
    elif cmd == "t":
        f = _flow(bot, arg)
        if f and await save(edit(arg, enabled=not f.get("enabled", True))):
            await _view(runner, bot, chat_id, arg, message)
    elif cmd == "x":
        if await save(lambda m: m.update(flows=[f for f in m.get("flows") or [] if f["id"] != arg])):
            await admin_home(runner, bot, chat_id, message)
    elif cmd == "nm":
        await admin.ask(runner, bot, chat_id, {"k": "fl_name", "flow": arg}, "✏️ Oqim nomini yuboring:")
    elif cmd == "s":  # qadam kartasi: fl:s:<flow>:<i>
        f = _flow(bot, arg)
        i = int(parts[3]) if len(parts) > 3 else 0
        if f and 0 <= i < len(f["steps"]):
            s = f["steps"][i]
            body = "\n".join(f"• {esc(x.label)}: <code>{esc(s['params'].get(x.name))}</code>" for x in caps.fields_of(caps.get("action", s["type"])))
            rows = [
                [{"text": "🔀 Shart", "callback_data": f"fl:w:{arg}:{i}"}, {"text": "⬆️", "callback_data": f"fl:up:{arg}:{i}"}, {"text": "⬇️", "callback_data": f"fl:dn:{arg}:{i}"}, {"text": "🗑", "callback_data": f"fl:sx:{arg}:{i}"}],
                [{"text": "⬅️ Oqim", "callback_data": f"fl:v:{arg}"}],
            ]
            cond = f"\n🔀 Shart: <i>{esc(describe_cond(s['when']))}</i>" if s.get("when") else "\n🔀 Shart: yo'q (har doim)"
            await editor.send(runner, bot, chat_id, f"{caps.get('action', s['type']).icon} <b>{i + 1}-qadam · {caps.get('action', s['type']).title}</b>\n\n{body}{cond}", rows, message=message)
    elif cmd in ("up", "dn", "sx"):
        i = int(parts[3])

        def mut(m: dict) -> None:
            for f in m.get("flows") or []:
                if f["id"] == arg:
                    steps = f["steps"]
                    if cmd == "sx" and len(steps) > 1:
                        steps.pop(i)
                    elif cmd == "up" and i > 0:
                        steps[i - 1], steps[i] = steps[i], steps[i - 1]
                    elif cmd == "dn" and i < len(steps) - 1:
                        steps[i + 1], steps[i] = steps[i], steps[i + 1]

        f = _flow(bot, arg)
        if cmd == "sx" and f and len(f["steps"]) <= 1:
            await runner.api(bot, "sendMessage", {"chat_id": chat_id, "text": "⚠️ Oqimda kamida bitta qadam bo'lishi kerak (butun oqimni 🗑 bilan o'chiring)."})
            return
        if await save(mut):
            await _view(runner, bot, chat_id, arg, message)
    elif cmd == "w":
        await admin.ask(
            runner, bot, chat_id, {"k": "fl_when", "flow": arg, "i": int(parts[3])},
            "🔀 Qadam qachon bajarilsin? Shartni yozing:\n\n<code>ball >= 10</code>\n<code>ism bor</code>\n<code>shahar = Toshkent</code>\n\n<code>-</code> — shartsiz (har doim).",
        )
    elif cmd == "run":
        f = _flow(bot, arg)
        if f:
            await runner.api(bot, "sendMessage", {"chat_id": chat_id, "text": "🧪 Sinov: oqim sizga ishga tushirildi (trigger o'rniga)."})
            ctx = await _ctx(runner, bot, chat_id, user, None)
            await run(runner, bot, f, ctx)


async def admin_input(runner, bot, chat_id: int, message: dict, state: dict) -> bool:
    import admin
    import editor

    kind = state.get("k", "")
    if not kind.startswith("fl_"):
        return False
    text = (message.get("text") or "").strip()
    if kind == "fl_p":
        await _accept(runner, bot, chat_id, state, message.get("text") or message.get("caption") or "", message)
        return True
    if kind == "fl_name":
        def rename(m: dict) -> None:
            for f in m.get("flows") or []:
                if f["id"] == state["flow"]:
                    f["title"] = text[:64]

        error = await editor.save(runner, bot, rename)
        await admin.set_state(runner, bot, chat_id, None)
        if error:
            await runner.api(bot, "sendMessage", {"chat_id": chat_id, "text": f"⚠️ {error}"})
        else:
            await _view(runner, bot, chat_id, state["flow"], None)
        return True
    if kind == "fl_when":
        cond = None
        if text != "-":
            cond = parse_cond(text)
            if cond is None:
                await runner.api(bot, "sendMessage", {"chat_id": chat_id, "text": "⚠️ Tushunmadim. Namuna: <code>ball >= 10</code>, <code>ism bor</code>, <code>shahar = Toshkent</code>", "parse_mode": "HTML"})
                return True

        def setc(m: dict) -> None:
            for f in m.get("flows") or []:
                if f["id"] == state["flow"] and 0 <= state["i"] < len(f["steps"]):
                    f["steps"][state["i"]]["when"] = cond

        error = await editor.save(runner, bot, setc)
        await admin.set_state(runner, bot, chat_id, None)
        if error:
            await runner.api(bot, "sendMessage", {"chat_id": chat_id, "text": f"⚠️ {error}"})
        else:
            await _view(runner, bot, chat_id, state["flow"], None)
        return True
    return False
