"""Botning o'zida tahrirlash — MenuBuilder uslubi (klaviatura orqali, ikki rejim).

Admin klaviaturasi (oddiy holat): foydalanuvchi tugmalari + [🎛 Tugmalar muharriri] [📝 Postlar muharriri] [⚙️ Admin panel]

🎛 Tugmalar muharriri:
    • tugmani bosing — u tanlanadi («[ Katalog ]») va sozlamalar paneli chiqadi:
      ⬅️ ⬆️ ⬇️ ➡️ ✳️ (ko'chirish), nomi, o'chirish, kesish, vazifa, shart, buyruq, xossalar
    • tanlangan tugmani yana bosing — ichiga kirasiz (uning menyusi)
    • ➕ Tugma qo'shish — «📦 Katalog | 🛒 Savat» (har qator — qator, | — bir qatorda)
    • ✂️ Kesish → boshqa menyuga o'tib «📋 Qo'yish»
📝 Postlar muharriri:
    • tugmani bosing — uning postlari har biri o'z boshqaruvi bilan chiqadi (⬆️ ⬇️ ✏️ 🗑, ➕ inline tugma)
    • ➕ Post qo'shish — istalgan xabar (matn formatlash bilan, rasm, video, fayl, ovoz, stiker, GIF)
    • ➕ Savol qo'shish — foydalanuvchidan javob so'raydi va o'zgaruvchiga saqlaydi

Holat (redis): emode — rejim, esel — tanlangan tugma, eclip — kesilgan tugma, epage — postlari
tahrirlanayotgan sahifa, est — kutilayotgan kiritish.
"""

import copy
import html
import json
from typing import TYPE_CHECKING, Callable

from sqlalchemy import update

from core.botbuilder import (
    ACTION_LABELS,
    MAX_MESSAGES,
    MAX_PER_ROW,
    MAX_ROWS,
    MSG_LABELS,
    MenuError,
    describe_cond,
    fill,
    form_by_id,
    html_to_plain,
    iter_buttons,
    message_to_msg,
    new_page_id,
    page_by_id,
    parse_cond,
    parse_op,
    validate_menu,
)
from core.db.base import async_session
from core.db.models import UserBot
from core.entitlements import get_entitlement

if TYPE_CHECKING:
    from main import RunningBot, Runner

EDIT_TTL = 24 * 3600
NAV_HINT = "⬅️ Orqaga / 🏠 Bosh menyu — menyular bo'ylab yurish"
STATE_TTL = 3600

BTN_EDITOR = "🎛 Tugmalar muharriri"
POST_EDITOR = "📝 Postlar muharriri"
ADMIN_PANEL = "⚙️ Admin panel"
STOP = "🛑 Muharrirni to'xtatish"
ADD_BTN = "➕ Tugma qo'shish"
ADD_POST = "➕ Post qo'shish"
ADD_Q = "➕ Savol qo'shish"
PASTE = "📋 Qo'yish: "
TOGGLE_KB = "🔁 Klaviatura ⇄ Inline"
AI_BTN = "🤖 InetTime AI"
AI_RESET = "🧹 Yangi suhbat"
AI_EXIT = "🚪 AI'dan chiqish"
SBX_APPLY = "✅ Qo'llash"
SBX_EXIT = "🚪 Sinovdan chiqish"
CONTROLS = (BTN_EDITOR, POST_EDITOR, ADMIN_PANEL, STOP, ADD_BTN, ADD_POST, ADD_Q, TOGGLE_KB, AI_BTN)
SANDBOX_CONTROLS = (SBX_APPLY, SBX_EXIT)

INPUT_LABELS = {"text": "📝 Matn", "number": "🔢 Son", "phone": "📱 Telefon", "email": "📧 Email", "photo": "🖼 Rasm", "choice": "🔘 Tanlov", "location": "📍 Joylashuv"}


def _k(bot: "RunningBot", kind: str, chat_id: int) -> str:
    return f"ub:{bot.bot_id}:{kind}:{chat_id}"


def esc(text) -> str:
    return html.escape(str(text or ""), quote=False)


def onoff(v) -> str:
    return "✅" if v else "❌"


# ============================================================
# Saqlash va holat
# ============================================================


async def save(runner: "Runner", bot: "RunningBot", mutate: Callable[[dict], object]) -> str | None:
    """Hujjat nusxasini o'zgartiradi, tekshiradi va saqlaydi. Xato bo'lsa — o'zbekcha matn qaytaradi."""
    if getattr(bot, "sandbox", False):
        return "🧪 Sinov rejimida o'zgartirib bo'lmaydi — avval «✅ Qo'llash» yoki «🚪 Sinovdan chiqish»"
    draft = copy.deepcopy(bot.menu)
    try:
        result = mutate(draft)
    except MenuError as exc:
        return str(exc)
    if isinstance(result, str):
        return result
    async with async_session() as db:
        ent = await get_entitlement(db, bot.user_id)
        limit = max(ent.bot_pages_limit, len(bot.menu.get("pages", [])))
        try:
            menu = validate_menu(draft, limit)
        except MenuError as exc:
            return str(exc)
        await db.execute(update(UserBot).where(UserBot.id == bot.bot_id).values(menu=menu))
        await db.commit()
    bot.menu = menu
    await runner.apply_commands(bot)
    return None


async def mode(runner: "Runner", bot: "RunningBot", chat_id: int) -> str | None:
    raw = await runner.redis.get(_k(bot, "emode", chat_id))
    return raw.decode() if raw else None


async def set_mode(runner: "Runner", bot: "RunningBot", chat_id: int, value: str | None) -> None:
    await runner.redis.delete(_k(bot, "esel", chat_id), _k(bot, "est", chat_id))
    if value:
        await runner.redis.set(_k(bot, "emode", chat_id), value, ex=EDIT_TTL)
    else:
        await runner.redis.delete(_k(bot, "emode", chat_id), _k(bot, "epage", chat_id))


async def selected(runner: "Runner", bot: "RunningBot", chat_id: int) -> tuple | None:
    raw = await runner.redis.get(_k(bot, "esel", chat_id))
    if not raw:
        return None
    pid, r, c = raw.decode().split(".")
    return pid, int(r), int(c)


async def set_selected(runner: "Runner", bot: "RunningBot", chat_id: int, sel: tuple | None) -> None:
    if sel is None:
        await runner.redis.delete(_k(bot, "esel", chat_id))
    else:
        await runner.redis.set(_k(bot, "esel", chat_id), f"{sel[0]}.{sel[1]}.{sel[2]}", ex=EDIT_TTL)


async def clip(runner: "Runner", bot: "RunningBot", chat_id: int) -> dict | None:
    raw = await runner.redis.get(_k(bot, "eclip", chat_id))
    return json.loads(raw) if raw else None


async def get_state(runner: "Runner", bot: "RunningBot", chat_id: int) -> dict | None:
    raw = await runner.redis.get(_k(bot, "est", chat_id))
    return json.loads(raw) if raw else None


async def set_state(runner: "Runner", bot: "RunningBot", chat_id: int, state: dict | None) -> None:
    if state is None:
        await runner.redis.delete(_k(bot, "est", chat_id))
    else:
        await runner.redis.set(_k(bot, "est", chat_id), json.dumps(state), ex=STATE_TTL)


async def admin_rows(runner: "Runner", bot: "RunningBot", chat_id: int, current: str | None) -> list:
    if current == "buttons":
        rows = [[ADD_BTN, TOGGLE_KB]]
        c = await clip(runner, bot, chat_id)
        if c:
            rows.append([(PASTE + c["button"]["text"])[:64]])
        rows.append([STOP, POST_EDITOR])
    elif current == "posts":
        rows = [[ADD_POST, ADD_Q], [STOP, BTN_EDITOR]]
    elif current == "ai":
        rows = [[AI_RESET, AI_EXIT]]
    elif current == "sandbox":
        rows = [[SBX_APPLY, SBX_EXIT]]
    else:
        rows = [[BTN_EDITOR, POST_EDITOR], [AI_BTN, ADMIN_PANEL]]
    return [[{"text": t} for t in row] for row in rows]


async def send(runner: "Runner", bot: "RunningBot", chat_id: int, text: str, rows: list | None = None, *, message: dict | None = None, markup: dict | None = None) -> dict | None:
    data = {"chat_id": chat_id, "text": text[:4096], "parse_mode": "HTML", "disable_web_page_preview": True}
    if markup is not None:
        data["reply_markup"] = markup
    elif rows is not None:
        data["reply_markup"] = {"inline_keyboard": rows}
    if message is not None and markup is None:
        try:
            return await runner.api(bot, "editMessageText", {**data, "message_id": message["message_id"]})
        except Exception as exc:  # noqa: BLE001
            if "not modified" in str(exc):
                return None
    return await runner.api(bot, "sendMessage", data)


# ============================================================
# Hujjat bilan ishlash
# ============================================================


