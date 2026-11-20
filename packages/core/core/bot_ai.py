"""InetTime AI — bot va Web App konstruktori uchun suhbatdosh yordamchi.

Egasi oddiy so'z bilan yozadi («restoran uchun bot: menyu, buyurtma formasi, referal bilan ball») — AI to'liq
bot hujjatini (core/botbuilder.py formatida) qaytaradi. Hujjat tozalanadi va tekshiriladi; xato bo'lsa AI'ga bir
marta tuzatish uchun qaytariladi. Mavjud botni o'zgartirish ham shu yo'l bilan: AI joriy hujjatni ko'radi va
faqat so'ralgan qismni o'zgartiradi.

Xarajat: tarif bo'yicha kunlik limit (builder_ai_daily), har chaqiruv ai_usage'ga yoziladi."""

import copy
import datetime
import json
import re
from zoneinfo import ZoneInfo

from core import ai
from core.botbuilder import MenuError, html_to_plain, validate_menu
from core.settings import settings

DEFAULT_DAILY = 10
MAX_TOKENS = 14000
HISTORY = 6

BOT_SYSTEM = """You are InetTime AI — an expert Telegram bot architect inside a no-code bot builder.
The owner describes what they want in plain words; you design or modify their bot by returning the COMPLETE bot document.

Answer ONLY with a JSON object: {"reply": "<message to the owner>", "menu": <full bot document> | null}
- "reply": 1-5 short sentences in the owner's language (default: Uzbek, Latin script): what you built/changed, and what
  the owner should fill in themselves (real prices, phone, address, channel for mandatory subscription...). No JSON here.
- "menu": null ONLY when the owner asks a question or you truly need a clarification. Otherwise always the FULL document.

BOT DOCUMENT
{
 "start": "<id of the main page>",
 "style": "reply" | "inline" | "hybrid",
 "first_start": null | "<page id shown only on a user's very first /start>",
 "pages": [PAGE, ...],
 "variables": [{"key": "ball", "label": "Ball", "default": "0", "scope": "user" | "global"}],
 "forms": [{"id": "order", "title": "Buyurtma", "steps": [{"key": "ism", "question": "Ismingiz?", "type": "text|number|phone|email|photo|choice|location", "options": []}],
            "done_text": "✅ Rahmat, {ism}!", "target": null | "<page id opened after>", "notify": true}],
 "keywords": [{"words": ["narx", "price"], "match": "exact" | "contains" | "start", "target": "<page id>" | null, "reply": "<HTML text>"}],
 "commands": [{"command": "help", "description": "Yordam", "target": "<page id>"}],
 "referral": {"enabled": false, "reward": 1, "var": "balance", "notify": true, "text": "🎉 {name} sizning havolangiz orqali qo'shildi! +{reward}"},
 "fallback": "<reply to unknown messages>", "feedback_prompt": "...", "feedback_done": "...", "forward_all": false,
 "shop": SHOP, "booking": BOOKING
}
SHOP (built-in store with cart, checkout and order statuses — use it for ANY selling bot instead of order forms):
 {"enabled": true, "currency": "so'm", "delivery_fee": 0, "free_from": 0, "min_order": 0,
  "items": [{"id": "<[a-z0-9_-]>", "category": "<id of a page with module catalog>", "title": "Latte", "price": 28000,
             "old_price": null, "badge": "🔥 Hit", "text": "<HTML description>", "active": true}],
  "checkout": [{"key": "ism", "label": "👤 Ismingiz?", "type": "text|number|phone|email|choice|location", "options": []}],
  "done_text": "✅ Buyurtmangiz qabul qilindi! Raqami: <b>#{order}</b>"}
 Pages with "module": {"type": "catalog", "layout": "list"|"cards", "per_page": 8} show their category's items with
 ➕/➖ and a cart button (keyboard "inline", one intro post, a back button). {"type": "cart"} — the cart page;
 {"type": "orders"} — "My orders". A shop needs catalog pages, one cart page and one orders page reachable from the menu.
 Keep existing items (same id, file_id) unless the owner asks to change them; never invent file_id.
 Variables {cart_count} {cart_total} show the user's cart.
BOOKING (appointments: salon, clinic, car service, tutor, gym... — use it instead of "booking forms"):
 {"enabled": true, "services": [{"id": "<[a-z0-9_-]>", "title": "Soch olish", "minutes": 45, "price": 80000}],
  "staff": [{"id": "<id>", "title": "Aziza"}] (optional; empty = one shared schedule),
  "hours": {"0": "09:00-18:00", "1": "09:00-18:00", ..., "6": ""} ("0"=Monday ... "6"=Sunday, "" = day off),
  "step": 30, "days_ahead": 14, "min_notice": 1, "tz": 5, "confirm": "manual" | "auto", "remind": [24, 2]}
 Pages with "module": {"type": "booking"} (the booking wizard: service → staff → day → time → name/phone) and
 {"type": "mybookings"} ("My bookings" with cancel). Free times, double-booking protection, owner confirmation and
 reminders are automatic. Keep the owner's existing services/staff/hours unless asked to change them.
PAGE = {"id": "<[a-z0-9_-], max 24>", "title": "<short name>", "keyboard": "reply" | "inline", "nav": true|false,
        "messages": [POST, ...] (1-10), "buttons": [[BUTTON, ...], ...] (rows, max 8 per row, max 12 rows),
        "placeholder": "", "random_post": false, "ops": [{"var": "visits", "op": "add", "value": "1"}]}
POST = {"type": "text", "text": "<Telegram HTML: <b> <i> <u> <s> <code> <a href=\\"...\\"> <blockquote> <tg-spoiler>; may use {variables}>",
        "buttons": [[BUTTON]]  (inline buttons under THIS post)}
     | {"type": "question", "text": "Ismingiz nima?", "var": "ism", "input": "text|number|phone|email|photo|choice|location", "options": ["A", "B"]}
     | posts with "file_id" are the owner's photos/videos — keep them exactly as they are, never invent file_id.
BUTTON = {"text": "📦 Katalog", "action": ACTION, ...params,
          "cond": {"var": "ball", "op": "eq|ne|gt|lt|ge|le|set|unset|contains", "value": "10"} (optional visibility),
          "admin_only": false, "need_sub": false}
ACTION and params:
  page (target) · back · home · feedback (user's next message goes to the owner) · webapp
  url (url) [inline only] · alert (alert = popup text) [inline only]
  form (form = form id) · set (var, op: set|add|sub|clear, value, optional target) · share (share_text using {ref_link})
  check_sub (optional target) · notify (alert = note for admin, optional target) · random (targets: [page ids])
  contact (var, default "phone") [reply keyboard only] · location (var) [reply keyboard only]
Built-in variables: {name} {first_name} {last_name} {username} {user_id} {mention} {bot} {bot_username} {date} {time}
{ref_link} {ref_count} {subscribers}. Declare every custom variable (including question vars and form step keys you
reuse) in "variables".

HOW IT BEHAVES
- keyboard "reply": the page's buttons are the reply keyboard (a menu). A reply page WITHOUT buttons is a "leaf": tapping
  its button only sends its posts and keeps the current keyboard. nav: true adds a "⬅️ Orqaga | 🏠 Bosh menyu" row
  automatically to reply menus (never add your own back/home buttons to reply pages).
- keyboard "inline": buttons appear under the last post and tapping a page button replaces the message in place. Every
  inline page except the start page MUST end with an inline back button {"text": "⬅️ Orqaga", "action": "back"}.
- style "reply": all menus are reply keyboards. "inline": every page is inline. "hybrid": main menus are reply keyboards,
  details use inline buttons under posts (order, links, more info). Follow the owner's requested style exactly;
  if not specified, use "hybrid".
- A question post waits for the user's answer, stores it in var, then the following posts are sent (they can use {var}).
- Forms ask several questions in a row; answers are saved to variables and sent to the owner.

QUALITY RULES
- Build COMPLETE, working, rich bots with real structure and concrete content (emojis, real-looking prices like
  "25 000 so'm", phone numbers, hours). NEVER write placeholders such as "...", "…", "[narx]", "XXX" or "lorem".
  typically 8-30 pages for a full business bot: main menu, catalog/services with sub-sections, prices, about, FAQ,
  contacts with location, order/booking form, profile page with the user's variables, referral page if useful.
- Make it creative and specific to the owner's business; no lorem ipsum.
- When modifying, keep everything the owner did not ask to change (same ids, texts, media).
- Every referenced page id and form id must exist. Max {max_pages} pages.
- Never invent mandatory-subscription channels or admin IDs.
"""


class BuilderAIError(ai.AIError):
    pass



# --- Kunlik limit ---


def daily_limit(flags: dict) -> int:
    value = flags.get("builder_ai_daily")
    return DEFAULT_DAILY if value is None else int(value)


def _quota_key(user_id: int) -> str:
    today = datetime.datetime.now(ZoneInfo(settings.default_timezone)).strftime("%Y%m%d")
    return f"ai:builder:{user_id}:{today}"


async def take_quota(redis, user_id: int, limit: int) -> bool:
    if limit <= 0:
        return False
    key = _quota_key(user_id)
    used = await redis.incr(key)
    if used == 1:
        await redis.expire(key, 2 * 86400)
    if used > limit:
        await redis.decr(key)
        return False
    return True


async def refund_quota(redis, user_id: int) -> None:
    await redis.decr(_quota_key(user_id))


async def used_today(redis, user_id: int) -> int:
    value = await redis.get(_quota_key(user_id))
    return int(value) if value else 0


# --- Hujjatni AI uchun ixchamlash va qaytgan javobni tozalash ---

_DEFAULTS = {
    "url": None, "alert": "", "form": None, "var": None, "op": "set", "value": "", "targets": [], "share_text": "",
    "cond": None, "admin_only": False, "hidden": False, "need_sub": False, "file_id": None, "media_id": None,
    "buttons": [], "input": "text", "options": [], "placeholder": "", "protect": False, "notify": False, "ops": [],
    "random_post": False, "target": None,
}


def _strip(value):
    if isinstance(value, dict):
        return {k: _strip(v) for k, v in value.items() if not (k in _DEFAULTS and v == _DEFAULTS[k])}
    if isinstance(value, list):
        return [_strip(v) for v in value]
    return value


