"""Botning o'zida chat orqali tahrirlash (MenuBuilder uslubi).

Egasi (yoki admin) /admin → «✏️ Botni tahrirlash» ni bosadi — tahrirlash rejimi yoqiladi. Endi har bir
sahifa ko'rsatilganda ostida «tahrirlash kartasi» chiqadi:

    📝 Kontent      — sahifa xabarlarini almashtirish: istalgan xabar (matn formatlash bilan, rasm, video,
                      fayl, ovoz, stiker, GIF...) yuboriladi — aynan shunday saqlanadi; bir nechta xabar ham mumkin
    ➕ Tugma         — «📦 Katalog | 🛒 Savat» ko'rinishida yoziladi: har qator — tugmalar qatori;
                      har bir yangi tugma o'z sahifasini oladi (ichiga kirib to'ldiriladi)
    🔘 Tugmalar      — tugmani tanlash → nomi, vazifasi (15 xil), joyi (⬅️➡️⬆️⬇️), ko'rinish sharti, o'chirish
    ⌨️ Inline/Reply  — tugmalar xabar ostida yoki klaviatura o'rnida
    ⚙️ Sozlamalar    — nomi, bosh sahifa, nusxa taqiqlash, ochilganda xabar, o'chirish
    📄 Sahifalar     — barcha sahifalar ro'yxati, yangi sahifa

Tugmalarning o'zi oddiy ishlaydi — egasi botini foydalanuvchi kabi aylanib, kerakli joyni tahrirlaydi.
Holat redis'da: ub:{bot}:edit:{chat} (rejim), ub:{bot}:est:{chat} (kutilayotgan kiritish), ub:{bot}:ebuf:{chat}.
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
    form_by_id,
    html_to_plain,
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

EDIT_TTL = 12 * 3600
STATE_TTL = 1800
PAGE_SIZE = 8


def _k(bot: "RunningBot", kind: str, chat_id: int) -> str:
    return f"ub:{bot.bot_id}:{kind}:{chat_id}"


def esc(text: str) -> str:
    return html.escape(text or "", quote=False)


# --- Saqlash ---


async def save(runner: "Runner", bot: "RunningBot", mutate: Callable[[dict], object]) -> str | None:
    """Hujjat nusxasini o'zgartiradi, tekshiradi va saqlaydi. Xato bo'lsa — o'zbekcha matn qaytaradi."""
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


async def editing(runner: "Runner", bot: "RunningBot", chat_id: int) -> bool:
    return bool(await runner.redis.get(_k(bot, "edit", chat_id)))


async def set_state(runner: "Runner", bot: "RunningBot", chat_id: int, state: dict | None) -> None:
    if state is None:
        await runner.redis.delete(_k(bot, "est", chat_id), _k(bot, "ebuf", chat_id))
    else:
        await runner.redis.set(_k(bot, "est", chat_id), json.dumps(state), ex=STATE_TTL)


async def get_state(runner: "Runner", bot: "RunningBot", chat_id: int) -> dict | None:
    raw = await runner.redis.get(_k(bot, "est", chat_id))
    return json.loads(raw) if raw else None


async def send(runner: "Runner", bot: "RunningBot", chat_id: int, text: str, rows: list | None = None, *, message: dict | None = None) -> None:
    data = {"chat_id": chat_id, "text": text[:4096], "parse_mode": "HTML", "disable_web_page_preview": True}
    if rows is not None:
        data["reply_markup"] = {"inline_keyboard": rows}
    if message is not None:
        try:
            await runner.api(bot, "editMessageText", {**data, "message_id": message["message_id"]})
            return
        except Exception as exc:  # noqa: BLE001
            if "not modified" in str(exc):
                return
    await runner.api(bot, "sendMessage", data)


# --- Tahrirlash kartasi ---


def _summary(page: dict) -> str:
    if page.get("messages"):
        kinds = [MSG_LABELS.get(m["type"], m["type"]) for m in page["messages"]]
        content = ", ".join(kinds)
    else:
        content = "🖼 Rasm + matn" if page.get("media_id") else "📝 Matn"
    n = sum(len(r) for r in page.get("buttons") or [])
    kb = "⌨️ Klaviatura (reply)" if page.get("keyboard") == "reply" else "💬 Xabar ostida (inline)"
    return f"📨 {content}\n{kb} · 🔘 {n} ta tugma"


def card(bot: "RunningBot", page: dict) -> tuple[str, list]:
    pid = page["id"]
    start = " 🏠" if pid == bot.menu.get("start") else ""
    text = f"✏️ <b>Tahrirlash · «{esc(page['title'])}»</b>{start}\n{_summary(page)}"
    reply = page.get("keyboard") == "reply"
    rows = [
        [{"text": "📝 Kontent", "callback_data": f"e:c:{pid}"}, {"text": "➕ Tugma qo'shish", "callback_data": f"e:a:{pid}"}],
        [{"text": "🔘 Tugmalar", "callback_data": f"e:B:{pid}"}, {"text": "⌨️ → Inline" if reply else "⌨️ → Reply", "callback_data": f"e:k:{pid}"}],
        [{"text": "⚙️ Sozlamalar", "callback_data": f"e:s:{pid}"}, {"text": "📄 Sahifalar", "callback_data": "e:P:0"}],
        [{"text": "🏁 Tahrirlashni tugatish", "callback_data": "e:x"}],
    ]
    return text, rows


async def after_page(runner: "Runner", bot: "RunningBot", chat_id: int, page: dict) -> None:
    if await editing(runner, bot, chat_id):
        text, rows = card(bot, page)
        await send(runner, bot, chat_id, text, rows)


