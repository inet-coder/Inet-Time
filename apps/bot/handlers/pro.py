"""Pro xizmatlar: Bio playlist, Jadval, Emoji status, Rasm almashtirish — sozlash bosqichlari bilan."""

import asyncio
import re
from collections import defaultdict

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, Message

import keyboards as kb
from api_client import ApiError, api_client
from catalog import INTERVAL_CHOICES, PRO_SERVICES, TEMPLATE_HELP, UPDATE_INTERVAL_SECONDS, interval_text
from common import current_account, db_user_id, safe_answer, safe_edit
from core.settings import settings
from core.templates import TemplateContext, render
from states import ProSetup

router = Router(name="pro")

MAX_ITEMS = 10
_FIELD_LIMITS = {"name": 64, "bio": 70}
_FIELD_TITLES = {"name": "Ism", "bio": "Bio"}
_TIME_LINE = re.compile(r"^(\d{1,2})[:.](\d{2})\s+(.+)$")
_ORDER_TITLES = {"SEQUENTIAL": "ketma-ket", "RANDOM": "tasodifiy"}
# Albom yuborilganda bir nechta rasm bir vaqtda keladi — FSM ro'yxatiga yozishni ketma-ket qilamiz.
_photo_locks: dict[int, asyncio.Lock] = defaultdict(asyncio.Lock)


async def _load(tg_user) -> tuple[int, dict, dict | None]:
    user_id = await db_user_id(tg_user)
    overview = await api_client.get_overview(user_id)
    return user_id, overview, current_account(overview, tg_user.id)


def _preview(template: str, account: dict) -> str:
    ctx = TemplateContext(first_name=account["first_name"], username=account["username"], timezone=settings.default_timezone)
    return render(template, ctx)


def _limit(field: str, account: dict) -> int:
    return _FIELD_LIMITS[field] * (2 if field == "bio" and account["is_premium"] else 1)


def _check_text(template: str, field: str, account: dict) -> str | None:
    """Xato matnini qaytaradi (yoki None — hammasi joyida)."""
    try:
        preview = _preview(template, account)
    except ValueError:
        return f"«{template}» — noma'lum o'zgaruvchi bor.\n\n{TEMPLATE_HELP}"
    if not preview or len(preview) > _limit(field, account):
        return f"«{template}» juda uzun ({len(preview)}/{_limit(field, account)} belgi)."
    return None


def _summary(code: str, automation: dict, account: dict) -> str:
    actions = automation["actions"]
    interval = interval_text(automation["interval_seconds"] or UPDATE_INTERVAL_SECONDS)
    order = _ORDER_TITLES.get(automation["selection_strategy"], "")
    if code == "playlist":
        items = "\n".join(f"{i}. {_preview(a['template'], account)}" for i, a in enumerate(actions, 1))
        return f"Har {interval}da {order} almashadi:\n{items}"
    if code == "schedule":
        field = _FIELD_TITLES.get(actions[0]["field"], actions[0]["field"])
        items = "\n".join(f"{a['at_time']} → {_preview(a['template'], account)}" for a in actions)
        return f"{field} jadvali:\n{items}"
    if code == "emoji":
        return f"{len(actions)} ta emoji" + (f", har {interval}da almashadi" if len(actions) > 1 else "")
    if code == "photo":
        return f"{len(actions)} ta rasm" + (f", har {interval}da almashadi" if len(actions) > 1 else "")
    return ""


async def _service_screen(overview: dict, account: dict, code: str) -> tuple[str, InlineKeyboardMarkup]:
    meta = PRO_SERVICES[code]
    automation = next((a for a in account["automations"] if a["service_code"] == code), None)
    if automation is not None:
        status = {"ACTIVE": "✅ yoqilgan", "STARTING": "⏳ ishga tushmoqda", "ERROR": "⚠️ xatolik"}.get(
            automation["status"], automation["status"]
        )
        text = f"{meta['title']} — {status}\n\n{_summary(code, automation, account)}"
        if automation["status"] == "ERROR":
            text += "\n\n⚠️ Telegram bilan muammo yuz berdi. O'chirib, qayta sozlab ko'ring."
        return text, kb.pro_service_on(code, automation["id"])

    locked = not overview["plan"]["flags"].get(meta["flag"])
    text = f"{meta['title']} — ❌ o'chiq\n\n{meta['desc']}"
    if locked:
        text += "\n\n🔒 Bu xizmat Pro tarifda ochiladi."
    elif code == "emoji" and not account["is_premium"]:
        text += "\n\n⚠️ Bu akkauntda Telegram Premium yo'q — emoji status ishlamaydi."
    return text, kb.pro_service_off(code, locked)