def compact(menu: dict) -> str:
    """Joriy hujjat — standart qiymatlarsiz (token tejaladi)."""
    doc = _strip(copy.deepcopy(menu))
    for p in doc.get("pages", []):
        p.pop("text", None)  # postlardan tiklanadi
        if p.get("media_id") is None:
            p.pop("media_id", None)
    return json.dumps(doc, ensure_ascii=False, separators=(",", ":"))


_ID = re.compile(r"[^a-z0-9_-]")


def _clean_id(raw, used: set) -> str:
    base = _ID.sub("", str(raw or "").lower().replace(" ", "_"))[:24] or "p"
    candidate, n = base, 2
    while candidate in used:
        suffix = f"_{n}"
        candidate = base[: 24 - len(suffix)] + suffix
        n += 1
    used.add(candidate)
    return candidate


def prepare(new: dict, current: dict) -> dict:
    """AI javobini hujjatga aylantiradi: id'lar tozalanadi, havolalar yangilanadi, egasining mediasi va
    xavfsizlik sozlamalari (adminlar, kanallar) saqlanadi, sahifa matni postlardan tiklanadi."""
    if not isinstance(new, dict) or not isinstance(new.get("pages"), list) or not new["pages"]:
        raise MenuError("AI bo'sh menyu qaytardi")
    doc = copy.deepcopy(new)
    valid_files = {m.get("file_id") for p in current.get("pages", []) for m in p.get("messages") or [] if m.get("file_id")}
    used: set = set()
    mapping: dict = {}
    for p in doc["pages"]:
        if not isinstance(p, dict):
            raise MenuError("AI noto'g'ri sahifa qaytardi")
        old = p.get("id")
        p["id"] = _clean_id(old, used)
        mapping[old] = p["id"]

    def remap(x):
        return mapping.get(x, x) if x is not None else None

    style = doc.get("style") if doc.get("style") in ("reply", "inline", "hybrid") else current.get("style", "hybrid")
    doc["style"] = style
    doc["start"] = remap(doc.get("start")) or doc["pages"][0]["id"]
    doc["first_start"] = remap(doc.get("first_start"))

    def fix_buttons(rows):
        out = []
        for row in rows or []:
            if not isinstance(row, list):
                row = [row]
            line = []
            for b in row:
                if not isinstance(b, dict) or not str(b.get("text", "")).strip():
                    continue
                b["text"] = str(b["text"]).strip()[:64]
                if b.get("target"):
                    b["target"] = remap(b["target"])
                if b.get("targets"):
                    b["targets"] = [remap(t) for t in b["targets"]]
                line.append(b)
            if line:
                out.append(line[:8])
        return out[:12]

    for p in doc["pages"]:
        p["title"] = str(p.get("title") or p["id"])[:64]
        p["keyboard"] = p.get("keyboard") if p.get("keyboard") in ("reply", "inline") else ("inline" if style == "inline" else "reply")
        msgs = []
        for m in p.get("messages") or []:
            if isinstance(m, str):
                m = {"type": "text", "text": m}
            if not isinstance(m, dict):
                continue
            kind = m.get("type", "text")
            if kind not in ("text", "question"):
                if m.get("file_id") not in valid_files:
                    continue  # AI o'ylab topgan media — tashlab yuboriladi
            if kind == "question" and m.get("var"):
                m["var"] = str(m["var"]).strip("{} ").lower()[:32]
            m["buttons"] = fix_buttons(m.get("buttons"))
            if kind == "text":
                m["text"] = str(m.get("text") or "").strip()[:4096] or p["title"]
            msgs.append(m)
        if not msgs:
            msgs = [{"type": "text", "text": str(p.get("text") or p["title"])[:4096], "buttons": []}]
        p["messages"] = msgs[:10]
        p["buttons"] = fix_buttons(p.get("buttons"))
        first = next((html_to_plain(m.get("text", "")) for m in msgs if m.get("type") != "question" and m.get("text")), "")
        p["text"] = (first or p["title"])[:4096]
        p["media_id"] = None
    for kw in doc.get("keywords") or []:
        if isinstance(kw, dict):
            kw["target"] = remap(kw.get("target"))
    for c in doc.get("commands") or []:
        if isinstance(c, dict):
            c["target"] = remap(c.get("target"))
    for f in doc.get("forms") or []:
        if isinstance(f, dict):
            f["target"] = remap(f.get("target"))
    _prepare_shop(doc, current, remap)
    _prepare_booking(doc, current)
    # Tizim kodi va tugallanmagan sozlash ustasi AI tahririda yo'qolmasin
    if current.get("system") and not doc.get("system"):
        doc["system"] = current["system"]
    if current.get("setup") and not doc.get("setup"):
        doc["setup"] = current["setup"]
    # Xavfsizlik: adminlar va majburiy obuna kanallarini faqat egasi o'zgartiradi
    doc["admins"] = current.get("admins") or []
    doc["channels"] = current.get("channels") or []
    if current.get("sub_text"):
        doc.setdefault("sub_text", current["sub_text"])
    # Savol o'zgaruvchilari e'lon qilinsin
    declared = {v.get("key") for v in doc.get("variables") or [] if isinstance(v, dict)}
    for p in doc["pages"]:
        for m in p["messages"]:
            if m.get("type") == "question" and m.get("var") and m["var"] not in declared:
                doc.setdefault("variables", []).append({"key": m["var"], "label": m["var"], "default": "", "scope": "user"})
                declared.add(m["var"])
    return doc


def _prepare_shop(doc: dict, current: dict, remap) -> None:
    """Do'kon: AI tashlab ketsa — egasining mahsulotlari saqlanadi; rasm (file_id) faqat mavjud mahsulotdan;
    bo'lim id'lari yangilanadi; katalog bo'limi yo'qolgan mahsulotlar birinchi katalogga o'tadi."""
    cur_shop = current.get("shop") or {}
    shop = doc.get("shop")
    if not isinstance(shop, dict):
        shop = copy.deepcopy(cur_shop) if cur_shop.get("items") else {"enabled": False}
        doc["shop"] = shop
    old_items = {i.get("id"): i for i in cur_shop.get("items") or []}
    if "items" not in shop and old_items:
        shop["items"] = copy.deepcopy(list(old_items.values()))
    catalogs = [p["id"] for p in doc["pages"] if isinstance(p.get("module"), dict) and p["module"].get("type") == "catalog"]
    for p in doc["pages"]:
        if p.get("module") is not None and (not isinstance(p["module"], dict) or p["module"].get("type") not in ("catalog", "cart", "orders", "booking", "mybookings")):
            p["module"] = None
    items, used = [], set()
    for it in shop.get("items") or []:
        if not isinstance(it, dict) or not it.get("title"):
            continue
        it["id"] = _clean_id(it.get("id") or it["title"], used)
        prev = old_items.get(it["id"])
        it["file_id"] = prev.get("file_id") if prev else None
        it["media_id"] = prev.get("media_id") if prev else None
        it["category"] = remap(it.get("category"))
        if it["category"] not in catalogs:
            if not catalogs:
                raise MenuError("mahsulotlar bor, lekin katalog bo'limi (module catalog) yo'q — katalog sahifalarini saqlang")
            it["category"] = catalogs[0]
        items.append(it)
    shop["items"] = items


def _prepare_booking(doc: dict, current: dict) -> None:
    """Yozilish: AI tashlab ketsa — egasining xizmat/xodim/jadvali saqlanadi; id'lar tozalanadi; sahifa yo'q bo'lsa — o'chiriladi."""
    cur = current.get("booking") or {}
    bk = doc.get("booking")
    if not isinstance(bk, dict):
        bk = copy.deepcopy(cur) if cur else {"enabled": False}
        doc["booking"] = bk
    for page in doc["pages"]:
        if page.get("module") is not None and (not isinstance(page["module"], dict) or page["module"].get("type") not in ("catalog", "cart", "orders", "booking", "mybookings")):
            page["module"] = None
    has_page = any(isinstance(p.get("module"), dict) and p["module"].get("type") == "booking" for p in doc["pages"])
    if not has_page:
        bk["enabled"] = False
    for key in ("services", "staff"):
        used: set = set()
        clean = []
        for x in bk.get(key) or []:
            if isinstance(x, dict) and x.get("title"):
                x["id"] = _clean_id(x.get("id") or x["title"], used)
                clean.append(x)
        bk[key] = clean
    if cur.get("hours") and not bk.get("hours"):
        bk["hours"] = cur["hours"]


def _parse(text: str) -> dict:
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        m = re.search(r"\{.*\}", text, re.S)
        if not m:
            raise BuilderAIError("AI javobini o'qib bo'lmadi, qaytadan urinib ko'ring") from None
        try:
            data = json.loads(m.group(0))
        except json.JSONDecodeError as exc:
            raise BuilderAIError("AI javobini o'qib bo'lmadi, qaytadan urinib ko'ring") from exc
    if not isinstance(data, dict):
        raise BuilderAIError("AI javobini o'qib bo'lmadi")
    return data


async def build_bot(model: str, current: dict, history: list[dict], request: str, max_pages: int) -> tuple[str, dict | None, list, dict]:
    """Mavjud botni o'zgartirish: (javob matni, yangi hujjat yoki None, [AIResult...], linter hisoboti)."""
    system = BOT_SYSTEM.replace("{max_pages}", str(max_pages))
    messages = [
        {"role": "system", "content": system},
        {"role": "user", "content": "CURRENT BOT DOCUMENT (modify it, or replace it entirely if the owner asks for a new bot):\n" + compact(current)},
    ]
    messages += [h for h in history[-HISTORY:] if h.get("role") in ("user", "assistant")]
    messages.append({"role": "user", "content": request[:4000]})
    results = []
    for attempt in range(2):
        result = await ai._complete(model, messages, MAX_TOKENS, json_mode=True)
        results.append(result)
        data = _parse(result.text)
        reply = str(data.get("reply") or "").strip()[:3000] or "Tayyor."
        raw = data.get("menu")
        if not raw:
            return reply, None, results, {}
        try:
            doc = prepare(raw, current)
            doc, ok, warn = lint(doc)
            menu = validate_menu(doc, max_pages)
            return reply, menu, results, {"ok": ok, "warn": warn, "verify": []}
        except MenuError as exc:
            if attempt == 1:
                raise BuilderAIError(f"AI tuzgan bot tekshiruvdan o'tmadi: {exc}. Talabni aniqroq yozib qayta urinib ko'ring.") from exc
            messages.append({"role": "assistant", "content": result.text[:20000]})
            messages.append({"role": "user", "content": f"Validation error: {exc}. Fix it and return the corrected FULL JSON again (same format)."})
    return "", None, results, {}


