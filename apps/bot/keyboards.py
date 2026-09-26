from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, WebAppInfo

from catalog import PRO_SERVICES, SERVICES, STATUS_ICONS, STUDIO, interval_text
from common import webapp_url


def _button(text: str, data: str) -> InlineKeyboardButton:
    # https:// bilan boshlansa — Mini App tugmasi, aks holda oddiy callback.
    if data.startswith("https://"):
        return InlineKeyboardButton(text=text, web_app=WebAppInfo(url=data))
    return InlineKeyboardButton(text=text, callback_data=data)


def _kb(rows: list[list[tuple[str, str]]]) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[_button(text, data) for text, data in row] for row in rows])


def _webapp_row() -> list[list[tuple[str, str]]]:
    url = webapp_url()
    return [[(STUDIO, url)]] if url else []


def home_no_account(admin: bool) -> InlineKeyboardMarkup:
    rows = [
        [("📞 Raqam orqali ulash", "login_phone"), ("📷 QR orqali", "login_qr")],
        *_webapp_row(),
        [("💎 Tariflar", "plans"), ("❓ Yordam", "help")],
    ]
    if admin:
        rows.append([("🛠 Admin panel", "adm")])
    return _kb(rows)


def _status_icon(live: dict[str, dict], code: str) -> str:
    # Faqat yoqilganlar belgilanadi — o'chiq xizmat tugmasi toza qoladi.
    return " " + STATUS_ICONS.get(live[code]["status"], "✅") if code in live else ""


def home(live: dict[str, dict], multi_account: bool, admin: bool) -> InlineKeyboardMarkup:
    def svc_button(code: str) -> tuple[str, str]:
        return f"{SERVICES[code]['title']}{_status_icon(live, code)}", f"svc:{code}"

    extra_active = sum(1 for code in PRO_SERVICES if code in live)
    rows = [
        *_webapp_row(),
        [svc_button("clock_name"), svc_button("auto_bio")],
        [svc_button("auto_name"), (f"➕ Ko'proq{f' ({extra_active} ✅)' if extra_active else ''}", "pro")],
    ]
    if multi_account:
        rows.append([("🔄 Boshqa akkaunt", "acc_switch")])
    rows += [
        [("💎 Tarif", "plans"), ("💰 Balans", "bal")],
        [("⚙️ Akkaunt", "acc"), ("❓ Yordam", "help")],
    ]
    if admin:
        rows.append([("🛠 Admin panel", "adm")])
    return _kb(rows)


def back_home() -> InlineKeyboardMarkup:
    return _kb([[("🏠 Bosh sahifa", "home")]])


def help_menu() -> InlineKeyboardMarkup:
    return _kb([*_webapp_row(), [("🎁 Do'stga ulashish", "ref")], [("🏠 Bosh sahifa", "home")]])


def cancel() -> InlineKeyboardMarkup:
    return _kb([[("❌ Bekor qilish", "home")]])


def _back_for(code: str) -> tuple[str, str]:
    return ("⬅️ Orqaga", "pro") if code in PRO_SERVICES else ("⬅️ Orqaga", "home")


def service_on(code: str, automation_id: int) -> InlineKeyboardMarkup:
    rows = [[("⏹ O'chirish", f"svc_off:{automation_id}")]]
    if SERVICES[code]["field"] != "online":
        rows.append([("✏️ Matnni o'zgartirish", f"svc_tpl:{code}")])
    rows.append([_back_for(code)])
    return _kb(rows)


def service_off(code: str, locked: bool, plan_name: str | None = None) -> InlineKeyboardMarkup:
    if locked:
        return _kb([[(f"💎 {plan_name or 'Tarif'}ga o'tish", "plans")], [_back_for(code)]])
    rows = [[("✅ Yoqish", f"svc_on:{code}")]]
    if SERVICES[code]["field"] != "online":
        rows.append([("✏️ O'z matnim bilan", f"svc_tpl:{code}")])
    rows.append([_back_for(code)])
    return _kb(rows)


# --- Pro xizmatlar ---


def pro_menu(live: dict[str, dict], flags: dict) -> InlineKeyboardMarkup:
    rows = []
    for code, meta in PRO_SERVICES.items():
        icon = _status_icon(live, code) if flags.get(meta["flag"]) or code in live else " 🔒"
        target = "svc:online" if code == "online" else f"pro:{code}"
        rows.append([(f"{meta['title']}{icon}", target)])
    rows.append([("🎂 Tug'ilgan kun", "bday"), ("👁 Faollik holati", "presence")])
    rows.append([("🏠 Bosh sahifa", "home")])
    return _kb(rows)


def pro_service_on(code: str, automation_id: int) -> InlineKeyboardMarkup:
    return _kb(
        [
            [("⏹ O'chirish", f"svc_off:{automation_id}")],
            [("✏️ Qayta sozlash", f"pro_set:{code}")],
            [("⬅️ Orqaga", "pro")],
        ]
    )


