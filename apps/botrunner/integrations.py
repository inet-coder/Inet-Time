"""🔌 Integratsiyalar: webhook (JSON) va Google Sheets (Apps Script orqali) — hodisalar tashqi tizimga yuboriladi.

Hodisalar: user.started, order.created, order.paid, order.status, booking.created, booking.status, form.submitted, ticket.created.
Xavfsizlik:
    • faqat https; host manzillari ommaviy (global) IP bo'lishi shart — localhost, ichki tarmoq va bulut metadata manzillari rad etiladi;
    • yo'naltirishlar (redirect) kuzatilmaydi;
    • har so'rov HMAC-SHA256 bilan imzolanadi (X-InetTime-Signature: sha256=...), kalit — webhook sirri.
Yetkazish fonda, 3 urinish (darhol, 3 s, 20 s); natijalar oxirgi 30 tasi egasiga ko'rsatiladi."""

import asyncio
import hashlib
import hmac
import html
import ipaddress
import json
import secrets
import socket
import time
from typing import TYPE_CHECKING
from urllib.parse import urlparse

import httpx

from core.botbuilder import WEBHOOK_EVENTS, new_page_id

if TYPE_CHECKING:
    from main import Runner, RunningBot

EVENT_LABELS = {
    "user.started": "👤 Yangi foydalanuvchi",
    "order.created": "🛒 Yangi buyurtma",
    "order.paid": "💳 To'langan buyurtma",
    "order.status": "📦 Buyurtma holati",
    "booking.created": "📅 Yangi yozilish",
    "booking.status": "📅 Yozilish holati",
    "form.submitted": "📝 Ariza (forma)",
    "ticket.created": "🎫 Yangi murojaat",
}
PRESETS = {
    "all": ("Hammasi", list(WEBHOOK_EVENTS)),
    "shop": ("Buyurtmalar", ["order.created", "order.paid", "order.status"]),
    "book": ("Yozilishlar", ["booking.created", "booking.status"]),
    "leads": ("Arizalar va murojaatlar", ["form.submitted", "ticket.created", "user.started"]),
}
APPS_SCRIPT = """function doPost(e) {
  var d = JSON.parse(e.postData.contents);
  var sh = SpreadsheetApp.getActiveSheet();
  var keys = Object.keys(d);
  if (sh.getLastRow() === 0) { sh.appendRow(keys); }
  var header = sh.getRange(1, 1, 1, Math.max(1, sh.getLastColumn())).getValues()[0];
  keys.forEach(function (k) {
    if (header.indexOf(k) < 0) { header.push(k); sh.getRange(1, header.length).setValue(k); }
  });
  sh.appendRow(header.map(function (h) { return d[h] === undefined ? '' : d[h]; }));
  return ContentService.createTextOutput('ok');
}"""
_tasks: set = set()


def esc(t) -> str:
    return html.escape(str(t or ""), quote=False)


# ============================================================
# Xavfsiz yuborish
# ============================================================


async def safe_url(url: str) -> str | None:
    """None — xavfsiz; aks holda sabab matni. Host barcha IP manzillari ommaviy bo'lishi kerak."""
    try:
        u = urlparse(url)
    except ValueError:
        return "manzil noto'g'ri"
    if u.scheme != "https" or not u.hostname:
        return "faqat https:// manzil"
    try:
        infos = await asyncio.get_running_loop().getaddrinfo(u.hostname, u.port or 443, type=socket.SOCK_STREAM)
    except OSError:
        return "domen topilmadi"
    for info in infos:
        try:
            ip = ipaddress.ip_address(info[4][0])
        except ValueError:
            return "manzil noto'g'ri"
        if not ip.is_global:
            return "ichki tarmoq manzillariga yuborish taqiqlangan"
    return None