def tree(menu: dict, limit: int = 45) -> str:
    """Bot tuzilmasi: bosh sahifadan tugmalar bo'ylab daraxt (egasiga ko'rsatish uchun)."""
    pages = {p["id"]: p for p in menu.get("pages", [])}
    lines: list[str] = []
    seen: set = set()

    def walk(pid: str, depth: int) -> None:
        if len(lines) >= limit or pid in seen or pid not in pages:
            return
        seen.add(pid)
        p = pages[pid]
        icon = "⌨️" if p.get("keyboard") == "reply" else "💬"
        posts = len(p.get("messages") or [])
        q = sum(1 for m in p.get("messages") or [] if m.get("type") == "question")
        extra = f" · ❓{q}" if q else ""
        mod = (p.get("module") or {}).get("type")
        if mod == "catalog":
            n = sum(1 for i in (menu.get("shop") or {}).get("items") or [] if i.get("category") == pid)
            extra += f" · 🛍 {n} mahsulot"
        elif mod:
            extra += " · " + {"cart": "🛒 savat", "orders": "📦 buyurtmalar", "booking": "📅 yozilish", "mybookings": "📋 yozilishlarim"}.get(mod, mod)
        lines.append(f"{'   ' * depth}{icon} {p['title']} ({posts} post{extra})")
        children = [b for row in p.get("buttons") or [] for b in row] + [b for m in p.get("messages") or [] for row in m.get("buttons") or [] for b in row]
        for b in children:
            if b.get("action") == "page" and b.get("target"):
                walk(b["target"], depth + 1)
            elif depth < 3 and b.get("action") not in ("back", "home") and len(lines) < limit:
                lines.append(f"{'   ' * (depth + 1)}• {b['text']} → {b.get('action')}")

    walk(menu.get("start"), 0)
    for pid in pages:
        if pid not in seen and len(lines) < limit:
            walk(pid, 0)
    if len(lines) >= limit:
        lines.append("…")
    return "\n".join(lines)


def summary(menu: dict) -> str:
    pages = menu.get("pages", [])
    buttons = sum(len(r) for p in pages for r in p.get("buttons") or []) + sum(len(r) for p in pages for m in p.get("messages") or [] for r in m.get("buttons") or [])
    parts = [f"📄 {len(pages)} bo'lim", f"🔘 {buttons} tugma"]
    if menu.get("forms"):
        parts.append(f"📝 {len(menu['forms'])} forma")
    if menu.get("variables"):
        parts.append(f"🔢 {len(menu['variables'])} o'zgaruvchi")
    if menu.get("keywords"):
        parts.append(f"🔑 {len(menu['keywords'])} kalit so'z")
    if menu.get("commands"):
        parts.append(f"⌨️ {len(menu['commands'])} buyruq")
    if (menu.get("referral") or {}).get("enabled"):
        parts.append("👥 referal")
    if (menu.get("shop") or {}).get("items"):
        parts.append(f"🛒 do'kon: {len(menu['shop']['items'])} mahsulot")
    if (menu.get("booking") or {}).get("enabled"):
        parts.append(f"📅 yozilish: {len(menu['booking'].get('services') or [])} xizmat")
    style = {"reply": "⌨️ klaviatura", "inline": "💬 inline", "hybrid": "🔀 aralash"}.get(menu.get("style", "reply"), "")
    return " · ".join(parts) + f" · uslub: {style}"


# ============================================================
# Web App (Mini App) — AI bilan yaratish
# ============================================================

WEBAPP_HEAD = """You are InetTime AI — an expert designer of Telegram Mini Apps inside a no-code Web App builder.
The owner describes the app in plain words; you return the COMPLETE app document.

Answer ONLY with JSON: {"reply": "<1-4 sentences to the owner in their language (default Uzbek, Latin script)>", "doc": <full app document> | null,
                        "collections": [COLLECTION, ...] (only NEW data collections the app needs; omit if none)}
"doc": null only for questions/clarifications.
"""

WEBAPP_SPEC = """APP DOCUMENT
{"version": 1,
 "theme": {"preset": "light", "adaptive": false, "primary": "#RRGGBB", "background": "#RRGGBB", "surface": "#RRGGBB", "text": "#RRGGBB", "radius": 0-28,
           "font": "system|rounded|serif|mono|inter|manrope|montserrat|rubik|nunito|poppins|raleway|playfair|lora|oswald|comfortaa|jetbrains"},
 "settings": {"title": "<app name>", "currency": "so'm"},
 "start": "<page id>",
 "pages": [{"id": "<[A-Za-z0-9_-]>", "title": "<nav title>", "emoji": "🏠", "in_nav": true, "blocks": [BLOCK, ...]}]  (1-8 pages, up to 25 blocks each)}
BLOCK (every block may have "anim": "none|fade|up|zoom|left|right"):
 {"type": "hero", "title": "...", "subtitle": "...", "emoji": "🍕", "align": "center|left", "button": {"text": "...", "action": ACTION}}
 {"type": "heading", "text": "...", "size": 1|2|3, "align": "left|center"}
 {"type": "text", "text": "**bold** supported, line breaks", "align": "left|center", "muted": false}
 {"type": "button", "text": "...", "action": ACTION}
 {"type": "features", "columns": 1|2, "items": [{"emoji": "⚡", "title": "...", "text": "..."}]}
 {"type": "links", "items": [{"emoji": "📞", "title": "...", "subtitle": "...", "action": ACTION}]}
 {"type": "products", "title": "...", "columns": 1|2, "items": [{"title": "...", "price": 45000, "old_price": null, "emoji": "🍕", "text": "...", "badge": "Hit"}]}  (adds a cart + checkout)
 {"type": "form", "title": "...", "fields": [{"type": "text|textarea|phone|email|number|select|radio|checkbox|date", "label": "...", "placeholder": "", "required": true, "options": []}], "submit_text": "Yuborish", "success_text": "✅ ..."}
 {"type": "contacts", "phone": "+998...", "telegram": "@...", "instagram": "...", "website": "https://...", "address": "...", "map_url": "https://maps..."}
 {"type": "faq", "items": [{"q": "...", "a": "..."}]}
 {"type": "pricing", "items": [{"name": "...", "price": "99 000 so'm", "period": "oyiga", "features": ["..."], "highlight": false, "button": {"text": "...", "action": ACTION}}]}
 {"type": "stats", "items": [{"value": "10K+", "label": "Mijozlar"}]}
 {"type": "countdown", "title": "...", "date": "2026-12-31T20:00:00", "done_text": "..."}
 {"type": "video", "url": "<YouTube URL>", "caption": ""}
 {"type": "divider", "size": "s|m|l"}
 {"type": "custom", "name": "<section name>", "root": NODE}   — free design for creative sections (banners, cards, bento grids...)
ACTION = {"type": "none|page|url|bot|phone|share|cart", "page": "<page id>", "url": "https://...", "phone": "+998..."}
NODE (custom tree, max depth 8):
 {"kind": "box", "layout": "column|row|grid|scroll|stack|tabs|accordion|marquee", "gap": 0-96, "align": "start|center|end|stretch",
  "justify": "start|center|end|between|around", "columns": 1-6, "columns_wide": 1-8 (optional), "name": "<tab/accordion title>", "children": [NODE...]}
 {"kind": "text", "text": "...", "tag": "h1|h2|h3|p|small"} · {"kind": "button", "text": "...", "variant": "primary|secondary|outline|ghost|link", "icon": null, "action": ACTION}
 {"kind": "icon", "icon": "Star|Zap|Heart|ShoppingBag|Phone|MapPin|Clock|Gift|Rocket|Sparkles|Check|Truck|Users|Award|Coffee|Pizza", "size": 28, "emoji": ""}
 {"kind": "progress", "value": 0-100, "label": "..."} · {"kind": "rating", "value": 4.8} · {"kind": "spacer", "size": 16} · {"kind": "divider"}
 Any node may have "style": {"bg": "#RRGGBB|$primary|$surface|$bg|$text", "bg2": "#RRGGBB" (gradient), "bg_angle": 135, "color": "...",
   "px": 0-160, "py": 0-200, "radius": 0-999, "shadow": "s|m|l|xl|glow", "size": 8-120, "weight": 100-900, "align": "left|center|right",
   "backdrop": 0-60 (glass), "w": px, "h": px, "aspect": "1:1|4:3|16:9", "grow": true} and "anim", "loop": "float|pulse|bounce|glow".
RULES
- Make it beautiful, modern and specific to the owner's business: coherent theme colors, a strong hero, clear sections,
  realistic Uzbek content (unless the owner writes in another language), prices with real-looking numbers as placeholders.
- Use "custom" blocks for creative/unique sections when the owner wants a special design.
- When modifying, keep everything not asked to change. Never invent media_id values (images are uploaded by the owner).

DATA — build WHOLE SYSTEMS, not just pages. When the app shows a list of things the owner will keep updating (products,
menu items, services, courses, doctors, real estate, events, job vacancies, news, portfolio...) or collects submissions
(applications, bookings, reviews), create a data COLLECTION and bind blocks to it:
COLLECTION = {"key": "<[a-z][a-z0-9_]>", "name": "Mahsulotlar", "read": "public|own|none", "create": false,
              "fields": [{"key": "title", "label": "Nomi", "type": "text|longtext|number|money|date|bool|select|phone|url|email|image",
                          "required": true, "private": false, "options": []}],
              "records": [{"title": "...", "price": 45000, ...}]  (6-20 realistic starter records; never values for image fields)}
 {"type": "collection", "title": "...", "query": {"collection": "<key>", "limit": 20, "sort_field": null, "sort_dir": "desc",
   "filter_field": null, "filter_value": null, "search": true}, "layout": "cards|list|grid", "columns": 2,
   "title_field": "title", "subtitle_field": "...", "image_field": null, "price_field": "price", "badge_field": null,
   "detail_page": "<id of a detail page>"}
 Detail page: {"id": "item", "title": "Batafsil", "in_nav": false, "collection": "<key>", "blocks": [...]} — its texts use
   {{field_key}} placeholders (e.g. heading "{{title}}", text "{{description}}", button "Buyurtma berish").
 Submissions: a form block with "save_to": "<key>" writes answers into a collection with "read": "none" (owner only) or
   "own" (each user sees their own, e.g. "My bookings"), "create": true; the form field "id"s MUST equal the collection field keys.
 A "collection" block with read "own" shows the current user's own records (e.g. "📋 Mening arizalarim").
"""