async def start_editing(runner: "Runner", bot: "RunningBot", chat_id: int, user: dict, page_id: str | None = None) -> None:
    await runner.redis.set(_k(bot, "edit", chat_id), "1", ex=EDIT_TTL)
    await set_state(runner, bot, chat_id, None)
    await send(
        runner,
        bot,
        chat_id,
        "✏️ <b>Tahrirlash rejimi yoqildi</b>\n\n"
        "Botingizni oddiy foydalanuvchi kabi aylaning — har bir sahifa ostida tahrirlash kartasi chiqadi:\n"
        "• <b>📝 Kontent</b> — matn, rasm, video, fayl... yuboring (formatlash saqlanadi)\n"
        "• <b>➕ Tugma qo'shish</b> — <code>📦 Katalog | 🛒 Savat</code> (| — bir qatorda)\n"
        "• <b>🔘 Tugmalar</b> — nomi, vazifasi, joyi, sharti\n\n"
        "O'zgaruvchilar: <code>{name}</code> <code>{user_id}</code> <code>{ref_link}</code> <code>{ref_count}</code> va o'zingiznikilar.",
    )
    await runner.open_page(bot, chat_id, page_id or bot.menu.get("start"), user, push=False)


async def reopen(runner: "Runner", bot: "RunningBot", chat_id: int, page_id: str, user: dict) -> None:
    """Saqlangandan keyin sahifani yangi ko'rinishda qayta ko'rsatadi (karta bilan)."""
    page = page_by_id(bot.menu, page_id)
    if page is None:
        page = page_by_id(bot.menu, bot.menu.get("start"))
    await runner.redis.set(f"ub:{bot.bot_id}:cur:{chat_id}", page["id"], ex=30 * 24 * 3600)
    await runner.send_page(bot, chat_id, page, user)


# --- Yordamchi: tugmalar ---


def _btn(menu: dict, pid: str, r: int, c: int) -> dict | None:
    page = page_by_id(menu, pid)
    try:
        return page["buttons"][r][c] if page else None
    except IndexError:
        return None


def _new_child(parent: dict, title: str) -> dict:
    back = {"text": "⬅️ Orqaga", "action": "back"}
    return {
        "id": new_page_id(),
        "title": title[:64],
        "text": title[:64],
        "media_id": None,
        "messages": [{"type": "text", "text": f"<b>{esc(title)}</b>\n\nBu bo'lim matnini o'zgartiring: ✏️ → 📝 Kontent", "file_id": None, "media_id": None}],
        "keyboard": parent.get("keyboard", "inline"),
        "buttons": [[back]],
    }


def _action_detail(bot: "RunningBot", b: dict) -> str:
    a = b["action"]
    if a == "page":
        p = page_by_id(bot.menu, b.get("target"))
        return f"«{esc(p['title'])}»" if p else ""
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
        return f"{len(b.get('targets') or [])} ta sahifadan"
    return ""


def buttons_grid(bot: "RunningBot", page: dict) -> tuple[str, list]:
    pid = page["id"]
    rows = []
    for r, row in enumerate(page.get("buttons") or []):
        line = []
        for c, b in enumerate(row):
            mark = ("👁" if b.get("cond") else "") + ("🔒" if b.get("admin_only") else "")
            line.append({"text": f"{mark}{b['text']}"[:64], "callback_data": f"e:b:{pid}:{r}:{c}"})
        rows.append(line)
    rows.append([{"text": "➕ Tugma qo'shish", "callback_data": f"e:a:{pid}"}, {"text": "⬅️ Orqaga", "callback_data": f"e:card:{pid}"}])
    text = f"🔘 <b>«{esc(page['title'])}» tugmalari</b>\n\nTugmani bosing — sozlamalari ochiladi (nomi, vazifasi, joyi, sharti)."
    if not page.get("buttons"):
        text += "\n\nHozircha tugma yo'q."
    return text, rows


def button_panel(bot: "RunningBot", pid: str, r: int, c: int) -> tuple[str, list] | None:
    b = _btn(bot.menu, pid, r, c)
    if b is None:
        return None
    page = page_by_id(bot.menu, pid)
    loc = f"{pid}:{r}:{c}"
    text = (
        f"🔘 <b>«{esc(b['text'])}»</b>\n\n"
        f"🎯 Vazifasi: {ACTION_LABELS.get(b['action'], b['action'])} {_action_detail(bot, b)}\n"
        f"📍 Joyi: {r + 1}-qator, {c + 1}-o'rin (qatorda {len(page['buttons'][r])} ta)\n"
        f"👁 Ko'rinish sharti: {esc(describe_cond(b.get('cond')))}"
        + ("\n🔒 Faqat adminlar ko'radi" if b.get("admin_only") else "")
    )
    rows = [
        [{"text": "✏️ Nomi", "callback_data": f"e:bn:{loc}"}, {"text": "🎯 Vazifasi", "callback_data": f"e:ba:{loc}"}],
        [
            {"text": "⬅️", "callback_data": f"e:bm:L:{loc}"},
            {"text": "➡️", "callback_data": f"e:bm:R:{loc}"},
            {"text": "⬆️", "callback_data": f"e:bm:U:{loc}"},
            {"text": "⬇️", "callback_data": f"e:bm:D:{loc}"},
        ],
        [{"text": "↩️ Alohida qatorga", "callback_data": f"e:bm:S:{loc}"}],
        [
            {"text": "👁 Shart", "callback_data": f"e:bc:{loc}"},
            {"text": f"🔒 Faqat admin {'✅' if b.get('admin_only') else '❌'}", "callback_data": f"e:bo:{loc}"},
        ],
    ]
    if b["action"] == "page" and b.get("target"):
        rows.append([{"text": "↪️ Ichiga kirish (sahifasini tahrirlash)", "callback_data": f"e:o:{b['target']}"}])
    rows.append([{"text": "🗑 O'chirish", "callback_data": f"e:bx:{loc}"}, {"text": "⬅️ Tugmalar", "callback_data": f"e:B:{pid}"}])
    return text, rows


