"""Bot konstruktori: asosiy menyu, bot yaratish (shablon → token), «Botlarim».

Asosiy botning vazifasi — botni yaratish va ishlatib turish. Botni sozlash (menyu, tugmalar, xabar tarqatish)
foydalanuvchi yaratgan botning o'zida: /admin."""

import re
from html import escape

from aiogram import Bot, F, Router
from aiogram.filters import Command, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

import keyboards as kb
from api_client import ApiError, api_client
from common import db_user_id, is_admin, safe_answer
from states import CreateBot

router = Router(name="bots")

# BotFather tokeni: 123456789:AA... — forward qilingan BotFather xabari ichidan ham topiladi.
TOKEN_RE = re.compile(r"\b(\d{6,12}:[A-Za-z0-9_-]{30,})\b")

STATUS = {"active": "🟢 Ishlayapti", "paused": "⏸ To'xtatilgan", "error": "⚠️ Xatolik"}

MAIN_TEXT = (
    "🤖 <b>Inet-Time</b> — Telegram botlar konstruktori\n\n"
    "Kod yozmasdan o'z botingizni yarating: menyular va tugmalar, buyurtma va murojaatlarni qabul qilish, "
    "obunachilarga xabar tarqatish.\n\n"
    "{stats}\n\n"
    "Kerakli bo'limni tanlang:"
)

HOW_TO = (
    "<b>Bot tokenini yuboring</b> (2/2)\n\n"
    "1. @BotFather botini oching\n"
    "2. /newbot buyrug'ini yuboring\n"
    "3. Bot nomi va username kiriting (username <code>bot</code> bilan tugashi kerak)\n"
    "4. BotFather bergan tokenni shu yerga yuboring — yoki uning xabarini shunchaki forward qiling\n\n"
    "Tanlangan shablon: {template}"
)


async def _templates() -> list[dict]:
    return await api_client.bot_templates()


async def main_text(user_id: int) -> tuple[str, int]:
    data = await api_client.list_bots(user_id)
    count = len(data["bots"])
    subscribers = sum(b["subscribers"] for b in data["bots"])
    stats = f"📊 Botlaringiz: {count}/{data['limit']} · obunachilar: {subscribers}\n💎 Tarif: {data['plan_name']}"
    return MAIN_TEXT.format(stats=stats), count


async def send_main(bot: Bot, chat_id: int, tg_user_id: int, user_id: int) -> None:
    text, count = await main_text(user_id)
    await bot.send_message(chat_id, text, reply_markup=kb.main_menu(count, is_admin(tg_user_id)), parse_mode="HTML")


async def edit_main(callback: CallbackQuery) -> None:
    user_id = await db_user_id(callback.from_user)
    text, count = await main_text(user_id)
    try:
        await callback.message.edit_text(text, reply_markup=kb.main_menu(count, is_admin(callback.from_user.id)), parse_mode="HTML")
    except Exception:  # noqa: BLE001 — eski xabar tahrirlanmasa yangisi
        await callback.message.answer(text, reply_markup=kb.main_menu(count, is_admin(callback.from_user.id)), parse_mode="HTML")