def normalize(menu: dict, pid: str) -> None:
    """Eski sahifada postlar ro'yxati bo'lmasa — matni/rasmi post qilinadi (ko'rinish o'zgarmaydi)."""
    p = page_by_id(menu, pid)
    if p is None or p.get("messages"):
        return
    p["messages"] = [
        {"type": "photo" if p.get("media_id") else "text", "text": esc(p.get("text") or p["title"]), "media_id": p.get("media_id"), "file_id": None, "buttons": []}
    ]
    p["media_id"] = None


def sync_text(p: dict) -> None:
    first = next((html_to_plain(m["text"]) for m in p.get("messages") or [] if m.get("text") and m.get("type") != "question"), "")
    p["text"] = (first or p["title"])[:4096]


def new_leaf(title: str, style: str = "reply") -> dict:
    """Yangi bo'lim: bitta post. Inline uslubda — «⬅️ Orqaga» inline tugmasi bilan."""
    inline = style == "inline"
    return {
        "id": new_page_id(),
        "title": title[:64],
        "text": title[:64],
        "media_id": None,
        "messages": [{"type": "text", "text": f"<b>{esc(title)}</b>\n\nBu bo'lim posti. O'zgartirish: 📝 Postlar muharriri", "file_id": None, "media_id": None, "buttons": []}],
        "keyboard": "inline" if inline else "reply",
        "buttons": [[{"text": "⬅️ Orqaga", "action": "back"}]] if inline else [],
        "nav": not inline,
    }


def parse_loc(loc: str) -> tuple[str, int | None, int, int]:
    parts = loc.split(".")
    if len(parts) == 3:
        return parts[0], None, int(parts[1]), int(parts[2])
    return parts[0], int(parts[1]), int(parts[2]), int(parts[3])


def rows_of(menu: dict, loc: str) -> list | None:
    pid, i, _, _ = parse_loc(loc)
    p = page_by_id(menu, pid)
    if p is None:
        return None
    if i is None:
        return p["buttons"]
    msgs = p.get("messages") or []
    if i >= len(msgs):
        return None
    msgs[i].setdefault("buttons", [])
    return msgs[i]["buttons"]


def get_btn(menu: dict, loc: str) -> dict | None:
    rows = rows_of(menu, loc)
    _, _, r, c = parse_loc(loc)
    try:
        return rows[r][c] if rows is not None else None
    except IndexError:
        return None


def move_button(rows: list, r: int, c: int, d: str) -> tuple[int, int]:
    b = rows[r][c]
    if d == "L" and c > 0:
        rows[r][c - 1], rows[r][c] = rows[r][c], rows[r][c - 1]
        return r, c - 1
    if d == "R" and c < len(rows[r]) - 1:
        rows[r][c + 1], rows[r][c] = rows[r][c], rows[r][c + 1]
        return r, c + 1
    if d in ("U", "D"):
        rows[r].pop(c)
        j = r - 1 if d == "U" else r + 1
        if not rows[r]:
            rows.pop(r)
            if d == "D":
                j = r
        if d == "U" and j < 0:
            rows.insert(0, [b])
            return 0, 0
        if d == "D" and j >= len(rows):
            rows.append([b])
            return len(rows) - 1, 0
        if len(rows[j]) >= MAX_PER_ROW:
            raise MenuError(f"Qatorda ko'pi bilan {MAX_PER_ROW} ta tugma")
        rows[j].append(b)
        return j, len(rows[j]) - 1
    if d == "S":
        if len(rows[r]) == 1:
            return r, c
        rows[r].pop(c)
        rows.insert(r + 1, [b])
        return r + 1, 0
    return r, c


def _refs(menu: dict) -> set[str]:
    refs = {menu.get("start"), menu.get("first_start")}
    for p in menu["pages"]:
        for b in iter_buttons(p):
            if b.get("target"):
                refs.add(b["target"])
            refs.update(b.get("targets") or [])
    refs.update(k.get("target") for k in menu.get("keywords") or [])
    refs.update(c.get("target") for c in menu.get("commands") or [])
    refs.update(f.get("target") for f in menu.get("forms") or [])
    return {r for r in refs if r}


def drop_orphans(menu: dict, candidates: list[str]) -> None:
    """O'chirilgan tugmaning sahifasi (va uning ichidagilar) boshqa joyda ishlatilmasa — o'chadi."""
    queue = list(candidates)
    while queue:
        pid = queue.pop()
        if pid in _refs(menu):
            continue
        page = page_by_id(menu, pid)
        if page is None:
            continue
        children = [b.get("target") for b in iter_buttons(page) if b.get("target")]
        menu["pages"] = [p for p in menu["pages"] if p["id"] != pid]
        queue.extend(children)


def assign(menu: dict, loc: str, values: dict) -> None:
    b = get_btn(menu, loc)
    keep = {k: b.get(k) for k in ("text", "cond", "admin_only", "hidden", "need_sub") if k in b}
    b.clear()
    b.update(keep)
    b.update(values)


# ============================================================
# Ko'rinishlar
# ============================================================


def action_detail(bot: "RunningBot", b: dict) -> str:
    a = b["action"]
    if a == "page":
        p = page_by_id(bot.menu, b.get("target"))
        if not p:
            return ""
        posts = len(p.get("messages") or []) or 1
        n = sum(len(r) for r in p.get("buttons") or [])
        return f"«{esc(p['title'])}» · {posts} post" + (f" · {n} tugma" if n else "")
    if a == "url":
        return esc(b.get("url") or "")
    if a in ("alert", "notify"):
        return f"«{esc(b.get('alert', ''))[:60]}»"
    if a == "form":
        f = form_by_id(bot.menu, b.get("form"))
        return f"«{esc(f['title'])}»" if f else ""
    if a == "set":
        sym = {"set": "=", "add": "+", "sub": "−", "clear": "tozalash"}[b.get("op", "set")]
        return f"<code>{{{b.get('var')}}} {sym} {esc(b.get('value', ''))}</code>"
    if a in ("contact", "location"):
        return f"→ <code>{{{b.get('var')}}}</code>"
    if a == "random":
        return f"{len(b.get('targets') or [])} ta bo'limdan"
    return ""


def button_panel(bot: "RunningBot", loc: str) -> tuple[str, list] | None:
    b = get_btn(bot.menu, loc)
    if b is None:
        return None
    pid, i, r, c = parse_loc(loc)
    target = page_by_id(bot.menu, b.get("target")) if b["action"] == "page" else None
    cmd = next((f"/{x['command']}" for x in bot.menu.get("commands") or [] if target and x["target"] == target["id"]), "—")
    where = "post ostida (inline)" if i is not None else "klaviaturada"
    lines = [
        f"🔧 <b>Tugma: «{esc(b['text'])}»</b>",
        f"📍 {r + 1}-qator, {c + 1}-o'rin · {where}",
        "━━━━━━━━━━━━",
        f"🎯 Vazifa: {ACTION_LABELS.get(b['action'], b['action'])} {action_detail(bot, b)}",
        f"▫️ Faqat admin: {onoff(b.get('admin_only'))}",
        f"▫️ Obuna talab qilinadi: {onoff(b.get('need_sub'))}",
        f"▫️ Ko'rinish sharti: {esc(describe_cond(b.get('cond')))}",
    ]
    if i is None:
        lines.insert(5, f"▫️ Ko'rinmas (nomi bilan ishlaydi): {onoff(b.get('hidden'))}")
    if target:
        lines += [
            f"▫️ Buyruq: {cmd}",
            f"▫️ Tasodifiy post: {onoff(target.get('random_post'))}",
            f"▫️ Navigatsiya (Orqaga/Bosh menyu): {onoff(target.get('nav'))}",
            f"▫️ Bosilganda sizga xabar: {onoff(target.get('notify'))}",
        ]
    rows = [
        [
            {"text": "⬅️", "callback_data": f"e:m:L:{loc}"},
            {"text": "⬆️", "callback_data": f"e:m:U:{loc}"},
            {"text": "⬇️", "callback_data": f"e:m:D:{loc}"},
            {"text": "➡️", "callback_data": f"e:m:R:{loc}"},
            {"text": "✳️", "callback_data": f"e:m:S:{loc}"},
        ],
        [
            {"text": "✏️ Nomi", "callback_data": f"e:n:{loc}"},
            {"text": "🗑 O'chirish", "callback_data": f"e:x:{loc}"},
            {"text": "✂️ Kesish", "callback_data": f"e:cut:{loc}"},
        ],
        [
            {"text": "🎯 Vazifa", "callback_data": f"e:a:{loc}"},
            {"text": "👁 Shart", "callback_data": f"e:cond:{loc}"},
            {"text": "🔒 Admin", "callback_data": f"e:t:adm:{loc}"},
        ],
        [
            {"text": "📢 Obuna", "callback_data": f"e:t:sub:{loc}"},
        ],
    ]
    if i is None:
        rows[3].append({"text": "🙈 Ko'rinmas", "callback_data": f"e:t:hid:{loc}"})
    if target:
        rows[3].append({"text": "⌨️ Buyruq", "callback_data": f"e:cmd:{loc}"})
        rows.append(
            [
                {"text": "🎲 Tasodifiy", "callback_data": f"e:t:rnd:{loc}"},
                {"text": "🧭 Navigatsiya", "callback_data": f"e:t:nav:{loc}"},
                {"text": "🔔 Xabar", "callback_data": f"e:t:ntf:{loc}"},
            ]
        )
        rows.append([{"text": "📂 Ichiga kirish", "callback_data": f"e:in:{loc}"}])
    if i is not None:
        rows.append([{"text": "⬅️ Postlarga qaytish", "callback_data": f"e:pp:{pid}"}])
    return "\n".join(lines), rows