WEBAPP_SYSTEM = WEBAPP_HEAD + "\n" + WEBAPP_SPEC

WEBAPP_PLAN_SYSTEM = """You are the lead product architect of InetTime AI, a no-code Telegram Mini App builder. Like a senior
product designer you first design the whole system: pages, navigation, data collections and the visual identity.
Other designers will build each page from your plan.

Answer ONLY with JSON:
{"mode": "new" | "edit" | "answer",
 "reply": "<1-3 sentences to the owner in their language (default Uzbek, Latin script)>",
 "brief": {"name": "", "business": "", "audience": "", "tone": "", "facts": {"phone": "", "address": "", "hours": "", "city": ""}},
 "theme": {"preset": "light", "adaptive": false, "primary": "#RRGGBB", "background": "#RRGGBB", "surface": "#RRGGBB", "text": "#RRGGBB",
           "radius": 0-28, "font": "inter|manrope|montserrat|rubik|nunito|poppins|raleway|playfair|lora|oswald|comfortaa|system"},
 "settings": {"title": "<app name>", "currency": "so'm"},
 "pages": [{"id": "home", "title": "Bosh sahifa", "emoji": "🏠", "in_nav": true, "collection": null,
            "purpose": "<what this page contains, block by block, specific to the business>"}],
 "collections": [COLLECTION]}
Modes: "new" — the owner describes an app to create (the current app is empty). "edit" — change the current app. "answer" — a question.
RULES
- 3-7 pages in the bottom navigation (in_nav true) + detail pages (in_nav false, "collection": "<key>") for collections.
- Home page: a strong hero, the value proposition, highlights and shortcuts to the main pages.
- Use collections for everything list-like the owner will update and for submissions (see DATA below).
- Pick a coherent, attractive palette and font that fit the business (e.g. coffee: warm browns; clinic: clean blue/white).
""" 

WEBAPP_PAGE_SYSTEM = """You are a senior UI designer and copywriter of InetTime AI. Build the blocks of ONE page of a Telegram
Mini App whose architecture is already designed. Make it beautiful, concrete and specific to the business: realistic Uzbek
texts (or the owner's language), real-looking prices and facts, creative "custom" sections where they add wow.
Answer ONLY with JSON: {"blocks": [BLOCK, ...]} (5-14 blocks).
Use only page ids, collection keys and field keys that exist in the plan. Navigation between pages uses ACTION {"type": "page"}.
"""


def _rid(prefix: str) -> str:
    import secrets

    return prefix + secrets.token_hex(4)


def prepare_webapp(new: dict, allowed_media: set[int], collections: dict[str, list[str]] | None = None) -> dict:
    """collections — {kalit: [maydon kalitlari]}: mavjud + AI taklif qilgan to'plamlar (ulardan boshqasiga bog'lanish olib tashlanadi)."""
    collections = collections or {}
    if not isinstance(new, dict) or not isinstance(new.get("pages"), list) or not new["pages"]:
        raise MenuError("AI bo'sh ilova qaytardi")
    doc = copy.deepcopy(new)
    doc["version"] = 1
    used: set = set()
    mapping: dict = {}
    for p in doc["pages"]:
        old = p.get("id")
        pid = re.sub(r"[^A-Za-z0-9_-]", "", str(old or ""))[:32] or _rid("p")
        while pid in used:
            pid = _rid("p")
        used.add(pid)
        mapping[old] = pid
        p["id"] = pid
    doc["start"] = mapping.get(doc.get("start"), doc["pages"][0]["id"])

    def fix_action(a):
        if isinstance(a, dict) and a.get("page") is not None:
            a["page"] = mapping.get(a["page"], a["page"])
        return a

    def walk_node(n):
        if not isinstance(n, dict):
            return
        n["id"] = _rid("n")
        if n.get("media_id") not in allowed_media:
            n.pop("media_id", None)
        if "action" in n:
            fix_action(n["action"])
        for c in n.get("children") or []:
            walk_node(c)

    page_ids = {p["id"] for p in doc["pages"]}
    for p in doc["pages"]:
        p["title"] = str(p.get("title") or "Sahifa")[:40]
        if p.get("collection") not in collections:
            p["collection"] = None
        blocks = []
        for b in p.get("blocks") or []:
            if not isinstance(b, dict) or b.get("type") in ("image", "gallery"):
                continue  # rasm bloklari egasining fayllarini talab qiladi
            if b.get("type") == "collection":
                q = b.get("query") if isinstance(b.get("query"), dict) else {}
                fields = collections.get(q.get("collection"))
                if fields is None:
                    continue
                b["query"] = q
                for name in ("title_field", "subtitle_field", "image_field", "price_field", "badge_field"):
                    if b.get(name) not in fields:
                        b[name] = None
                for name in ("sort_field", "filter_field"):
                    if q.get(name) not in fields:
                        q[name] = None
                if not q.get("filter_field"):
                    q["filter_value"] = None
                if not b.get("title_field") and fields:
                    b["title_field"] = fields[0]
                b["detail_page"] = mapping.get(b.get("detail_page"), b.get("detail_page"))
                if b["detail_page"] not in page_ids:
                    b["detail_page"] = None
            if b.get("type") == "form" and b.get("save_to") and b["save_to"] not in collections:
                b["save_to"] = None
            b["id"] = _rid("b")
            if b.get("media_id") not in allowed_media:
                b.pop("media_id", None)
            if "action" in b:
                fix_action(b["action"])
            if isinstance(b.get("button"), dict):
                fix_action(b["button"].get("action"))
            for item in b.get("items") or []:
                if isinstance(item, dict):
                    if b.get("type") == "products":
                        item["id"] = _rid("i")
                        item.pop("media_id", None)
                    if "action" in item:
                        fix_action(item["action"])
                    if isinstance(item.get("button"), dict):
                        fix_action(item["button"].get("action"))
            keep_ids = bool(b.get("type") == "form" and b.get("save_to"))
            seen_f: set = set()
            for f in b.get("fields") or []:
                if isinstance(f, dict):
                    fid = str(f.get("id") or "")
                    if not (keep_ids and re.match(r"^[a-z][a-z0-9_]{0,31}$", fid) and fid not in seen_f):
                        fid = _rid("f")
                    seen_f.add(fid)
                    f["id"] = fid
            if b.get("type") == "custom":
                walk_node(b.get("root"))
            blocks.append(b)
        p["blocks"] = blocks[:60]
    return doc


MAX_AI_COLLECTIONS = 8
MAX_AI_RECORDS = 40


def prepare_collections(raw, existing: dict[str, list[str]]) -> list[dict]:
    """AI taklif qilgan to'plamlar: tekshiriladi, yozuvlar tozalanadi (rasm qiymatlarisiz). Mavjud kalitlar o'tkaziladi."""
    from core.appdata import DataError, clean_record, validate_collection

    out: list[dict] = []
    for c in raw if isinstance(raw, list) else []:
        if not isinstance(c, dict) or len(out) >= MAX_AI_COLLECTIONS:
            continue
        key = re.sub(r"[^a-z0-9_]", "", str(c.get("key") or "").lower())[:32]
        if not key or not key[0].isalpha() or key in existing or any(x["key"] == key for x in out):
            continue
        fields = []
        for f in c.get("fields") or []:
            if not isinstance(f, dict):
                continue
            fk = re.sub(r"[^a-z0-9_]", "", str(f.get("key") or "").lower())[:32]
            if not fk or not fk[0].isalpha() or fk == "id" or any(x["key"] == fk for x in fields):
                continue
            opts = [str(o)[:80] for o in f.get("options") or [] if str(o).strip()][:50]
            ftype = f.get("type") if f.get("type") in ("text", "longtext", "number", "money", "image", "date", "bool", "select", "phone", "url", "email") else "text"
            if ftype == "select" and not opts:
                ftype = "text"
            fields.append({"key": fk, "label": str(f.get("label") or fk)[:64], "type": ftype, "required": bool(f.get("required")) and ftype != "image",
                           "private": bool(f.get("private")), "options": opts})
        try:
            spec = validate_collection({"key": key, "name": str(c.get("name") or key)[:64], "read": c.get("read") if c.get("read") in ("public", "own", "none") else "public",
                                        "create": bool(c.get("create")), "fields": fields[:40]})
        except DataError:
            continue
        records = []
        for r in (c.get("records") or [])[:MAX_AI_RECORDS]:
            if not isinstance(r, dict):
                continue
            r = {k: v for k, v in r.items() if k in {f["key"] for f in spec["fields"] if f["type"] != "image"}}
            try:
                records.append(clean_record([{**f, "required": False} if f["type"] == "image" else f for f in spec["fields"]], r))
            except DataError:
                continue
        spec["records"] = records
        out.append(spec)
    return out


def _app_blank(doc: dict) -> bool:
    return sum(len(p.get("blocks") or []) for p in doc.get("pages") or []) <= 3