ACTION_CODES = [
    ("np", "📄 Yangi sahifa"),
    ("ep", "📑 Mavjud sahifa"),
    ("ur", "🔗 Havola"),
    ("fb", "💬 Adminga yozish"),
    ("fo", "📝 Forma"),
    ("al", "🔔 Ogohlantirish (alert)"),
    ("st", "🔢 O'zgaruvchi"),
    ("rn", "🎲 Tasodifiy sahifa"),
    ("sh", "📤 Ulashish / referal"),
    ("cs", "✅ Obunani tekshirish"),
    ("ct", "📱 Telefon so'rash"),
    ("lc", "📍 Joylashuv so'rash"),
    ("nt", "🔔 Adminga bildirish"),
    ("bk", "⬅️ Orqaga"),
    ("hm", "🏠 Bosh menyu"),
    ("wa", "🌐 Web App"),
]


def action_picker(bot: "RunningBot", pid: str, r: int, c: int) -> tuple[str, list]:
    loc = f"{pid}:{r}:{c}"
    b = _btn(bot.menu, pid, r, c)
    rows, line = [], []
    for code, label in ACTION_CODES:
        line.append({"text": label, "callback_data": f"e:bs:{code}:{loc}"})
        if len(line) == 2:
            rows.append(line)
            line = []
    if line:
        rows.append(line)
    rows.append([{"text": "⬅️ Orqaga", "callback_data": f"e:b:{loc}"}])
    text = (
        f"🎯 <b>«{esc(b['text'] if b else '')}» tugmasi vazifasi</b>\n\n"
        "📄 Yangi sahifa — ichki menyu (eng ko'p ishlatiladi)\n"
        "🔗 Havola, 🔔 Ogohlantirish — faqat xabar ostidagi (inline) tugmalarda\n"
        "📝 Forma — savollar beradi, javoblarni eslab qoladi va sizga yuboradi\n"
        "🔢 O'zgaruvchi — masalan <code>ball +1</code> (ball yig'ish, ovoz berish)\n"
        "📱 / 📍 — telefon yoki joylashuvni so'rab, o'zgaruvchiga saqlaydi"
    )
    return text, rows