ACTION_CODES = [
    ("pg", "📄 Bo'lim (post + menyu)"),
    ("ep", "📑 Mavjud bo'lim"),
    ("ur", "🔗 Havola"),
    ("al", "🔔 Ogohlantirish (alert)"),
    ("fb", "💬 Adminga yozish"),
    ("fo", "📝 Forma"),
    ("st", "🔢 O'zgaruvchi"),
    ("rn", "🎲 Tasodifiy bo'lim"),
    ("sh", "📤 Ulashish / referal"),
    ("cs", "✅ Obunani tekshirish"),
    ("ct", "📱 Telefon so'rash"),
    ("lc", "📍 Joylashuv so'rash"),
    ("nt", "🔔 Adminga bildirish"),
    ("bk", "⬅️ Orqaga"),
    ("hm", "🏠 Bosh menyu"),
    ("wa", "🌐 Web App"),
]
INLINE_ONLY = ("ur", "al")
REPLY_ONLY = ("ct", "lc")


def action_picker(bot: "RunningBot", loc: str) -> tuple[str, list]:
    _, i, _, _ = parse_loc(loc)
    b = get_btn(bot.menu, loc)
    codes = [(c, t) for c, t in ACTION_CODES if not (i is None and c in INLINE_ONLY) and not (i is not None and c in REPLY_ONLY)]
    rows, line = [], []
    for code, label in codes:
        line.append({"text": label, "callback_data": f"e:as:{code}:{loc}"})
        if len(line) == 2:
            rows.append(line)
            line = []
    if line:
        rows.append(line)
    rows.append([{"text": "⬅️ Orqaga", "callback_data": f"e:p:{loc}"}])
    note = "🔗 Havola va 🔔 Ogohlantirish — post ostidagi (inline) tugmalarda." if i is None else "📱 Telefon va 📍 joylashuv — klaviatura tugmalarida."
    text = (
        f"🎯 <b>«{esc(b['text'] if b else '')}» vazifasi</b>\n\n"
        "📄 <b>Bo'lim</b> — bosilganda o'z postlari chiqadi; ichiga tugma qo'shsangiz menyu bo'ladi\n"
        "📝 <b>Forma</b> — savollar beradi, javoblarni eslab qoladi\n"
        "🔢 <b>O'zgaruvchi</b> — masalan <code>ball +1</code>\n"
        f"{note}"
    )
    return text, rows


# --- Tahrirlanayotgan bo'lim (muharrirning o'z joyi va tarixi) ---


async def section(runner: "Runner", bot: "RunningBot", chat_id: int) -> dict:
    raw = await runner.redis.get(_k(bot, "epage", chat_id))
    page = page_by_id(bot.menu, raw.decode()) if raw else None
    return page or await runner.current_page(bot, chat_id) or page_by_id(bot.menu, bot.menu["start"])


async def go_section(runner: "Runner", bot: "RunningBot", chat_id: int, page: dict, *, push: bool = True) -> None:
    key = _k(bot, "estack", chat_id)
    if push:
        cur = await runner.redis.get(_k(bot, "epage", chat_id))
        if cur and cur.decode() != page["id"]:
            await runner.redis.rpush(key, cur)
            await runner.redis.ltrim(key, -30, -1)
            await runner.redis.expire(key, EDIT_TTL)
    await runner.redis.set(_k(bot, "epage", chat_id), page["id"], ex=EDIT_TTL)
    await set_selected(runner, bot, chat_id, None)
    if page.get("keyboard") == "reply":
        # foydalanuvchi ko'rinishi ham shu menyuda tursin
        await runner.redis.set(f"ub:{bot.bot_id}:cur:{chat_id}", page["id"], ex=30 * 24 * 3600)


async def section_back(runner: "Runner", bot: "RunningBot", chat_id: int, home: bool) -> dict:
    key = _k(bot, "estack", chat_id)
    if home:
        await runner.redis.delete(key, f"ub:{bot.bot_id}:nav:{chat_id}")
        target = bot.menu["start"]
    else:
        prev = await runner.redis.rpop(key)
        target = prev.decode() if prev else bot.menu["start"]
    page = page_by_id(bot.menu, target) or page_by_id(bot.menu, bot.menu["start"])
    await go_section(runner, bot, chat_id, page, push=False)
    return page


def mirror(bot: "RunningBot", page: dict, sel: tuple | None, *, posts: bool = False) -> tuple[str, list]:
    """Inline bo'lim tugmalari muharrirda: bosilsa tanlanadi (yoki postlar rejimida — ichiga kiriladi)."""
    pid = page["id"]
    rows = []
    for r, row in enumerate(page.get("buttons") or []):
        line = []
        for c, b in enumerate(row):
            t = b["text"]
            if not posts and sel == (pid, r, c):
                t = f"[ {t} ]"
            line.append({"text": t[:64], "callback_data": f"e:{'po' if posts else 'sel'}:{pid}.{r}.{c}"})
        rows.append(line)
    if posts:
        text = f"💬 <b>«{esc(page['title'])}»</b> inline tugmalari — bosing, uning postlari ochiladi."
    else:
        rows.append([{"text": ADD_BTN, "callback_data": f"e:addb:{pid}"}])
        text = (
            f"💬 <b>«{esc(page['title'])}» — inline bo'lim</b> (tugmalar post ostida)\n"
            "Tugmani bosing — tanlanadi va sozlamalari chiqadi. Tanlanganini yana bosing — ichiga kirasiz."
        )
    return text, rows


async def show_section(runner: "Runner", bot: "RunningBot", chat_id: int, page: dict, user: dict, text: str | None = None) -> None:
    current = await mode(runner, bot, chat_id)
    if current == "posts":
        await show_posts(runner, bot, chat_id, page, user)
        return
    await show_menu(runner, bot, chat_id, page, text)
    if current == "buttons" and page.get("keyboard") != "reply":
        m = mirror(bot, page, await selected(runner, bot, chat_id))
        await send(runner, bot, chat_id, m[0], m[1])


async def show_menu(runner: "Runner", bot: "RunningBot", chat_id: int, page: dict, text: str | None = None) -> None:
    """Bo'limni muharrir klaviaturasi bilan ko'rsatadi (inline bo'limda — faqat navigatsiya va muharrir tugmalari)."""
    vals = await runner.values(bot, {"id": chat_id, "first_name": "Admin"})
    markup = await runner.menu_markup(bot, chat_id, page, vals)
    current = await mode(runner, bot, chat_id)
    n = sum(len(r) for r in page.get("buttons") or [])
    kind = "⌨️ klaviatura" if page.get("keyboard") == "reply" else "💬 inline"
    if text is None:
        if current == "buttons":
            text = f"🎛 <b>«{esc(page['title'])}»</b> · {kind} · {n} tugma"
            if page.get("keyboard") == "reply":
                text += "\nTugmani bosing — tanlanadi. Tanlangan tugmani yana bosing — ichiga kirasiz."
        elif current == "posts":
            text = f"📝 <b>«{esc(page['title'])}»</b>"
        else:
            text = f"📂 {esc(page['title'])}"
    await send(runner, bot, chat_id, text, markup=markup or {"remove_keyboard": True})