def flatten(data: dict, prefix: str = "") -> dict:
    out: dict = {}
    for k, v in data.items():
        key = f"{prefix}{k}"
        if isinstance(v, dict):
            out.update(flatten(v, f"{key}_"))
        elif isinstance(v, list):
            out[key] = ", ".join(json.dumps(x, ensure_ascii=False) if isinstance(x, (dict, list)) else str(x) for x in v)
        else:
            out[key] = v
    return out


def build_body(bot: "RunningBot", hook: dict, event: str, data: dict) -> bytes:
    stamp = time.strftime("%Y-%m-%d %H:%M:%S", time.gmtime())
    if hook.get("kind") == "sheets":
        body = {"time": stamp, "event": event, "bot": bot.username, **flatten(data)}
    else:
        body = {"event": event, "time": stamp, "bot": {"id": bot.bot_id, "username": bot.username}, "data": data}
    return json.dumps(body, ensure_ascii=False, default=str).encode()


async def _log(runner: "Runner", bot: "RunningBot", hook: dict, event: str, ok: bool, info: str) -> None:
    key = f"ub:{bot.bot_id}:hooklog"
    await runner.redis.lpush(key, json.dumps({"t": time.strftime("%d.%m %H:%M:%S", time.gmtime(time.time() + 5 * 3600)), "hook": hook["id"], "event": event, "ok": ok, "info": info[:120]}, ensure_ascii=False))
    await runner.redis.ltrim(key, 0, 29)


async def deliver(runner: "Runner", bot: "RunningBot", hook: dict, event: str, data: dict, *, retries: tuple = (0, 3, 20)) -> bool:
    payload = build_body(bot, hook, event, data)
    headers = {"Content-Type": "application/json", "User-Agent": "InetTime-Webhook/1"}
    if hook.get("secret"):
        headers["X-InetTime-Signature"] = "sha256=" + hmac.new(hook["secret"].encode(), payload, hashlib.sha256).hexdigest()
    last = ""
    for delay in retries:
        if delay:
            await asyncio.sleep(delay)
        problem = await safe_url(hook["url"])
        if problem:
            await _log(runner, bot, hook, event, False, problem)
            return False
        try:
            async with httpx.AsyncClient(timeout=10, follow_redirects=False) as client:
                resp = await client.post(hook["url"], content=payload, headers=headers)
            if resp.status_code < 400:  # 3xx ham muvaffaqiyat (Apps Script natijani yo'naltiradi)
                await _log(runner, bot, hook, event, True, f"HTTP {resp.status_code}")
                return True
            last = f"HTTP {resp.status_code}"
        except httpx.HTTPError as exc:
            last = type(exc).__name__
    await _log(runner, bot, hook, event, False, last or "xato")
    return False


def emit(runner: "Runner", bot: "RunningBot", event: str, data: dict) -> None:
    """Hodisani mos webhooklarga fonda yuboradi (hech qachon botni sekinlashtirmaydi)."""
    if getattr(bot, "sandbox", False):
        return
    for hook in bot.menu.get("webhooks") or []:
        if hook.get("enabled", True) and event in hook.get("events", []):
            task = asyncio.create_task(deliver(runner, bot, hook, event, data))
            _tasks.add(task)
            task.add_done_callback(_tasks.discard)


# ============================================================
# Egasi: /admin → 🔌 Integratsiyalar
# ============================================================


def _hook(bot: "RunningBot", hid: str) -> dict | None:
    return next((h for h in bot.menu.get("webhooks") or [] if h["id"] == hid), None)