async def build_webapp(
    model: str, current: dict, history: list[dict], request: str, allowed_media: set[int], existing: dict[str, list[str]] | None = None, progress=None
) -> tuple[str, dict | None, list, list]:
    """(javob, ilova hujjati yoki None, [AIResult], yangi to'plamlar). Bo'sh ilova uchun — v2: reja → sahifalar parallel."""
    from core.webapp_builder import WebAppError, validate_app

    existing = existing or {}
    if _app_blank(current):
        out = await _build_webapp_v2(model, current, history, request, allowed_media, existing)
        if out is not None:
            return out
    messages = [
        {"role": "system", "content": WEBAPP_SYSTEM},
        {"role": "user", "content": "CURRENT APP DOCUMENT (modify it, or replace it if the owner asks for a new app):\n" + json.dumps(current, ensure_ascii=False, separators=(",", ":"))[:60000]},
    ]
    messages += [h for h in history[-HISTORY:] if isinstance(h, dict) and h.get("role") in ("user", "assistant") and isinstance(h.get("content"), str)]
    messages.append({"role": "user", "content": request[:4000]})
    results = []
    for attempt in range(2):
        result = await ai._complete(model, messages, MAX_TOKENS, json_mode=True)
        results.append(result)
        data = _parse(result.text)
        reply = str(data.get("reply") or "").strip()[:3000] or "Tayyor."
        raw = data.get("doc")
        if not raw:
            return reply, None, results, []
        try:
            new_colls = prepare_collections(data.get("collections"), existing)
            known = {**existing, **{c["key"]: [f["key"] for f in c["fields"]] for c in new_colls}}
            doc = prepare_webapp(raw, allowed_media, known)
            # Sozlamalardagi buyurtma maydonlari egasiniki bo'lib qolsin
            if isinstance(current.get("settings"), dict):
                doc.setdefault("settings", {})
                for key in ("checkout_fields", "checkout_success", "currency"):
                    if key in current["settings"] and key not in doc["settings"]:
                        doc["settings"][key] = current["settings"][key]
            used = _used_keys(doc)
            return reply, validate_app(doc), results, [c for c in new_colls if c["key"] in used]
        except (MenuError, WebAppError) as exc:
            if attempt == 1:
                raise BuilderAIError(f"AI tuzgan ilova tekshiruvdan o'tmadi: {exc}. Talabni aniqroq yozib qayta urinib ko'ring.") from exc
            messages.append({"role": "assistant", "content": result.text[:20000]})
            messages.append({"role": "user", "content": f"Validation error: {exc}. Fix it and return the corrected FULL JSON again (same format)."})
    return "", None, results, []


def _used_keys(doc: dict) -> set[str]:
    from core.webapp_builder import used_collections

    return used_collections(doc)


async def _build_webapp_v2(model, current, history, request, allowed_media, existing) -> tuple[str, dict | None, list, list] | None:
    """Yangi ilova: 1) reja (sahifalar, to'plamlar, dizayn) 2) har sahifa bloklari parallel 3) yig'ish va tekshiruv.
    None — reja «edit» dedi (oddiy yo'l bilan davom etiladi)."""
    from core.webapp_builder import WebAppError, validate_app

    msgs = [{"role": "system", "content": WEBAPP_PLAN_SYSTEM + "\nDATA — " + WEBAPP_SPEC.split("DATA — ", 1)[1]}]
    msgs.append({"role": "user", "content": "CURRENT APP: empty (new app)." + (f" Existing data collections: {json.dumps(existing, ensure_ascii=False)}" if existing else "")})
    msgs += [h for h in history[-HISTORY:] if isinstance(h, dict) and h.get("role") in ("user", "assistant") and isinstance(h.get("content"), str)]
    msgs.append({"role": "user", "content": request[:4000]})
    res = await ai._complete(model, msgs, 9000, json_mode=True)
    results = [res]
    plan = _parse(res.text)
    mode = plan.get("mode")
    reply = str(plan.get("reply") or "").strip()[:3000] or "Tayyor."
    if mode == "answer":
        return reply, None, results, []
    if mode == "edit" or not isinstance(plan.get("pages"), list) or not plan["pages"]:
        return None
    new_colls = prepare_collections(plan.get("collections"), existing)
    known = {**existing, **{c["key"]: [f["key"] for f in c["fields"]] for c in new_colls}}
    pages = [p for p in plan["pages"] if isinstance(p, dict) and p.get("title")][:12]
    for p in pages:
        p["id"] = re.sub(r"[^A-Za-z0-9_-]", "", str(p.get("id") or ""))[:32] or _rid("p")
    outline = "\n".join(
        f"- {p['id']} | {p.get('emoji', '')} {p['title']} | nav: {bool(p.get('in_nav', True))} | detail of: {p.get('collection') or '—'} | {p.get('purpose', '')}" for p in pages
    )
    colls = "\n".join(f"- {k}: fields {', '.join(v)}" for k, v in known.items()) or "—"
    head = (
        f"BRIEF: {json.dumps(plan.get('brief') or {}, ensure_ascii=False)}\nTHEME: {json.dumps(plan.get('theme') or {}, ensure_ascii=False)}\n"
        f"PAGES (id | title | nav | detail of collection | purpose):\n{outline}\nCOLLECTIONS:\n{colls}\n\n"
    )
    system = WEBAPP_PAGE_SYSTEM + "\n" + WEBAPP_SPEC

    async def one(p: dict):
        r = await ai._complete(model, [{"role": "system", "content": system}, {"role": "user", "content": head + f"BUILD PAGE: {p['id']}"}], 9000, json_mode=True)
        try:
            blocks = _parse(r.text).get("blocks")
        except BuilderAIError:
            blocks = None
        return (blocks if isinstance(blocks, list) else []), r

    built = await asyncio.gather(*(one(p) for p in pages))
    results += [r for _, r in built]
    raw = {
        "version": 1,
        "theme": plan.get("theme") if isinstance(plan.get("theme"), dict) else {},
        "settings": plan.get("settings") if isinstance(plan.get("settings"), dict) else {},
        "start": pages[0]["id"],
        "pages": [
            {"id": p["id"], "title": p["title"], "emoji": str(p.get("emoji") or "")[:8], "in_nav": bool(p.get("in_nav", True)) and not p.get("collection"),
             "collection": p.get("collection"), "blocks": blocks}
            for p, (blocks, _) in zip(pages, built)
        ],
    }
    if isinstance(current.get("settings"), dict):
        for key in ("checkout_fields", "checkout_success"):
            if key in current["settings"]:
                raw["settings"].setdefault(key, current["settings"][key])
    try:
        doc = prepare_webapp(raw, allowed_media, known)
        # bo'sh qolgan sahifa — sarlavha bilan (validatsiya o'tsin, egasi to'ldiradi)
        for p in doc["pages"]:
            if not p["blocks"]:
                p["blocks"] = [{"id": _rid("b"), "type": "heading", "text": p["title"], "size": 1, "align": "left"}]
        doc = validate_app(doc)
    except (MenuError, WebAppError):
        return None  # bitta so'rovli yo'l bilan qayta urinadi
    used = _used_keys(doc)
    return reply, doc, results, [c for c in new_colls if c["key"] in used]



# ============================================================
# Quruvchi v2: dasturchi kabi bosqichma-bosqich
#   1) reja (brif + arxitektura, kerak bo'lsa aniqlashtiruvchi savollar)
#   2) mazmun (har bir bo'lim uchun postlar — parallel)
#   3) yig'ish (kod: navigatsiya, uslub, tugmalar — UX qoidalari kafolatlangan)
#   4) linter (tekshiruv va avtomatik tuzatish) → validate
# ============================================================

import asyncio  # noqa: E402

KINDS = ("menu", "info", "item", "form", "faq", "contacts", "profile", "referral", "feedback", "link", "catalog", "cart", "orders", "booking", "mybookings")

PLAN_SYSTEM = """You are the lead architect of InetTime AI, a no-code Telegram bot builder. You work like a senior bot developer:
first understand the business, then design a clean, logical bot architecture. Another step will write the texts.

Answer ONLY with JSON:
{
 "mode": "new" | "edit" | "ask" | "answer",
 "reply": "<short message to the owner in their language (default Uzbek, Latin script)>",
 "questions": ["..."],          // only for mode "ask": 2-5 short, specific questions with example answers
 "brief": {"name": "", "business": "", "audience": "", "tone": "", "facts": {"phone": "", "address": "", "hours": "", "city": "", "other": ""}},
 "plan": {...}                   // only for mode "new"
}
Modes:
- "new": the owner wants a new bot (or the current bot is empty/basic and they describe a bot) → design the full plan.
- "edit": the owner wants to change the CURRENT bot (add/remove/rename sections, change texts, style, buttons...).
- "ask": ONLY if questions are allowed (see the request) AND essential information is missing to build a good bot
  (e.g. what exactly they sell/offer). Do not ask about things you can reasonably invent (prices, texts).
- "answer": the owner asks a question about the builder or bot-making; answer in "reply".

PLAN FORMAT
{"style": "reply" | "inline" | "hybrid",
 "sections": [{"id": "start", "parent": null, "title": "🏠 Bosh menyu", "kind": "menu", "purpose": "<what this section does and what to say>"},
              {"id": "<snake_case>", "parent": "<parent id>", "title": "<emoji + 1-3 words, max 24 chars>", "kind": KIND, "purpose": "...",
               "fields": [...] (kind form only), "url": "https://..." (kind link only)}],
 "variables": [{"key": "ball", "label": "Ball", "default": "0"}],
 "keywords": [{"words": ["narx", "menyu"], "section": "<id>"}],
 "commands": [{"command": "menu", "description": "Menyu", "section": "<id>"}],
 "referral": {"enabled": false, "reward": 1, "var": "ball"},
 "booking": null | {"services": [{"title": "Soch olish", "minutes": 45, "price": 80000}], "staff": ["Aziza", "Dilnoza"],
                    "hours": "Du-Sha 09:00-18:00\\nYa yopiq", "confirm": "manual", "days_ahead": 14},
 "shop": null | {"currency": "so'm", "delivery_fee": 15000, "free_from": 200000, "min_order": 0, "pickup": false,
                 "checkout": [{"key": "ism", "label": "👤 Ismingiz?", "type": "text"}, ...]}}
KIND:
 menu — a group with children sections (catalog, categories, services list). info — a content page (about, delivery terms, promotions).
 item — one product/service card (name, description, price). form — a questionnaire/application/order form with
 "fields": [{"key": "ism", "label": "Ismingiz?", "type": "text|number|phone|email|photo|choice|location", "options": []}].
 faq — frequently asked questions. contacts — phone, address, hours, map. profile — the user's personal cabinet (their variables,
 points, referral stats). referral — invite friends page (needs referral.enabled). feedback — "write to admin" (live chat with the owner).
 link — opens an external URL (site, channel, Instagram) — needs "url".
 catalog — a product category of the built-in STORE (cart, checkout, order numbers and statuses are automatic). Needs
 "products": [{"title": "Latte", "price": 28000, "old_price": null, "badge": "", "text": "1-2 appetizing lines: taste, size, weight"}]
 (4-12 realistic products per category, integer prices in the currency). Leaf section (no children). "layout": "cards" when
 photos/visuals matter (clothes, cakes), otherwise "list".
 cart — the shopping cart page. orders — "📦 Buyurtmalarim" (the user's orders and their statuses).
 booking — the appointment wizard of the built-in BOOKING system (services, optional staff, working hours, free-time calendar,
 owner confirmation, reminders — all automatic). Define services/staff/hours in plan "booking". mybookings — "📋 Yozilishlarim".
ARCHITECTURE RULES
- Exactly one section with id "start" and parent null; every other section has an existing parent; max depth 3.
- The start menu has 4-8 children. A menu has 2-12 children. Put related things together (e.g. catalog → categories → items).
- Real businesses need: what you offer (catalog/services with real items), how to order/book (form), promotions, about,
  contacts, FAQ, feedback. Add profile + referral when points/bonuses/contests make sense.
- Anything that SELLS products (shop, restaurant/cafe delivery, bakery, flowers, clothes, pharmacy...) uses the STORE:
  "catalog" sections (one per category, under a "🛍 Katalog"/"🍽 Menyu" menu if more than one) + one "cart" + one "orders"
  section in the start menu + "shop" settings. Do NOT build order forms or item sections for such products.
  Businesses that take APPOINTMENTS (salon, barbershop, clinic, dentist, car service, tutor, gym, photographer...) use ONE
  "booking" section (+ plan "booking" with 3-8 real services with minutes and prices, staff names if several specialists,
  realistic hours) — never a plain form. Add info sections (about, prices, FAQ, contacts) around it.
- Products do not count as sections; sections count is limited.
- Titles: emoji + 1-3 words, max 24 characters, unique within a parent.
- Style: follow the owner's request exactly. If not specified: "hybrid" (main menus as keyboard, details inline).
- Typical size: 10-30 sections. Max {max_pages} sections.
- Use the owner's own language for titles (default Uzbek, Latin script)."""