async def show_posts(runner: "Runner", bot: "RunningBot", chat_id: int, page: dict, user: dict) -> None:
    """Postlar muharriri: har bir post o'z boshqaruv tugmalari bilan."""
    if not page.get("messages"):
        await save(runner, bot, lambda m: normalize(m, page["id"]))
        page = page_by_id(bot.menu, page["id"]) or page
    await runner.redis.set(_k(bot, "epage", chat_id), page["id"], ex=EDIT_TTL)
    vals = await runner.values(bot, user)
    msgs = page.get("messages") or []
    pid = page["id"]
    for i, m in enumerate(msgs):
        rows = []
        for r, row in enumerate(m.get("buttons") or []):
            rows.append([{"text": fill(b["text"], vals, escape=False)[:64], "callback_data": f"e:pb:{pid}.{i}.{r}.{c}"} for c, b in enumerate(row)])
        rows.append(
            [
                {"text": "⬆️", "callback_data": f"e:pu:{pid}:{i}"},
                {"text": "⬇️", "callback_data": f"e:pd:{pid}:{i}"},
                {"text": "✏️", "callback_data": f"e:pe:{pid}:{i}"},
                {"text": "🗑", "callback_data": f"e:px:{pid}:{i}"},
            ]
        )
        if m["type"] != "question":
            rows.append([{"text": "➕ Inline tugma", "callback_data": f"e:pa:{pid}:{i}"}])
        markup = {"inline_keyboard": rows}
        if m["type"] == "question":
            opts = f" ({esc(', '.join(m.get('options') or []))})" if m.get("options") else ""
            await send(
                runner,
                bot,
                chat_id,
                f"❓ <b>Savol</b> → <code>{{{m['var']}}}</code> · {INPUT_LABELS.get(m.get('input', 'text'))}{opts}\n\n{m['text']}",
                rows,
            )
            continue
        shown = dict(m, text=fill(m.get("text") or "", vals, escape=True), html=True)
        try:
            await runner.send_one(bot, chat_id, shown, markup)
        except Exception as exc:  # noqa: BLE001 — masalan noto'g'ri HTML
            await send(runner, bot, chat_id, f"⚠️ {i + 1}-postni ko'rsatib bo'lmadi: {esc(str(exc))[:200]}", rows)
    if page.get("keyboard") != "reply" and page.get("buttons"):
        m = mirror(bot, page, None, posts=True)
        await send(runner, bot, chat_id, m[0], m[1])
    head = (
        f"📝 <b>«{esc(page['title'])}» postlari</b> · {len(msgs)} ta\n"
        f"Har bir post ostida: ⬆️⬇️ joyi, ✏️ almashtirish, 🗑 o'chirish, ➕ inline tugma.\n"
        "Boshqa tugmani bosing — uning postlari chiqadi."
    )
    vals2 = await runner.values(bot, {"id": chat_id, "first_name": "Admin"})
    markup = await runner.menu_markup(bot, chat_id, page, vals2)
    await send(runner, bot, chat_id, head, markup=markup)


async def start_editing(runner: "Runner", bot: "RunningBot", chat_id: int, user: dict, which: str = "buttons") -> None:
    await set_mode(runner, bot, chat_id, which)
    cur = await section(runner, bot, chat_id)
    await go_section(runner, bot, chat_id, cur, push=False)
    if which == "buttons":
        style = {"reply": "⌨️ klaviatura", "inline": "💬 inline", "hybrid": "🔀 aralash"}[bot.menu.get("style", "reply")]
        await show_section(
            runner,
            bot,
            chat_id,
            cur,
            user,
            "🎛 <b>Tugmalar muharriri</b>\n\n"
            "• Tugmani bosing — <b>tanlanadi</b> va sozlamalari chiqadi\n"
            "• Tanlangan tugmani yana bosing — <b>ichiga kirasiz</b>\n"
            f"• {ADD_BTN} — yangi tugmalar · {TOGGLE_KB} — bo'lim uslubi\n"
            f"• {NAV_HINT}\n\nBot uslubi (yangi bo'limlar uchun): {style} — /admin → ⚙️ Sozlamalar → 🎨 Uslub",
        )
    else:
        await show_posts(runner, bot, chat_id, cur, user)


async def reopen(runner: "Runner", bot: "RunningBot", chat_id: int, page_id: str, user: dict) -> None:
    page = page_by_id(bot.menu, page_id) or page_by_id(bot.menu, bot.menu.get("start"))
    if await mode(runner, bot, chat_id) in ("posts", "buttons"):
        await go_section(runner, bot, chat_id, page, push=False)
        await show_section(runner, bot, chat_id, page, user)
    else:
        await runner.send_page(bot, chat_id, page, user)


# ============================================================
# Xabarlar (klaviatura va kiritishlar)
# ============================================================


def _match(runner: "Runner", page: dict, text: str, vals: dict) -> tuple[int, int] | None:
    clean = text[2:-2] if text.startswith("[ ") and text.endswith(" ]") else text
    for r, row in enumerate(page.get("buttons") or []):
        for c, b in enumerate(row):
            if clean in (b["text"], runner.label(b, vals)):
                return r, c
    return None


async def on_message(runner: "Runner", bot: "RunningBot", message: dict) -> bool:
    """Admin xabari muharrirga tegishli bo'lsa — qayta ishlab True qaytaradi."""
    chat_id = message["chat"]["id"]
    user = message["from"]
    text = (message.get("text") or "").strip()
    current = await mode(runner, bot, chat_id)

    import admin  # aylanma import bo'lmasligi uchun shu yerda

    if current == "sandbox":
        import ai_chat

        if text == SBX_APPLY:
            await ai_chat.apply(runner, bot, chat_id, user)
            return True
        if text == SBX_EXIT:
            await ai_chat.exit_sandbox(runner, bot, chat_id, user)
            return True
        return False  # sinovda bot oddiy foydalanuvchi kabi ishlaydi

    is_control = text in CONTROLS or (current == "buttons" and text.startswith(PASTE))
    if text in ("/edit", "/tahrir") or is_control:
        await admin.set_state(runner, bot, chat_id, None)
        await set_state(runner, bot, chat_id, None)
        if is_control:
            await control(runner, bot, chat_id, user, text, current)
        else:
            await start_editing(runner, bot, chat_id, user, "buttons")
        return True
    # Admin paneli biror narsa so'ragan bo'lsa (kalit so'z, forma...) — javob o'shanga boradi
    if await admin.get_state(runner, bot, chat_id) is not None:
        return False

    state = await get_state(runner, bot, chat_id)
    if state is not None:
        if text == "/cancel":
            await set_state(runner, bot, chat_id, None)
            await send(runner, bot, chat_id, "❌ Bekor qilindi.")
            return True
        if text in (NAV_BACK, NAV_HOME) and current:
            await set_state(runner, bot, chat_id, None)
        else:
            return await on_input(runner, bot, chat_id, user, message, state)

    if not current:
        return False
    if current == "ai":
        import ai_chat

        return await ai_chat.on_message(runner, bot, message)

    if text in (NAV_BACK, NAV_HOME):
        page = await section_back(runner, bot, chat_id, home=text == NAV_HOME)
        await show_section(runner, bot, chat_id, page, user)
        return True

    cur = await section(runner, bot, chat_id)
    vals = await runner.values(bot, user)
    pos = _match(runner, cur, text, vals) if text and cur.get("keyboard") == "reply" else None
    if pos is None:
        if text:
            hint = "Tugmani bosing yoki " + (ADD_BTN if current == "buttons" else ADD_POST)
            await send(runner, bot, chat_id, f"ℹ️ {hint}. Muharrirdan chiqish: {STOP}")
        return True
    r, c = pos
    b = cur["buttons"][r][c]
    if current == "buttons":
        await select_button(runner, bot, chat_id, user, cur, r, c)
        return True
    # posts
    target = page_by_id(bot.menu, b.get("target")) if b["action"] == "page" else None
    if target is None:
        await send(runner, bot, chat_id, f"ℹ️ «{esc(b['text'])}» tugmasida post yo'q — vazifasi: {ACTION_LABELS.get(b['action'], b['action'])}.")
        return True
    await go_section(runner, bot, chat_id, target)
    await show_posts(runner, bot, chat_id, target, user)
    return True


async def select_button(runner: "Runner", bot: "RunningBot", chat_id: int, user: dict, cur: dict, r: int, c: int, message: dict | None = None) -> None:
    """Birinchi bosish — tanlash (panel), ikkinchisi — ichiga kirish. Klaviatura va inline bo'limlarda bir xil."""
    b = cur["buttons"][r][c]
    sel = await selected(runner, bot, chat_id)
    if sel == (cur["id"], r, c):
        await enter_button(runner, bot, chat_id, user, cur, b)
        return
    await set_selected(runner, bot, chat_id, (cur["id"], r, c))
    if cur.get("keyboard") == "reply":
        await show_menu(runner, bot, chat_id, cur, f"🔧 Tanlandi: <b>[ {esc(b['text'])} ]</b> — yana bossangiz ichiga kirasiz")
    else:
        m = mirror(bot, cur, (cur["id"], r, c))
        await send(runner, bot, chat_id, m[0], m[1], message=message)
    panel = button_panel(bot, f"{cur['id']}.{r}.{c}")
    await send(runner, bot, chat_id, panel[0], panel[1])


async def enter_button(runner: "Runner", bot: "RunningBot", chat_id: int, user: dict, cur: dict, b: dict) -> None:
    target = page_by_id(bot.menu, b.get("target")) if b["action"] == "page" else None
    if target is None:
        await send(
            runner,
            bot,
            chat_id,
            f"ℹ️ «{esc(b['text'])}» bo'lim ochmaydi (vazifasi: {ACTION_LABELS.get(b['action'], b['action'])}).\n"
            "Ichiga tugma qo'shish uchun avval 🎯 Vazifa → 📄 Bo'lim qiling.",
        )
        return
    await go_section(runner, bot, chat_id, target)
    n = sum(len(r) for r in target.get("buttons") or [])
    kind = "⌨️ klaviatura" if target.get("keyboard") == "reply" else "💬 inline"
    await show_section(
        runner,
        bot,
        chat_id,
        target,
        user,
        f"📂 <b>«{esc(target['title'])}»</b> ichidasiz · {kind} · {n} tugma\n{ADD_BTN} — ichki tugmalar. {TOGGLE_KB} — uslubni almashtirish.",
    )


