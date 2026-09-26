"""🤖 AI avto-javob va 👀 Stories — «➕ Ko'proq» bo'limidan."""

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

import keyboards as kb
from api_client import ApiError, api_client
from catalog import PRO_SERVICES, STUDIO
from common import current_account, db_user_id, safe_answer, safe_edit
from states import AISetup, StoriesAsk

router = Router(name="ai")


async def _load(tg_user) -> tuple[int, dict, dict | None]:
    user_id = await db_user_id(tg_user)
    overview = await api_client.get_overview(user_id)
    return user_id, overview, current_account(overview, tg_user.id)


def _yes(value: bool) -> str:
    return "ha" if value else "yo'q"


def _ai_text(data: dict) -> str:
    s = data["settings"]
    preset = next((p["title"] for p in data["presets"] if p["code"] == s["preset"]), "✍️ O'z uslubim")
    lines = [
        "🤖 AI avto-javob · " + ("✅ yoqilgan" if s["enabled"] else "o'chiq"),
        "",
        PRO_SERVICES["ai"]["desc"],
        "",
        f"🎨 Uslub: {preset}",
    ]
    if s["preset"] == "custom" and s["style"]:
        lines.append(f"   «{s['style']}»")
    lines += [
        f"🙋 Faqat men javob bermasam: {_yes(s['only_when_away'])}",
        f"🤖 belgisi: {_yes(s['signature'])}",
        f"📊 Bugun: {data['used_today']}/{data['daily_limit']}",
    ]
    if not data["available"]:
        lines += ["", "⚠️ AI hali sozlanmagan — admin kalitni qo'shgach ishlaydi."]
    return "\n".join(lines)


async def _show_ai(target: CallbackQuery | Message, note: str = "") -> None:
    user_id, overview, account = await _load(target.from_user)
    if account is None:
        text, markup = "Avval akkauntni ulang 👇", kb.login_methods()
    elif not overview["plan"]["flags"].get("ai_service"):
        text, markup = f"🤖 AI avto-javob\n\n{PRO_SERVICES['ai']['desc']}\n\n🔒 Tarifingizda yo'q.", kb.upsell()
    else:
        data = await api_client.get_ai(user_id, account["id"])
        text, markup = _ai_text(data) + note, kb.ai_menu(data)
    if isinstance(target, CallbackQuery):
        await safe_edit(target, text, markup)
    else:
        await target.answer(text, reply_markup=markup)


async def _update(callback: CallbackQuery, **changes) -> None:
    user_id, _, account = await _load(callback.from_user)
    data = await api_client.get_ai(user_id, account["id"])
    try:
        await api_client.save_ai(user_id, account["id"], {**data["settings"], **changes})
    except ApiError as exc:
        await safe_answer(callback, exc.message, show_alert=True)
        return
    await safe_answer(callback, "✅ Saqlandi")
    await _show_ai(callback)


@router.callback_query(F.data == "pro:ai")
async def show_ai(callback: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    await _show_ai(callback)
    await safe_answer(callback)


@router.callback_query(F.data.in_({"ai_on", "ai_off"}))
async def toggle_ai(callback: CallbackQuery) -> None:
    await _update(callback, enabled=callback.data == "ai_on")


@router.callback_query(F.data.startswith("ai_preset:"))
async def set_preset(callback: CallbackQuery) -> None:
    await _update(callback, preset=callback.data.split(":", 1)[1])


@router.callback_query(F.data == "ai_sig")
async def toggle_signature(callback: CallbackQuery) -> None:
    user_id, _, account = await _load(callback.from_user)
    current = (await api_client.get_ai(user_id, account["id"]))["settings"]["signature"]
    await _update(callback, signature=not current)


@router.callback_query(F.data == "ai_away")
async def toggle_away(callback: CallbackQuery) -> None:
    user_id, _, account = await _load(callback.from_user)
    current = (await api_client.get_ai(user_id, account["id"]))["settings"]["only_when_away"]
    await _update(callback, only_when_away=not current)


@router.callback_query(F.data == "ai_custom")
async def ask_style(callback: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(AISetup.waiting_style)
    await safe_edit(
        callback,
        "✍️ AI qanday javob bersin? Qisqa yozing (300 belgigacha).\n\n"
        "Masalan: Qisqa va do'stona javob ber, ish haqida bo'lsa ertaga javob berishimni ayt.",
        kb.cancel_to("pro:ai"),
    )
    await safe_answer(callback)


@router.message(AISetup.waiting_style)
async def style_received(message: Message, state: FSMContext) -> None:
    style = (message.text or "").strip()
    if not 3 <= len(style) <= 300:
        await message.answer("3–300 belgi yozing.", reply_markup=kb.cancel_to("pro:ai"))
        return
    user_id, _, account = await _load(message.from_user)
    data = await api_client.get_ai(user_id, account["id"])
    try:
        await api_client.save_ai(user_id, account["id"], {**data["settings"], "preset": "custom", "style": style})
    except ApiError as exc:
        await message.answer(f"⚠️ {exc.message}", reply_markup=kb.cancel_to("pro:ai"))
        return
    await state.clear()
    await _show_ai(message, "\n\n✅ Uslub saqlandi.")


# --- Stories ---


@router.callback_query(F.data == "pro:stories")
async def ask_username(callback: CallbackQuery, state: FSMContext) -> None:
    _, overview, account = await _load(callback.from_user)
    if account is None:
        await safe_edit(callback, "Avval akkauntni ulang 👇", kb.login_methods())
    elif not overview["plan"]["flags"].get("stories_service"):
        await safe_edit(callback, f"👀 Stories\n\n{PRO_SERVICES['stories']['desc']}\n\n🔒 Tarifingizda yo'q.", kb.upsell())
    else:
        await state.set_state(StoriesAsk.waiting_username)
        await safe_edit(
            callback,
            "👀 Kimning hikoyalari? Username yuboring: @username\n\n"
            "• faqat akkauntingiz ko'ra oladiganlari\n"
            "• ko'rganingiz egasiga ko'rinadi\n"
            "• himoyalangan hikoyalar yuklanmaydi\n\n"
            f"💡 {STUDIO}da oldindan ko'rib, tanlab olasiz.",
            kb.cancel_to("pro"),
        )
    await safe_answer(callback)


@router.message(StoriesAsk.waiting_username)
async def username_received(message: Message, state: FSMContext) -> None:
    username = (message.text or "").strip().lstrip("@").split("/")[-1]
    if not username or " " in username:
        await message.answer("Username yuboring, masalan: @durov", reply_markup=kb.cancel_to("pro"))
        return
    user_id, _, account = await _load(message.from_user)
    try:
        await api_client.send_stories(user_id, account["id"], username)
    except ApiError as exc:
        await message.answer(f"⚠️ {exc.message}", reply_markup=kb.cancel_to("pro"))
        return
    await state.clear()
    await message.answer(f"📥 @{username} hikoyalari yuklanmoqda… Bir necha soniyada shu yerga keladi.", reply_markup=kb.stories_again())