def pro_service_off(code: str, locked: bool, plan_name: str | None = None) -> InlineKeyboardMarkup:
    if locked:
        return _kb([[(f"💎 {plan_name or 'Tarif'}ga o'tish", "plans")], [("⬅️ Orqaga", "pro")]])
    rows = [[("⚙️ Sozlash va yoqish", f"pro_set:{code}")]]
    if webapp_url():
        rows.append([(f"{STUDIO}da sozlash", webapp_url())])
    rows.append([("⬅️ Orqaga", "pro")])
    return _kb(rows)


def choose_order() -> InlineKeyboardMarkup:
    return _kb([[("➡️ Ketma-ket", "pl_ord:SEQUENTIAL"), ("🎲 Tasodifiy", "pl_ord:RANDOM")], [("❌ Bekor qilish", "pro")]])


def choose_interval(prefix: str, seconds_list: list[int]) -> InlineKeyboardMarkup:
    buttons = [(f"har {interval_text(s)}", f"{prefix}:{s}") for s in seconds_list]
    rows = [buttons[i : i + 2] for i in range(0, len(buttons), 2)]
    rows.append([("❌ Bekor qilish", "pro")])
    return _kb(rows)


def choose_schedule_field() -> InlineKeyboardMarkup:
    return _kb([[("📝 Bio", "sc_field:bio"), ("✏️ Ism", "sc_field:name")], [("❌ Bekor qilish", "pro")]])


def photo_collecting(count: int) -> InlineKeyboardMarkup:
    return _kb([[(f"✅ Tayyor ({count} ta rasm)", "ph_done")], [("❌ Bekor qilish", "pro")]])


def cancel_to_pro() -> InlineKeyboardMarkup:
    return _kb([[("❌ Bekor qilish", "pro")]])


def upsell() -> InlineKeyboardMarkup:
    return _kb([[("💎 Tariflarni ko'rish", "plans")], [("🏠 Bosh sahifa", "home")]])


def account_menu(multi_account: bool) -> InlineKeyboardMarkup:
    rows = [[("👁 Faollik holati", "presence")], [("➕ Akkaunt qo'shish", "acc_add")]]
    if multi_account:
        rows.append([("🔄 Boshqa akkaunt", "acc_switch")])
    rows.append([("🚫 Akkauntni uzish", "acc_del")])
    rows.append([("🏠 Bosh sahifa", "home")])
    return _kb(rows)


def account_picker(accounts: list[dict]) -> InlineKeyboardMarkup:
    rows = [[(f"@{a['username']}" if a["username"] else (a["first_name"] or f"#{a['id']}"), f"acc_sel:{a['id']}")] for a in accounts]
    rows.append([("⬅️ Orqaga", "home")])
    return _kb(rows)


def confirm_revoke(account_id: int) -> InlineKeyboardMarkup:
    return _kb([[("🚫 Ha, uzilsin", f"acc_del_yes:{account_id}")], [("⬅️ Yo'q, qolsin", "acc")]])


def login_methods() -> InlineKeyboardMarkup:
    return _kb(
        [
            [("📞 Raqam orqali", "login_phone"), ("📷 QR orqali", "login_qr")],
            [("⬅️ Orqaga", "home")],
        ]
    )


def qr_waiting() -> InlineKeyboardMarkup:
    return _kb([[("❌ Bekor qilish", "home")]])


def qr_expired() -> InlineKeyboardMarkup:
    return _kb([[("🔄 Yangi QR kod", "login_qr")], [("📞 Raqam orqali ulash", "login_phone")], [("🏠 Bosh sahifa", "home")]])


def plans(plans_list: list[dict], current_code: str) -> InlineKeyboardMarkup:
    rows = []
    for p in plans_list:
        verb = "uzaytirish" if p["code"] == current_code else "olish"
        rows.append([(f"{p['name']} {verb}", f"buy:{p['code']}")])
    rows += _webapp_row()
    rows.append([("💰 Balans", "bal"), ("🏠 Bosh sahifa", "home")])
    return _kb(rows)


def after_purchase(online_unlocked: bool) -> InlineKeyboardMarkup:
    rows = []
    if online_unlocked:
        rows.append([("🟢 24/7 Online'ni yoqish", "svc:online")])
    rows.append([("🏠 Bosh sahifa", "home")])
    return _kb(rows)


def confirm_buy(plan_code: str) -> InlineKeyboardMarkup:
    return _kb([[("✅ To'lash", f"buy_yes:{plan_code}")], [("⬅️ Bekor qilish", "plans")]])


def need_topup() -> InlineKeyboardMarkup:
    return _kb([[("💳 Balansni to'ldirish", "topup")], [("⬅️ Orqaga", "plans")]])


def balance() -> InlineKeyboardMarkup:
    return _kb([[("💳 Balansni to'ldirish", "topup")], [("💎 Tariflar", "plans"), ("🏠 Bosh sahifa", "home")]])


def topup_amounts(amounts: list[int]) -> InlineKeyboardMarkup:
    rows = [[(f"{a:,}".replace(",", " ") + " so'm", f"topup_amt:{a}")] for a in amounts]
    rows.append([("✍️ Boshqa summa", "topup_custom")])
    rows.append([("⬅️ Orqaga", "bal")])
    return _kb(rows)