async def control(runner: "Runner", bot: "RunningBot", chat_id: int, user: dict, text: str, current: str | None) -> None:
    if text == BTN_EDITOR:
        await start_editing(runner, bot, chat_id, user, "buttons")
    elif text == AI_BTN:
        import ai_chat

        await ai_chat.start(runner, bot, chat_id, user)
    elif text == TOGGLE_KB:
        cur = await section(runner, bot, chat_id)

        def toggle(m: dict):
            p = page_by_id(m, cur["id"])
            p["keyboard"] = "inline" if p.get("keyboard") == "reply" else "reply"
            if p["keyboard"] == "reply":
                p["nav"] = True

        error = await save(runner, bot, toggle)
        if error:
            await send(runner, bot, chat_id, f"⚠️ {esc(error)}")
            return
        page = page_by_id(bot.menu, cur["id"])
        await go_section(runner, bot, chat_id, page, push=False)
        kind = "⌨️ klaviatura tugmalari" if page["keyboard"] == "reply" else "💬 inline (post ostidagi) tugmalar"
        await show_section(runner, bot, chat_id, page, user, f"🔁 «{esc(page['title'])}» endi: {kind}")
    elif text == POST_EDITOR:
        await set_mode(runner, bot, chat_id, "posts")
        cur = await section(runner, bot, chat_id)
        await send(
            runner,
            bot,
            chat_id,
            "📝 <b>Postlar muharriri</b>\n\nTugmani bosing — uning postlari boshqaruv tugmalari bilan chiqadi.\n"
            f"{ADD_POST} — istalgan xabar (matn, rasm, video, fayl, ovoz, stiker...)\n{ADD_Q} — foydalanuvchidan javob so'rash",
        )
        await show_posts(runner, bot, chat_id, cur, user)
    elif text == STOP:
        cur = await runner.current_page(bot, chat_id)
        await set_mode(runner, bot, chat_id, None)
        await show_menu(runner, bot, chat_id, cur, "✅ Muharrir o'chirildi — botingiz shu ko'rinishda ishlaydi.")
    elif text == ADMIN_PANEL:
        import admin

        await admin.panel(runner, bot, chat_id)
    elif text == ADD_BTN:
        await set_state(runner, bot, chat_id, {"k": "addbtn", "p": (await section(runner, bot, chat_id))["id"]})
        await send(
            runner,
            bot,
            chat_id,
            "➕ <b>Yangi tugma(lar) nomini yuboring</b>\n\n"
            "• Har bir qator — alohida qator\n• Bir qatorda bir nechta — <code>|</code> bilan\n\n"
            "Masalan:\n<code>📦 Katalog | 🛒 Savat\n📞 Aloqa</code>\n\n"
            "Har bir tugma o'z bo'limini oladi: postlarini 📝 Postlar muharririda yozasiz, ichiga tugma qo'shsangiz — menyu bo'ladi.",
        )
    elif text == ADD_POST:
        page = await section(runner, bot, chat_id)
        page_id = page["id"]
        await set_state(runner, bot, chat_id, {"k": "post_add", "p": page_id})
        await send(
            runner,
            bot,
            chat_id,
            f"➕ <b>«{esc(page['title'] if page else '')}»</b> bo'limiga post yuboring.\n\n"
            "Istalgan xabar: matn (qalin, kursiv, havola saqlanadi), rasm, video, fayl, audio, ovozli xabar, stiker, GIF.\n"
            "Bir nechta yuborsangiz — hammasi qo'shiladi. Tugatish uchun istalgan tugmani bosing.\n"
            "O'zgaruvchilar: <code>{name}</code> <code>{user_id}</code> <code>{ref_link}</code>...",
        )
    elif text == ADD_Q:
        page_id = (await section(runner, bot, chat_id))["id"]
        await set_state(runner, bot, chat_id, {"k": "q_text", "p": page_id})
        await send(runner, bot, chat_id, "❓ <b>Savol matnini yuboring</b>\nMasalan: «Ismingiz nima?»\n\nJavob o'zgaruvchiga saqlanadi va keyingi postlarda <code>{ism}</code> ko'rinishida ishlatiladi.")
    elif text.startswith(PASTE):
        c = await clip(runner, bot, chat_id)
        cur = await section(runner, bot, chat_id)
        if not c or cur is None:
            return

        def paste(m: dict):
            p = page_by_id(m, cur["id"])
            if len(p["buttons"]) >= MAX_ROWS:
                return f"Bo'limda ko'pi bilan {MAX_ROWS} qator"
            p["buttons"].append([c["button"]])
            return None

        error = await save(runner, bot, paste)
        if error:
            await send(runner, bot, chat_id, f"⚠️ {esc(error)}")
            return
        await runner.redis.delete(_k(bot, "eclip", chat_id))
        await show_section(runner, bot, chat_id, page_by_id(bot.menu, cur["id"]), user, f"📋 «{esc(c['button']['text'])}» shu yerga qo'yildi")