async def admin_home(runner, bot, chat_id: int, message: dict | None = None) -> None:
    import editor

    hooks = bot.menu.get("webhooks") or []
    text = (
        "🔌 <b>Integratsiyalar</b>\n\nBotdagi hodisalar (buyurtma, yozilish, ariza, murojaat...) tashqi tizimga avtomatik yuboriladi:\n"
        "• 🟢 <b>Google Sheets</b> — har bir hodisa jadvalga yangi qator bo'lib tushadi\n• 🔗 <b>Webhook</b> — CRM, Zapier/Make, o'z serveringiz (imzolangan JSON)\n\n"
        + ("\n".join(f"{'✅' if h.get('enabled', True) else '⏸'} {'🟢' if h['kind'] == 'sheets' else '🔗'} <b>{esc(h['title'] or h['url'][:30])}</b> — {len(h['events'])} hodisa" for h in hooks) if hooks else "<i>Hozircha yo'q.</i>")
    )
    rows = [[{"text": f"{'🟢' if h['kind'] == 'sheets' else '🔗'} {h['title'] or h['url'][8:30]}"[:50], "callback_data": f"wh:v:{h['id']}"}] for h in hooks]
    rows.append([{"text": "➕ Google Sheets", "callback_data": "wh:new:sheets"}, {"text": "➕ Webhook", "callback_data": "wh:new:json"}])
    rows.append([{"text": "📜 Yuborishlar tarixi", "callback_data": "wh:log"}, {"text": "⬅️ Panel", "callback_data": "adm:st"}])
    await editor.send(runner, bot, chat_id, text, rows, message=message)