def pages_list(bot: "RunningBot", n: int, prefix: str = "e:o:", extra: str = "") -> tuple[list, int]:
    pages = bot.menu.get("pages") or []
    total = max(1, (len(pages) + PAGE_SIZE - 1) // PAGE_SIZE)
    n = max(0, min(n, total - 1))
    rows = []
    for i, p in enumerate(pages[n * PAGE_SIZE : (n + 1) * PAGE_SIZE]):
        idx = n * PAGE_SIZE + i
        home = "🏠 " if p["id"] == bot.menu.get("start") else ""
        data = f"{prefix}{p['id']}" if prefix == "e:o:" else f"{prefix}{idx}"
        rows.append([{"text": f"{home}{p['title']}"[:64], "callback_data": data}])
    return rows, total


def move_button(page: dict, r: int, c: int, d: str) -> tuple[int, int]:
    rows = page["buttons"]
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
                j = r  # bo'shagan qator o'chdi — keyingi qator shu indeksga siljidi
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


# --- Callbacklar ---


async def on_callback(runner: "Runner", bot: "RunningBot", chat_id: int, data: str, message: dict, user: dict) -> None:
    parts = data.split(":")
    cmd = parts[1] if len(parts) > 1 else ""
    args = parts[2:]

    async def show(text_rows: tuple[str, list] | None) -> None:
        if text_rows is not None:
            await send(runner, bot, chat_id, text_rows[0], text_rows[1], message=message)

    async def err(text: str) -> None:
        await runner.api(bot, "sendMessage", {"chat_id": chat_id, "text": f"⚠️ {text}"})

    if cmd == "on":
        await start_editing(runner, bot, chat_id, user, args[0] if args else None)
        return
    if not await editing(runner, bot, chat_id):
        await runner.redis.set(_k(bot, "edit", chat_id), "1", ex=EDIT_TTL)
    if cmd == "x":
        await runner.redis.delete(_k(bot, "edit", chat_id))
        await set_state(runner, bot, chat_id, None)
        await send(
            runner,
            bot,
            chat_id,
            "🏁 Tahrirlash rejimi o'chirildi. Botingiz yangi ko'rinishda ishlamoqda.",
            [[{"text": "✏️ Yana tahrirlash", "callback_data": "e:on"}, {"text": "⚙️ Panel", "callback_data": "adm:st"}]],
            message=message,
        )
        return
    if cmd == "card":
        page = page_by_id(bot.menu, args[0])
        if page:
            await show(card(bot, page))
        return
    if cmd == "o":
        page = page_by_id(bot.menu, args[0])
        if page:
            await reopen(runner, bot, chat_id, page["id"], user)
        return
    if cmd == "P":
        n = int(args[0]) if args else 0
        rows, total = pages_list(bot, n)
        nav = []
        if n > 0:
            nav.append({"text": "◀️", "callback_data": f"e:P:{n - 1}"})
        if n < total - 1:
            nav.append({"text": "▶️", "callback_data": f"e:P:{n + 1}"})
        if nav:
            rows.append(nav)
        rows.append([{"text": "➕ Yangi sahifa", "callback_data": "e:pn"}])
        await show((f"📄 <b>Sahifalar</b> ({len(bot.menu['pages'])} ta)\n\nTahrirlash uchun sahifani tanlang.", rows))
        return
    if cmd == "pn":
        await set_state(runner, bot, chat_id, {"k": "newpage"})
        await runner.api(bot, "sendMessage", {"chat_id": chat_id, "text": "📄 Yangi sahifa nomini yuboring.\n\nBekor qilish: /cancel"})
        return

    pid = args[0] if args else ""
    page = page_by_id(bot.menu, pid)
    page_cmds = ("c", "cr", "ca", "cd", "a", "B", "k", "s", "sp", "sv", "sh", "sf", "sn", "sl", "so", "sd", "sdy")
    if cmd in page_cmds and page is None:
        await err("Sahifa topilmadi — u o'chirilgan bo'lishi mumkin")
        return

    # --- Kontent ---
    if cmd == "c":
        msgs = page.get("messages") or []
        if msgs:
            lines = [f"{i + 1}. {MSG_LABELS.get(m['type'], m['type'])}" + (f": «{esc(html_to_plain(m.get('text', ''))[:50])}»" if m.get("text") else "") for i, m in enumerate(msgs)]
        else:
            lines = [f"1. {'🖼 Rasm + ' if page.get('media_id') else ''}📝 «{esc(page['text'][:50])}»"]
        rows = [
            [{"text": "✏️ Almashtirish", "callback_data": f"e:cr:{pid}"}, {"text": "➕ Xabar qo'shish", "callback_data": f"e:ca:{pid}"}],
        ]
        if len(msgs) > 1:
            rows.append([{"text": "🗑 Oxirgi xabarni o'chirish", "callback_data": f"e:cd:{pid}"}])
        rows.append([{"text": "⬅️ Orqaga", "callback_data": f"e:card:{pid}"}])
        await show(
            (
                f"📝 <b>«{esc(page['title'])}» kontenti</b>\n\n" + "\n".join(lines) + "\n\n"
                "«✏️ Almashtirish» ni bosib, yangi kontentni yuboring: matn (qalin, kursiv, havola — saqlanadi), rasm, video, "
                "fayl, ovozli xabar, stiker, GIF. Bir nechta xabar yuborsangiz — hammasi ketma-ket chiqadi.",
                rows,
            )
        )
        return
    if cmd in ("cr", "ca"):
        await set_state(runner, bot, chat_id, {"k": "content", "p": pid, "m": "replace" if cmd == "cr" else "append"})
        await runner.redis.delete(_k(bot, "ebuf", chat_id))
        await runner.api(
            bot,
            "sendMessage",
            {
                "chat_id": chat_id,
                "text": "📨 Endi kontentni yuboring (bir yoki bir nechta xabar).\n\n"
                "Matnda o'zgaruvchilar ishlaydi: {name}, {user_id}, {ref_link}, {ball}...\n"
                "Tugatgach «✅ Saqlash» ni bosing. Bekor qilish: /cancel",
            },
        )
        return
    if cmd == "cd":

        def drop_last(menu: dict):
            p = page_by_id(menu, pid)
            if len(p.get("messages") or []) > 1:
                p["messages"].pop()

        error = await save(runner, bot, drop_last)
        if error:
            await err(error)
        await reopen(runner, bot, chat_id, pid, user)
        return

    # --- Tugma qo'shish ---
    if cmd == "a":
        await set_state(runner, bot, chat_id, {"k": "addbtn", "p": pid})
        await runner.api(
            bot,
            "sendMessage",
            {
                "chat_id": chat_id,
                "parse_mode": "HTML",
                "text": "➕ <b>Yangi tugma(lar) nomini yuboring</b>\n\n"
                "• Har bir qator — alohida tugmalar qatori\n"
                "• Bir qatorda bir nechta tugma — <code>|</code> bilan ajrating\n\n"
                "Masalan:\n<code>📦 Katalog | 🛒 Savat\n📞 Aloqa</code>\n\n"
                "Har bir yangi tugma o'z sahifasini oladi — keyin ichiga kirib kontentini yozasiz. "
                "Vazifasini (havola, forma, alert...) keyin 🔘 Tugmalar orqali o'zgartirasiz.\n\nBekor qilish: /cancel",
            },
        )
        return
    if cmd == "B":
        await show(buttons_grid(bot, page))
        return
    if cmd == "k":

        def toggle(menu: dict):
            p = page_by_id(menu, pid)
            p["keyboard"] = "inline" if p.get("keyboard") == "reply" else "reply"

        error = await save(runner, bot, toggle)
        if error:
            await err(error)
            return
        await reopen(runner, bot, chat_id, pid, user)
        return

    # --- Bitta tugma ---
    if cmd in ("b", "bn", "ba", "bc", "bo", "bx", "bxy") or cmd in ("bm", "bs", "bt", "bf", "br", "brd"):
        if cmd in ("bm", "bs"):
            sub, pid, r, c = args[0], args[1], int(args[2]), int(args[3])
        elif cmd in ("bt", "bf", "br"):
            pid, r, c, idx = args[0], int(args[1]), int(args[2]), int(args[3])
        else:
            pid, r, c = args[0], int(args[1]), int(args[2])
        b = _btn(bot.menu, pid, r, c)
        if b is None:
            await err("Tugma topilmadi")
            return
        if cmd == "b":
            await show(button_panel(bot, pid, r, c))
        elif cmd == "bn":
            await set_state(runner, bot, chat_id, {"k": "rename", "p": pid, "r": r, "c": c})
            await runner.api(bot, "sendMessage", {"chat_id": chat_id, "text": f"✏️ «{b['text']}» tugmasining yangi nomini yuboring.\n\nBekor qilish: /cancel"})
        elif cmd == "ba":
            await show(action_picker(bot, pid, r, c))
        elif cmd == "bc":
            await set_state(runner, bot, chat_id, {"k": "cond", "p": pid, "r": r, "c": c})
            await runner.api(
                bot,
                "sendMessage",
                {
                    "chat_id": chat_id,
                    "parse_mode": "HTML",
                    "text": "👁 <b>Ko'rinish sharti</b> — tugma faqat shart bajarilganda ko'rinadi.\n\n"
                    "Misollar:\n<code>vip = 1</code>\n<code>ball >= 100</code>\n<code>phone bor</code>\n<code>phone yo'q</code>\n\n"
                    "Shartni olib tashlash: <code>-</code>\nBekor qilish: /cancel",
                },
            )
        elif cmd == "bo":

            def flip(menu: dict):
                x = _btn(menu, pid, r, c)
                x["admin_only"] = not x.get("admin_only")

            error = await save(runner, bot, flip)
            if error:
                await err(error)
            await show(button_panel(bot, pid, r, c))
        elif cmd == "bx":
            await show(
                (
                    f"🗑 «{esc(b['text'])}» tugmasi o'chirilsinmi?",
                    [[{"text": "✅ Ha, o'chirish", "callback_data": f"e:bxy:{pid}:{r}:{c}"}, {"text": "❌ Yo'q", "callback_data": f"e:b:{pid}:{r}:{c}"}]],
                )
            )
        elif cmd == "bxy":

            def drop(menu: dict):
                p = page_by_id(menu, pid)
                p["buttons"][r].pop(c)
                p["buttons"] = [row for row in p["buttons"] if row]

            error = await save(runner, bot, drop)
            if error:
                await err(error)
            await reopen(runner, bot, chat_id, pid, user)
        elif cmd == "bm":
            pos = {}

            def mv(menu: dict):
                pos["rc"] = move_button(page_by_id(menu, pid), r, c, sub)

            error = await save(runner, bot, mv)
            if error:
                await err(error)
                return
            nr, nc = pos["rc"]
            await show(button_panel(bot, pid, nr, nc))
        elif cmd == "bs":
            await choose_action(runner, bot, chat_id, user, message, sub, pid, r, c)
        elif cmd == "bt":
            target = (bot.menu.get("pages") or [])[idx]["id"] if idx < len(bot.menu.get("pages") or []) else None
            if not target:
                return
            error = await save(runner, bot, lambda m: _assign(m, pid, r, c, {"action": "page", "target": target}))
            if error:
                await err(error)
            await show(button_panel(bot, pid, r, c))
        elif cmd == "bf":
            forms = bot.menu.get("forms") or []
            if idx >= len(forms):
                return
            error = await save(runner, bot, lambda m: _assign(m, pid, r, c, {"action": "form", "form": forms[idx]["id"]}))
            if error:
                await err(error)
            await show(button_panel(bot, pid, r, c))
        elif cmd == "br":
            state = await get_state(runner, bot, chat_id) or {}
            sel = set(state.get("sel") or [])
            target = (bot.menu.get("pages") or [])[idx]["id"]
            sel.symmetric_difference_update({target})
            await set_state(runner, bot, chat_id, {"k": "random", "p": pid, "r": r, "c": c, "sel": sorted(sel)})
            await show(random_picker(bot, pid, r, c, sel))
        elif cmd == "brd":
            state = await get_state(runner, bot, chat_id) or {}
            sel = state.get("sel") or []
            await set_state(runner, bot, chat_id, None)
            if not sel:
                await err("Kamida bitta sahifa tanlang")
                return
            error = await save(runner, bot, lambda m: _assign(m, pid, r, c, {"action": "random", "targets": sel}))
            if error:
                await err(error)
            await show(button_panel(bot, pid, r, c))
        return

    # --- Sahifa sozlamalari ---
    if cmd == "s":
        await show(page_settings(bot, page))
        return
    if cmd in ("sp", "sv", "sh", "sf"):

        def change(menu: dict):
            p = page_by_id(menu, pid)
            if cmd == "sp":
                p["protect"] = not p.get("protect")
            elif cmd == "sv":
                p["notify"] = not p.get("notify")
            elif cmd == "sh":
                menu["start"] = pid
            else:
                menu["first_start"] = None if menu.get("first_start") == pid else pid

        error = await save(runner, bot, change)
        if error:
            await err(error)
        await show(page_settings(bot, page_by_id(bot.menu, pid)))
        return
    if cmd in ("sn", "sl", "so"):
        kind = {"sn": "ptitle", "sl": "placeholder", "so": "pageops"}[cmd]
        prompt = {
            "ptitle": "✏️ Sahifaning yangi nomini yuboring (faqat sizga ko'rinadi).",
            "placeholder": "💬 Klaviatura ustidagi xira yozuvni yuboring (64 belgigacha). Olib tashlash: -",
            "pageops": "🔢 Sahifa ochilganda bajariladigan amallarni yuboring, har biri yangi qatorda:\n\n"
            "<code>tashrif +1</code>\n<code>oxirgi_sahifa = katalog</code>\n\nOlib tashlash: -",
        }[kind]
        await set_state(runner, bot, chat_id, {"k": kind, "p": pid})
        await runner.api(bot, "sendMessage", {"chat_id": chat_id, "text": prompt + "\n\nBekor qilish: /cancel", "parse_mode": "HTML"})
        return
    if cmd == "sd":
        if pid == bot.menu.get("start"):
            await err("Bosh sahifani o'chirib bo'lmaydi — avval boshqa sahifani bosh qiling")
            return
        await show(
            (
                f"🗑 «{esc(page['title'])}» sahifasi o'chirilsinmi?\nUnga olib boradigan tugmalar ham o'chiriladi.",
                [[{"text": "✅ Ha, o'chirish", "callback_data": f"e:sdy:{pid}"}, {"text": "❌ Yo'q", "callback_data": f"e:s:{pid}"}]],
            )
        )
        return
    if cmd == "sdy":
        error = await save(runner, bot, lambda m: delete_page(m, pid))
        if error:
            await err(error)
            return
        await reopen(runner, bot, chat_id, bot.menu["start"], user)
        return

    # --- Kontentni saqlash / bekor qilish ---
    if cmd in ("cs", "cx"):
        await finish_content(runner, bot, chat_id, user, save_it=cmd == "cs")
        return


def _assign(menu: dict, pid: str, r: int, c: int, values: dict) -> None:
    b = _btn(menu, pid, r, c)
    keep = {"text": b["text"], "cond": b.get("cond"), "admin_only": b.get("admin_only", False)}
    b.clear()
    b.update(keep)
    b.update(values)


def delete_page(menu: dict, pid: str) -> None:
    menu["pages"] = [p for p in menu["pages"] if p["id"] != pid]
    for p in menu["pages"]:
        p["buttons"] = [[b for b in row if b.get("target") != pid] for row in p.get("buttons") or []]
        p["buttons"] = [row for row in p["buttons"] if row]
        for row in p["buttons"]:
            for b in row:
                if b.get("action") == "random":
                    b["targets"] = [t for t in b.get("targets") or [] if t != pid]
        p["buttons"] = [[b for b in row if b.get("action") != "random" or b.get("targets")] for row in p["buttons"]]
        p["buttons"] = [row for row in p["buttons"] if row]
    menu["keywords"] = [k for k in menu.get("keywords") or [] if k.get("target") != pid or k.get("reply")]
    menu["commands"] = [c for c in menu.get("commands") or [] if c.get("target") != pid]
    for f in menu.get("forms") or []:
        if f.get("target") == pid:
            f["target"] = None
    if menu.get("first_start") == pid:
        menu["first_start"] = None


def page_settings(bot: "RunningBot", page: dict) -> tuple[str, list]:
    pid = page["id"]
    ops = ", ".join(f"{o['var']} {o['op']} {o.get('value', '')}" for o in page.get("ops") or []) or "yo'q"
    text = (
        f"⚙️ <b>«{esc(page['title'])}» sozlamalari</b>\n\n"
        f"🔗 To'g'ridan-to'g'ri havola: <code>https://t.me/{bot.username}?start=p_{pid}</code>\n"
        f"🔢 Ochilganda: {esc(ops)}"
    )
    rows = [[{"text": "✏️ Nomi", "callback_data": f"e:sn:{pid}"}]]
    if pid != bot.menu.get("start"):
        rows[0].append({"text": "🏠 Bosh sahifa qilish", "callback_data": f"e:sh:{pid}"})
    rows += [
        [
            {"text": f"🔒 Nusxa taqiqi {'✅' if page.get('protect') else '❌'}", "callback_data": f"e:sp:{pid}"},
            {"text": f"🔔 Ochilganda xabar {'✅' if page.get('notify') else '❌'}", "callback_data": f"e:sv:{pid}"},
        ],
        [{"text": f"🆕 Yangi kelganlarga shu sahifa {'✅' if bot.menu.get('first_start') == pid else '❌'}", "callback_data": f"e:sf:{pid}"}],
        [{"text": "🔢 Ochilganda o'zgaruvchi", "callback_data": f"e:so:{pid}"}],
    ]
    if page.get("keyboard") == "reply":
        rows.append([{"text": "💬 Klaviatura yozuvi (placeholder)", "callback_data": f"e:sl:{pid}"}])
    if pid != bot.menu.get("start"):
        rows.append([{"text": "🗑 Sahifani o'chirish", "callback_data": f"e:sd:{pid}"}])
    rows.append([{"text": "⬅️ Orqaga", "callback_data": f"e:card:{pid}"}])
    return text, rows


def random_picker(bot: "RunningBot", pid: str, r: int, c: int, sel: set) -> tuple[str, list]:
    rows = []
    for i, p in enumerate((bot.menu.get("pages") or [])[:40]):
        mark = "✅ " if p["id"] in sel else ""
        rows.append([{"text": f"{mark}{p['title']}"[:64], "callback_data": f"e:br:{pid}:{r}:{c}:{i}"}])
    rows.append([{"text": "💾 Tayyor", "callback_data": f"e:brd:{pid}:{r}:{c}"}, {"text": "⬅️ Bekor", "callback_data": f"e:b:{pid}:{r}:{c}"}])
    return "🎲 Tasodifiy ochiladigan sahifalarni belgilang (bir nechta):", rows


async def choose_action(runner: "Runner", bot: "RunningBot", chat_id: int, user: dict, message: dict, code: str, pid: str, r: int, c: int) -> None:
    page = page_by_id(bot.menu, pid)
    b = _btn(bot.menu, pid, r, c)
    loc = {"p": pid, "r": r, "c": c}

    async def done(values: dict) -> None:
        error = await save(runner, bot, lambda m: _assign(m, pid, r, c, values))
        if error:
            await runner.api(bot, "sendMessage", {"chat_id": chat_id, "text": f"⚠️ {error}"})
            return
        text, rows = button_panel(bot, pid, r, c)
        await send(runner, bot, chat_id, text, rows, message=message)

    async def ask(kind: str, prompt: str) -> None:
        await set_state(runner, bot, chat_id, {"k": kind, **loc})
        await runner.api(bot, "sendMessage", {"chat_id": chat_id, "text": prompt + "\n\nBekor qilish: /cancel", "parse_mode": "HTML"})

    reply = page.get("keyboard") == "reply"
    if code in ("ur", "al") and reply:
        await runner.api(bot, "sendMessage", {"chat_id": chat_id, "text": "⚠️ Bu vazifa faqat xabar ostidagi (inline) tugmalarda ishlaydi. Avval sahifani «⌨️ → Inline» qiling."})
        return
    if code == "np":
        child = _new_child(page, b["text"])

        def add_child(menu: dict):
            menu["pages"].append(child)
            _assign(menu, pid, r, c, {"action": "page", "target": child["id"]})

        error = await save(runner, bot, add_child)
        if error:
            await runner.api(bot, "sendMessage", {"chat_id": chat_id, "text": f"⚠️ {error}"})
            return
        await reopen(runner, bot, chat_id, child["id"], user)
    elif code == "ep":
        pages = bot.menu.get("pages") or []
        rows = [[{"text": p["title"][:64], "callback_data": f"e:bt:{pid}:{r}:{c}:{i}"}] for i, p in enumerate(pages[:40])]
        rows.append([{"text": "⬅️ Orqaga", "callback_data": f"e:ba:{pid}:{r}:{c}"}])
        await send(runner, bot, chat_id, "📑 Qaysi sahifa ochilsin?", rows, message=message)
    elif code == "ur":
        await ask("url", "🔗 Havolani yuboring (https://... yoki t.me/...).")
    elif code == "al":
        await ask("alert", "🔔 Bosilganda qalqib chiqadigan matnni yuboring (200 belgigacha). O'zgaruvchilar ishlaydi: {name}, {ball}...")
    elif code == "nt":
        await ask("notify", "🔔 Adminga boradigan qo'shimcha matn (masalan «Qo'ng'iroq so'radi»). Kerak bo'lmasa: -")
    elif code == "st":
        await ask(
            "setvar",
            "🔢 Bosilganda nima bo'lsin? Masalan:\n<code>ball +1</code> — 1 qo'shish\n<code>ball -5</code> — ayirish\n"
            "<code>vip = 1</code> — qiymat berish\n<code>promo tozalash</code> — o'chirish\n\nQiymat matnda <code>{ball}</code> ko'rinishida chiqadi.",
        )
    elif code == "fo":
        forms = bot.menu.get("forms") or []
        if not forms:
            await runner.api(
                bot,
                "sendMessage",
                {"chat_id": chat_id, "text": "📝 Hali forma yo'q. /admin → ⚙️ Sozlamalar → 📝 Formalar bo'limida yarating, keyin shu yerdan tanlang."},
            )
            return
        rows = [[{"text": f["title"][:64], "callback_data": f"e:bf:{pid}:{r}:{c}:{i}"}] for i, f in enumerate(forms)]
        rows.append([{"text": "⬅️ Orqaga", "callback_data": f"e:ba:{pid}:{r}:{c}"}])
        await send(runner, bot, chat_id, "📝 Qaysi forma boshlansin?", rows, message=message)
    elif code == "rn":
        await set_state(runner, bot, chat_id, {"k": "random", **loc, "sel": list(b.get("targets") or [])})
        text, rows = random_picker(bot, pid, r, c, set(b.get("targets") or []))
        await send(runner, bot, chat_id, text, rows, message=message)
    elif code == "sh":
        await ask("share", "📤 Ulashiladigan matnni yuboring. <code>{ref_link}</code> — foydalanuvchining shaxsiy taklif havolasi.\nStandart matn uchun: -")
    elif code == "cs":
        await done({"action": "check_sub", "target": None})
    elif code == "ct":
        await done({"action": "contact", "var": "phone"})
    elif code == "lc":
        await done({"action": "location", "var": "location"})
    else:
        simple = {"fb": "feedback", "bk": "back", "hm": "home", "wa": "webapp"}
        if code in simple:
            await done({"action": simple[code]})


# --- Kiritishlar (egasining xabarlari) ---


async def finish_content(runner: "Runner", bot: "RunningBot", chat_id: int, user: dict, *, save_it: bool) -> None:
    state = await get_state(runner, bot, chat_id)
    raw = await runner.redis.get(_k(bot, "ebuf", chat_id))
    buf = json.loads(raw) if raw else []
    await set_state(runner, bot, chat_id, None)
    if not state or state.get("k") != "content":
        return
    pid = state["p"]
    if not save_it or not buf:
        await runner.api(bot, "sendMessage", {"chat_id": chat_id, "text": "❌ Bekor qilindi."})
        return

    def apply(menu: dict):
        p = page_by_id(menu, pid)
        if state["m"] == "append":
            base = p.get("messages") or (
                [{"type": "photo" if p.get("media_id") else "text", "text": esc(p["text"]), "media_id": p.get("media_id"), "file_id": None}]
            )
            p["messages"] = (base + buf)[:MAX_MESSAGES]
        else:
            p["messages"] = buf[:MAX_MESSAGES]
            p["media_id"] = None
        first_text = next((html_to_plain(m["text"]) for m in p["messages"] if m.get("text")), "") or p["title"]
        p["text"] = first_text[:4096]

    error = await save(runner, bot, apply)
    if error:
        await runner.api(bot, "sendMessage", {"chat_id": chat_id, "text": f"⚠️ {error}"})
        return
    await runner.api(bot, "sendMessage", {"chat_id": chat_id, "text": "✅ Saqlandi. Sahifa endi shunday ko'rinadi 👇"})
    await reopen(runner, bot, chat_id, pid, user)


async def on_message(runner: "Runner", bot: "RunningBot", message: dict) -> bool:
    """Egasining xabari tahrirlashga tegishli bo'lsa — qayta ishlab True qaytaradi."""
    chat_id = message["chat"]["id"]
    user = message["from"]
    text = (message.get("text") or "").strip()
    if text in ("/edit", "/tahrir"):
        await start_editing(runner, bot, chat_id, user)
        return True
    state = await get_state(runner, bot, chat_id)
    if state is None:
        return False
    if text == "/cancel":
        await set_state(runner, bot, chat_id, None)
        await runner.api(bot, "sendMessage", {"chat_id": chat_id, "text": "❌ Bekor qilindi."})
        return True
    kind = state["k"]

    async def say(t: str) -> None:
        await runner.api(bot, "sendMessage", {"chat_id": chat_id, "text": t, "parse_mode": "HTML"})

    if kind == "content":
        msg = message_to_msg(message)
        if msg is None:
            await say("⚠️ Bu turdagi xabarni saqlab bo'lmaydi. Matn, rasm, video, fayl, audio, ovozli xabar, stiker yoki GIF yuboring.")
            return True
        if msg["type"] == "text" and len(msg["text"]) > 4096:
            await say("⚠️ Matn juda uzun (4096 belgigacha).")
            return True
        if msg["type"] not in ("text", "sticker", "video_note") and len(msg["text"]) > 1024:
            await say("⚠️ Izoh juda uzun (1024 belgigacha) — matnni alohida xabar qilib yuboring.")
            return True
        raw = await runner.redis.get(_k(bot, "ebuf", chat_id))
        buf = json.loads(raw) if raw else []
        if len(buf) >= MAX_MESSAGES:
            await say(f"⚠️ Bitta sahifada ko'pi bilan {MAX_MESSAGES} ta xabar.")
            return True
        buf.append(msg)
        await runner.redis.set(_k(bot, "ebuf", chat_id), json.dumps(buf), ex=STATE_TTL)
        await runner.api(
            bot,
            "sendMessage",
            {
                "chat_id": chat_id,
                "text": f"✅ Qabul qilindi: {MSG_LABELS.get(msg['type'], msg['type'])} (jami {len(buf)}). Yana yuboring yoki saqlang.",
                "reply_to_message_id": message["message_id"],
                "reply_markup": {"inline_keyboard": [[{"text": "✅ Saqlash", "callback_data": "e:cs"}, {"text": "❌ Bekor", "callback_data": "e:cx"}]]},
            },
        )
        return True

    if not text:
        await say("✍️ Matn ko'rinishida yuboring yoki /cancel")
        return True

    pid = state.get("p")

    if kind == "addbtn":
        lines = [ln for ln in text.splitlines() if ln.strip()]
        new_rows = [[t.strip()[:64] for t in ln.split("|") if t.strip()] for ln in lines]
        new_rows = [r for r in new_rows if r]
        if not new_rows:
            await say("⚠️ Tugma nomi bo'sh")
            return True
        created = []

        def add(menu: dict):
            p = page_by_id(menu, pid)
            if len(p["buttons"]) + len(new_rows) > MAX_ROWS:
                return f"Sahifada ko'pi bilan {MAX_ROWS} qator tugma"
            for row in new_rows:
                if len(row) > MAX_PER_ROW:
                    return f"Bir qatorda ko'pi bilan {MAX_PER_ROW} ta tugma"
                line = []
                for label in row:
                    child = _new_child(p, label)
                    menu["pages"].append(child)
                    created.append(child)
                    line.append({"text": label, "action": "page", "target": child["id"]})
                p["buttons"].append(line)
            # «Orqaga» tugmasi oxirida tursin
            back = [row for row in p["buttons"] if all(b.get("action") in ("back", "home") for b in row)]
            if back and back[0] is not p["buttons"][-1]:
                p["buttons"] = [row for row in p["buttons"] if row not in back] + back
            return None

        error = await save(runner, bot, add)
        if error:
            await say(f"⚠️ {esc(error)}")
            return True
        await set_state(runner, bot, chat_id, None)
        await say(f"✅ {len(created)} ta tugma qo'shildi. Har biri o'z sahifasiga ega — tugmani bosib ichiga kiring va kontentini o'zgartiring.")
        await reopen(runner, bot, chat_id, pid, user)
        return True

    if kind == "newpage":
        page = {**_new_child({"keyboard": "inline"}, text[:64])}
        error = await save(runner, bot, lambda m: m["pages"].append(page))
        await set_state(runner, bot, chat_id, None)
        if error:
            await say(f"⚠️ {esc(error)}")
            return True
        await say("✅ Sahifa yaratildi. Unga boshqa sahifadagi tugma orqali bog'lang (🎯 Vazifasi → 📑 Mavjud sahifa) yoki buyruq/kalit so'z bilan oching.")
        await reopen(runner, bot, chat_id, page["id"], user)
        return True

    if kind in ("ptitle", "placeholder", "pageops"):

        def change(menu: dict):
            p = page_by_id(menu, pid)
            if kind == "ptitle":
                p["title"] = text[:64]
            elif kind == "placeholder":
                p["placeholder"] = "" if text == "-" else text[:64]
            else:
                if text == "-":
                    p["ops"] = []
                    return None
                ops = [parse_op(ln) for ln in text.splitlines() if ln.strip()]
                if not ops or any(o is None for o in ops):
                    return "Amal tushunarsiz. Masalan: tashrif +1"
                p["ops"] = ops[:5]
            return None

        error = await save(runner, bot, change)
        if error:
            await say(f"⚠️ {esc(error)}")
            return True
        await set_state(runner, bot, chat_id, None)
        text_rows = page_settings(bot, page_by_id(bot.menu, pid))
        await send(runner, bot, chat_id, "✅ Saqlandi\n\n" + text_rows[0], text_rows[1])
        return True

    # Tugmaga oid kiritishlar
    r, c = state.get("r"), state.get("c")
    b = _btn(bot.menu, pid, r, c) if pid is not None and r is not None else None
    if b is None:
        await set_state(runner, bot, chat_id, None)
        await say("⚠️ Tugma topilmadi")
        return True

    values: dict | None = None
    if kind == "rename":
        values = {"text": text[:64]}
    elif kind == "url":
        url = text if text.startswith(("http://", "https://", "tg://")) else f"https://{text.removeprefix('//')}"
        values = {"action": "url", "url": url}
    elif kind == "alert":
        values = {"action": "alert", "alert": text[:200]}
    elif kind == "notify":
        values = {"action": "notify", "alert": "" if text == "-" else text[:200], "target": None}
    elif kind == "share":
        values = {"action": "share", "share_text": "" if text == "-" else text[:300]}
    elif kind == "setvar":
        op = parse_op(text)
        if op is None:
            await say("⚠️ Tushunarsiz. Masalan: <code>ball +1</code> yoki <code>vip = 1</code>")
            return True
        values = {"action": "set", **op, "target": None}
    elif kind == "cond":
        if text == "-":
            values = {"cond": None}
        else:
            cond = parse_cond(text)
            if cond is None:
                await say("⚠️ Shart tushunarsiz. Masalan: <code>ball >= 10</code> yoki <code>phone bor</code>")
                return True
            values = {"cond": cond}
    if values is None:
        return False

    def apply(menu: dict):
        x = _btn(menu, pid, r, c)
        if "action" in values:
            _assign(menu, pid, r, c, values)
        else:
            x.update(values)

    error = await save(runner, bot, apply)
    if error:
        await say(f"⚠️ {esc(error)}")
        return True
    await set_state(runner, bot, chat_id, None)
    text_rows = button_panel(bot, pid, r, c)
    if text_rows:
        await send(runner, bot, chat_id, "✅ Saqlandi\n\n" + text_rows[0], text_rows[1])
    if kind == "rename":
        await reopen(runner, bot, chat_id, pid, user)
    return True
