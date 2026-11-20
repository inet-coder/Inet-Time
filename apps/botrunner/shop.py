"""🛒 Do'kon moduli: katalog → mahsulot kartasi → savatcha → rasmiylashtirish → buyurtma → holatlar.

Mahsulotlar bot hujjatida (menu["shop"]["items"]) — shuning uchun AI taklifi, 🧪 sinov va ↩️ qaytarish ular bilan ham
ishlaydi. Savatcha — redis'da (ub:{bot}:cart:{chat}), buyurtmalar — bazada (bot_orders, har bot uchun #1, #2...).

Sahifa moduli (page.module):
    catalog — shu bo'lim mahsulotlari (list: bitta xabarda ro'yxat; cards: har mahsulot alohida xabar)
    cart    — savatcha
    orders  — «Buyurtmalarim»
Callbacklar: sl (ro'yxat sahifasi), si (karta), sa (miqdor), sk (savat), sz (tozalash), sx (rasmiylashtirish),
sm (buyurtmalarim), so (admin: holat), sh (admin: do'kon boshqaruvi)."""

import datetime
import html
import re
from typing import TYPE_CHECKING

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError

from core.botapi import BotApiError
from core.botbuilder import catalog_pages, fill, money, new_page_id, page_by_id, shop_item
from core.db.base import async_session
from core.db.models import BotOrder

if TYPE_CHECKING:
    from main import RunningBot, Runner

CART_TTL = 30 * 24 * 3600
CHECKOUT_ID = "__checkout"
STATUS = {
    "new": "🆕 Yangi",
    "accepted": "✅ Qabul qilindi",
    "delivering": "🚚 Yo'lda",
    "done": "✔️ Yetkazildi",
    "cancelled": "❌ Bekor qilindi",
}


def esc(text) -> str:
    return html.escape(str(text or ""), quote=False)


def _ck(bot: "RunningBot", chat_id: int) -> str:
    return f"ub:{bot.bot_id}:cart:{chat_id}"


def cur(bot: "RunningBot") -> str:
    return (bot.menu.get("shop") or {}).get("currency") or "so'm"


# ============================================================
# Savatcha
# ============================================================


async def cart(runner: "Runner", bot: "RunningBot", chat_id: int) -> dict[str, int]:
    raw = await runner.redis.hgetall(_ck(bot, chat_id))
    out: dict[str, int] = {}
    for k, v in raw.items():
        key = k.decode() if isinstance(k, bytes) else k
        item = shop_item(bot.menu, key)
        qty = int(v)
        if item and item.get("active", True) and qty > 0:
            out[key] = qty
    return out


async def change(runner: "Runner", bot: "RunningBot", chat_id: int, item_id: str, delta: int) -> int:
    key = _ck(bot, chat_id)
    qty = await runner.redis.hincrby(key, item_id, delta)
    if qty <= 0:
        await runner.redis.hdel(key, item_id)
        qty = 0
    elif qty > 99:
        await runner.redis.hset(key, item_id, 99)
        qty = 99
    await runner.redis.expire(key, CART_TTL)
    return qty


def totals(bot: "RunningBot", items: dict[str, int]) -> tuple[int, int, int]:
    """(mahsulotlar summasi, yetkazish, jami)."""
    shop = bot.menu.get("shop") or {}
    subtotal = sum(shop_item(bot.menu, i)["price"] * q for i, q in items.items())
    fee = int(shop.get("delivery_fee") or 0)
    free_from = int(shop.get("free_from") or 0)
    if not subtotal or (free_from and subtotal >= free_from):
        fee = 0
    return subtotal, fee, subtotal + fee


async def cart_values(runner: "Runner", bot: "RunningBot", chat_id: int) -> dict[str, str]:
    if not (bot.menu.get("shop") or {}).get("items"):
        return {"cart_count": "0", "cart_total": "0"}
    items = await cart(runner, bot, chat_id)
    _, _, total = totals(bot, items)
    return {"cart_count": str(sum(items.values())), "cart_total": money(total, cur(bot))}


def _cart_button(bot: "RunningBot", items: dict[str, int]) -> dict:
    n = sum(items.values())
    if not n:
        return {"text": "🛒 Savat bo'sh", "callback_data": "sk"}
    return {"text": f"🛒 Savat ({n}) · {money(totals(bot, items)[2], cur(bot))}", "callback_data": "sk"}


# ============================================================
# Ko'rinishlar
# ============================================================


def _price(bot: "RunningBot", item: dict) -> str:
    p = money(item["price"], cur(bot))
    if item.get("old_price") and item["old_price"] > item["price"]:
        p = f"<s>{money(item['old_price'], cur(bot))}</s> <b>{p}</b>"
    else:
        p = f"<b>{p}</b>"
    return p


def card_text(bot: "RunningBot", item: dict) -> str:
    badge = f" · {esc(item['badge'])}" if item.get("badge") else ""
    body = f"\n\n{item['text']}" if item.get("text") else ""
    return f"<b>{esc(item['title'])}</b>{badge}{body}\n\n💰 {_price(bot, item)}"


def qty_row(item: dict, qty: int, view: str) -> list[dict]:
    if qty:
        return [
            {"text": "➖", "callback_data": f"sa:{item['id']}:-:{view}"},
            {"text": f"🛒 {qty} ta", "callback_data": "sk"},
            {"text": "➕", "callback_data": f"sa:{item['id']}:+:{view}"},
        ]
    return [{"text": "➕ Savatga qo'shish", "callback_data": f"sa:{item['id']}:+:{view}"}]


def _items_of(bot: "RunningBot", page_id: str) -> list[dict]:
    return [i for i in (bot.menu.get("shop") or {}).get("items") or [] if i["category"] == page_id and i.get("active", True)]


def _photo(item: dict) -> str | None:
    return item.get("file_id")