CONTENT_SYSTEM = """You are the senior copywriter of InetTime AI. You write the posts (messages) of a Telegram bot whose
architecture is already designed. Write like a professional SMM specialist for this exact business: concrete, warm,
scannable, persuasive. Language: the owner's language (default Uzbek, Latin script, correct spelling: o', g', sh, ch).

Answer ONLY with JSON:
{"sections": {"<section id>": {"posts": [{"text": "<Telegram HTML>", "buttons": [[{"text": "🗺 Xaritada ochish", "url": "https://..."}]]}],
                               "done_text": "<only for form sections: thank-you message, may use {field keys}>"}},
 "fallback": "<reply when the user writes something unknown>",
 "verify": ["<facts you invented that the owner must check: prices, phone, address...>"]}
Write entries ONLY for the section ids listed in the request.
FORMAT RULES
- Telegram HTML only: <b>, <i>, <u>, <s>, <code>, <a href="...">, <blockquote>. Use \\n for new lines. No markdown.
- 1 post per section (2 only if really needed). 2-12 lines. Start with a bold title line with emoji.
- Use variables where natural: {name} (user's first name), {ref_link}, {ref_count}, and plan variables like {ball}.
- menu: 1-3 lines inviting to choose (the buttons are added automatically — do NOT list the buttons in text).
- item: name, 2-3 lines of appetizing/convincing description, key details (size, weight, duration...), "💰 Narxi: 45 000 so'm".
- info / promotions / about: concrete facts, benefits as short emoji lines.
- faq: 5-8 questions: "<b>❓ Savol?</b>\\nJavob." separated by blank lines.
- contacts: phone, address, working hours, and a map button (url https://maps.google.com/?q=<address>).
- form: 2-4 lines explaining what happens after submitting (the start button is added automatically).
- profile: template with {name} and the plan variables, e.g. "💎 Ballaringiz: <b>{ball}</b>".
- referral: how it works + "🔗 Sizning havolangiz:\\n{ref_link}" + "👥 Taklif qilganlaringiz: <b>{ref_count}</b>".
- booking: 2-3 lines inviting to book online, what the owner will do after (confirm, remind).
- catalog: 1-2 lines inviting to choose from this category (products and prices are shown automatically — do NOT list them).
- cart / orders: one short line title (content is generated automatically).
- start: a warm welcome with {name}, the bot's value in 2-3 lines, and a hint to use the menu.
- url buttons only with real https links. Never placeholders like "...", "[narx]", "XXX". If a fact is unknown,
  write a realistic value and add it to "verify"."""


def _sid(raw, used: set) -> str:
    return _clean_id(raw, used)


def summary_tree_plan(plan: dict) -> str:
    sections = plan.get("sections") or []
    children: dict = {}
    for sct in sections:
        children.setdefault(sct.get("parent"), []).append(sct)
    lines: list[str] = []

    def walk(pid, depth):
        for sct in children.get(pid, []):
            if len(lines) >= 45:
                return
            lines.append(f"{'   ' * depth}{sct.get('title')}")
            walk(sct.get("id"), depth + 1)

    walk(None, 0)
    return "\n".join(lines)


def _plan_fix(plan: dict, max_pages: int) -> dict:
    """Rejani tozalaydi: id'lar, ota-bola bog'lanishlar, chuqurlik, takrorlar."""
    sections = [sct for sct in plan.get("sections") or [] if isinstance(sct, dict) and sct.get("title")]
    used: set = set()
    mapping: dict = {}
    for sct in sections:
        old = sct.get("id")
        sct["id"] = "start" if old == "start" and "start" not in used else _sid(old or sct["title"], used)
        used.add(sct["id"])
        mapping[old] = sct["id"]
    if not any(sct["id"] == "start" for sct in sections):
        sections.insert(0, {"id": "start", "parent": None, "title": "🏠 Bosh menyu", "kind": "menu", "purpose": "welcome"})
    ids = {sct["id"] for sct in sections}
    for sct in sections:
        if sct["id"] == "start":
            sct["parent"] = None
            sct["kind"] = "menu"
            continue
        parent = mapping.get(sct.get("parent"), sct.get("parent"))
        sct["parent"] = parent if parent in ids and parent != sct["id"] else "start"
        if sct.get("kind") not in KINDS:
            sct["kind"] = "info"
        sct["title"] = str(sct["title"]).strip()[:24]
    # chuqurlik ≤ 4 va aylanmalar yo'q
    by_id = {sct["id"]: sct for sct in sections}
    for sct in sections:
        seen, cur, depth = set(), sct, 0
        while cur.get("parent") and depth < 6:
            if cur["parent"] in seen:
                sct["parent"] = "start"
                break
            seen.add(cur["parent"])
            cur = by_id.get(cur["parent"], {})
            depth += 1
        if depth > 4:
            sct["parent"] = "start"
    # yozilish: «Yozilishlarim» bitta; yozilish bo'lsa — avtomatik qo'shiladi
    for mod in ("booking", "mybookings"):
        for sct in [x for x in sections if x.get("kind") == mod][1:]:
            sections.remove(sct)
    if any(sct.get("kind") == "booking" for sct in sections):
        if not any(sct.get("kind") == "mybookings" for sct in sections):
            sid = _sid("mybookings", used)
            used.add(sid)
            sections.append({"id": sid, "parent": "start", "title": "📋 Yozilishlarim", "kind": "mybookings", "purpose": "my bookings"})
        by_id = {sct["id"]: sct for sct in sections}
    # do'kon: savat va buyurtmalar bitta; katalog bo'lsa — avtomatik qo'shiladi
    for mod in ("cart", "orders"):
        dup = [sct for sct in sections if sct.get("kind") == mod][1:]
        for sct in dup:
            sections.remove(sct)
    if any(sct.get("kind") == "catalog" for sct in sections):
        for mod, title in (("cart", "🛒 Savat"), ("orders", "📦 Buyurtmalarim")):
            if not any(sct.get("kind") == mod for sct in sections):
                sid = _sid(mod, used)
                used.add(sid)
                sections.append({"id": sid, "parent": "start", "title": title, "kind": mod, "purpose": title})
        by_id = {sct["id"]: sct for sct in sections}
    # bolasi bor bo'limlar — menyu (katalog/savat bargligicha qoladi — bolalari ota menyuga ko'chadi)
    for sct in sections:
        parent = by_id.get(sct.get("parent"))
        if parent and parent.get("kind") in ("catalog", "cart", "orders", "booking", "mybookings"):
            sct["parent"] = parent.get("parent") or "start"
    parents = {sct["parent"] for sct in sections if sct.get("parent")}
    for sct in sections:
        if sct["id"] in parents and sct["kind"] not in ("menu",):
            sct["kind"] = "menu"
    # Tarif limiti: avval yuqori darajalar (bosh menyu bo'limlari saqlanadi), eng chuqurlari qisqaradi.
    # «Adminga yozish» sahifa yaratmaydi — hisobga kirmaydi.
    def level(sct) -> int:
        d, cur = 0, sct
        while cur.get("parent") and d < 6:
            cur = by_id.get(cur["parent"], {})
            d += 1
        return d

    ordered = sorted(sections, key=level)
    keep: set = set()
    pages_used = 0
    for sct in ordered:
        if sct["id"] != "start" and sct["parent"] not in keep:
            continue
        cost = 0 if sct["kind"] == "feedback" else 1
        if pages_used + cost > max_pages:
            continue
        keep.add(sct["id"])
        pages_used += cost
    plan["_dropped"] = len(sections) - len(keep)
    # Bolalari qisqargan menyu bo'sh qolmasin: matnli sahifaga aylanadi va qisqargan narsalarni matnda sanab beradi
    for sct in sections:
        if sct["id"] in keep and sct["kind"] == "menu" and sct["id"] != "start":
            kids = [k for k in sections if k.get("parent") == sct["id"]]
            if kids and not any(k["id"] in keep for k in kids):
                sct["kind"] = "info"
                sct["purpose"] = f"{sct.get('purpose', '')}. List these items with short descriptions and prices in the text: " + ", ".join(k["title"] for k in kids)
    plan["sections"] = [sct for sct in sections if sct["id"] in keep]
    if not any(sct["kind"] == "catalog" for sct in plan["sections"]):
        plan["sections"] = [sct for sct in plan["sections"] if sct["kind"] not in ("cart", "orders")]
    if not any(sct["kind"] == "booking" for sct in plan["sections"]):
        plan["sections"] = [sct for sct in plan["sections"] if sct["kind"] != "mybookings"]
    plan["style"] = plan.get("style") if plan.get("style") in ("reply", "inline", "hybrid") else "hybrid"
    return plan