# --- Menyu va ekranlar ---


@router.callback_query(F.data == "pro")
async def show_pro_menu(callback: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    _, overview, account = await _load(callback.from_user)
    if account is None:
        await safe_edit(callback, "Avval akkaunt ulang.", kb.login_methods())
        await safe_answer(callback)
        return
    flags = overview["plan"]["flags"]
    live = {a["service_code"]: a for a in account["automations"]}
    text = "⭐ Pro xizmatlar\n\nXizmatni tanlang — sozlaysiz va yoqasiz."
    if not any(flags.get(m["flag"]) for m in PRO_SERVICES.values()):
        text += "\n\n🔒 Bu xizmatlar Pro tarifda ochiladi. 💎 Tariflar bo'limidan oling."
    await safe_edit(callback, text, kb.pro_menu(live, flags))
    await safe_answer(callback)


@router.callback_query(F.data.startswith("pro:"))
async def show_pro_service(callback: CallbackQuery) -> None:
    _, overview, account = await _load(callback.from_user)
    text, markup = await _service_screen(overview, account, callback.data.split(":", 1)[1])
    await safe_edit(callback, text, markup)
    await safe_answer(callback)


async def _enable(target: CallbackQuery | Message, state: FSMContext, code: str, actions: list[dict], interval: int, strategy: str) -> None:
    """Yoqadi va natija ekranini ko'rsatadi. target — oxirgi bosilgan tugma yoki yuborilgan xabar."""
    message = target.message if isinstance(target, CallbackQuery) else target
    _, _, account = await _load(target.from_user)
    try:
        await api_client.enable_service(account["id"], code, actions, interval, strategy)
    except ApiError as exc:
        await state.clear()
        markup = kb.upsell() if exc.status_code == 402 else kb.cancel_to_pro()
        await message.answer(f"{'🔒' if exc.status_code == 402 else '⚠️'} {exc.message}", reply_markup=markup)
        return
    await state.clear()
    await asyncio.sleep(1.5)  # worker faollashtirishga ulgursin
    _, overview, account = await _load(target.from_user)
    text, markup = await _service_screen(overview, account, code)
    await message.answer(f"✅ {PRO_SERVICES[code]['title']} yoqildi!\n\n{text}", reply_markup=markup)


@router.callback_query(F.data.startswith("pro_set:"))
async def start_setup(callback: CallbackQuery, state: FSMContext) -> None:
    code = callback.data.split(":", 1)[1]
    _, overview, account = await _load(callback.from_user)
    if not overview["plan"]["flags"].get(PRO_SERVICES[code]["flag"]):
        await safe_edit(callback, "🔒 Bu xizmat Pro tarifda ochiladi.", kb.upsell())
        await safe_answer(callback)
        return

    await state.clear()
    if code == "playlist":
        await state.set_state(ProSetup.playlist_items)
        await safe_edit(
            callback,
            f"🔁 Bio matnlarini yuboring — har birini alohida qatorda (2–{MAX_ITEMS} ta).\n\n"
            "Masalan:\nBugun ajoyib kun ☀️\nKod yozyapman 💻\nQahva ichyapman ☕️\n\n"
            "{time}, {weekday} kabi o'zgaruvchilar ham ishlaydi.",
            kb.cancel_to_pro(),
        )
    elif code == "schedule":
        await safe_edit(callback, "🗓 Jadval bo'yicha nimani o'zgartiramiz?", kb.choose_schedule_field())
    elif code == "emoji":
        if not account["is_premium"]:
            await safe_answer(
                callback, "Bu akkauntda Telegram Premium yo'q — emoji status faqat Premium akkauntlarda ishlaydi.", show_alert=True
            )
            return
        await state.set_state(ProSetup.emoji_items)
        await safe_edit(
            callback,
            f"😀 Status uchun Premium emoji(lar) yuboring (1–{MAX_ITEMS} ta, bitta xabarda).\n\n"
            "Bitta yuborsangiz — doim shu turadi. Bir nechta yuborsangiz — navbat bilan almashadi.\n"
            "Oddiy emoji emas, Premium (animatsion) emoji kerak.",
            kb.cancel_to_pro(),
        )
    elif code == "photo":
        await state.set_state(ProSetup.photo_collecting)
        await state.update_data(photos=[])
        await safe_edit(
            callback,
            f"🖼 Profil uchun rasmlarni yuboring (1–{MAX_ITEMS} ta). Tugatgach «✅ Tayyor» ni bosing.\n\n"
            "Bitta rasm — doim shu turadi. Bir nechta — navbat bilan almashadi.",
            kb.cancel_to_pro(),
        )
    await safe_answer(callback)


# --- Bio playlist ---


@router.message(ProSetup.playlist_items)
async def playlist_items(message: Message, state: FSMContext) -> None:
    _, _, account = await _load(message.from_user)
    items = [line.strip() for line in (message.text or "").splitlines() if line.strip()]
    if not 2 <= len(items) <= MAX_ITEMS:
        await message.answer(f"2 tadan {MAX_ITEMS} tagacha matn yuboring, har birini alohida qatorda.", reply_markup=kb.cancel_to_pro())
        return
    for item in items:
        error = _check_text(item, "bio", account)
        if error:
            await message.answer(error + "\n\nQaytadan yuboring.", reply_markup=kb.cancel_to_pro())
            return
    await state.update_data(items=items)
    await message.answer(f"✅ {len(items)} ta matn qabul qilindi.\n\nQanday tartibda almashsin?", reply_markup=kb.choose_order())


@router.callback_query(F.data.startswith("pl_ord:"))
async def playlist_order(callback: CallbackQuery, state: FSMContext) -> None:
    await state.update_data(order=callback.data.split(":", 1)[1])
    await safe_edit(callback, "Qanchada bir almashsin?", kb.choose_interval("pl_int", INTERVAL_CHOICES["playlist"]))
    await safe_answer(callback)


@router.callback_query(F.data.startswith("pl_int:"))
async def playlist_interval(callback: CallbackQuery, state: FSMContext) -> None:
    data = await state.get_data()
    if "items" not in data:
        await safe_answer(callback, "Sozlash muddati o'tdi, qaytadan boshlang.", show_alert=True)
        return
    actions = [{"field": "bio", "template": t} for t in data["items"]]
    await safe_answer(callback)
    await _enable(callback, state, "playlist", actions, int(callback.data.split(":", 1)[1]), data.get("order", "SEQUENTIAL"))


# --- Jadval ---


@router.callback_query(F.data.startswith("sc_field:"))
async def schedule_field(callback: CallbackQuery, state: FSMContext) -> None:
    field = callback.data.split(":", 1)[1]
    await state.set_state(ProSetup.schedule_lines)
    await state.update_data(field=field)
    await safe_edit(
        callback,
        f"🗓 {_FIELD_TITLES[field]} jadvalini yuboring — har qatorda vaqt va matn (2–{MAX_ITEMS} ta).\n\n"
        "Masalan:\n09:00 Ishdaman 💼\n13:00 Tushlikda 🍽\n18:00 Uydaman 🏠\n23:00 Uxlayapman 😴\n\n"
        f"Vaqt — {settings.default_timezone} bo'yicha. Har vaqtda matn o'zgaradi va keyingi vaqtgacha turadi.",
        kb.cancel_to_pro(),
    )
    await safe_answer(callback)


@router.message(ProSetup.schedule_lines)
async def schedule_lines(message: Message, state: FSMContext) -> None:
    field = (await state.get_data())["field"]
    _, _, account = await _load(message.from_user)
    slots: dict[str, str] = {}
    for line in (message.text or "").splitlines():
        if not line.strip():
            continue
        match = _TIME_LINE.match(line.strip())
        if not match or int(match.group(1)) > 23 or int(match.group(2)) > 59:
            await message.answer(f"«{line.strip()}» — noto'g'ri. Ko'rinishi: 09:00 Matn", reply_markup=kb.cancel_to_pro())
            return
        at_time = f"{int(match.group(1)):02d}:{match.group(2)}"
        error = _check_text(match.group(3).strip(), field, account)
        if error:
            await message.answer(error + "\n\nQaytadan yuboring.", reply_markup=kb.cancel_to_pro())
            return
        slots[at_time] = match.group(3).strip()
    if not 2 <= len(slots) <= MAX_ITEMS:
        await message.answer(f"2 tadan {MAX_ITEMS} tagacha turli vaqt kiriting.", reply_markup=kb.cancel_to_pro())
        return
    actions = [{"field": field, "template": text, "at_time": t} for t, text in sorted(slots.items())]
    await _enable(message, state, "schedule", actions, UPDATE_INTERVAL_SECONDS, "BY_TIME")


# --- Emoji status ---


@router.message(ProSetup.emoji_items)
async def emoji_items(message: Message, state: FSMContext) -> None:
    ids = list(
        dict.fromkeys(e.custom_emoji_id for e in (message.entities or []) if e.type == "custom_emoji" and e.custom_emoji_id)
    )
    if not ids:
        await message.answer(
            "Premium emoji topilmadi. Oddiy emoji emas, Premium (animatsion) emoji yuboring.", reply_markup=kb.cancel_to_pro()
        )
        return
    ids = ids[:MAX_ITEMS]
    if len(ids) == 1:
        await _enable(message, state, "emoji", [{"field": "emoji_status", "template": ids[0]}], UPDATE_INTERVAL_SECONDS, "NONE")
        return
    await state.update_data(emojis=ids)
    await message.answer(f"✅ {len(ids)} ta emoji qabul qilindi.\n\nQanchada bir almashsin?", reply_markup=kb.choose_interval("em_int", INTERVAL_CHOICES["emoji"]))


@router.callback_query(F.data.startswith("em_int:"))
async def emoji_interval(callback: CallbackQuery, state: FSMContext) -> None:
    data = await state.get_data()
    if "emojis" not in data:
        await safe_answer(callback, "Sozlash muddati o'tdi, qaytadan boshlang.", show_alert=True)
        return
    actions = [{"field": "emoji_status", "template": e} for e in data["emojis"]]
    await safe_answer(callback)
    await _enable(callback, state, "emoji", actions, int(callback.data.split(":", 1)[1]), "SEQUENTIAL")


# --- Rasm almashtirish ---


@router.message(ProSetup.photo_collecting, F.photo)
async def photo_received(message: Message, state: FSMContext) -> None:
    user_id = await db_user_id(message.from_user)
    buffer = await message.bot.download(message.photo[-1])
    async with _photo_locks[message.from_user.id]:
        photos = (await state.get_data()).get("photos", [])
        if len(photos) >= MAX_ITEMS:
            await message.answer(f"Maksimum {MAX_ITEMS} ta rasm. «✅ Tayyor» ni bosing.", reply_markup=kb.photo_collecting(len(photos)))
            return
        photos.append(await api_client.upload_media(user_id, buffer.read()))
        await state.update_data(photos=photos)
    await message.answer(
        f"✅ {len(photos)}-rasm qabul qilindi. Yana yuboring yoki «Tayyor» ni bosing.", reply_markup=kb.photo_collecting(len(photos))
    )


@router.message(ProSetup.photo_collecting)
async def photo_expected(message: Message, state: FSMContext) -> None:
    count = len((await state.get_data()).get("photos", []))
    await message.answer(
        "Rasmni oddiy rasm sifatida yuboring (fayl emas).", reply_markup=kb.photo_collecting(count) if count else kb.cancel_to_pro()
    )


@router.callback_query(F.data == "ph_done")
async def photos_done(callback: CallbackQuery, state: FSMContext) -> None:
    photos = (await state.get_data()).get("photos", [])
    if not photos:
        await safe_answer(callback, "Avval kamida 1 ta rasm yuboring", show_alert=True)
        return
    await safe_answer(callback)
    if len(photos) == 1:
        await _enable(callback, state, "photo", [{"field": "photo", "template": str(photos[0])}], 3600, "NONE")
        return
    await safe_edit(callback, f"{len(photos)} ta rasm. Qanchada bir almashsin?", kb.choose_interval("ph_int", INTERVAL_CHOICES["photo"]))


@router.callback_query(F.data.startswith("ph_int:"))
async def photo_interval(callback: CallbackQuery, state: FSMContext) -> None:
    photos = (await state.get_data()).get("photos", [])
    if not photos:
        await safe_answer(callback, "Sozlash muddati o'tdi, qaytadan boshlang.", show_alert=True)
        return
    actions = [{"field": "photo", "template": str(p)} for p in photos]
    await safe_answer(callback)
    await _enable(callback, state, "photo", actions, int(callback.data.split(":", 1)[1]), "SEQUENTIAL")

