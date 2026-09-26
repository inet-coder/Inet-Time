from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from catalog import SERVICES, STATUS_ICONS


def _kb(rows: list[list[tuple[str, str]]]) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text=text, callback_data=data) for text, data in row] for row in rows]
    )


def home_no_account(admin: bool) -> InlineKeyboardMarkup:
    rows = [
        [("📞 Telefon raqam orqali ulash", "login_phone")],
        [("📷 QR kod orqali ulash", "login_qr")],
        [("💎 Tariflar", "plans"), ("💰 Balans", "bal")],
        [("🤝 Do'stlarni taklif qilish", "ref")],
    ]
    if admin:
        rows.append([("🛠 Admin panel", "adm")])
    return _kb(rows)


def home(live: dict[str, dict], plan_flags: dict, multi_account: bool, admin: bool) -> InlineKeyboardMarkup:
    def svc_button(code: str) -> tuple[str, str]:
        meta = SERVICES[code]
        if code in live:
            icon = STATUS_ICONS.get(live[code]["status"], "✅")
        elif meta.get("pro_flag") and not plan_flags.get(meta["pro_flag"]):
            icon = "🔒"
        else:
            icon = "❌"
        return f"{meta['title']} {icon}", f"svc:{code}"

    rows = [
        [svc_button("clock_name"), svc_button("auto_bio")],
        [svc_button("auto_name"), svc_button("online")],
        [("💎 Tariflar", "plans"), ("💰 Balans", "bal")],
        [("🤝 Taklif qilish", "ref"), ("⚙️ Akkaunt", "acc")],
    ]
    if multi_account:
        rows.insert(2, [("🔄 Boshqa akkauntga o'tish", "acc_switch")])
    if admin:
        rows.append([("🛠 Admin panel", "adm")])
    return _kb(rows)


def back_home() -> InlineKeyboardMarkup:
    return _kb([[("⬅️ Bosh sahifa", "home")]])


def cancel() -> InlineKeyboardMarkup:
    return _kb([[("❌ Bekor qilish", "home")]])


def service_on(code: str, automation_id: int) -> InlineKeyboardMarkup:
    rows = [[("⏹ O'chirish", f"svc_off:{automation_id}")]]
    if SERVICES[code]["field"] != "online":
        rows.append([("✏️ Shablonni o'zgartirish", f"svc_tpl:{code}")])
    rows.append([("⬅️ Orqaga", "home")])
    return _kb(rows)


def service_off(code: str, locked: bool) -> InlineKeyboardMarkup:
    if locked:
        return _kb([[("💎 Pro tarifni olish", "plans")], [("⬅️ Orqaga", "home")]])
    rows = [[("✅ Yoqish", f"svc_on:{code}")]]
    if SERVICES[code]["field"] != "online":
        rows.append([("✏️ O'z shablonim bilan yoqish", f"svc_tpl:{code}")])
    rows.append([("⬅️ Orqaga", "home")])
    return _kb(rows)


def upsell() -> InlineKeyboardMarkup:
    return _kb([[("💎 Tariflar", "plans")], [("⬅️ Bosh sahifa", "home")]])


def account_menu(multi_account: bool) -> InlineKeyboardMarkup:
    rows = [[("➕ Yana akkaunt qo'shish", "acc_add")]]
    if multi_account:
        rows.append([("🔄 Boshqa akkauntga o'tish", "acc_switch")])
    rows.append([("🚫 Akkauntni uzish", "acc_del")])
    rows.append([("⬅️ Bosh sahifa", "home")])
    return _kb(rows)


def account_picker(accounts: list[dict]) -> InlineKeyboardMarkup:
    rows = [[(f"@{a['username']}" if a["username"] else (a["first_name"] or f"#{a['id']}"), f"acc_sel:{a['id']}")] for a in accounts]
    rows.append([("⬅️ Orqaga", "home")])
    return _kb(rows)


def confirm_revoke(account_id: int) -> InlineKeyboardMarkup:
    return _kb([[("✅ Ha, uzish", f"acc_del_yes:{account_id}")], [("⬅️ Yo'q", "acc")]])


def login_methods() -> InlineKeyboardMarkup:
    return _kb(
        [
            [("📞 Telefon raqam orqali", "login_phone")],
            [("📷 QR kod orqali", "login_qr")],
            [("⬅️ Orqaga", "home")],
        ]
    )


def qr_waiting() -> InlineKeyboardMarkup:
    return _kb([[("❌ Bekor qilish", "home")]])


def qr_expired() -> InlineKeyboardMarkup:
    return _kb([[("🔄 Yangi QR kod", "login_qr")], [("📞 Telefon orqali ulash", "login_phone")], [("⬅️ Bosh sahifa", "home")]])


def plans(plans_list: list[dict], current_code: str) -> InlineKeyboardMarkup:
    rows = []
    for p in plans_list:
        verb = "uzaytirish" if p["code"] == current_code else "olish"
        rows.append([(f"{p['name']} {verb}", f"buy:{p['code']}")])
    rows.append([("💰 Balans", "bal"), ("⬅️ Bosh sahifa", "home")])
    return _kb(rows)


def after_purchase(online_unlocked: bool) -> InlineKeyboardMarkup:
    rows = []
    if online_unlocked:
        rows.append([("🟢 24/7 Online'ni yoqish", "svc:online")])
    rows.append([("🏠 Bosh sahifa", "home")])
    return _kb(rows)


def confirm_buy(plan_code: str) -> InlineKeyboardMarkup:
    return _kb([[("✅ Tasdiqlash", f"buy_yes:{plan_code}")], [("⬅️ Bekor qilish", "plans")]])


def need_topup() -> InlineKeyboardMarkup:
    return _kb([[("💳 Balansni to'ldirish", "topup")], [("⬅️ Orqaga", "plans")]])


def balance() -> InlineKeyboardMarkup:
    return _kb([[("💳 Balansni to'ldirish", "topup")], [("💎 Tariflar", "plans"), ("⬅️ Bosh sahifa", "home")]])


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
            [("⬅️ Bosh sahifa", "home")],
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