async def on_input(runner: "Runner", bot: "RunningBot", chat_id: int, user: dict, message: dict, state: dict) -> bool:
    kind = state["k"]
    text = (message.get("text") or "").strip()

    async def say(t: str, rows: list | None = None) -> None:
        await send(runner, bot, chat_id, t, rows)

    async def fail(error: str | None) -> bool:
        if error:
            await say(f"⚠️ {esc(error)}")
            return True
        return False

    # --- Post qo'shish / almashtirish (istalgan turdagi xabar) ---
    if kind in ("post_add", "post_replace"):
        msg = message_to_msg(message)
        if msg is None:
            await say("⚠️ Bu turdagi xabarni saqlab bo'lmaydi. Matn, rasm, video, fayl, audio, ovozli xabar, stiker yoki GIF yuboring.")
            return True
        if msg["type"] == "text" and len(msg["text"]) > 4096:
            await say("⚠️ Matn juda uzun (4096 belgigacha).")
            return True
        if msg["type"] not in ("text", "sticker", "video_note") and len(msg["text"]) > 1024:
            await say("⚠️ Izoh juda uzun (1024 belgigacha) — matnni alohida post qiling.")
            return True
        pid = state["p"]

        def apply(m: dict):
            normalize(m, pid)
            p = page_by_id(m, pid)
            if kind == "post_add":
                if len(p["messages"]) >= MAX_MESSAGES:
                    return f"Bitta bo'limda ko'pi bilan {MAX_MESSAGES} ta post"
                p["messages"].append({**msg, "buttons": []})
            else:
                i = state["i"]
                old = p["messages"][i]
                p["messages"][i] = {**msg, "buttons": old.get("buttons") or []}
            sync_text(p)
            return None

        if await fail(await save(runner, bot, apply)):
            return True
        page = page_by_id(bot.menu, pid)
        if kind == "post_replace":
            await set_state(runner, bot, chat_id, None)
            await say("✅ Post almashtirildi")
            await show_posts(runner, bot, chat_id, page, user)
        else:
            await runner.api(
                bot,
                "sendMessage",
                {
                    "chat_id": chat_id,
                    "text": f"✅ Post qo'shildi: {MSG_LABELS.get(msg['type'], msg['type'])} (bo'limda jami {len(page['messages'])}). Yana yuboring yoki istalgan tugmani bosing.",
                    "reply_to_message_id": message["message_id"],
                    "reply_markup": {"inline_keyboard": [[{"text": "👁 Postlarni ko'rish", "callback_data": f"e:pp:{pid}"}]]},
                },
            )
        return True

    if not text:
        await say("✍️ Matn ko'rinishida yuboring yoki /cancel")
        return True

    if kind == "addbtn":
        cur = page_by_id(bot.menu, state.get("p") or "") or await section(runner, bot, chat_id)
        style = bot.menu.get("style", "reply")
        rows = [[t.strip()[:64] for t in ln.split("|") if t.strip()] for ln in text.splitlines() if ln.strip()]
        rows = [r for r in rows if r]
        created: list = []

        def add(m: dict):
            normalize(m, cur["id"])
            p = page_by_id(m, cur["id"])
            if len(p["buttons"]) + len(rows) > MAX_ROWS:
                return f"Bo'limda ko'pi bilan {MAX_ROWS} qator tugma"
            existing = {b["text"] for row in p["buttons"] for b in row}
            for row in rows:
                if len(row) > MAX_PER_ROW:
                    return f"Bir qatorda ko'pi bilan {MAX_PER_ROW} ta tugma"
                line = []
                for name in row:
                    if name in existing:
                        return f"«{name}» nomli tugma bu bo'limda bor"
                    existing.add(name)
                    leaf = new_leaf(name, style)
                    m["pages"].append(leaf)
                    created.append(name)
                    line.append({"text": name, "action": "page", "target": leaf["id"]})
                p["buttons"].append(line)
            if p.get("keyboard") == "reply":
                p["nav"] = p.get("nav") or p["id"] != m["start"]
            else:
                # inline bo'limda «⬅️ Orqaga» qatori oxirida tursin
                back = [row for row in p["buttons"] if all(b.get("action") in ("back", "home") for b in row)]
                p["buttons"] = [row for row in p["buttons"] if row not in back] + back
            return None

        if await fail(await save(runner, bot, add)):
            return True
        await set_state(runner, bot, chat_id, None)
        await show_section(
            runner,
            bot,
            chat_id,
            page_by_id(bot.menu, cur["id"]),
            user,
            f"✅ {len(created)} ta tugma qo'shildi.\nTugmani bosing — sozlamalari; yana bosing — ichiga kirasiz. Postlarini 📝 Postlar muharririda yozasiz.",
        )
        return True

    if kind == "q_text":
        q_html = message_to_msg(message)["text"] if message.get("text") else esc(text)
        state.update({"k": "q_type", "q": q_html})
        await set_state(runner, bot, chat_id, state)
        rows = [[{"text": l, "callback_data": f"e:qt:{k}"} for k, l in list(INPUT_LABELS.items())[i : i + 2]] for i in range(0, len(INPUT_LABELS), 2)]
        await say("Javob turi qanday?", rows)
        return True
    if kind == "q_opts":
        opts = [o.strip()[:64] for o in text.split(",") if o.strip()][:12]
        if not opts:
            await say("⚠️ Variantlar bo'sh")
            return True
        state.update({"k": "q_var", "options": opts})
        await set_state(runner, bot, chat_id, state)
        await say("🔢 Javob qaysi o'zgaruvchiga saqlansin? Lotin harflarida, masalan <code>ism</code>, <code>telefon</code>, <code>jins</code>")
        return True
    if kind == "q_var":
        key = text.strip("{} ").lower()
        if not key.replace("_", "").isalnum() or not key.isascii() or not key[0].isalpha():
            await say("⚠️ Faqat lotin harf, raqam va _ (harf bilan boshlansin)")
            return True
        pid = state["p"]
        q = {"type": "question", "text": state["q"], "var": key[:32], "input": state.get("input", "text"), "options": state.get("options") or [], "buttons": []}

        def add_q(m: dict):
            normalize(m, pid)
            p = page_by_id(m, pid)
            if len(p["messages"]) >= MAX_MESSAGES:
                return f"Bitta bo'limda ko'pi bilan {MAX_MESSAGES} ta post"
            p["messages"].append(q)
            if not any(v["key"] == q["var"] for v in m.get("variables") or []):
                m.setdefault("variables", []).append({"key": q["var"], "label": q["var"], "default": "", "scope": "user"})
            return None

        if await fail(await save(runner, bot, add_q)):
            return True
        await set_state(runner, bot, chat_id, None)
        await say(f"✅ Savol qo'shildi. Javob <code>{{{esc(key)}}}</code> ga saqlanadi va keyingi postlarda ishlatiladi.")
        await show_posts(runner, bot, chat_id, page_by_id(bot.menu, pid), user)
        return True

    if kind == "ib_name":
        pid, i = state["p"], state["i"]
        name, sep, url = text.partition(" - ")
        name = name.strip()[:64]
        url = url.strip()
        leaf = None
        if sep and url:
            if not url.startswith(("http://", "https://", "tg://")):
                url = "https://" + url.lstrip("/")
            button = {"text": name, "action": "url", "url": url}
        else:
            leaf = new_leaf(name)
            button = {"text": name, "action": "page", "target": leaf["id"]}

        def add_ib(m: dict):
            normalize(m, pid)
            p = page_by_id(m, pid)
            msg = p["messages"][i]
            msg.setdefault("buttons", [])
            if len(msg["buttons"]) >= MAX_ROWS:
                return f"Postda ko'pi bilan {MAX_ROWS} qator tugma"
            if leaf:
                leaf["nav"] = False
                m["pages"].append(leaf)
            msg["buttons"].append([button])
            return None

        if await fail(await save(runner, bot, add_ib)):
            return True
        await set_state(runner, bot, chat_id, None)
        page = page_by_id(bot.menu, pid)
        loc = f"{pid}.{i}.{len(page['messages'][i]['buttons']) - 1}.0"
        panel = button_panel(bot, loc)
        await say("✅ Inline tugma qo'shildi.\n\n" + panel[0], panel[1])
        return True

    # Tugmaga oid kiritishlar
    loc = state.get("loc")
    b = get_btn(bot.menu, loc) if loc else None
    if b is None:
        await set_state(runner, bot, chat_id, None)
        await say("⚠️ Tugma topilmadi")
        return True
    values: dict | None = None
    props: dict | None = None
    if kind == "rename":
        props = {"text": text[:64]}
    elif kind == "url":
        url = text if text.startswith(("http://", "https://", "tg://")) else f"https://{text.lstrip('/')}"
        values = {"action": "url", "url": url}
    elif kind == "alert":
        values = {"action": "alert", "alert": text[:200]}
    elif kind == "notify":
        values = {"action": "notify", "alert": "" if text == "-" else text[:200]}
    elif kind == "share":
        values = {"action": "share", "share_text": "" if text == "-" else text[:300]}
    elif kind == "setvar":
        op = parse_op(text)
        if op is None:
            await say("⚠️ Tushunarsiz. Masalan: <code>ball +1</code> yoki <code>vip = 1</code>")
            return True
        values = {"action": "set", **op}
    elif kind == "cond":
        if text == "-":
            props = {"cond": None}
        else:
            cond = parse_cond(text)
            if cond is None:
                await say("⚠️ Shart tushunarsiz. Masalan: <code>ball >= 10</code> yoki <code>phone bor</code>")
                return True
            props = {"cond": cond}
    elif kind == "command":
        name = text.lstrip("/").split()[0].lower() if text != "-" else ""
        target = b.get("target")

        def set_cmd(m: dict):
            m["commands"] = [x for x in m.get("commands") or [] if x["target"] != target]
            if name:
                if not name.replace("_", "").isalnum() or not name.isascii() or name in ("start", "admin", "cancel", "edit"):
                    return "Buyruq nomi faqat lotin harf, raqam va _ bo'lsin (start, admin band)"
                m["commands"] = [x for x in m["commands"] if x["command"] != name]
                m["commands"].append({"command": name[:32], "description": b["text"][:256], "target": target})
            return None

        if await fail(await save(runner, bot, set_cmd)):
            return True
        await set_state(runner, bot, chat_id, None)
        panel = button_panel(bot, loc)
        await say("✅ Saqlandi\n\n" + panel[0], panel[1])
        return True
    if values is None and props is None:
        return False

    def apply(m: dict):
        if values is not None:
            assign(m, loc, values)
        else:
            get_btn(m, loc).update(props)

    if await fail(await save(runner, bot, apply)):
        return True
    await set_state(runner, bot, chat_id, None)
    panel = button_panel(bot, loc)
    if panel:
        await say("✅ Saqlandi\n\n" + panel[0], panel[1])
    pid, i, _, _ = parse_loc(loc)
    if kind == "rename" and i is None:
        cur = await runner.current_page(bot, chat_id)
        if cur and cur["id"] == pid:
            await show_menu(runner, bot, chat_id, cur, "✏️ Nomi o'zgardi")
    return True


# ============================================================
# Inline boshqaruv (callbacklar)
# ============================================================