async def _edit_or_send(runner, bot, chat_id, text: str, rows: list, message: dict | None) -> None:
    data = {"chat_id": chat_id, "text": text[:4096], "parse_mode": "HTML", "disable_web_page_preview": True, "reply_markup": {"inline_keyboard": rows}}
    if message is not None and "text" in message:
        try:
            await runner.api(bot, "editMessageText", {**data, "message_id": message["message_id"]})
            return
        except BotApiError as exc:
            if "not modified" in exc.description:
                return
    await runner.api(bot, "sendMessage", data)


async def render_catalog(runner, bot, chat_id: int, page: dict, vals: dict, *, message: dict | None = None, n: int = 0, header: str | None = None) -> None:
    module = page.get("module") or {}
    items = _items_of(bot, page["id"])
    per = int(module.get("per_page") or 8)
    pages = max(1, (len(items) + per - 1) // per)
    n = max(0, min(n, pages - 1))
    chunk = items[n * per : (n + 1) * per]
    in_cart = await cart(runner, bot, chat_id)
    if header is None:
        first = next((m for m in page.get("messages") or [] if m.get("type") == "text"), None)
        header = fill(first["text"], vals, escape=True) if first else f"<b>{esc(page['title'])}</b>"
    nav = []
    if pages > 1:
        nav = [
            {"text": "◀️", "callback_data": f"sl:{page['id']}:{(n - 1) % pages}"},
            {"text": f"{n + 1}/{pages}", "callback_data": f"sl:{page['id']}:{n}"},
            {"text": "▶️", "callback_data": f"sl:{page['id']}:{(n + 1) % pages}"},
        ]
    tail = [[_cart_button(bot, in_cart)]]
    if page.get("keyboard") != "reply":
        tail += [[b for b in row] for row in runner.inline_rows(bot, page, vals, runner.is_admin(bot, chat_id), page.get("buttons") or [], f"x:{page['id']}")]
    if not items:
        await _edit_or_send(runner, bot, chat_id, header + "\n\n<i>Hozircha mahsulot yo'q — tez orada qo'shiladi.</i>", tail, message)
        return
    if module.get("layout") == "cards":
        for item in chunk:
            rows = [qty_row(item, in_cart.get(item["id"], 0), "c")]
            if _photo(item):
                await runner.api(bot, "sendPhoto", {"chat_id": chat_id, "photo": _photo(item), "caption": card_text(bot, item)[:1024], "parse_mode": "HTML", "reply_markup": {"inline_keyboard": rows}})
            else:
                await runner.api(bot, "sendMessage", {"chat_id": chat_id, "text": card_text(bot, item), "parse_mode": "HTML", "reply_markup": {"inline_keyboard": rows}})
        await runner.api(
            bot,
            "sendMessage",
            {"chat_id": chat_id, "text": header + (f"\n\n📄 {n + 1}/{pages}" if pages > 1 else ""), "parse_mode": "HTML", "reply_markup": {"inline_keyboard": ([nav] if nav else []) + tail}},
        )
        return
    rows = []
    for item in chunk:
        mark = f" ✅{in_cart[item['id']]}" if in_cart.get(item["id"]) else ""
        rows.append([{"text": f"{item['title']} · {money(item['price'], cur(bot))}{mark}"[:64], "callback_data": f"si:{item['id']}"}])
    if nav:
        rows.append(nav)
    await _edit_or_send(runner, bot, chat_id, header, rows + tail, message)


async def render_card(runner, bot, chat_id: int, item: dict, *, message: dict | None = None) -> None:
    in_cart = await cart(runner, bot, chat_id)
    rows = [qty_row(item, in_cart.get(item["id"], 0), "c"), [_cart_button(bot, in_cart)], [{"text": "⬅️ Ro'yxatga", "callback_data": f"sl:{item['category']}:0"}]]
    if _photo(item):
        await runner.api(
            bot,
            "sendPhoto",
            {"chat_id": chat_id, "photo": _photo(item), "caption": card_text(bot, item)[:1024], "parse_mode": "HTML", "reply_markup": {"inline_keyboard": rows}},
        )
        return
    await _edit_or_send(runner, bot, chat_id, card_text(bot, item), rows, message)


async def render_cart(runner, bot, chat_id: int, *, message: dict | None = None) -> None:
    items = await cart(runner, bot, chat_id)
    catalogs = catalog_pages(bot.menu)
    back = [[{"text": "🛍 Katalogga", "callback_data": f"sl:{catalogs[0]['id']}:0"}]] if catalogs else []
    if not items:
        await _edit_or_send(runner, bot, chat_id, "🛒 <b>Savatingiz bo'sh</b>\n\nKatalogdan mahsulot tanlang 👇", back, message)
        return
    subtotal, fee, total = totals(bot, items)
    lines = ["🛒 <b>Savatingiz</b>", ""]
    rows = []
    for i, (item_id, qty) in enumerate(items.items(), 1):
        item = shop_item(bot.menu, item_id)
        lines.append(f"{i}. {esc(item['title'])} × {qty} = {money(item['price'] * qty, cur(bot))}")
        rows.append(
            [
                {"text": "➖", "callback_data": f"sa:{item_id}:-:k"},
                {"text": f"{item['title'][:18]} ×{qty}", "callback_data": f"si:{item_id}"},
                {"text": "➕", "callback_data": f"sa:{item_id}:+:k"},
            ]
        )
    lines.append("")
    shop = bot.menu.get("shop") or {}
    if fee:
        lines.append(f"🚚 Yetkazib berish: {money(fee, cur(bot))}")
        if shop.get("free_from"):
            lines.append(f"<i>{money(shop['free_from'], cur(bot))} dan yetkazish bepul</i>")
    lines.append(f"💰 <b>Jami: {money(total, cur(bot))}</b>")
    if shop.get("min_order") and subtotal < shop["min_order"]:
        lines.append(f"\n⚠️ Minimal buyurtma: {money(shop['min_order'], cur(bot))}")
    rows.append([{"text": "🗑 Tozalash", "callback_data": "sz"}, {"text": "✅ Rasmiylashtirish", "callback_data": "sx"}])
    await _edit_or_send(runner, bot, chat_id, "\n".join(lines), rows + back, message)


async def render_orders(runner, bot, chat_id: int, *, message: dict | None = None) -> None:
    async with async_session() as db:
        orders = (
            await db.scalars(select(BotOrder).where(BotOrder.bot_id == bot.bot_id, BotOrder.tg_user_id == chat_id).order_by(BotOrder.id.desc()).limit(10))
        ).all()
    if not orders:
        await _edit_or_send(runner, bot, chat_id, "📦 <b>Buyurtmalaringiz</b>\n\nHali buyurtma bermagansiz.", [], message)
        return
    lines = ["📦 <b>Buyurtmalaringiz</b>", ""]
    for o in orders:
        lines.append(f"<b>#{o.number}</b> · {o.created_at:%d.%m %H:%M} · {money(o.total, cur(bot))}\n{STATUS.get(o.status, o.status)}")
    await _edit_or_send(runner, bot, chat_id, "\n\n".join(lines[:2]) + "\n".join(lines[2:]), [], message)


async def render_module(runner, bot, chat_id: int, page: dict, vals: dict, *, message: dict | None = None) -> bool:
    """deliver() dan chaqiriladi. True — sahifa modul orqali ko'rsatildi."""
    module = (page.get("module") or {}).get("type")
    if module == "catalog":
        await render_catalog(runner, bot, chat_id, page, vals, message=message)
    elif module == "cart":
        await render_cart(runner, bot, chat_id, message=message)
    elif module == "orders":
        await render_orders(runner, bot, chat_id, message=message)
    else:
        return False
    return True


# ============================================================
# Callbacklar (foydalanuvchi)
# ============================================================


async def on_callback(runner, bot, chat_id: int, data: str, message: dict, user: dict, query_id: str) -> None:
    parts = data.split(":")
    cmd = parts[0]
    if cmd == "sl":
        page = page_by_id(bot.menu, parts[1])
        await runner.answer(bot, query_id)
        if page:
            vals = await runner.values(bot, user)
            await render_catalog(runner, bot, chat_id, page, vals, message=message, n=int(parts[2]) if len(parts) > 2 else 0)
    elif cmd == "si":
        item = shop_item(bot.menu, parts[1])
        await runner.answer(bot, query_id)
        if item:
            await render_card(runner, bot, chat_id, item, message=message)
    elif cmd == "sa":
        item = shop_item(bot.menu, parts[1])
        if item is None or not item.get("active", True):
            await runner.answer(bot, query_id, "Bu mahsulot hozir mavjud emas", alert=True)
            return
        qty = await change(runner, bot, chat_id, item["id"], 1 if parts[2] == "+" else -1)
        await runner.answer(bot, query_id, f"🛒 {item['title']}: {qty} ta" if qty else "Savatdan olib tashlandi")
        if parts[3] == "k":
            await render_cart(runner, bot, chat_id, message=message)
        else:
            in_cart = await cart(runner, bot, chat_id)
            rows = [qty_row(item, qty, "c"), [_cart_button(bot, in_cart)]]
            if (page_by_id(bot.menu, item["category"]) or {}).get("module", {}).get("layout") != "cards":
                rows.append([{"text": "⬅️ Ro'yxatga", "callback_data": f"sl:{item['category']}:0"}])
            try:
                await runner.api(bot, "editMessageReplyMarkup", {"chat_id": chat_id, "message_id": message["message_id"], "reply_markup": {"inline_keyboard": rows}})
            except BotApiError:
                pass
    elif cmd == "sk":
        await runner.answer(bot, query_id)
        await render_cart(runner, bot, chat_id, message=message)
    elif cmd == "sz":
        await runner.redis.delete(_ck(bot, chat_id))
        await runner.answer(bot, query_id, "🗑 Savat tozalandi")
        await render_cart(runner, bot, chat_id, message=message)
    elif cmd == "sx":
        await start_checkout(runner, bot, chat_id, user, query_id)
    elif cmd == "sm":
        await runner.answer(bot, query_id)
        await render_orders(runner, bot, chat_id, message=message)
    elif cmd == "so":
        await runner.answer(bot, query_id)
        if runner.is_admin(bot, chat_id):
            await set_status(runner, bot, int(parts[1]), parts[2], message)


# ============================================================
# Rasmiylashtirish va buyurtma
# ============================================================


def checkout_form(bot: "RunningBot") -> dict:
    shop = bot.menu.get("shop") or {}
    steps = [{"key": f["key"], "question": f["label"], "type": f.get("type", "text"), "options": f.get("options") or []} for f in shop.get("checkout") or []]
    return {"id": CHECKOUT_ID, "title": "🛒 Buyurtma", "steps": steps, "done_text": "", "target": None, "notify": False}


async def start_checkout(runner, bot, chat_id: int, user: dict, query_id: str | None = None) -> None:
    items = await cart(runner, bot, chat_id)
    if not items:
        await runner.answer(bot, query_id, "Savat bo'sh", alert=True)
        return
    subtotal, _, _ = totals(bot, items)
    min_order = int((bot.menu.get("shop") or {}).get("min_order") or 0)
    if min_order and subtotal < min_order:
        await runner.answer(bot, query_id, f"Minimal buyurtma: {money(min_order, cur(bot))}", alert=True)
        return
    await runner.answer(bot, query_id)
    await runner.start_form(bot, chat_id, CHECKOUT_ID, user)


async def _next_number(db, bot_id: int) -> int:
    return int(await db.scalar(select(func.coalesce(func.max(BotOrder.number), 0)).where(BotOrder.bot_id == bot_id)) or 0) + 1


def order_text(bot: "RunningBot", order: BotOrder, who: str, form: dict) -> str:
    lines = [f"🛒 <b>Buyurtma #{order.number}</b>", f"👤 {who}", ""]
    for i, it in enumerate(order.items, 1):
        lines.append(f"{i}. {esc(it['title'])} × {it['qty']} = {money(it['price'] * it['qty'], cur(bot))}")
    if order.delivery:
        lines.append(f"🚚 Yetkazib berish: {money(order.delivery, cur(bot))}")
    lines += [f"💰 <b>Jami: {money(order.total, cur(bot))}</b>", ""]
    for step in form["steps"]:
        value = str(order.data.get(step["key"], ""))
        if re.match(r"^-?\d+\.\d+,-?\d+\.\d+$", value):
            value = f'<a href="https://maps.google.com/?q={value}">📍 xaritada</a>'
        else:
            value = esc(value)
        lines.append(f"{esc(re.sub(r'^[^A-Za-zА-Яа-яЎўҚқҒғҲҳ]+', '', step['question']).rstrip('?')[:40])}: {value}")
    lines += ["", f"Holat: <b>{STATUS.get(order.status, order.status)}</b>"]
    return "\n".join(lines)


def status_rows(order_id: int) -> list:
    return [
        [{"text": "✅ Qabul qilish", "callback_data": f"so:{order_id}:accepted"}, {"text": "🚚 Yo'lda", "callback_data": f"so:{order_id}:delivering"}],
        [{"text": "✔️ Yetkazildi", "callback_data": f"so:{order_id}:done"}, {"text": "❌ Bekor", "callback_data": f"so:{order_id}:cancelled"}],
    ]


async def create_order(runner, bot, chat_id: int, user: dict, data: dict) -> None:
    items = await cart(runner, bot, chat_id)
    if not items:
        await runner.api(bot, "sendMessage", {"chat_id": chat_id, "text": "⚠️ Savatingiz bo'sh — buyurtma yaratilmadi.", "reply_markup": {"remove_keyboard": True}})
        return
    subtotal, fee, total = totals(bot, items)
    if getattr(bot, "sandbox", False):
        await runner.redis.delete(_ck(bot, chat_id))
        await runner.api(
            bot,
            "sendMessage",
            {"chat_id": chat_id, "text": f"🧪 Sinov rejimi: buyurtma ({money(total, cur(bot))}) to'g'ri yig'ildi, lekin saqlanmadi.", "reply_markup": {"remove_keyboard": True}},
        )
        return
    lines = [{"id": i, "title": shop_item(bot.menu, i)["title"], "price": shop_item(bot.menu, i)["price"], "qty": q} for i, q in items.items()]
    order = None
    for _ in range(4):
        async with async_session() as db:
            order = BotOrder(bot_id=bot.bot_id, number=await _next_number(db, bot.bot_id), tg_user_id=chat_id, items=lines, total=total, delivery=fee, data=data, status="new")
            db.add(order)
            try:
                await db.commit()
                await db.refresh(order)
                break
            except IntegrityError:
                await db.rollback()
                order = None
    if order is None:
        await runner.api(bot, "sendMessage", {"chat_id": chat_id, "text": "⚠️ Buyurtmani saqlab bo'lmadi, qayta urinib ko'ring."})
        return
    await runner.redis.delete(_ck(bot, chat_id))
    await runner.set_vars(bot, user["id"], {k: v for k, v in data.items() if k})
    vals = await runner.values(bot, user)
    vals.update({"order": str(order.number), "total": money(total, cur(bot))})
    done = (bot.menu.get("shop") or {}).get("done_text") or "✅ Buyurtma #{order} qabul qilindi"
    cur_page = await runner.current_page(bot, chat_id)
    markup = await runner.menu_markup(bot, chat_id, cur_page, vals) if cur_page else None
    await runner.api(
        bot,
        "sendMessage",
        {"chat_id": chat_id, "text": fill(done, vals, escape=True), "parse_mode": "HTML", "reply_markup": markup or {"remove_keyboard": True}},
    )
    who = esc(user.get("first_name") or "Mijoz") + (f" (@{esc(user['username'])})" if user.get("username") else "") + f" · <code>{chat_id}</code>"
    text = order_text(bot, order, who, checkout_form(bot))
    for admin_chat in runner.admin_chats(bot):
        try:
            sent = await runner.api(bot, "sendMessage", {"chat_id": admin_chat, "text": text, "parse_mode": "HTML", "disable_web_page_preview": True, "reply_markup": {"inline_keyboard": status_rows(order.id)}})
            # egasi shu xabarga «Reply» qilsa — javob mijozga boradi
            await runner.redis.set(f"ub:{bot.bot_id}:fb:{admin_chat}:{sent['message_id']}", chat_id, ex=CART_TTL)
        except BotApiError:
            pass


async def set_status(runner, bot, order_id: int, status: str, message: dict | None) -> None:
    if status not in STATUS:
        return
    async with async_session() as db:
        order = await db.get(BotOrder, order_id)
        if order is None or order.bot_id != bot.bot_id:
            return
        changed = order.status != status
        order.status = status
        order.updated_at = datetime.datetime.now(datetime.timezone.utc)
        await db.commit()
        await db.refresh(order)
    if message is not None:
        old = message.get("text") or ""
        head = old.rsplit("Holat:", 1)[0] if "Holat:" in old else ""
        try:
            await runner.api(
                bot,
                "editMessageText",
                {
                    "chat_id": message["chat"]["id"],
                    "message_id": message["message_id"],
                    "text": esc(head) + f"Holat: <b>{STATUS[status]}</b>" if head else f"🛒 Buyurtma #{order.number}\nHolat: <b>{STATUS[status]}</b>",
                    "parse_mode": "HTML",
                    "reply_markup": {"inline_keyboard": status_rows(order.id) if status not in ("done", "cancelled") else []},
                },
            )
        except BotApiError:
            pass
    if changed:
        try:
            await runner.api(bot, "sendMessage", {"chat_id": order.tg_user_id, "text": f"📦 Buyurtma <b>#{order.number}</b>: {STATUS[status]}", "parse_mode": "HTML"})
        except BotApiError:
            pass


# ============================================================
# Admin: do'konni chatda boshqarish (/admin → 🛒 Do'kon)
# ============================================================


async def _stats(bot) -> dict:
    today = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(days=1)
    async with async_session() as db:
        new = await db.scalar(select(func.count(BotOrder.id)).where(BotOrder.bot_id == bot.bot_id, BotOrder.status == "new"))
        day = await db.scalar(
            select(func.coalesce(func.sum(BotOrder.total), 0)).where(BotOrder.bot_id == bot.bot_id, BotOrder.created_at >= today, BotOrder.status != "cancelled")
        )
        count = await db.scalar(select(func.count(BotOrder.id)).where(BotOrder.bot_id == bot.bot_id))
    return {"new": new or 0, "day": int(day or 0), "count": count or 0}


async def admin_home(runner, bot, chat_id: int, message: dict | None = None) -> None:
    import editor

    shop = bot.menu.get("shop") or {}
    st = await _stats(bot)
    cats = catalog_pages(bot.menu)
    text = (
        f"🛒 <b>Do'kon</b> — {'✅ ishlayapti' if shop.get('enabled') else '❌ o\'chiq'}\n\n"
        f"📦 Mahsulotlar: {len(shop.get('items') or [])} · 🗂 Kategoriyalar: {len(cats)}\n"
        f"🆕 Yangi buyurtmalar: <b>{st['new']}</b> · jami: {st['count']}\n"
        f"💰 So'nggi 24 soat: {money(st['day'], cur(bot))}\n"
        f"🚚 Yetkazish: {money(int(shop.get('delivery_fee') or 0), cur(bot))}"
        + (f" (≥ {money(shop['free_from'], cur(bot))} bepul)" if shop.get("free_from") else "")
        + (f" · Minimal: {money(shop['min_order'], cur(bot))}" if shop.get("min_order") else "")
    )
    if not cats:
        text += "\n\nDo'konni ishga tushirish uchun kategoriyalarni yarating 👇"
        rows = [[{"text": "🚀 Do'konni yaratish", "callback_data": "sh:setup"}]]
    else:
        rows = [
            [{"text": "➕ Mahsulot qo'shish", "callback_data": "sh:add"}, {"text": "📋 Mahsulotlar", "callback_data": "sh:items:0"}],
            [{"text": f"📦 Buyurtmalar ({st['new']} yangi)", "callback_data": "sh:orders"}, {"text": "⚙️ Sozlamalar", "callback_data": "sh:cfg"}],
            [{"text": "🗂 Kategoriya qo'shish", "callback_data": "sh:setup"}],
        ]
    rows.append([{"text": "⬅️ Panel", "callback_data": "adm:st"}])
    await editor.send(runner, bot, chat_id, text, rows, message=message)


def _structure(menu: dict, names: list[str]) -> list[str]:
    """Kategoriyalar sahifalari, savatcha va «Buyurtmalarim» — bosh menyuga ulanadi. Yangi kategoriyalar id'lari."""
    style = menu.get("style", "reply")
    start = page_by_id(menu, menu["start"])
    inline_cats = style in ("inline", "hybrid") or start.get("keyboard") != "reply"
    created = []
    hub = next((p for p in menu["pages"] if p.get("id") == "shop_hub"), None)
    existing = catalog_pages(menu)
    if len(names) + len(existing) > 1 and hub is None:
        hub = {
            "id": "shop_hub",
            "title": "🛍 Katalog",
            "text": "Katalog",
            "messages": [{"type": "text", "text": "🛍 <b>Katalog</b>\n\nKategoriyani tanlang 👇", "buttons": []}],
            "keyboard": "inline" if inline_cats else "reply",
            "buttons": [],
            "nav": not inline_cats,
        }
        menu["pages"].append(hub)
        # mavjud yagona kategoriya tugmasi bosh menyudan hubga ko'chadi
        for p in existing:
            for row in start.get("buttons") or []:
                for b in row:
                    if b.get("target") == p["id"]:
                        b.update({"text": "🛍 Katalog", "target": "shop_hub"})
            hub["buttons"].append([{"text": p["title"], "action": "page", "target": p["id"]}])
        if not any(b.get("target") == "shop_hub" for row in start.get("buttons") or [] for b in row):
            start.setdefault("buttons", []).insert(0, [{"text": "🛍 Katalog", "action": "page", "target": "shop_hub"}])
    for name in names:
        pid = new_page_id()
        page = {
            "id": pid,
            "title": name[:64],
            "text": name[:64],
            "messages": [{"type": "text", "text": f"<b>{esc(name)}</b>\n\nTanlang 👇", "buttons": []}],
            "keyboard": "inline",
            "buttons": [[{"text": "⬅️ Orqaga", "action": "back"}]] if hub else [],
            "module": {"type": "catalog", "layout": "list", "per_page": 8},
        }
        menu["pages"].append(page)
        created.append(pid)
        if hub:
            back = [row for row in hub["buttons"] if all(b.get("action") == "back" for b in row)]
            hub["buttons"] = [row for row in hub["buttons"] if row not in back] + [[{"text": name[:64], "action": "page", "target": pid}]] + back
        else:
            start.setdefault("buttons", []).insert(0, [{"text": "🛍 Katalog", "action": "page", "target": pid}])
    if hub and hub.get("keyboard") == "inline" and not any(b.get("action") == "back" for row in hub["buttons"] for b in row):
        hub["buttons"].append([{"text": "⬅️ Orqaga", "action": "back"}])
    for mod, title in (("cart", "🛒 Savat"), ("orders", "📦 Buyurtmalarim")):
        if not any((p.get("module") or {}).get("type") == mod for p in menu["pages"]):
            pid = "shop_" + mod
            menu["pages"].append({"id": pid, "title": title, "text": title, "messages": [{"type": "text", "text": f"<b>{title}</b>", "buttons": []}], "keyboard": "inline", "buttons": [], "module": {"type": mod}})
            start.setdefault("buttons", []).append([{"text": title, "action": "page", "target": pid}])
    menu.setdefault("shop", {})["enabled"] = True
    return created


_PRICE = re.compile(r"(\d[\d\s.,]*)\s*(ming|k|mln|млн|тыс)?", re.I)


def parse_item(text: str) -> tuple[str, int, str] | None:
    """«Latte\\n28 000\\nTavsif...» yoki «Latte — 28000 so'm» → (nom, narx, tavsif)."""
    lines = [ln.strip() for ln in (text or "").strip().splitlines() if ln.strip()]
    if not lines:
        return None
    title, rest = lines[0], lines[1:]
    m = re.match(r"^(.*?)\s*[—\-–:|]\s*(\d[\d\s.,]*)\s*(ming|k|mln)?\b.*$", title, re.I)
    if m and not rest:
        title, price_raw, mult = m.group(1), m.group(2), m.group(3)
    elif rest:
        pm = _PRICE.search(rest[0])
        if not pm:
            return None
        price_raw, mult = pm.group(1), pm.group(2)
        rest = rest[1:]
    else:
        return None
    digits = re.sub(r"[^\d]", "", price_raw.split(",")[0] if "," in price_raw and len(price_raw.split(",")[-1]) <= 2 else price_raw)
    if not digits:
        return None
    price = int(digits)
    if mult:
        price *= 1_000_000 if mult.lower() in ("mln", "млн") else 1000
    return title.strip()[:64], price, "\n".join(rest)[:900]


async def admin_callback(runner, bot, chat_id: int, data: str, message: dict, user: dict) -> None:
    import admin
    import editor

    parts = data.split(":")
    cmd = parts[1] if len(parts) > 1 else ""

    async def save(fn) -> bool:
        error = await editor.save(runner, bot, fn)
        if error:
            await runner.api(bot, "sendMessage", {"chat_id": chat_id, "text": f"⚠️ {error}"})
            return False
        return True

    if cmd == "home":
        await admin.set_state(runner, bot, chat_id, None)
        await admin_home(runner, bot, chat_id, message)
    elif cmd == "setup":
        await admin.ask(
            runner,
            bot,
            chat_id,
            {"k": "shop_cats"},
            "🗂 Kategoriyalarni yuboring — bir nechta bo'lsa <code>|</code> bilan:\n<code>☕ Issiq ichimliklar | 🧊 Sovuq ichimliklar | 🍰 Desertlar</code>\n\n"
            "Bitta kategoriya bo'lsa — bitta nom yozing (masalan <code>🛍 Mahsulotlar</code>). Savat va «Buyurtmalarim» avtomatik qo'shiladi.",
        )
    elif cmd == "add":
        cats = catalog_pages(bot.menu)
        if len(cats) == 1:
            await _ask_item(runner, bot, chat_id, cats[0]["id"])
            return
        rows = [[{"text": c["title"][:64], "callback_data": f"sh:ac:{c['id']}"}] for c in cats]
        rows.append([{"text": "⬅️ Do'kon", "callback_data": "sh:home"}])
        await editor.send(runner, bot, chat_id, "➕ Qaysi kategoriyaga qo'shamiz?", rows, message=message)
    elif cmd == "ac":
        await _ask_item(runner, bot, chat_id, parts[2])
    elif cmd == "items":
        await _items_view(runner, bot, chat_id, int(parts[2]) if len(parts) > 2 else 0, message)
    elif cmd == "it":
        await _item_view(runner, bot, chat_id, parts[2], message)
    elif cmd in ("in", "ip", "id", "ir", "io"):
        item = shop_item(bot.menu, parts[2])
        if not item:
            return
        prompts = {
            "in": "✏️ Yangi nomini yuboring.",
            "ip": "💰 Yangi narxini yuboring (masalan <code>28000</code> yoki <code>28 ming</code>).",
            "id": "📝 Yangi tavsifini yuboring (formatlash saqlanadi).",
            "ir": "🖼 Mahsulot rasmini yuboring.",
            "io": "🏷 Eski narxni yuboring (chegirma ko'rsatish uchun) yoki <code>0</code> — olib tashlash.",
        }
        await admin.ask(runner, bot, chat_id, {"k": "shop_edit", "f": cmd, "id": item["id"]}, prompts[cmd])
    elif cmd == "ia":
        item_id = parts[2]

        def flip(m):
            it = next(i for i in m["shop"]["items"] if i["id"] == item_id)
            it["active"] = not it.get("active", True)

        if await save(flip):
            await _item_view(runner, bot, chat_id, item_id, message)
    elif cmd == "ix":
        item_id = parts[2]
        if await save(lambda m: m["shop"].update(items=[i for i in m["shop"]["items"] if i["id"] != item_id])):
            await _items_view(runner, bot, chat_id, 0, message)
    elif cmd == "orders":
        await _orders_view(runner, bot, chat_id, message)
    elif cmd == "o":
        async with async_session() as db:
            order = await db.get(BotOrder, int(parts[2]))
        if order and order.bot_id == bot.bot_id:
            text = order_text(bot, order, f"<code>{order.tg_user_id}</code>", checkout_form(bot))
            rows = (status_rows(order.id) if order.status not in ("done", "cancelled") else []) + [[{"text": "⬅️ Buyurtmalar", "callback_data": "sh:orders"}]]
            await editor.send(runner, bot, chat_id, text, rows, message=message)
    elif cmd == "cfg":
        await _cfg_view(runner, bot, chat_id, message)
    elif cmd in ("cur", "fee", "free", "min", "done"):
        prompts = {
            "cur": "💱 Valyutani yuboring (masalan <code>so'm</code>, <code>$</code>).",
            "fee": "🚚 Yetkazib berish narxini yuboring (<code>0</code> — bepul).",
            "free": "🎁 Qaysi summadan yetkazish bepul? (<code>0</code> — o'chirish).",
            "min": "📉 Minimal buyurtma summasi (<code>0</code> — cheklovsiz).",
            "done": "✍️ Buyurtmadan keyingi xabar. <code>{order}</code> — raqami, <code>{total}</code> — summasi.",
        }
        await admin.ask(runner, bot, chat_id, {"k": "shop_cfg", "f": cmd}, prompts[cmd])
    elif cmd == "tog":
        if await save(lambda m: m["shop"].update(enabled=not m["shop"].get("enabled"))):
            await admin_home(runner, bot, chat_id, message)
    elif cmd == "addr":

        def toggle_addr(m):
            fields = m["shop"]["checkout"]
            if any(f["key"] == "manzil" for f in fields):
                m["shop"]["checkout"] = [f for f in fields if f["key"] != "manzil"] or fields
            else:
                fields.append({"key": "manzil", "label": "📍 Yetkazib berish manzili? (yoki joylashuvni yuboring)", "type": "text", "options": []})

        if await save(toggle_addr):
            await _cfg_view(runner, bot, chat_id, message)


async def _ask_item(runner, bot, chat_id: int, cat_id: str) -> None:
    import admin

    page = page_by_id(bot.menu, cat_id)
    await admin.ask(
        runner,
        bot,
        chat_id,
        {"k": "shop_item", "cat": cat_id},
        f"➕ <b>«{esc(page['title'] if page else '')}»</b> ga mahsulot yuboring — rasm bilan (izohda) yoki matn:\n\n"
        "<code>Latte\n28000\nYumshoq ko'pikli kofe, 350 ml</code>\n\n"
        "1-qator — nomi, 2-qator — narxi, qolgani — tavsif. Ketma-ket bir nechta yuborishingiz mumkin. Tugatish: /cancel",
    )


async def _items_view(runner, bot, chat_id: int, n: int, message: dict | None) -> None:
    import editor

    items = (bot.menu.get("shop") or {}).get("items") or []
    per = 12
    chunk = items[n * per : (n + 1) * per]
    rows = [[{"text": f"{'' if i.get('active', True) else '🚫 '}{i['title']} · {money(i['price'], cur(bot))}"[:64], "callback_data": f"sh:it:{i['id']}"}] for i in chunk]
    nav = []
    if n > 0:
        nav.append({"text": "◀️", "callback_data": f"sh:items:{n - 1}"})
    if (n + 1) * per < len(items):
        nav.append({"text": "▶️", "callback_data": f"sh:items:{n + 1}"})
    if nav:
        rows.append(nav)
    rows.append([{"text": "➕ Mahsulot qo'shish", "callback_data": "sh:add"}, {"text": "⬅️ Do'kon", "callback_data": "sh:home"}])
    await editor.send(runner, bot, chat_id, f"📋 <b>Mahsulotlar</b> · {len(items)} ta\nTahrirlash uchun bosing.", rows, message=message)


async def _item_view(runner, bot, chat_id: int, item_id: str, message: dict | None) -> None:
    import editor

    item = shop_item(bot.menu, item_id)
    if not item:
        return
    cat = page_by_id(bot.menu, item["category"])
    text = card_text(bot, item) + f"\n\n🗂 {esc(cat['title'] if cat else '')} · {'✅ sotuvda' if item.get('active', True) else '🚫 yashirilgan'}" + ("\n🖼 rasm bor" if item.get("file_id") else "")
    rows = [
        [{"text": "✏️ Nom", "callback_data": f"sh:in:{item_id}"}, {"text": "💰 Narx", "callback_data": f"sh:ip:{item_id}"}, {"text": "🏷 Eski narx", "callback_data": f"sh:io:{item_id}"}],
        [{"text": "📝 Tavsif", "callback_data": f"sh:id:{item_id}"}, {"text": "🖼 Rasm", "callback_data": f"sh:ir:{item_id}"}],
        [{"text": "🚫 Yashirish" if item.get("active", True) else "✅ Sotuvga qaytarish", "callback_data": f"sh:ia:{item_id}"}, {"text": "🗑 O'chirish", "callback_data": f"sh:ix:{item_id}"}],
        [{"text": "⬅️ Mahsulotlar", "callback_data": "sh:items:0"}],
    ]
    await editor.send(runner, bot, chat_id, text, rows, message=message)


async def _orders_view(runner, bot, chat_id: int, message: dict | None) -> None:
    import editor

    async with async_session() as db:
        orders = (await db.scalars(select(BotOrder).where(BotOrder.bot_id == bot.bot_id).order_by(BotOrder.id.desc()).limit(15))).all()
    if not orders:
        await editor.send(runner, bot, chat_id, "📦 Hali buyurtma yo'q.", [[{"text": "⬅️ Do'kon", "callback_data": "sh:home"}]], message=message)
        return
    rows = [[{"text": f"#{o.number} · {money(o.total, cur(bot))} · {STATUS.get(o.status, o.status)}"[:64], "callback_data": f"sh:o:{o.id}"}] for o in orders]
    rows.append([{"text": "⬅️ Do'kon", "callback_data": "sh:home"}])
    await editor.send(runner, bot, chat_id, "📦 <b>So'nggi buyurtmalar</b>", rows, message=message)


async def _cfg_view(runner, bot, chat_id: int, message: dict | None) -> None:
    import editor

    shop = bot.menu.get("shop") or {}
    has_addr = any(f["key"] == "manzil" for f in shop.get("checkout") or [])
    text = (
        "⚙️ <b>Do'kon sozlamalari</b>\n\n"
        f"💱 Valyuta: {esc(cur(bot))}\n🚚 Yetkazish: {money(int(shop.get('delivery_fee') or 0), cur(bot))}\n"
        f"🎁 Bepul yetkazish: {money(int(shop.get('free_from') or 0), cur(bot)) if shop.get('free_from') else 'yo‘q'}\n"
        f"📉 Minimal buyurtma: {money(int(shop.get('min_order') or 0), cur(bot)) if shop.get('min_order') else 'yo‘q'}\n"
        f"📍 Manzil so'raladi: {'✅' if has_addr else '❌ (olib ketish)'}"
    )
    rows = [
        [{"text": "💱 Valyuta", "callback_data": "sh:cur"}, {"text": "🚚 Yetkazish narxi", "callback_data": "sh:fee"}],
        [{"text": "🎁 Bepul yetkazish", "callback_data": "sh:free"}, {"text": "📉 Minimal summa", "callback_data": "sh:min"}],
        [{"text": f"📍 Manzil so'rash {'✅' if has_addr else '❌'}", "callback_data": "sh:addr"}, {"text": "✍️ Tasdiq xabari", "callback_data": "sh:done"}],
        [{"text": "✅ Do'konni o'chirish" if shop.get("enabled") else "▶️ Do'konni yoqish", "callback_data": "sh:tog"}],
        [{"text": "⬅️ Do'kon", "callback_data": "sh:home"}],
    ]
    await editor.send(runner, bot, chat_id, text, rows, message=message)


def _amount(text: str) -> int | None:
    m = re.match(r"^\s*(\d[\d\s.,]*)\s*(ming|k|mln)?\s*\D*$", text or "", re.I)
    if not m:
        return None
    digits = re.sub(r"[^\d]", "", m.group(1))
    if not digits:
        return None
    value = int(digits)
    if m.group(2):
        value *= 1_000_000 if m.group(2).lower() == "mln" else 1000
    return value


async def admin_input(runner, bot, chat_id: int, message: dict, state: dict) -> bool:
    """Admin paneli kiritishlari (shop_*). True — qayta ishlandi."""
    import admin
    import editor
    from core.botbuilder import entities_to_html

    kind = state.get("k", "")
    if not kind.startswith("shop_"):
        return False
    text = (message.get("text") or message.get("caption") or "").strip()

    async def say(t: str, rows: list | None = None) -> None:
        await editor.send(runner, bot, chat_id, t, rows)

    async def save(fn) -> bool:
        error = await editor.save(runner, bot, fn)
        if error:
            await say(f"⚠️ {esc(error)}")
            return False
        return True

    if kind == "shop_cats":
        names = [n.strip()[:64] for n in text.split("|") if n.strip()][:20]
        if not names:
            await say("⚠️ Kategoriya nomini yuboring")
            return True
        created: list = []
        if not await save(lambda m: created.extend(_structure(m, names))):
            return True
        await admin.set_state(runner, bot, chat_id, None)
        await say(f"✅ {len(created)} ta kategoriya yaratildi, «🛒 Savat» va «📦 Buyurtmalarim» bosh menyuga qo'shildi.\nEndi mahsulot qo'shing 👇", [[{"text": "➕ Mahsulot qo'shish", "callback_data": "sh:add"}]])
        return True
    if kind == "shop_item":
        caption = message.get("caption") if message.get("photo") else message.get("text")
        parsed = parse_item(caption or "")
        if parsed is None:
            await say("⚠️ Tushunmadim. 1-qator — nomi, 2-qator — narxi (masalan <code>28000</code>), keyin tavsif.")
            return True
        title, price, desc = parsed
        if desc:
            ents = message.get("caption_entities") if message.get("photo") else message.get("entities")
            full = message.get("caption") if message.get("photo") else message.get("text")
            html_full = entities_to_html(full or "", ents)
            desc_html = "\n".join(html_full.splitlines()[2:]).strip() or esc(desc)
        else:
            desc_html = ""
        item = {
            "id": new_page_id(),
            "category": state["cat"],
            "title": title,
            "text": desc_html[:900],
            "price": price,
            "file_id": message["photo"][-1]["file_id"] if message.get("photo") else None,
            "active": True,
        }
        if not await save(lambda m: m["shop"]["items"].append(item)):
            return True
        await runner.api(
            bot,
            "sendMessage",
            {
                "chat_id": chat_id,
                "text": f"✅ «{title}» qo'shildi — {money(price, cur(bot))}. Yana yuboring yoki tugating.",
                "reply_to_message_id": message["message_id"],
                "reply_markup": {"inline_keyboard": [[{"text": "✅ Tayyor", "callback_data": "sh:home"}, {"text": "✏️ Tahrirlash", "callback_data": f"sh:it:{item['id']}"}]]},
            },
        )
        return True
    if kind == "shop_edit":
        f, item_id = state["f"], state["id"]
        values: dict = {}
        if f == "in":
            values["title"] = text[:64]
        elif f in ("ip", "io"):
            amount = _amount(text)
            if amount is None:
                await say("⚠️ Son yuboring, masalan <code>28000</code>")
                return True
            values["price" if f == "ip" else "old_price"] = amount if (f == "ip" or amount) else None
        elif f == "id":
            values["text"] = entities_to_html(message.get("text") or "", message.get("entities"))[:900]
        elif f == "ir":
            if not message.get("photo"):
                await say("⚠️ Rasm yuboring")
                return True
            values["file_id"] = message["photo"][-1]["file_id"]
        if not values.get("title", "x") or not await save(lambda m: next(i for i in m["shop"]["items"] if i["id"] == item_id).update(values)):
            return True
        await admin.set_state(runner, bot, chat_id, None)
        await _item_view(runner, bot, chat_id, item_id, None)
        return True
    if kind == "shop_cfg":
        f = state["f"]
        if f == "cur":
            if not text or len(text) > 12:
                await say("⚠️ 12 belgigacha")
                return True
            ok = await save(lambda m: m["shop"].update(currency=text))
        elif f == "done":
            ok = await save(lambda m: m["shop"].update(done_text=entities_to_html(message.get("text") or "", message.get("entities"))[:1000]))
        else:
            amount = _amount(text)
            if amount is None:
                await say("⚠️ Son yuboring")
                return True
            key = {"fee": "delivery_fee", "free": "free_from", "min": "min_order"}[f]
            ok = await save(lambda m: m["shop"].update({key: amount}))
        if ok:
            await admin.set_state(runner, bot, chat_id, None)
            await _cfg_view(runner, bot, chat_id, None)
        return True
    return False
