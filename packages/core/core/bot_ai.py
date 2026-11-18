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
 "fallback": "<reply to unknown messages>", "feedback_prompt": "...", "feedback_done": "...", "forward_all": false
}
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
- Build COMPLETE, working, rich bots with real structure and realistic content (emojis, prices as "... so'm" placeholders),
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


async def build_bot(model: str, current: dict, history: list[dict], request: str, max_pages: int) -> tuple[str, dict | None, list]:
    """(javob matni, yangi hujjat yoki None, [AIResult...])."""
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
            return reply, None, results
        try:
            doc = prepare(raw, current)
            menu = validate_menu(doc, max_pages)
            return reply, menu, results
        except MenuError as exc:
            if attempt == 1:
                raise BuilderAIError(f"AI tuzgan bot tekshiruvdan o'tmadi: {exc}. Talabni aniqroq yozib qayta urinib ko'ring.") from exc
            messages.append({"role": "assistant", "content": result.text[:20000]})
            messages.append({"role": "user", "content": f"Validation error: {exc}. Fix it and return the corrected FULL JSON again (same format)."})
    return "", None, results


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
    style = {"reply": "⌨️ klaviatura", "inline": "💬 inline", "hybrid": "🔀 aralash"}.get(menu.get("style", "reply"), "")
    return " · ".join(parts) + f" · uslub: {style}"


# ============================================================
# Web App (Mini App) — AI bilan yaratish
# ============================================================

WEBAPP_SYSTEM = """You are InetTime AI — an expert designer of Telegram Mini Apps inside a no-code Web App builder.
The owner describes the app in plain words; you return the COMPLETE app document.

Answer ONLY with JSON: {"reply": "<1-4 sentences to the owner in their language (default Uzbek, Latin script)>", "doc": <full app document> | null}
"doc": null only for questions/clarifications.

APP DOCUMENT
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
"""


def _rid(prefix: str) -> str:
    import secrets

    return prefix + secrets.token_hex(4)


def prepare_webapp(new: dict, allowed_media: set[int]) -> dict:
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

    for p in doc["pages"]:
        p["title"] = str(p.get("title") or "Sahifa")[:40]
        blocks = []
        for b in p.get("blocks") or []:
            if not isinstance(b, dict) or b.get("type") in ("image", "gallery", "collection"):
                continue  # rasm/ma'lumot bloklari egasining fayllari va to'plamlarini talab qiladi
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
            for f in b.get("fields") or []:
                if isinstance(f, dict):
                    f["id"] = _rid("f")
            if b.get("type") == "custom":
                walk_node(b.get("root"))
            blocks.append(b)
        p["blocks"] = blocks[:60]
    return doc


async def build_webapp(model: str, current: dict, history: list[dict], request: str, allowed_media: set[int]) -> tuple[str, dict | None, list]:
    from core.webapp_builder import WebAppError, validate_app

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
            return reply, None, results
        try:
            doc = prepare_webapp(raw, allowed_media)
            # Sozlamalardagi buyurtma maydonlari egasiniki bo'lib qolsin
            if isinstance(current.get("settings"), dict):
                doc.setdefault("settings", {})
                for key in ("checkout_fields", "checkout_success", "currency"):
                    if key in current["settings"] and key not in doc["settings"]:
                        doc["settings"][key] = current["settings"][key]
            return reply, validate_app(doc), results
        except (MenuError, WebAppError) as exc:
            if attempt == 1:
                raise BuilderAIError(f"AI tuzgan ilova tekshiruvdan o'tmadi: {exc}. Talabni aniqroq yozib qayta urinib ko'ring.") from exc
            messages.append({"role": "assistant", "content": result.text[:20000]})
            messages.append({"role": "user", "content": f"Validation error: {exc}. Fix it and return the corrected FULL JSON again (same format)."})
    return "", None, results