@router.callback_query(F.data == "main")
async def show_main(callback: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    await edit_main(callback)
    await safe_answer(callback)


# --- Shablonlar va yaratish ---


def _templates_text(templates: list[dict], title: str) -> str:
    lines = [title, ""]
    for t in templates:
        lines.append(f"{t['icon']} <b>{t['title']}</b> — {t['desc']}")
    lines += ["", "Shablon — tayyor menyu. Yaratilgandan keyin hammasini o'zgartirishingiz mumkin."]
    return "\n".join(lines)


async def _show_templates(callback: CallbackQuery, title: str) -> None:
    templates = await _templates()
    await callback.message.edit_text(_templates_text(templates, title), reply_markup=kb.templates_menu(templates), parse_mode="HTML")


@router.callback_query(F.data.in_({"bot_new", "tpls"}))
async def choose_template(callback: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    title = "<b>Yangi bot yaratish</b> (1/2)\n\nShablonni tanlang:" if callback.data == "bot_new" else "<b>📚 Tayyor shablonlar</b>"
    try:
        await _show_templates(callback, title)
    except Exception:  # noqa: BLE001
        templates = await _templates()
        await callback.message.answer(_templates_text(templates, title), reply_markup=kb.templates_menu(templates), parse_mode="HTML")
    await safe_answer(callback)


@router.message(Command("newbot"))
async def cmd_newbot(message: Message, state: FSMContext) -> None:
    await state.clear()
    templates = await _templates()
    await message.answer(
        _templates_text(templates, "<b>Yangi bot yaratish</b> (1/2)\n\nShablonni tanlang:"),
        reply_markup=kb.templates_menu(templates),
        parse_mode="HTML",
    )


@router.callback_query(F.data.startswith("tpl:"))
async def template_chosen(callback: CallbackQuery, state: FSMContext) -> None:
    code = callback.data.split(":", 1)[1]
    template = next((t for t in await _templates() if t["code"] == code), None)
    if template is None:
        await safe_answer(callback, "Shablon topilmadi")
        return
    await state.set_state(CreateBot.waiting_token)
    await state.update_data(template=code, update_bot=None)
    label = f"{template['icon']} {template['title']} ({template['pages']} sahifa)"
    await safe_edit_html(callback, HOW_TO.format(template=label), kb.token_wait())
    await safe_answer(callback)


async def safe_edit_html(callback: CallbackQuery, text: str, markup) -> None:
    try:
        await callback.message.edit_text(text, reply_markup=markup, parse_mode="HTML", disable_web_page_preview=True)
    except Exception:  # noqa: BLE001
        await callback.message.answer(text, reply_markup=markup, parse_mode="HTML", disable_web_page_preview=True)


async def _connect(message: Message, state: FSMContext, token: str, template: str, update_bot: int | None) -> None:
    user_id = await db_user_id(message.from_user)
    wait = await message.answer("⏳ Token tekshirilmoqda…")
    try:
        bot = await api_client.connect_bot(user_id, token, template)
    except ApiError as exc:
        if exc.status_code == 402:
            await state.clear()
            await wait.edit_text(f"🔒 {exc.message}", reply_markup=kb.upsell())
        else:
            await wait.edit_text(f"⚠️ {exc.message}\n\nTo'g'ri tokenni qayta yuboring.", reply_markup=kb.token_wait())
        return
    except Exception:  # noqa: BLE001 — Telegram vaqtincha javob bermadi va h.k.
        await wait.edit_text("⚠️ Telegram bilan bog'lanib bo'lmadi. Bir ozdan keyin tokenni qayta yuboring.", reply_markup=kb.token_wait())
        return
    await state.clear()
    try:
        await message.delete()  # token chatda ochiq qolmasin
    except Exception:  # noqa: BLE001
        pass
    if update_bot and bot["id"] == update_bot:
        text = f"✅ <b>@{bot['username']}</b> tokeni yangilandi — bot qayta ishga tushdi."
    else:
        text = (
            f"✅ <b>Bot tayyor: @{bot['username']}</b>\n\n"
            "Botingiz ishga tushdi va hozirning o'zida foydalanuvchilarga javob beradi.\n\n"
            "<b>Keyingi qadam — sozlash:</b>\n"
            "1. Pastdagi tugma orqali botingizga o'ting\n"
            "2. Boshqaruv paneli ochiladi (keyinchalik: /admin)\n"
            "3. «🧩 Menyu va tugmalar» — matn, rasm va tugmalarni o'zgartiring\n\n"
            "Murojaat va buyurtmalar sizga o'sha botning o'zida keladi."
        )
    await wait.edit_text(text, reply_markup=kb.bot_created(bot["username"]), parse_mode="HTML")


@router.message(CreateBot.waiting_token)
async def token_received(message: Message, state: FSMContext) -> None:
    match = TOKEN_RE.search(message.text or message.caption or "")
    if not match:
        await message.answer(
            "Bu xabarda token topilmadi.\n\nToken quyidagicha ko'rinadi:\n<code>1234567890:AAH...</code>\n\n"
            "@BotFather xabarini forward qilsangiz ham bo'ladi.",
            reply_markup=kb.token_wait(),
            parse_mode="HTML",
        )
        return
    data = await state.get_data()
    await _connect(message, state, match.group(1), data.get("template") or "blank", data.get("update_bot"))


@router.message(StateFilter(None), F.text.regexp(TOKEN_RE) | F.caption.regexp(TOKEN_RE))
async def token_without_state(message: Message, state: FSMContext) -> None:
    """Yaratish bosqichidan tashqarida ham token (yoki BotFather xabari) yuborilsa — bo'sh shablon bilan yaratamiz."""
    match = TOKEN_RE.search(message.text or message.caption or "")
    await _connect(message, state, match.group(1), "blank", None)


# --- Botlarim ---


async def _bots_screen(user_id: int) -> tuple[str, object]:
    data = await api_client.list_bots(user_id)
    bots = data["bots"]
    if not bots:
        text = "🤖 <b>Botlarim</b>\n\nSizda hali bot yo'q. Birinchi botingizni 1 daqiqada yarating."
    else:
        text = f"🤖 <b>Botlarim</b> · {len(bots)}/{data['limit']}\n\nBoshqarish uchun botni tanlang:"
    return text, kb.bots_list(bots, len(bots) < data["limit"])


@router.callback_query(F.data == "bots")
async def show_bots(callback: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    text, markup = await _bots_screen(await db_user_id(callback.from_user))
    await safe_edit_html(callback, text, markup)
    await safe_answer(callback)


@router.message(Command("mybots"))
async def cmd_mybots(message: Message, state: FSMContext) -> None:
    await state.clear()
    text, markup = await _bots_screen(await db_user_id(message.from_user))
    await message.answer(text, reply_markup=markup, parse_mode="HTML")


def _card_text(bot: dict) -> str:
    lines = [
        f"🤖 <b>{escape(bot['name'])}</b> · @{bot['username']}",
        "",
        f"Holat: {STATUS.get(bot['status'], bot['status'])}",
    ]
    if bot.get("error_message"):
        lines.append(f"⚠️ {escape(bot['error_message'])}")
    stats = bot["stats"]
    lines += [
        f"👥 Obunachilar: {stats['subscribers']} · 24 soatda faol: {stats['active_24h']}",
        f"🆕 7 kunda yangi: {stats['new_7d']} · 🚫 bloklagan: {stats['blocked']}",
        f"📄 Menyu sahifalari: {bot['pages']}",
        "",
        "Sozlash (menyu, tugmalar, xabar tarqatish) — botingizning o'zida: /admin",
    ]
    return "\n".join(lines)


async def _show_card(callback: CallbackQuery, bot_id: int) -> None:
    user_id = await db_user_id(callback.from_user)
    try:
        bot = await api_client.bot_detail(user_id, bot_id)
    except ApiError:
        text, markup = await _bots_screen(user_id)
        await safe_edit_html(callback, text, markup)
        return
    await safe_edit_html(callback, _card_text(bot), kb.bot_card(bot))


@router.callback_query(F.data.startswith("ubot:"))
async def bot_card(callback: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    await _show_card(callback, int(callback.data.split(":", 1)[1]))
    await safe_answer(callback)


@router.callback_query(F.data.startswith("ubot_tog:"))
async def bot_toggle(callback: CallbackQuery) -> None:
    _, bot_id, active = callback.data.split(":")
    await api_client.set_bot_active(await db_user_id(callback.from_user), int(bot_id), active == "1")
    await safe_answer(callback, "▶️ Ishga tushirildi" if active == "1" else "⏸ To'xtatildi")
    await _show_card(callback, int(bot_id))


@router.callback_query(F.data.startswith("ubot_tok:"))
async def bot_token_update(callback: CallbackQuery, state: FSMContext) -> None:
    bot_id = int(callback.data.split(":", 1)[1])
    await state.set_state(CreateBot.waiting_token)
    await state.update_data(template="blank", update_bot=bot_id)
    await safe_edit_html(
        callback,
        "🔑 <b>Tokenni yangilash</b>\n\n@BotFather → /mybots → botingiz → API Token → Revoke current token.\n"
        "Yangi tokenni shu yerga yuboring. Menyu va obunachilar saqlanib qoladi.",
        kb.token_wait(back=f"ubot:{bot_id}"),
    )
    await safe_answer(callback)


@router.callback_query(F.data.startswith("ubot_del:"))
async def bot_delete_ask(callback: CallbackQuery) -> None:
    bot_id = int(callback.data.split(":", 1)[1])
    await safe_edit_html(
        callback,
        "🗑 <b>Bot o'chirilsinmi?</b>\n\n• bot javob berishni to'xtatadi\n• menyu va obunachilar ro'yxati o'chadi\n"
        "• bot Telegram'da qoladi — uni @BotFather orqali o'chirish yoki boshqa joyda ishlatish mumkin",
        kb.confirm_bot_delete(bot_id),
    )
    await safe_answer(callback)


@router.callback_query(F.data.startswith("ubot_delok:"))
async def bot_delete(callback: CallbackQuery) -> None:
    user_id = await db_user_id(callback.from_user)
    try:
        await api_client.delete_bot(user_id, int(callback.data.split(":", 1)[1]))
    except ApiError:
        pass
    await safe_answer(callback, "🗑 Bot o'chirildi")
    text, markup = await _bots_screen(user_id)
    await safe_edit_html(callback, text, markup)