async def on_callback(runner: "Runner", bot: "RunningBot", chat_id: int, data: str, message: dict, user: dict) -> None:
    parts = data.split(":")
    cmd = parts[1] if len(parts) > 1 else ""

    async def panel(loc: str) -> None:
        p = button_panel(bot, loc)
        if p:
            await send(runner, bot, chat_id, p[0], p[1], message=message)

    async def err(text: str) -> None:
        await runner.api(bot, "sendMessage", {"chat_id": chat_id, "text": f"⚠️ {text}"})

    async def refresh_menu(pid: str, text: str) -> None:
        cur = await section(runner, bot, chat_id)
        if cur and cur["id"] == pid and await mode(runner, bot, chat_id) == "buttons":
            await show_section(runner, bot, chat_id, cur, user, text)

    if cmd == "on":
        await start_editing(runner, bot, chat_id, user, "buttons")
        return
    if cmd == "x" and len(parts) == 2:  # eski «tugatish» tugmasi
        await set_mode(runner, bot, chat_id, None)
        return
    if cmd == "p":
        await panel(parts[2])
        return
    if cmd in ("sel", "po"):
        pid, _, r, c = parse_loc(parts[2])
        page = page_by_id(bot.menu, pid)
        try:
            b = page["buttons"][r][c]
        except (TypeError, IndexError, KeyError):
            await err("Tugma topilmadi")
            return
        if cmd == "sel":
            if await mode(runner, bot, chat_id) != "buttons":
                await set_mode(runner, bot, chat_id, "buttons")
            if (await section(runner, bot, chat_id))["id"] != pid:
                await go_section(runner, bot, chat_id, page, push=False)
            await select_button(runner, bot, chat_id, user, page, r, c, message)
        else:
            target = page_by_id(bot.menu, b.get("target")) if b["action"] == "page" else None
            if target is None:
                await err(f"«{b['text']}» tugmasida post yo'q — vazifasi: {ACTION_LABELS.get(b['action'], b['action'])}")
                return
            await go_section(runner, bot, chat_id, target)
            await show_posts(runner, bot, chat_id, target, user)
        return
    if cmd == "addb":
        await set_state(runner, bot, chat_id, {"k": "addbtn", "p": parts[2]})
        await send(
            runner,
            bot,
            chat_id,
            "➕ <b>Yangi tugma(lar) nomini yuboring</b>\n\n• Har bir qator — alohida qator\n• Bir qatorda bir nechta — <code>|</code> bilan\n\n"
            "Masalan:\n<code>📦 Katalog | 🛒 Savat\n📞 Aloqa</code>",
        )
        return
    if cmd == "m":
        d, loc = parts[2], parts[3]
        pid, i, r, c = parse_loc(loc)
        pos: dict = {}

        def mv(m: dict):
            pos["rc"] = move_button(rows_of(m, loc), r, c, d)

        error = await save(runner, bot, mv)
        if error:
            await err(error)
            return
        nr, nc = pos["rc"]
        new_loc = f"{pid}.{nr}.{nc}" if i is None else f"{pid}.{i}.{nr}.{nc}"
        if i is None:
            await set_selected(runner, bot, chat_id, (pid, nr, nc))
            await refresh_menu(pid, "↔️ Joyi o'zgardi")
            p = button_panel(bot, new_loc)
            if p:
                await send(runner, bot, chat_id, p[0], p[1])
            return
        await panel(new_loc)
        return
    if cmd == "n":
        loc = parts[2]
        b = get_btn(bot.menu, loc)
        if b:
            await set_state(runner, bot, chat_id, {"k": "rename", "loc": loc})
            await runner.api(bot, "sendMessage", {"chat_id": chat_id, "text": f"✏️ «{b['text']}» tugmasining yangi nomini yuboring.\n\nBekor qilish: /cancel"})
        return
    if cmd == "x":
        loc = parts[2]
        b = get_btn(bot.menu, loc)
        if b:
            await send(
                runner,
                bot,
                chat_id,
                f"🗑 «{esc(b['text'])}» tugmasi o'chirilsinmi?\nUning bo'limi (postlari va ichki tugmalari) boshqa joyda ishlatilmasa — u ham o'chadi.",
                [[{"text": "✅ Ha, o'chirish", "callback_data": f"e:xy:{loc}"}, {"text": "❌ Yo'q", "callback_data": f"e:p:{loc}"}]],
                message=message,
            )
        return
    if cmd == "xy":
        loc = parts[2]
        pid, i, r, c = parse_loc(loc)
        removed: dict = {}

        def drop(m: dict):
            rows = rows_of(m, loc)
            removed["b"] = rows[r].pop(c)
            rows[:] = [row for row in rows if row]
            drop_orphans(m, [t for t in [removed["b"].get("target")] + list(removed["b"].get("targets") or []) if t])

        error = await save(runner, bot, drop)
        if error:
            await err(error)
            return
        await set_selected(runner, bot, chat_id, None)
        await send(runner, bot, chat_id, f"🗑 «{esc(removed['b']['text'])}» o'chirildi.", message=message)
        if i is None:
            await refresh_menu(pid, "✅ Yangilandi")
        else:
            await show_posts(runner, bot, chat_id, page_by_id(bot.menu, pid), user)
        return
    if cmd == "cut":
        loc = parts[2]
        pid, i, r, c = parse_loc(loc)
        removed = {}

        def cut(m: dict):
            rows = rows_of(m, loc)
            removed["b"] = rows[r].pop(c)
            rows[:] = [row for row in rows if row]

        b = get_btn(bot.menu, loc)
        if b is None:
            return
        # Kesilgan tugma bo'limi «yetim» bo'lib qolmasligi uchun avval nusxasi saqlanadi
        await runner.redis.set(_k(bot, "eclip", chat_id), json.dumps({"button": b}), ex=EDIT_TTL)
        error = await save(runner, bot, cut)
        if error:
            await runner.redis.delete(_k(bot, "eclip", chat_id))
            await err(error)
            return
        await set_selected(runner, bot, chat_id, None)
        await send(runner, bot, chat_id, f"✂️ «{esc(b['text'])}» kesildi. Kerakli menyuga o'ting va «{PASTE}{esc(b['text'])}» ni bosing.", message=message)
        if await mode(runner, bot, chat_id) != "buttons":
            await set_mode(runner, bot, chat_id, "buttons")
        await refresh_menu(pid, "📋 Qo'yish tugmasi paydo bo'ldi")
        return
    if cmd == "in":
        loc = parts[2]
        b = get_btn(bot.menu, loc)
        pid, i, _, _ = parse_loc(loc)
        if b is None:
            return
        if i is None:
            if await mode(runner, bot, chat_id) != "buttons":
                await set_mode(runner, bot, chat_id, "buttons")
            await enter_button(runner, bot, chat_id, user, page_by_id(bot.menu, pid), b)
        else:
            target = page_by_id(bot.menu, b.get("target"))
            if target:
                await go_section(runner, bot, chat_id, target)
                await show_posts(runner, bot, chat_id, target, user)
        return
    if cmd == "a":
        p = action_picker(bot, parts[2])
        await send(runner, bot, chat_id, p[0], p[1], message=message)
        return
    if cmd == "as":
        await choose_action(runner, bot, chat_id, user, message, parts[2], parts[3])
        return
    if cmd in ("ep", "fo", "rn"):
        loc, idx = parts[2], int(parts[3])
        if cmd == "ep":
            pages = bot.menu.get("pages") or []
            if idx < len(pages):
                error = await save(runner, bot, lambda m: assign(m, loc, {"action": "page", "target": pages[idx]["id"]}))
                if error:
                    await err(error)
            await panel(loc)
        elif cmd == "fo":
            forms = bot.menu.get("forms") or []
            if idx < len(forms):
                error = await save(runner, bot, lambda m: assign(m, loc, {"action": "form", "form": forms[idx]["id"]}))
                if error:
                    await err(error)
            await panel(loc)
        else:
            state = await get_state(runner, bot, chat_id) or {}
            sel = set(state.get("sel") or [])
            pages = bot.menu.get("pages") or []
            if idx < len(pages):
                sel.symmetric_difference_update({pages[idx]["id"]})
            await set_state(runner, bot, chat_id, {"k": "random", "loc": loc, "sel": sorted(sel)})
            p = random_picker(bot, loc, sel)
            await send(runner, bot, chat_id, p[0], p[1], message=message)
        return
    if cmd == "rd":
        loc = parts[2]
        state = await get_state(runner, bot, chat_id) or {}
        sel = state.get("sel") or []
        await set_state(runner, bot, chat_id, None)
        if not sel:
            await err("Kamida bitta bo'lim tanlang")
            return
        error = await save(runner, bot, lambda m: assign(m, loc, {"action": "random", "targets": sel}))
        if error:
            await err(error)
        await panel(loc)
        return
    if cmd == "t":
        prop, loc = parts[2], parts[3]
        b = get_btn(bot.menu, loc)
        if b is None:
            return
        target_id = b.get("target") if b["action"] == "page" else None

        def flip(m: dict):
            x = get_btn(m, loc)
            if prop in ("adm", "hid", "sub"):
                key = {"adm": "admin_only", "hid": "hidden", "sub": "need_sub"}[prop]
                x[key] = not x.get(key)
                if prop == "sub" and x[key] and not m.get("channels"):
                    return "Avval /admin → ⚙️ Sozlamalar → 📢 Majburiy obuna bo'limida kanal qo'shing"
            elif target_id:
                p = page_by_id(m, target_id)
                key = {"rnd": "random_post", "nav": "nav", "ntf": "notify"}[prop]
                p[key] = not p.get(key)
            return None

        error = await save(runner, bot, flip)
        if error:
            await err(error)
        await panel(loc)
        pid, i, _, _ = parse_loc(loc)
        if i is None and prop in ("hid", "adm"):
            await refresh_menu(pid, "✅ Yangilandi")
        return
    if cmd in ("cond", "cmd"):
        loc = parts[2]
        if cmd == "cond":
            await set_state(runner, bot, chat_id, {"k": "cond", "loc": loc})
            await send(
                runner,
                bot,
                chat_id,
                "👁 <b>Ko'rinish sharti</b> — tugma faqat shart bajarilsa ko'rinadi.\n\n"
                "<code>vip = 1</code>\n<code>ball >= 100</code>\n<code>phone bor</code>\n<code>phone yo'q</code>\n\n"
                "Olib tashlash: <code>-</code> · Bekor qilish: /cancel",
            )
        else:
            await set_state(runner, bot, chat_id, {"k": "command", "loc": loc})
            await send(runner, bot, chat_id, "⌨️ Shu bo'limni ochadigan buyruq nomini yuboring, masalan <code>katalog</code> (/katalog).\nOlib tashlash: <code>-</code>")
        return
    if cmd == "qt":
        state = await get_state(runner, bot, chat_id) or {}
        if state.get("k") != "q_type":
            return
        state["input"] = parts[2]
        if parts[2] == "choice":
            state["k"] = "q_opts"
            await set_state(runner, bot, chat_id, state)
            await send(runner, bot, chat_id, "🔘 Variantlarni vergul bilan yuboring:\n<code>Erkak, Ayol</code>", message=message)
        else:
            state["k"] = "q_var"
            await set_state(runner, bot, chat_id, state)
            await send(
                runner,
                bot,
                chat_id,
                f"{INPUT_LABELS.get(parts[2])} ✓\n\n🔢 Javob qaysi o'zgaruvchiga saqlansin? Lotin harflarida, masalan <code>ism</code>, <code>telefon</code>",
                message=message,
            )
        return

    # --- Postlar ---
    if cmd == "pp":
        page = page_by_id(bot.menu, parts[2])
        if page:
            await show_posts(runner, bot, chat_id, page, user)
        return
    if cmd == "pb":
        await panel(parts[2])
        return
    if cmd in ("pu", "pd", "pe", "px", "pxy", "pa"):
        pid, i = parts[2], int(parts[3])
        page = page_by_id(bot.menu, pid)
        if page is None or i >= len(page.get("messages") or []):
            await err("Post topilmadi")
            return
        if cmd in ("pu", "pd"):
            j = i - 1 if cmd == "pu" else i + 1
            if j < 0 or j >= len(page["messages"]):
                return

            def swap(m: dict):
                ms = page_by_id(m, pid)["messages"]
                ms[i], ms[j] = ms[j], ms[i]
                sync_text(page_by_id(m, pid))

            error = await save(runner, bot, swap)
            if error:
                await err(error)
                return
            await show_posts(runner, bot, chat_id, page_by_id(bot.menu, pid), user)
        elif cmd == "pe":
            if page["messages"][i]["type"] == "question":
                await set_state(runner, bot, chat_id, {"k": "q_text", "p": pid})
                await save(runner, bot, lambda m: page_by_id(m, pid)["messages"].pop(i))
                await send(runner, bot, chat_id, "❓ Savolning yangi matnini yuboring (eski savol o'rniga yangisi oxiriga qo'shiladi).")
                return
            await set_state(runner, bot, chat_id, {"k": "post_replace", "p": pid, "i": i})
            await send(runner, bot, chat_id, f"✏️ {i + 1}-post o'rniga yangi xabar yuboring (istalgan turdagi). Inline tugmalari saqlanadi.\nBekor qilish: /cancel")
        elif cmd == "px":
            await send(
                runner,
                bot,
                chat_id,
                f"🗑 {i + 1}-post o'chirilsinmi?",
                [[{"text": "✅ Ha", "callback_data": f"e:pxy:{pid}:{i}"}, {"text": "❌ Yo'q", "callback_data": f"e:pp:{pid}"}]],
            )
        elif cmd == "pxy":
            if len(page["messages"]) <= 1:
                await err("Bo'limda kamida bitta post qolishi kerak — o'rniga ✏️ bilan almashtiring")
                return

            def drop_post(m: dict):
                p = page_by_id(m, pid)
                removed = p["messages"].pop(i)
                sync_text(p)
                drop_orphans(m, [b.get("target") for row in removed.get("buttons") or [] for b in row if b.get("target")])

            error = await save(runner, bot, drop_post)
            if error:
                await err(error)
                return
            await show_posts(runner, bot, chat_id, page_by_id(bot.menu, pid), user)
        elif cmd == "pa":
            await set_state(runner, bot, chat_id, {"k": "ib_name", "p": pid, "i": i})
            await send(
                runner,
                bot,
                chat_id,
                "➕ <b>Inline tugma nomini yuboring</b>\n\n"
                "Havola tugmasi: <code>Saytimiz - https://example.uz</code>\n"
                "Oddiy nom yuborsangiz — bosilganda yangi post ochiladi (keyin vazifasini o'zgartirish mumkin).",
            )
        return