async def plan_request(model: str, current: dict, history: list[dict], request: str, *, allow_questions: bool, max_pages: int) -> tuple[dict, list]:
    system = PLAN_SYSTEM.replace("{max_pages}", str(max_pages))
    pages = len(current.get("pages") or [])
    context = (
        f"CURRENT BOT: {pages} sections. Structure:\n{tree(current, 40)}\n\n"
        f"Questions allowed: {'yes' if allow_questions else 'no — decide everything yourself'}."
    )
    messages = [{"role": "system", "content": system}, {"role": "user", "content": context}]
    messages += [h for h in history[-HISTORY:] if h.get("role") in ("user", "assistant")]
    messages.append({"role": "user", "content": request[:4000]})
    result = await ai._complete(model, messages, 9000, json_mode=True)
    data = _parse(result.text)
    mode = data.get("mode") if data.get("mode") in ("new", "edit", "ask", "answer") else "new"
    if mode == "ask" and not allow_questions:
        mode = "new"
    data["mode"] = mode
    if mode == "new":
        if not isinstance(data.get("plan"), dict) or not data["plan"].get("sections"):
            raise BuilderAIError("AI bot rejasini tuza olmadi — talabni batafsilroq yozib ko'ring")
        data["plan"] = _plan_fix(data["plan"], max_pages)
    return data, [result]


async def write_content(model: str, brief: dict, plan: dict) -> tuple[dict, list]:
    """Bo'limlar matnlari: katta botlarda bo'laklarga bo'linib parallel yoziladi."""
    sections = plan["sections"]
    outline = "\n".join(
        f"- {sct['id']} | parent: {sct.get('parent')} | {sct['kind']} | {sct['title']} | {sct.get('purpose', '')}"
        + (f" | fields: {', '.join(f.get('label', '') for f in sct.get('fields') or [] if isinstance(f, dict))}" if sct["kind"] == "form" else "")
        + (f" | products: {', '.join(str(x.get('title', '')) for x in sct.get('products') or [] if isinstance(x, dict))[:300]}" if sct["kind"] == "catalog" else "")
        for sct in sections
    )
    variables = ", ".join(f"{{{v.get('key')}}}" for v in plan.get("variables") or [] if isinstance(v, dict))
    head = (
        f"BUSINESS BRIEF: {json.dumps(brief, ensure_ascii=False)}\nSTYLE: {plan['style']}\nVARIABLES: {variables or '—'}\n"
        f"FULL ARCHITECTURE (id | parent | kind | title | purpose):\n{outline}\n\n"
    )
    writable = [sct for sct in sections if sct["kind"] not in ("feedback", "cart", "orders", "mybookings")]
    chunks = [writable[i : i + 10] for i in range(0, len(writable), 10)] or [[]]

    async def one(chunk: list) -> tuple[dict, ai.AIResult]:
        ids = ", ".join(sct["id"] for sct in chunk)
        res = await ai._complete(
            model,
            [{"role": "system", "content": CONTENT_SYSTEM}, {"role": "user", "content": head + f"WRITE POSTS FOR SECTIONS: {ids}"}],
            9000,
            json_mode=True,
        )
        return _parse(res.text), res

    results = await asyncio.gather(*(one(ch) for ch in chunks))
    content: dict = {"sections": {}, "fallback": "", "verify": []}
    for data, _ in results:
        if isinstance(data.get("sections"), dict):
            content["sections"].update(data["sections"])
        content["fallback"] = content["fallback"] or str(data.get("fallback") or "")
        content["verify"] += [str(v) for v in data.get("verify") or [] if v][:10]
    return content, [r for _, r in results]


def _rows(buttons: list[dict], per_row_short: int = 2) -> list[list[dict]]:
    rows, line = [], []
    for b in buttons:
        short = len(b["text"]) <= 16
        if not short:
            if line:
                rows.append(line)
                line = []
            rows.append([b])
            continue
        line.append(b)
        if len(line) == per_row_short:
            rows.append(line)
            line = []
    if line:
        rows.append(line)
    return rows


def compile_plan(plan: dict, content: dict) -> dict:
    """Reja + mazmun → bot hujjati. Navigatsiya va uslub kod bilan kafolatlanadi."""
    style = plan["style"]
    sections = plan["sections"]
    by_id = {sct["id"]: sct for sct in sections}
    children: dict = {}
    for sct in sections:
        if sct.get("parent"):
            children.setdefault(sct["parent"], []).append(sct)

    def depth(sct) -> int:
        d, cur = 0, sct
        while cur.get("parent"):
            d += 1
            cur = by_id[cur["parent"]]
        return d

    def keyboard(sct) -> str:
        if style == "inline":
            return "inline"
        if style == "reply":
            return "reply"
        # hybrid: bosh va 1-daraja menyular klaviatura, chuqurroqlari inline
        if sct["kind"] == "menu":
            return "reply" if depth(sct) <= 1 else "inline"
        parent = by_id.get(sct.get("parent"))
        return keyboard(parent) if parent and parent["kind"] == "menu" and depth(parent) > 1 else "reply"

    forms, pages, items = [], [], []
    item_ids: set = set()
    for sct in sections:
        if sct["kind"] == "feedback":
            continue
        if sct["kind"] in ("catalog", "cart", "orders", "booking", "mybookings"):
            page = _store_page(sct, (content.get("sections") or {}).get(sct["id"]) or {})
            if sct["kind"] == "catalog":
                items += _products(sct, item_ids)
            pages.append(page)
            continue
        data = (content.get("sections") or {}).get(sct["id"]) or {}
        posts = []
        for post in data.get("posts") or []:
            if isinstance(post, str):
                post = {"text": post}
            if not isinstance(post, dict) or not str(post.get("text", "")).strip():
                continue
            btns = []
            for row in post.get("buttons") or []:
                row = row if isinstance(row, list) else [row]
                line = [
                    {"text": str(b.get("text"))[:64], "action": "url", "url": str(b.get("url"))}
                    for b in row
                    if isinstance(b, dict) and b.get("text") and str(b.get("url", "")).startswith(("https://", "http://", "tg://"))
                ]
                if line:
                    btns.append(line)
            posts.append({"type": "text", "text": str(post["text"])[:4000], "buttons": btns})
        if not posts:
            posts = [{"type": "text", "text": f"<b>{sct['title']}</b>\n\n{sct.get('purpose') or ''}".strip(), "buttons": []}]
        kb = keyboard(sct)
        page = {"id": sct["id"], "title": sct["title"], "keyboard": kb, "messages": posts[:3], "buttons": [], "nav": False}
        extra: list[list[dict]] = []
        if sct["kind"] == "form":
            fid = "f_" + sct["id"][:20]
            steps, keys = [], set()
            for i, f in enumerate(sct.get("fields") or []):
                if not isinstance(f, dict) or not f.get("label"):
                    continue
                key = _ID.sub("", str(f.get("key") or f"javob{i + 1}").lower())[:32] or f"javob{i + 1}"
                if not key[0].isalpha():
                    key = "j" + key
                if key in keys:
                    key = f"{key}{i + 1}"
                keys.add(key)
                ftype = f.get("type") if f.get("type") in ("text", "number", "phone", "email", "photo", "choice", "location") else "text"
                opts = [str(o)[:64] for o in f.get("options") or [] if str(o).strip()][:12]
                if ftype == "choice" and not opts:
                    ftype = "text"
                steps.append({"key": key, "question": str(f["label"])[:500], "type": ftype, "options": opts})
            if not steps:
                steps = [{"key": "ism", "question": "Ismingiz?", "type": "text", "options": []}, {"key": "telefon", "question": "Telefon raqamingiz?", "type": "phone", "options": []}]
            forms.append({"id": fid, "title": sct["title"], "steps": steps[:20], "done_text": str(data.get("done_text") or "✅ Rahmat! Arizangiz qabul qilindi, tez orada bog'lanamiz."), "target": None, "notify": True})
            extra.append([{"text": "📝 To'ldirishni boshlash", "action": "form", "form": fid}])
        elif sct["kind"] == "referral":
            extra.append([{"text": "📤 Do'stlarga ulashish", "action": "share", "share_text": f"{sct['title']} — qo'shiling! {{ref_link}}"}])
        elif sct["kind"] == "link" and str(sct.get("url", "")).startswith("https://"):
            extra.append([{"text": "🔗 Ochish", "action": "url", "url": sct["url"]}])
        kids = children.get(sct["id"], [])
        kid_buttons = []
        for k in kids:
            if k["kind"] == "feedback":
                kid_buttons.append({"text": k["title"], "action": "feedback"})
            else:
                kid_buttons.append({"text": k["title"], "action": "page", "target": k["id"]})
        if kb == "reply":
            page["buttons"] = _rows(kid_buttons)
            page["nav"] = sct["id"] != "start" and bool(kid_buttons)
            if extra:
                posts[-1]["buttons"] = posts[-1]["buttons"] + extra
        else:
            rows = _rows(kid_buttons) + extra
            if sct["id"] != "start":
                rows.append([{"text": "⬅️ Orqaga", "action": "back"}])
            page["buttons"] = rows
        pages.append(page)

    variables = [
        {"key": str(v.get("key")).lower(), "label": str(v.get("label") or v.get("key"))[:64], "default": str(v.get("default") or ""),
         "scope": "global" if v.get("scope") == "global" else "user"}
        for v in plan.get("variables") or []
        if isinstance(v, dict) and v.get("key") and _VARKEY.match(str(v.get("key")).lower())
    ]
    ref = plan.get("referral") or {}
    if any(sct["kind"] == "referral" for sct in sections):
        ref = {**ref, "enabled": True}
    if ref.get("enabled"):
        var = str(ref.get("var") or "ball").lower()
        if not _VARKEY.match(var):
            var = "ball"
        ref = {"enabled": True, "reward": int(ref.get("reward") or 1), "var": var, "notify": True}
        if not any(v["key"] == var for v in variables):
            variables.append({"key": var, "label": var.capitalize(), "default": "0", "scope": "user"})
    known = {p["id"] for p in pages}
    keywords = [
        {"words": [str(w).lower()[:50] for w in k.get("words") or [] if str(w).strip()][:20], "match": "contains", "target": k.get("section"), "reply": ""}
        for k in plan.get("keywords") or []
        if isinstance(k, dict) and k.get("section") in known and k.get("words")
    ]
    commands = []
    for c in plan.get("commands") or []:
        if isinstance(c, dict) and c.get("section") in known:
            name = _ID.sub("", str(c.get("command") or "").lower().lstrip("/")).replace("-", "_")[:32]
            if name and name not in ("start", "admin", "cancel", "edit") and not any(x["command"] == name for x in commands):
                commands.append({"command": name, "description": str(c.get("description") or name)[:256], "target": c["section"]})
    shop = {"enabled": False}
    if items or any(sct["kind"] == "catalog" for sct in sections):
        cfg = plan.get("shop") if isinstance(plan.get("shop"), dict) else {}
        shop = {"enabled": True, "items": items, "currency": str(cfg.get("currency") or "so'm")[:12]}
        for key in ("delivery_fee", "free_from", "min_order"):
            try:
                shop[key] = max(0, int(float(cfg.get(key) or 0)))
            except (TypeError, ValueError):
                pass
        checkout, keys = [], set()
        for i, f in enumerate(cfg.get("checkout") or []):
            if not isinstance(f, dict) or not f.get("label"):
                continue
            key = _ID.sub("", str(f.get("key") or f"javob{i + 1}").lower()).replace("-", "_")[:32] or f"javob{i + 1}"
            key = key if key[0].isalpha() else "j" + key
            if key in keys:
                continue
            keys.add(key)
            ftype = f.get("type") if f.get("type") in ("text", "number", "phone", "email", "choice", "location") else "text"
            opts = [str(o)[:64] for o in f.get("options") or [] if str(o).strip()][:12]
            checkout.append({"key": key, "label": str(f["label"])[:200], "type": ftype if (ftype != "choice" or opts) else "text", "options": opts})
        if checkout:
            if not any(f["type"] == "phone" for f in checkout) and len(checkout) < 10:
                checkout.insert(min(1, len(checkout)), {"key": "telefon" if "telefon" not in keys else "tel", "label": "📱 Telefon raqamingiz?", "type": "phone", "options": []})
            shop["checkout"] = checkout[:10]
        elif cfg.get("pickup"):
            shop["checkout"] = [
                {"key": "ism", "label": "👤 Ismingiz?", "type": "text", "options": []},
                {"key": "telefon", "label": "📱 Telefon raqamingiz?", "type": "phone", "options": []},
            ]
    booking = _booking_cfg(plan) if any(sct["kind"] == "booking" for sct in sections) else {"enabled": False}
    return {
        "start": "start",
        "style": style,
        "shop": shop,
        "booking": booking,
        "pages": pages,
        "variables": variables,
        "forms": forms,
        "keywords": keywords,
        "commands": commands,
        "referral": ref if ref.get("enabled") else {"enabled": False},
        "fallback": content.get("fallback") or "Menyudan kerakli bo'limni tanlang 👇",
    }