def admin_payment_decision(payment_id: int) -> InlineKeyboardMarkup:
    return _kb([[("✅ Tasdiqlash", f"adm_ok:{payment_id}"), ("❌ Rad etish", f"adm_no:{payment_id}")]])


def admin_menu(pending_count: int) -> InlineKeyboardMarkup:
    return _kb(
        [
            [(f"💳 Kutayotgan to'lovlar ({pending_count})", "adm_pays")],
            [("👥 Foydalanuvchilar", "adm_users")],
            *_webapp_row(),
            [("🏠 Bosh sahifa", "home")],
        ]
    )


def admin_payments(payments: list[dict]) -> InlineKeyboardMarkup:
    rows = [[(f"#{p['id']} · {p['amount']:,.0f} so'm · user {p['user_id']}".replace(",", " "), f"adm_pay:{p['id']}")] for p in payments]
    rows.append([("⬅️ Orqaga", "adm")])
    return _kb(rows)


def admin_payment_view(payment_id: int) -> InlineKeyboardMarkup:
    return _kb(
        [
            [("✅ Tasdiqlash", f"adm_ok:{payment_id}"), ("❌ Rad etish", f"adm_no:{payment_id}")],
            [("⬅️ Orqaga", "adm_pays")],
        ]
    )


def admin_users(users: list[dict]) -> InlineKeyboardMarkup:
    rows = []
    for u in users:
        name = f"@{u['username']}" if u["username"] else (u["first_name"] or str(u["telegram_user_id"]))
        rows.append([(f"{'🚫' if u['is_banned'] else '👤'} {name} · {u['balance']:,.0f}".replace(",", " "), f"adm_user:{u['id']}")])
    rows.append([("⬅️ Orqaga", "adm")])
    return _kb(rows)


def admin_user_view(user_id: int, is_banned: bool) -> InlineKeyboardMarkup:
    action = ("✅ Blokdan chiqarish", f"adm_unban:{user_id}") if is_banned else ("🚫 Bloklash", f"adm_ban:{user_id}")
    return _kb([[action], [("⬅️ Orqaga", "adm_users")]])


# --- AI avto-javob va Stories ---


def ai_menu(data: dict) -> InlineKeyboardMarkup:
    s = data["settings"]
    presets = [(("✅ " if s["preset"] == p["code"] else "") + p["title"], f"ai_preset:{p['code']}") for p in data["presets"]]
    rows = [[("⏹ O'chirish", "ai_off")] if s["enabled"] else [("✅ Yoqish", "ai_on")]]
    rows += [presets[i : i + 2] for i in range(0, len(presets), 2)]
    rows.append([(("✅ " if s["preset"] == "custom" else "") + "✍️ O'z uslubim", "ai_custom")])
    rows.append(
        [
            ("🙋 Faqat bandligimda: " + ("ha" if s["only_when_away"] else "yo'q"), "ai_away"),
            ("🤖 belgi: " + ("ha" if s["signature"] else "yo'q"), "ai_sig"),
        ]
    )
    rows += _webapp_row()
    rows.append([("⬅️ Orqaga", "pro")])
    return _kb(rows)


def cancel_to(target: str) -> InlineKeyboardMarkup:
    return _kb([[("❌ Bekor qilish", target)]])


def stories_again() -> InlineKeyboardMarkup:
    return _kb([[("👀 Yana stories", "pro:stories")], [("🏠 Bosh sahifa", "home")]])


# --- Tug'ilgan kun va faollik holati ---


def birthday_menu(data: dict) -> InlineKeyboardMarkup:
    rows = []
    if data["birthday"]:
        rows += [[(t["preview"], f"bday_use:{i}")] for i, t in enumerate(data["templates"]) if t["preview"]]
    rows.append([("📥 Telegram profilidan olish", "bday_import")])
    rows += _webapp_row()
    rows.append([("⬅️ Orqaga", "pro")])
    return _kb(rows)


def presence_menu(current: str, online_unlocked: bool) -> InlineKeyboardMarkup:
    options = [
        ("online", "🟢 Doim onlayn"),
        ("recently", "🕶 Yaqinda onlayn edi"),
        ("contacts", "👥 Faqat kontaktlarga"),
        ("default", "🕐 Standart (aniq vaqt)"),
    ]
    rows = []
    for mode, title in options:
        if mode == "online" and not online_unlocked:
            rows.append([(f"{title} 🔒", "plans")])
        else:
            rows.append([(("✅ " if mode == current else "") + title, f"presence:{mode}")])
    rows.append([("⬅️ Orqaga", "pro")])
    return _kb(rows)


def playlist_packs(packs: list[dict]) -> InlineKeyboardMarkup:
    buttons = [(p["title"], f"pl_pack:{p['code']}") for p in packs]
    rows = [buttons[i : i + 3] for i in range(0, len(buttons), 3)]
    rows.append([("❌ Bekor qilish", "pro")])
    return _kb(rows)