async def _view(runner, bot, chat_id: int, hid: str, message: dict | None) -> None:
    import editor

    h = _hook(bot, hid)
    if h is None:
        await admin_home(runner, bot, chat_id, message)
        return
    text = (
        f"{'🟢 Google Sheets' if h['kind'] == 'sheets' else '🔗 Webhook'} — <b>{esc(h['title'] or '—')}</b>\n"
        f"📍 <code>{esc(h['url'][:120])}</code>\n📌 {'yoqilgan' if h.get('enabled', True) else 'to‘xtatilgan'}\n\n"
        "<b>Hodisalar:</b>\n" + "\n".join(f"• {EVENT_LABELS[e]}" for e in h["events"])
        + ("\n\n🔐 Imzo kaliti: <code>" + esc(h["secret"]) + "</code>\n<i>Server X-InetTime-Signature (HMAC-SHA256) orqali tekshiradi.</i>" if h["kind"] == "json" and h.get("secret") else "")
    )
    rows = [
        [{"text": "🧪 Sinov yuborish", "callback_data": f"wh:t:{hid}"}, {"text": "⏸ To'xtatish" if h.get("enabled", True) else "▶️ Yoqish", "callback_data": f"wh:o:{hid}"}],
        [{"text": "🎯 Hodisalar", "callback_data": f"wh:e:{hid}"}] + ([{"text": "📋 Skript (Sheets)", "callback_data": "wh:script"}] if h["kind"] == "sheets" else []),
        [{"text": "🗑 O'chirish", "callback_data": f"wh:x:{hid}"}, {"text": "⬅️ Ro'yxat", "callback_data": "wh:home"}],
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

    def edit(hid: str, **changes):
        def fn(m: dict) -> None:
            for h in m.get("webhooks") or []:
                if h["id"] == hid:
                    h.update(changes)

        return fn

    if cmd == "home":
        await admin.set_state(runner, bot, chat_id, None)
        await admin_home(runner, bot, chat_id, message)
    elif cmd == "new":
        if arg == "sheets":
            await runner.api(
                bot, "sendMessage",
                {
                    "chat_id": chat_id, "parse_mode": "HTML",
                    "text": "🟢 <b>Google Sheets ulash</b> (2 daqiqa):\n\n1) Google Sheets'da yangi jadval oching\n2) <b>Kengaytmalar → Apps Script</b>\n3) Quyidagi kodni joylang va saqlang\n4) <b>Deploy → New deployment → Web app</b> · Who has access: <b>Anyone</b> → Deploy\n5) Chiqqan <code>https://script.google.com/macros/s/.../exec</code> manzilni shu yerga yuboring\n\n<pre>" + esc(APPS_SCRIPT) + "</pre>",
                },
            )
        await admin.ask(runner, bot, chat_id, {"k": "wh_url", "kind": arg}, "🔗 Manzilni (https://...) yuboring:" if arg == "json" else "🔗 Apps Script web app manzilini yuboring:")
    elif cmd == "pre":
        # wh:pre:<preset>:<hid>
        hid = parts[3]
        events = PRESETS.get(arg, PRESETS["all"])[1]
        if await save(edit(hid, events=events)):
            await _view(runner, bot, chat_id, hid, message)
    elif cmd == "e":
        rows = [[{"text": label, "callback_data": f"wh:pre:{key}:{arg}"}] for key, (label, _) in PRESETS.items()] + [[{"text": "⬅️ Orqaga", "callback_data": f"wh:v:{arg}"}]]
        await editor.send(runner, bot, chat_id, "🎯 Qaysi hodisalar yuborilsin?", rows, message=message)
    elif cmd == "v":
        await _view(runner, bot, chat_id, arg, message)
    elif cmd == "o":
        h = _hook(bot, arg)
        if h and await save(edit(arg, enabled=not h.get("enabled", True))):
            await _view(runner, bot, chat_id, arg, message)
    elif cmd == "x":
        if await save(lambda m: m.update(webhooks=[h for h in m.get("webhooks") or [] if h["id"] != arg])):
            await admin_home(runner, bot, chat_id, message)
    elif cmd == "t":
        h = _hook(bot, arg)
        if h:
            ok = await deliver(runner, bot, h, "test.ping", {"message": "InetTime sinov xabari", "bot": bot.username}, retries=(0,))
            last = await runner.redis.lindex(f"ub:{bot.bot_id}:hooklog", 0)
            info = json.loads(last)["info"] if last else ""
            await runner.api(bot, "sendMessage", {"chat_id": chat_id, "text": ("✅ Yuborildi" if ok else "❌ Yuborilmadi") + f": {info}"})
    elif cmd == "log":
        entries = [json.loads(x) for x in await runner.redis.lrange(f"ub:{bot.bot_id}:hooklog", 0, 14)]
        body = "\n".join(f"{'✅' if e['ok'] else '❌'} {e['t']} · {e['event']} · {esc(e['info'])}" for e in entries) or "Hali yuborilmagan."
        await editor.send(runner, bot, chat_id, "📜 <b>Oxirgi yuborishlar</b>\n\n" + body, [[{"text": "⬅️ Integratsiyalar", "callback_data": "wh:home"}]], message=message)
    elif cmd == "script":
        await runner.api(bot, "sendMessage", {"chat_id": chat_id, "parse_mode": "HTML", "text": "📋 Apps Script kodi:\n\n<pre>" + esc(APPS_SCRIPT) + "</pre>"})


async def admin_input(runner, bot, chat_id: int, message: dict, state: dict) -> bool:
    import admin
    import editor

    kind = state.get("k", "")
    if not kind.startswith("wh_"):
        return False
    text = (message.get("text") or "").strip()
    if kind == "wh_url":
        problem = await safe_url(text) if text.startswith("https://") else "faqat https:// manzil"
        if problem:
            await runner.api(bot, "sendMessage", {"chat_id": chat_id, "text": f"⚠️ {problem}. Qayta yuboring yoki /cancel."})
            return True
        hid = new_page_id()
        hook = {
            "id": hid, "title": "Google Sheets" if state["kind"] == "sheets" else "Webhook", "url": text, "kind": state["kind"],
            "events": list(WEBHOOK_EVENTS), "secret": secrets.token_hex(12) if state["kind"] == "json" else "", "enabled": True,
        }
        error = await editor.save(runner, bot, lambda m: m.setdefault("webhooks", []).append(hook))
        if error:
            await runner.api(bot, "sendMessage", {"chat_id": chat_id, "text": f"⚠️ {error}"})
            return True
        await admin.set_state(runner, bot, chat_id, None)
        await runner.api(bot, "sendMessage", {"chat_id": chat_id, "text": "✅ Ulandi — hamma hodisalar yuboriladi. Kerak bo'lsa «🎯 Hodisalar» orqali toraytiring, «🧪 Sinov» bilan tekshiring."})
        await _view(runner, bot, chat_id, hid, None)
        return True
    return False