_VARKEY = re.compile(r"^[a-z][a-z0-9_]{0,31}$")


def _booking_cfg(plan: dict) -> dict:
    """Reja → yozilish sozlamalari (xizmatlar, xodimlar, jadval). Noto'g'ri qiymatlar standartga qaytadi."""
    from core.booking import parse_hours
    from core.botbuilder import DEFAULT_HOURS

    cfg = plan.get("booking") if isinstance(plan.get("booking"), dict) else {}
    used: set = set()
    services = []
    for x in (cfg.get("services") or [])[:40]:
        title = str(x.get("title") if isinstance(x, dict) else x or "").strip()
        if not title:
            continue
        x = x if isinstance(x, dict) else {}
        try:
            minutes = min(720, max(5, int(float(x.get("minutes") or 30))))
            price = max(0, int(float(str(x.get("price") or 0).replace(" ", ""))))
        except ValueError:
            minutes, price = 30, 0
        services.append({"id": _clean_id("s_" + title[:10], used), "title": title[:64], "minutes": minutes, "price": price})
    if not services:
        services = [{"id": "s_qabul", "title": "Qabul", "minutes": 30, "price": 0}]
    staff = []
    for n in (cfg.get("staff") or [])[:20]:
        n = str(n.get("title") if isinstance(n, dict) else n or "").strip()
        if n:
            staff.append({"id": _clean_id("t_" + n[:10], used), "title": n[:64]})
    hours = cfg.get("hours")
    if isinstance(hours, str):
        hours = parse_hours(hours)
    elif isinstance(hours, dict):
        hours = {str(k): str(v or "") for k, v in hours.items()}
    out = {"enabled": True, "services": services, "staff": staff, "hours": hours or dict(DEFAULT_HOURS), "confirm": "auto" if cfg.get("confirm") == "auto" else "manual"}
    try:
        out["days_ahead"] = min(90, max(1, int(cfg.get("days_ahead") or 14)))
    except (TypeError, ValueError):
        pass
    return out


def _store_page(sct: dict, data: dict) -> dict:
    """Do'kon bo'limi (katalog / savat / buyurtmalar) — doim inline, bitta kirish posti va «Orqaga»."""
    post = next((p for p in data.get("posts") or [] if (isinstance(p, dict) and str(p.get("text", "")).strip()) or (isinstance(p, str) and p.strip())), None)
    text = (post["text"] if isinstance(post, dict) else post) if post else f"<b>{sct['title']}</b>"
    module: dict = {"type": sct["kind"]}
    if sct["kind"] == "catalog":
        module.update(layout="cards" if sct.get("layout") == "cards" else "list", per_page=8)
    return {
        "id": sct["id"],
        "title": sct["title"],
        "keyboard": "inline",
        "messages": [{"type": "text", "text": str(text)[:1000], "buttons": []}],
        "buttons": [[{"text": "⬅️ Orqaga", "action": "back"}]] if sct.get("parent") != "start" else [],
        "nav": False,
        "module": module,
    }


def _products(sct: dict, used: set) -> list[dict]:
    out = []
    for x in (sct.get("products") or [])[:60]:
        if not isinstance(x, dict) or not str(x.get("title", "")).strip():
            continue
        try:
            price = max(0, int(float(str(x.get("price") or 0).replace(" ", "").replace(",", "."))))
        except ValueError:
            continue
        item = {
            "id": _clean_id("i_" + sct["id"][:12] + f"_{len(out) + 1}", used),
            "category": sct["id"],
            "title": str(x["title"]).strip()[:64],
            "price": price,
            "text": str(x.get("text") or "").strip()[:900],
            "badge": str(x.get("badge") or "").strip()[:20],
            "active": True,
        }
        try:
            old = int(float(x.get("old_price") or 0))
            if old > price:
                item["old_price"] = old
        except (TypeError, ValueError):
            pass
        out.append(item)
    return out


_PLACEHOLDER = re.compile(r"(\.\.\.|…|\[[^\]]{1,30}\]|XXX|lorem ipsum|TODO)", re.I)


def lint(menu: dict) -> tuple[dict, list[str], list[str]]:
    """Sifat tekshiruvi. (tuzatilgan hujjat, ✅ o'tganlar, ⚠️ ogohlantirishlar)."""
    doc = copy.deepcopy(menu)
    ok, warn = [], []
    pages = {p["id"]: p for p in doc.get("pages", [])}
    start = doc.get("start")
    fixed_back = 0
    for p in doc.get("pages", []):
        if p["id"] == start:
            continue
        if p.get("keyboard") == "inline":
            has_back = any(b.get("action") in ("back", "home") for row in p.get("buttons") or [] for b in row)
            if not has_back:
                p.setdefault("buttons", []).append([{"text": "⬅️ Orqaga", "action": "back"}])
                fixed_back += 1
        elif p.get("buttons") and not p.get("nav"):
            has_back = any(b.get("action") in ("back", "home") for row in p["buttons"] for b in row)
            if not has_back:
                p["nav"] = True
                fixed_back += 1
    if fixed_back:
        ok.append(f"{fixed_back} ta bo'limga «Orqaga» yo'li qo'shildi")
    # yetib borish
    reach, stack = set(), [start]
    while stack:
        pid = stack.pop()
        if pid in reach or pid not in pages:
            continue
        reach.add(pid)
        p = pages[pid]
        for row in (p.get("buttons") or []) + [r for m in p.get("messages") or [] for r in m.get("buttons") or []]:
            for b in row:
                for t in [b.get("target")] + list(b.get("targets") or []):
                    if t:
                        stack.append(t)
    reach |= {k.get("target") for k in doc.get("keywords") or []} | {c.get("target") for c in doc.get("commands") or []}
    lost = [p["title"] for p in doc.get("pages", []) if p["id"] not in reach]
    if lost:
        warn.append("Hech qayerdan ochilmaydigan bo'limlar: " + ", ".join(lost[:6]))
    else:
        ok.append("Barcha bo'limlarga yetib borish mumkin")
    # joy tutuvchilar
    holes = [p["title"] for p in doc.get("pages", []) for m in p.get("messages") or [] if _PLACEHOLDER.search(html_to_plain(m.get("text", "")))]
    if holes:
        warn.append("Matnda to'ldirilmagan joylar bor: " + ", ".join(sorted(set(holes))[:6]))
    else:
        ok.append("Matnlar to'liq (joy tutuvchilarsiz)")
    long = [b["text"] for p in doc.get("pages", []) for row in p.get("buttons") or [] for b in row if len(b["text"]) > 28]
    if long:
        warn.append("Uzun tugma nomlari: " + ", ".join(long[:4]))
    else:
        ok.append("Tugmalar qisqa va tushunarli")
    empty = [p["title"] for p in doc.get("pages", []) if not p.get("messages") and len(p.get("text", "")) < 5]
    if empty:
        warn.append("Mazmuni yo'q bo'limlar: " + ", ".join(empty[:6]))
    return doc, ok, warn


async def build_new(model: str, current: dict, brief: dict, plan: dict, max_pages: int, progress=None) -> tuple[dict, dict, list]:
    """Rejadan to'liq bot: mazmun → yig'ish → linter → tekshiruv."""
    if progress:
        await progress("write")
    content, results = await write_content(model, brief, plan)
    doc = compile_plan(plan, content)
    doc = prepare(doc, current)
    doc, ok, warn = lint(doc)
    try:
        menu = validate_menu(doc, max_pages)
    except MenuError as exc:
        raise BuilderAIError(f"Yig'ilgan bot tekshiruvdan o'tmadi: {exc}") from exc
    if plan.get("_dropped"):
        warn.append(f"Tarifingiz limiti {max_pages} bo'lim — {plan['_dropped']} ta ichki bo'lim qisqartirildi (tarifni oshirsangiz to'liq quriladi)")
    report = {"ok": ok, "warn": warn, "verify": content.get("verify") or []}
    return menu, report, results