def random_picker(bot: "RunningBot", loc: str, sel: set) -> tuple[str, list]:
    rows = []
    for i, p in enumerate((bot.menu.get("pages") or [])[:40]):
        mark = "✅ " if p["id"] in sel else ""
        rows.append([{"text": f"{mark}{p['title']}"[:64], "callback_data": f"e:rn:{loc}:{i}"}])
    rows.append([{"text": "💾 Tayyor", "callback_data": f"e:rd:{loc}"}, {"text": "⬅️ Bekor", "callback_data": f"e:p:{loc}"}])
    return "🎲 Tasodifiy ochiladigan bo'limlarni belgilang (bir nechta):", rows


async def choose_action(runner: "Runner", bot: "RunningBot", chat_id: int, user: dict, message: dict, code: str, loc: str) -> None:
    b = get_btn(bot.menu, loc)
    if b is None:
        return
    pid, i, _, _ = parse_loc(loc)

    async def done(values: dict) -> None:
        error = await save(runner, bot, lambda m: assign(m, loc, values))
        if error:
            await runner.api(bot, "sendMessage", {"chat_id": chat_id, "text": f"⚠️ {error}"})
            return
        p = button_panel(bot, loc)
        await send(runner, bot, chat_id, p[0], p[1], message=message)

    async def ask(kind: str, prompt: str) -> None:
        await set_state(runner, bot, chat_id, {"k": kind, "loc": loc})
        await send(runner, bot, chat_id, prompt + "\n\nBekor qilish: /cancel")

    if code == "pg":
        target = page_by_id(bot.menu, b.get("target")) if b["action"] == "page" else None
        if target:
            await done({"action": "page", "target": target["id"]})
            return
        leaf = new_leaf(b["text"])
        if i is not None:
            leaf["nav"] = False

        def add(m: dict):
            m["pages"].append(leaf)
            assign(m, loc, {"action": "page", "target": leaf["id"]})

        error = await save(runner, bot, add)
        if error:
            await runner.api(bot, "sendMessage", {"chat_id": chat_id, "text": f"⚠️ {error}"})
            return
        p = button_panel(bot, loc)
        await send(runner, bot, chat_id, p[0], p[1], message=message)
    elif code == "ep":
        pages = bot.menu.get("pages") or []
        rows = [[{"text": ("🏠 " if p["id"] == bot.menu["start"] else "") + p["title"][:60], "callback_data": f"e:ep:{loc}:{n}"}] for n, p in enumerate(pages[:40])]
        rows.append([{"text": "⬅️ Orqaga", "callback_data": f"e:a:{loc}"}])
        await send(runner, bot, chat_id, "📑 Qaysi bo'lim ochilsin?", rows, message=message)
    elif code == "ur":
        await ask("url", "🔗 Havolani yuboring (https://... yoki t.me/...).")
    elif code == "al":
        await ask("alert", "🔔 Bosilganda qalqib chiqadigan matn (200 belgigacha). O'zgaruvchilar ishlaydi: {name}, {ball}...")
    elif code == "nt":
        await ask("notify", "🔔 Adminga boradigan qo'shimcha matn (masalan «Qo'ng'iroq so'radi»). Kerak bo'lmasa: -")
    elif code == "st":
        await ask(
            "setvar",
            "🔢 Bosilganda nima bo'lsin?\n<code>ball +1</code> — qo'shish\n<code>ball -5</code> — ayirish\n"
            "<code>vip = 1</code> — qiymat berish\n<code>promo tozalash</code> — o'chirish\n\nQiymat matnda <code>{ball}</code> ko'rinishida chiqadi.",
        )
    elif code == "fo":
        forms = bot.menu.get("forms") or []
        if not forms:
            await runner.api(
                bot,
                "sendMessage",
                {"chat_id": chat_id, "text": "📝 Hali forma yo'q. ⚙️ Admin panel → Sozlamalar → 📝 Formalar da yarating yoki postlarga ➕ Savol qo'shing."},
            )
            return
        rows = [[{"text": f["title"][:64], "callback_data": f"e:fo:{loc}:{n}"}] for n, f in enumerate(forms)]
        rows.append([{"text": "⬅️ Orqaga", "callback_data": f"e:a:{loc}"}])
        await send(runner, bot, chat_id, "📝 Qaysi forma boshlansin?", rows, message=message)
    elif code == "rn":
        sel = set(b.get("targets") or [])
        await set_state(runner, bot, chat_id, {"k": "random", "loc": loc, "sel": sorted(sel)})
        p = random_picker(bot, loc, sel)
        await send(runner, bot, chat_id, p[0], p[1], message=message)
    elif code == "sh":
        await ask("share", "📤 Ulashiladigan matn. <code>{ref_link}</code> — foydalanuvchining shaxsiy taklif havolasi.\nStandart matn: -")
    elif code == "cs":
        await done({"action": "check_sub"})
    elif code == "ct":
        await done({"action": "contact", "var": "phone"})
    elif code == "lc":
        await done({"action": "location", "var": "location"})
    else:
        simple = {"fb": "feedback", "bk": "back", "hm": "home", "wa": "webapp"}
        if code in simple:
            await done({"action": simple[code]})


# main.py bilan bir xil yozuvlar (aylanma import bo'lmasligi uchun shu yerda)
NAV_BACK = "⬅️ Orqaga"
NAV_HOME = "🏠 Bosh menyu"
