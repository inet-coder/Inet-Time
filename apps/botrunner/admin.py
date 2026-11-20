"""Bot egasining boshqaruv paneli — foydalanuvchi yaratgan botning O'ZIDA (/admin).

Asosiy bot faqat botni yaratadi va ishlatib turadi; hamma sozlash shu yerda, chat orqali:
    ✏️ Botni tahrirlash  — sahifalar, kontent, tugmalar (editor.py)
    ⚙️ Sozlamalar        — kalit so'zlar, buyruqlar, o'zgaruvchilar, formalar, referal, majburiy obuna,
                           adminlar, qayta aloqa, matnlar
    👤 Foydalanuvchilar  — ID/@username bo'yicha topish, ma'lumotlari, xabar yuborish, bloklash, CSV
    📨 Xabar tarqatish   — istalgan xabar hammaga nusxalanadi
"""

import csv
import datetime
import html
import io
import json
from typing import TYPE_CHECKING

from sqlalchemy import func, select, update

from core.botapi import BotApiError
from core.botbuilder import (
    BUILTIN_VARS,
    apply_op,
    entities_to_html,
    html_to_plain,
    new_page_id,
    page_by_id,
    parse_op,
)
from core.db.base import async_session
from core.db.models import BotBroadcast, BotFormAnswer, BotSubscriber
from core.segments import tags_of
from core.webapp_url import discover_webapp_url

import editor

if TYPE_CHECKING:
    from main import RunningBot, Runner

from core.segments import SEGMENT_RE as SEGMENT_RE_  # noqa: E402
STATE_KEY = "ub:{bot}:ast:{chat}"  # egasining panel holati (JSON yoki eski "bc")
OWNER_HINT_KEY = "ub:{bot}:ownerhint"

OWNER_COMMANDS = [
    {"command": "start", "description": "Bosh menyu"},
    {"command": "admin", "description": "Boshqaruv paneli"},
    {"command": "edit", "description": "Botni tahrirlash"},
]

HELP = (
    "❓ <b>Botni boshqarish</b>\n\n"
    "✏️ <b>Botni tahrirlash</b> — botingizni foydalanuvchi kabi aylanasiz, har sahifa ostida tahrirlash kartasi chiqadi: "
    "kontent (matn, rasm, video, fayl...), tugmalar (qo'shish, ko'chirish, vazifa, shart), inline yoki klaviatura.\n\n"
    "🔑 <b>Kalit so'zlar</b> — foydalanuvchi so'z yozsa, javob yoki sahifa chiqadi.\n"
    "🔢 <b>O'zgaruvchilar</b> — har bir foydalanuvchi uchun alohida eslab qolinadi (ball, telefon, javoblar). "
    "Matnda <code>{ball}</code> ko'rinishida ishlatiladi.\n"
    "📝 <b>Formalar</b> — ketma-ket savollar; javoblar saqlanadi va sizga keladi, CSV yuklab olasiz.\n"
    "👥 <b>Referal</b> — har kimga shaxsiy havola <code>{ref_link}</code>, takliflar soni <code>{ref_count}</code>, mukofot.\n"
    "📢 <b>Majburiy obuna</b> — kanalga obuna bo'lmaguncha bot ishlamaydi (botni kanalga admin qiling).\n\n"
    "💬 Murojaatga javob: kelgan xabarga «Reply» qiling."
)


def _state_key(bot: "RunningBot", chat_id: int) -> str:
    return STATE_KEY.format(bot=bot.bot_id, chat=chat_id)


def esc(text) -> str:
    return html.escape(str(text or ""), quote=False)


async def set_state(runner: "Runner", bot: "RunningBot", chat_id: int, state: dict | None) -> None:
    if state is None:
        await runner.redis.delete(_state_key(bot, chat_id))
    else:
        await runner.redis.set(_state_key(bot, chat_id), json.dumps(state), ex=1800)


async def get_state(runner: "Runner", bot: "RunningBot", chat_id: int) -> dict | None:
    raw = await runner.redis.get(_state_key(bot, chat_id))
    if not raw:
        return None
    if raw == b"bc":
        return {"k": "bc"}
    try:
        return json.loads(raw)
    except ValueError:
        return None


async def show(runner: "Runner", bot: "RunningBot", chat_id: int, text: str, rows: list, message: dict | None = None) -> None:
    await editor.send(runner, bot, chat_id, text, rows, message=message)


async def ask(runner: "Runner", bot: "RunningBot", chat_id: int, state: dict, prompt: str) -> None:
    await set_state(runner, bot, chat_id, state)
    await runner.api(bot, "sendMessage", {"chat_id": chat_id, "text": prompt + "\n\nBekor qilish: /cancel", "parse_mode": "HTML", "disable_web_page_preview": True})


async def _stats(bot_id: int) -> dict:
    now = datetime.datetime.now(datetime.timezone.utc)
    async with async_session() as db:
        base = select(func.count(BotSubscriber.id)).where(BotSubscriber.bot_id == bot_id)
        return {
            "total": await db.scalar(base.where(BotSubscriber.blocked == False)),  # noqa: E712
            "active": await db.scalar(base.where(BotSubscriber.last_active_at >= now - datetime.timedelta(days=1))),
            "today": await db.scalar(base.where(BotSubscriber.started_at >= now - datetime.timedelta(days=1))),
            "blocked": await db.scalar(base.where(BotSubscriber.blocked == True)),  # noqa: E712
        }


# --- Panel ---


async def panel(runner: "Runner", bot: "RunningBot", chat_id: int, message: dict | None = None) -> None:
    stats = await _stats(bot.bot_id)
    m = bot.menu
    text = (
        f"⚙️ <b>Boshqaruv paneli</b> · @{esc(bot.username)}\n\n"
        f"👥 Obunachilar: <b>{stats['total']}</b> · 🟢 24 soatda: {stats['active']}\n"
        f"🆕 Bugun: {stats['today']} · 🚫 Bloklagan: {stats['blocked']}\n\n"
        f"📄 Sahifalar: {len(m.get('pages') or [])} · 🔑 Kalit so'zlar: {len(m.get('keywords') or [])} · 📝 Formalar: {len(m.get('forms') or [])}\n"
        f"👥 Referal: {'✅' if (m.get('referral') or {}).get('enabled') else '❌'} · 📢 Majburiy obuna: {len(m.get('channels') or [])} kanal"
    )
    import home

    rows = [[{"text": "✏️ Botni tahrirlash", "callback_data": "e:on"}]]
    url = await discover_webapp_url()
    if url:
        rows.append([{"text": "🧩 Kompyuterda tahrirlash (Mini App)", "web_app": {"url": f"{url.split('?')[0]}?bot={bot.bot_id}"}}])
    rows += [
        [{"text": "⚙️ Sozlamalar", "callback_data": "adm:cfg"}, {"text": "👤 Foydalanuvchilar", "callback_data": "adm:u"}],
        [{"text": "📨 Xabar tarqatish", "callback_data": "adm:bc"}, {"text": "🔄 Yangilash", "callback_data": "adm:st"}],
        [{"text": "👁 Foydalanuvchi ko'rinishi", "callback_data": "adm:view"}, {"text": "❓ Yordam", "callback_data": "adm:help"}],
    ]
    # Modul bo'limlari (Do'kon, Arizalar...), «Boshlash» ro'yxati, statistika — botdagi modullarga qarab
    at = next(i for i, r in enumerate(rows) if any(b.get("callback_data") == "adm:cfg" for b in r))
    rows = rows[:at] + await home.module_rows(runner, bot) + rows[at:]
    await show(runner, bot, chat_id, text, rows, message)


def settings_menu(bot: "RunningBot") -> tuple[str, list]:
    m = bot.menu
    text = "⚙️ <b>Bot sozlamalari</b>\n\nBo'limni tanlang:"
    rows = [
        [{"text": f"🔑 Kalit so'zlar · {len(m.get('keywords') or [])}", "callback_data": "adm:kw"}, {"text": f"⌨️ Buyruqlar · {len(m.get('commands') or [])}", "callback_data": "adm:cmd"}],
        [{"text": f"🔢 O'zgaruvchilar · {len(m.get('variables') or [])}", "callback_data": "adm:var"}, {"text": f"📝 Formalar · {len(m.get('forms') or [])}", "callback_data": "adm:form"}],
        [{"text": "👥 Referal tizimi", "callback_data": "adm:ref"}, {"text": f"📢 Majburiy obuna · {len(m.get('channels') or [])}", "callback_data": "adm:ch"}],
        [{"text": f"👮 Adminlar · {len(m.get('admins') or [])}", "callback_data": "adm:adm"}, {"text": "💬 Qayta aloqa", "callback_data": "adm:fbk"}],
        [{"text": f"🎨 Tugmalar uslubi: {STYLE_LABELS[m.get('style', 'reply')]}", "callback_data": "adm:sty"}],
        [{"text": "✍️ Javob topilmaganda matn", "callback_data": "adm:txt"}],
        [{"text": "⬅️ Panel", "callback_data": "adm:st"}],
    ]
    return text, rows


STYLE_LABELS = {"reply": "⌨️ Klaviatura", "inline": "💬 Inline", "hybrid": "🔀 Aralash"}
STYLE_HELP = (
    "🎨 <b>Tugmalar uslubi</b> — yangi qo'shiladigan bo'limlar qanday bo'lsin:\n\n"
    "⌨️ <b>Klaviatura</b> — tugmalar yozish maydoni o'rnida (MenuBuilder kabi)\n"
    "💬 <b>Inline</b> — tugmalar xabar ostida, bosilganda xabar joyida almashadi\n"
    "🔀 <b>Aralash</b> — menyular klaviaturada, postlar ostida inline tugmalar\n\n"
    "Har bir bo'limni alohida ham almashtirish mumkin: 🎛 Tugmalar muharriri → 🔁 Klaviatura ⇄ Inline."
)


def _pages_rows(bot: "RunningBot", prefix: str, back: str) -> list:
    rows = [[{"text": p["title"][:64], "callback_data": f"{prefix}{i}"}] for i, p in enumerate((bot.menu.get("pages") or [])[:40])]
    rows.append([{"text": "⬅️ Orqaga", "callback_data": back}])
    return rows


# --- Bo'limlar ---


def keywords_view(bot: "RunningBot") -> tuple[str, list]:
    kws = bot.menu.get("keywords") or []
    match_label = {"exact": "aynan", "contains": "ichida", "start": "boshida"}
    lines = []
    rows = []
    for i, k in enumerate(kws):
        target = page_by_id(bot.menu, k.get("target"))
        what = f"→ «{esc(target['title'])}»" if target else f"→ «{esc(html_to_plain(k.get('reply', ''))[:40])}»"
        lines.append(f"{i + 1}. <b>{esc(', '.join(k['words'])[:60])}</b> ({match_label[k.get('match', 'exact')]}) {what}")
        rows.append([{"text": f"🔁 {i + 1}: {match_label[k.get('match', 'exact')]}", "callback_data": f"adm:kwm:{i}"}, {"text": f"🗑 {i + 1}", "callback_data": f"adm:kwd:{i}"}])
    text = "🔑 <b>Kalit so'zlar</b>\n\nFoydalanuvchi shu so'zni yozsa — javob yoki sahifa chiqadi.\n\n" + ("\n".join(lines) if lines else "Hozircha yo'q.")
    rows.append([{"text": "➕ Kalit so'z qo'shish", "callback_data": "adm:kwa"}])
    rows.append([{"text": "⬅️ Sozlamalar", "callback_data": "adm:cfg"}])
    return text, rows


def commands_view(bot: "RunningBot") -> tuple[str, list]:
    cmds = bot.menu.get("commands") or []
    lines = []
    rows = []
    for i, c in enumerate(cmds):
        p = page_by_id(bot.menu, c["target"])
        lines.append(f"/{c['command']} — {esc(c.get('description', ''))} → «{esc(p['title'] if p else '?')}»")
        rows.append([{"text": f"🗑 /{c['command']}", "callback_data": f"adm:cmdd:{i}"}])
    text = "⌨️ <b>Buyruqlar</b>\n\nBuyruqlar bot menyusida ko'rinadi va sahifani ochadi.\n\n" + ("\n".join(lines) if lines else "Hozircha yo'q.")
    rows.append([{"text": "➕ Buyruq qo'shish", "callback_data": "adm:cmda"}])
    rows.append([{"text": "⬅️ Sozlamalar", "callback_data": "adm:cfg"}])
    return text, rows


def variables_view(bot: "RunningBot") -> tuple[str, list]:
    vs = bot.menu.get("variables") or []
    lines = [
        f"<code>{{{v['key']}}}</code> — {esc(v.get('label') or '')} · {'🌐 umumiy' if v.get('scope') == 'global' else '👤 har kimga'} · boshida: {esc(v.get('default') or '—')}"
        + (f" · hozir: {esc(bot.globals.get(v['key'], ''))}" if v.get("scope") == "global" else "")
        for v in vs
    ]
    rows = [[{"text": f"🗑 {{{v['key']}}}", "callback_data": f"adm:vard:{i}"}] for i, v in enumerate(vs)]
    text = (
        "🔢 <b>O'zgaruvchilar</b>\n\n"
        "👤 <b>har kimga</b> — har bir foydalanuvchi uchun alohida eslab qolinadi (ball, telefon, til...)\n"
        "🌐 <b>umumiy</b> — butun bot uchun bitta (masalan buyurtmalar soni)\n\n"
        "Tizim o'zgaruvchilari: " + " ".join(f"<code>{{{k}}}</code>" for k in BUILTIN_VARS) + "\n\n" + ("\n".join(lines) if lines else "O'zingizniki hozircha yo'q.")
    )
    rows.append([{"text": "➕ O'zgaruvchi qo'shish", "callback_data": "adm:vara"}])
    rows.append([{"text": "⬅️ Sozlamalar", "callback_data": "adm:cfg"}])
    return text, rows


async def forms_view(bot: "RunningBot") -> tuple[str, list]:
    forms = bot.menu.get("forms") or []
    async with async_session() as db:
        counts = dict(
            (
                await db.execute(
                    select(BotFormAnswer.form_id, func.count(BotFormAnswer.id)).where(BotFormAnswer.bot_id == bot.bot_id).group_by(BotFormAnswer.form_id)
                )
            ).all()
        )
    lines = [f"{i + 1}. <b>{esc(f['title'])}</b> — {len(f['steps'])} savol · {counts.get(f['id'], 0)} javob" for i, f in enumerate(forms)]
    rows = [[{"text": f"📝 {f['title']}"[:64], "callback_data": f"adm:fv:{i}"}] for i, f in enumerate(forms)]
    rows.append([{"text": "➕ Yangi forma", "callback_data": "adm:fa"}])
    rows.append([{"text": "⬅️ Sozlamalar", "callback_data": "adm:cfg"}])
    text = (
        "📝 <b>Formalar</b>\n\nForma — ketma-ket savollar (ism, telefon, rasm, tanlov...). Javoblar foydalanuvchi o'zgaruvchilariga "
        "saqlanadi, sizga yuboriladi va CSV yuklab olinadi. Formani tugmaga ulash: ✏️ Tahrirlash → 🔘 Tugma → 🎯 Vazifasi → 📝 Forma.\n\n"
        + ("\n".join(lines) if lines else "Hozircha forma yo'q.")
    )
    return text, rows


TYPE_LABELS = {"text": "📝 Matn", "number": "🔢 Son", "phone": "📱 Telefon", "email": "📧 Email", "photo": "🖼 Rasm", "choice": "🔘 Tanlov", "location": "📍 Joylashuv"}


def form_view(bot: "RunningBot", i: int) -> tuple[str, list] | None:
    forms = bot.menu.get("forms") or []
    if i >= len(forms):
        return None
    f = forms[i]
    steps = "\n".join(
        f"{n + 1}. {TYPE_LABELS.get(s['type'], s['type'])} <code>{{{s['key']}}}</code> — {esc(html_to_plain(s['question'])[:60])}"
        + (f" ({esc(', '.join(s['options']))})" if s.get("options") else "")
        for n, s in enumerate(f["steps"])
    )
    target = page_by_id(bot.menu, f.get("target"))
    text = (
        f"📝 <b>{esc(f['title'])}</b>\n\n{steps}\n\n"
        f"✅ Tugagach: «{esc(html_to_plain(f.get('done_text', ''))[:80])}»\n"
        f"➡️ Keyin ochiladi: {esc(target['title']) if target else 'joriy sahifa'}\n"
        f"🔔 Javoblar sizga keladi: {'✅' if f.get('notify', True) else '❌'}"
    )
    rows = [
        [{"text": "📥 Javoblar (CSV)", "callback_data": f"adm:fx:{i}"}, {"text": f"🔔 Xabar {'✅' if f.get('notify', True) else '❌'}", "callback_data": f"adm:fn:{i}"}],
        [{"text": "➡️ Keyin ochiladigan sahifa", "callback_data": f"adm:ft:{i}"}],
        [{"text": "🗑 O'chirish", "callback_data": f"adm:fd:{i}"}, {"text": "⬅️ Formalar", "callback_data": "adm:form"}],
    ]
    return text, rows


def referral_view(bot: "RunningBot") -> tuple[str, list]:
    ref = bot.menu.get("referral") or {}
    on = ref.get("enabled")
    text = (
        f"👥 <b>Referal tizimi</b> — {'✅ yoqilgan' if on else '❌ o\'chiq'}\n\n"
        f"Har bir foydalanuvchining shaxsiy havolasi: <code>{{ref_link}}</code>\nTaklif qilganlari soni: <code>{{ref_count}}</code>\n"
        f"Har bir yangi do'st uchun: <b>+{ref.get('reward', 1)}</b> → <code>{{{ref.get('var', 'balance')}}}</code>\n"
        f"Taklif qilganga xabar: {'✅' if ref.get('notify', True) else '❌'}\n\n"
        "💡 «👥 Taklif sahifasi» tugmasi bosh menyuga tayyor sahifa qo'shadi: havola, takliflar soni, balans va «📤 Ulashish»."
    )
    rows = [
        [{"text": "❌ O'chirish" if on else "✅ Yoqish", "callback_data": "adm:rft"}],
        [{"text": f"🎁 Mukofot: {ref.get('reward', 1)}", "callback_data": "adm:rfr"}, {"text": f"🔢 {{{ref.get('var', 'balance')}}}", "callback_data": "adm:rfv"}],
        [{"text": "✍️ Xabar matni", "callback_data": "adm:rfx"}, {"text": f"🔔 Xabar {'✅' if ref.get('notify', True) else '❌'}", "callback_data": "adm:rfn"}],
        [{"text": "👥 Taklif sahifasini qo'shish", "callback_data": "adm:rfp"}],
        [{"text": "⬅️ Sozlamalar", "callback_data": "adm:cfg"}],
    ]
    return text, rows


def channels_view(bot: "RunningBot") -> tuple[str, list]:
    chs = bot.menu.get("channels") or []
    lines = [f"{i + 1}. {esc(c.get('title') or c['chat'])} · <code>{esc(c['chat'])}</code>" for i, c in enumerate(chs)]
    rows = [[{"text": f"🗑 {c.get('title') or c['chat']}"[:64], "callback_data": f"adm:chd:{i}"}] for i, c in enumerate(chs)]
    text = (
        "📢 <b>Majburiy obuna</b>\n\nFoydalanuvchi shu kanallarga obuna bo'lmaguncha bot javob bermaydi.\n"
        "⚠️ Botingizni har bir kanalga <b>admin</b> qiling — aks holda obunani tekshirib bo'lmaydi.\n\n"
        + ("\n".join(lines) if lines else "Kanal qo'shilmagan — majburiy obuna o'chiq.")
        + f"\n\nXabar: «{esc(bot.menu.get('sub_text', ''))[:150]}»"
    )
    rows.append([{"text": "➕ Kanal qo'shish", "callback_data": "adm:cha"}, {"text": "✍️ Xabar matni", "callback_data": "adm:cht"}])
    rows.append([{"text": "⬅️ Sozlamalar", "callback_data": "adm:cfg"}])
    return text, rows


def admins_view(bot: "RunningBot") -> tuple[str, list]:
    admins = bot.menu.get("admins") or []
    lines = [f"{i + 1}. <code>{a}</code>" for i, a in enumerate(admins)]
    rows = [[{"text": f"🗑 {a}", "callback_data": f"adm:admd:{i}"}] for i, a in enumerate(admins)]
    text = (
        "👮 <b>Adminlar</b>\n\nAdminlar botni tahrirlay oladi, murojaatlar va forma javoblarini oladi, xabar tarqata oladi.\n\n"
        + ("\n".join(lines) if lines else "Faqat siz.")
    )
    rows.append([{"text": "➕ Admin qo'shish", "callback_data": "adm:adma"}])
    rows.append([{"text": "⬅️ Sozlamalar", "callback_data": "adm:cfg"}])
    return text, rows


def feedback_view(bot: "RunningBot") -> tuple[str, list]:
    m = bot.menu
    text = (
        "💬 <b>Qayta aloqa</b>\n\n"
        f"📥 Menyuda yo'q har qanday xabar sizga kelsin: {'✅' if m.get('forward_all') else '❌'}\n"
        f"🕶 Anonim (yozuvchi ismi ko'rsatilmasin): {'✅' if m.get('feedback_anonymous') else '❌'}\n\n"
        f"«Adminga yozish» bosilganda: «{esc(m.get('feedback_prompt', ''))[:100]}»\n"
        f"Yuborilgach: «{esc(m.get('feedback_done', ''))[:100]}»\n\nJavob berish: kelgan xabarga «Reply» qiling."
    )
    rows = [
        [{"text": f"📥 Hammasi menga {'✅' if m.get('forward_all') else '❌'}", "callback_data": "adm:fwd"}, {"text": f"🕶 Anonim {'✅' if m.get('feedback_anonymous') else '❌'}", "callback_data": "adm:anon"}],
        [{"text": "✍️ So'rov matni", "callback_data": "adm:fbp"}, {"text": "✍️ Tasdiq matni", "callback_data": "adm:fbd"}],
        [{"text": "⬅️ Sozlamalar", "callback_data": "adm:cfg"}],
    ]
    return text, rows


async def users_view(bot: "RunningBot") -> tuple[str, list]:
    stats = await _stats(bot.bot_id)
    text = (
        f"👤 <b>Foydalanuvchilar</b>: {stats['total']}\n\n"
        "Topish uchun foydalanuvchi <b>ID</b> raqamini yoki <b>@username</b>ini yuboring (yoki uning xabarini forward qiling) — "
        "ma'lumotlari, o'zgaruvchilari va takliflari ko'rinadi; xabar yuborish, bloklash mumkin."
    )
    rows = [
        [{"text": "🔍 Qidirish", "callback_data": "adm:uf"}, {"text": "📥 Ro'yxat (CSV)", "callback_data": "adm:ux"}],
        [{"text": "⬅️ Panel", "callback_data": "adm:st"}],
    ]
    return text, rows


async def user_card(bot: "RunningBot", tg_id: int) -> tuple[str, list] | None:
    async with async_session() as db:
        s = await db.scalar(select(BotSubscriber).where(BotSubscriber.bot_id == bot.bot_id, BotSubscriber.tg_user_id == tg_id))
    if s is None:
        return None
    data = s.data or {}
    vars_text = "\n".join(f"<code>{{{esc(k)}}}</code> = {esc(str(v))[:100]}" for k, v in data.items() if not k.startswith("_")) or "—"
    text = (
        f"👤 <b>{esc(s.first_name or 'Foydalanuvchi')}</b>" + (f" (@{esc(s.username)})" if s.username else "") + "\n"
        f"🆔 <code>{s.tg_user_id}</code>\n"
        f"📅 Qo'shilgan: {s.started_at:%d.%m.%Y %H:%M} · faol: {s.last_active_at:%d.%m.%Y %H:%M}\n"
        f"👥 Taklif qilgan: {s.ref_count or 0}" + (f" · uni taklif qilgan: <code>{s.referred_by}</code>" if s.referred_by else "") + "\n"
        + ("🚫 Botni bloklagan\n" if s.blocked else "")
        + ("⛔️ Siz bloklagansiz\n" if s.banned else "")
        + (f"🏷 Teglar: {', '.join(esc(t) for t in tags_of(data))}\n" if tags_of(data) else "")
        + f"\n🔢 <b>Ma'lumotlari</b>:\n{vars_text}"
    )
    rows = [
        [{"text": "✉️ Xabar yuborish", "callback_data": f"adm:um:{tg_id}"}, {"text": "🔢 O'zgaruvchi", "callback_data": f"adm:uv:{tg_id}"}],
        [{"text": "🏷 Teg qo'shish/olish", "callback_data": f"adm:ut:{tg_id}"}, {"text": "✅ Blokdan chiqarish" if s.banned else "⛔️ Bloklash", "callback_data": f"adm:ub:{tg_id}"}],
        [{"text": "⬅️ Foydalanuvchilar", "callback_data": "adm:u"}],
    ]
    return text, rows


# --- Yordamchi ---


async def set_owner_commands(runner: "Runner", bot: "RunningBot") -> None:
    commands = OWNER_COMMANDS + [
        {"command": c["command"], "description": (c.get("description") or c["command"])[:256]} for c in bot.menu.get("commands") or []
    ]
    for chat in runner.admin_chats(bot):
        try:
            await runner.api(bot, "setMyCommands", {"commands": commands, "scope": {"type": "chat", "chat_id": chat}})
        except Exception:  # noqa: BLE001 — admin botga hali kirmagan bo'lishi mumkin
            pass


async def owner_started(runner: "Runner", bot: "RunningBot", chat_id: int) -> None:
    """Egasi /start bosdi: buyruqlar menyusi va (haftada bir) panel haqida eslatma."""
    await set_owner_commands(runner, bot)
    if await runner.redis.set(OWNER_HINT_KEY.format(bot=bot.bot_id), "1", nx=True, ex=7 * 24 * 3600):
        await runner.api(
            bot,
            "sendMessage",
            {
                "chat_id": chat_id,
                "text": "ℹ️ Siz ushbu botning egasisiz — klaviaturangizda qo'shimcha tugmalar bor:\n\n"
                "🎛 Tugmalar muharriri — tugmalarni qo'shish, ko'chirish, vazifa berish\n"
                "📝 Postlar muharriri — har bir tugmaning xabarlari (matn, rasm, video...)\n"
                "🤖 InetTime AI — botni suhbat orqali tuzish: «restoran boti kerak…» deb yozasiz\n"
                "⚙️ Admin panel — sozlamalar, foydalanuvchilar, xabar tarqatish\n\n"
                "Foydalanuvchilar bu tugmalarni ko'rmaydi.",
            },
        )


async def _csv_send(runner: "Runner", bot: "RunningBot", chat_id: int, name: str, header: list, rows: list, caption: str) -> None:
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(header)
    w.writerows(rows)
    data = ("﻿" + buf.getvalue()).encode("utf-8")
    await runner.api(bot, "sendDocument", {"chat_id": chat_id, "caption": caption}, {"document": (name, data, "text/csv")})


async def save(runner: "Runner", bot: "RunningBot", chat_id: int, fn) -> bool:
    error = await editor.save(runner, bot, fn)
    if error:
        await runner.api(bot, "sendMessage", {"chat_id": chat_id, "text": f"⚠️ {error}"})
        return False
    return True


# --- Callbacklar ---


async def on_callback(runner: "Runner", bot: "RunningBot", chat_id: int, data: str, message: dict, user: dict) -> None:
    parts = data.split(":")
    action = parts[1] if len(parts) > 1 else ""
    arg = parts[2] if len(parts) > 2 else None
    i = int(arg) if arg is not None and arg.lstrip("-").isdigit() else None

    async def view(tr) -> None:
        if tr is not None:
            await show(runner, bot, chat_id, tr[0], tr[1], message)

    if action == "st":
        await set_state(runner, bot, chat_id, None)
        await panel(runner, bot, chat_id, message)
    elif action == "help":
        await view((HELP, [[{"text": "⬅️ Panel", "callback_data": "adm:st"}]]))
    elif action == "stats":
        import home

        await view(await home.stats_view(runner, bot))
    elif action == "mods":
        import home

        await view(home.mods_view(bot))
    elif action == "todo":
        import home

        await view(await home.todo_view(runner, bot))
    elif action == "share":
        import home

        await view(await home.share_view(runner, bot))
    elif action == "su":
        import home

        await home.wizard_next(runner, bot, chat_id, intro=True)
    elif action == "suskip":
        import home

        state = await get_state(runner, bot, chat_id) or {}
        if state.get("k") == "setup":
            await home.wizard_answer(runner, bot, chat_id, user, state, None)
    elif action == "view":
        import home

        await home.set_flag(runner, bot, "tried")
        await editor.set_mode(runner, bot, chat_id, None)
        start = page_by_id(bot.menu, bot.menu.get("start"))
        if start is not None:
            await runner.redis.set(f"ub:{bot.bot_id}:cur:{chat_id}", start["id"])
            await runner.send_page(bot, chat_id, start, user, with_branding=True)
    elif action == "cfg":
        await set_state(runner, bot, chat_id, None)
        await view(settings_menu(bot))
    elif action == "sty":
        order = ["reply", "inline", "hybrid"]

        def cycle(m):
            m["style"] = order[(order.index(m.get("style", "reply")) + 1) % 3]

        if await save(runner, bot, chat_id, cycle):
            tr = settings_menu(bot)
            await view((STYLE_HELP + "\n\nHozir: <b>" + STYLE_LABELS[bot.menu["style"]] + "</b>", tr[1]))

    # Kalit so'zlar
    elif action == "kw":
        await view(keywords_view(bot))
    elif action == "kwa":
        await ask(runner, bot, chat_id, {"k": "kw_words"}, "🔑 Kalit so'z(lar)ni yuboring — bir nechtasini vergul bilan:\n<code>narx, price, qancha</code>")
    elif action == "kwd" and i is not None:
        if await save(runner, bot, chat_id, lambda m: m["keywords"].pop(i)):
            await view(keywords_view(bot))
    elif action == "kwm" and i is not None:
        order = ["exact", "contains", "start"]

        def cycle(m):
            k = m["keywords"][i]
            k["match"] = order[(order.index(k.get("match", "exact")) + 1) % 3]

        if await save(runner, bot, chat_id, cycle):
            await view(keywords_view(bot))
    elif action == "kwp" and i is not None:
        state = await get_state(runner, bot, chat_id) or {}
        words = state.get("words")
        pages = bot.menu.get("pages") or []
        if words and i < len(pages):
            await set_state(runner, bot, chat_id, None)
            if await save(runner, bot, chat_id, lambda m: m["keywords"].append({"words": words, "match": "contains", "target": pages[i]["id"], "reply": ""})):
                await view(keywords_view(bot))
    elif action == "kwr":
        state = await get_state(runner, bot, chat_id) or {}
        if state.get("words"):
            await ask(runner, bot, chat_id, {"k": "kw_reply", "words": state["words"]}, "💬 Javob matnini yuboring (formatlash saqlanadi, o'zgaruvchilar ishlaydi).")

    # Buyruqlar
    elif action == "cmd":
        await view(commands_view(bot))
    elif action == "cmda":
        await ask(runner, bot, chat_id, {"k": "cmd_name"}, "⌨️ Buyruq va izohini yuboring:\n<code>narx Narxlar ro'yxati</code>\n(/narx buyrug'i yaratiladi)")
    elif action == "cmdd" and i is not None:
        if await save(runner, bot, chat_id, lambda m: m["commands"].pop(i)):
            await view(commands_view(bot))
    elif action == "cmdp" and i is not None:
        state = await get_state(runner, bot, chat_id) or {}
        pages = bot.menu.get("pages") or []
        if state.get("command") and i < len(pages):
            await set_state(runner, bot, chat_id, None)
            item = {"command": state["command"], "description": state.get("description", ""), "target": pages[i]["id"]}
            if await save(runner, bot, chat_id, lambda m: m["commands"].append(item)):
                await view(commands_view(bot))

    # O'zgaruvchilar
    elif action == "var":
        await view(variables_view(bot))
    elif action == "vara":
        await ask(
            runner,
            bot,
            chat_id,
            {"k": "var_add"},
            "🔢 O'zgaruvchini yuboring: <code>nom [boshlang'ich qiymat] [global]</code>\n\n"
            "<code>ball 0</code> — har bir foydalanuvchiga alohida ball\n<code>til uz</code>\n<code>buyurtmalar 0 global</code> — butun bot uchun bitta hisoblagich",
        )
    elif action == "vard" and i is not None:
        if await save(runner, bot, chat_id, lambda m: m["variables"].pop(i)):
            await view(variables_view(bot))

    # Formalar
    elif action == "form":
        await set_state(runner, bot, chat_id, None)
        await view(await forms_view(bot))
    elif action == "fa":
        await ask(runner, bot, chat_id, {"k": "form_title"}, "📝 Forma nomini yuboring (masalan «Ro'yxatdan o'tish», «Buyurtma»).")
    elif action == "fv" and i is not None:
        await view(form_view(bot, i))
    elif action == "fd" and i is not None:
        forms = bot.menu.get("forms") or []
        if i < len(forms):
            fid = forms[i]["id"]
            used = [b for p in bot.menu["pages"] for row in p.get("buttons") or [] for b in row if b.get("form") == fid]
            if used:
                await runner.api(bot, "sendMessage", {"chat_id": chat_id, "text": f"⚠️ Bu forma {len(used)} ta tugmada ishlatilmoqda — avval o'sha tugmalar vazifasini o'zgartiring."})
                return
            if await save(runner, bot, chat_id, lambda m: m["forms"].pop(i)):
                await view(await forms_view(bot))
    elif action == "fn" and i is not None:

        def flip(m):
            m["forms"][i]["notify"] = not m["forms"][i].get("notify", True)

        if await save(runner, bot, chat_id, flip):
            await view(form_view(bot, i))
    elif action == "ft" and i is not None:
        rows = _pages_rows(bot, f"adm:ftp:{i}:", f"adm:fv:{i}")
        rows.insert(0, [{"text": "↩️ Joriy sahifa (o'zgarmasin)", "callback_data": f"adm:ftp:{i}:-1"}])
        await view(("➡️ Forma tugagach qaysi sahifa ochilsin?", rows))
    elif action == "ftp" and i is not None and len(parts) > 3:
        j = int(parts[3])
        pages = bot.menu.get("pages") or []

        def set_target(m):
            m["forms"][i]["target"] = pages[j]["id"] if 0 <= j < len(pages) else None

        if await save(runner, bot, chat_id, set_target):
            await view(form_view(bot, i))
    elif action == "fx" and i is not None:
        forms = bot.menu.get("forms") or []
        if i < len(forms):
            f = forms[i]
            async with async_session() as db:
                answers = (
                    await db.execute(
                        select(BotFormAnswer.tg_user_id, BotFormAnswer.data, BotFormAnswer.created_at)
                        .where(BotFormAnswer.bot_id == bot.bot_id, BotFormAnswer.form_id == f["id"])
                        .order_by(BotFormAnswer.id.desc())
                        .limit(20000)
                    )
                ).all()
            keys = [s["key"] for s in f["steps"]]
            rows = [[a.created_at.strftime("%d.%m.%Y %H:%M"), a.tg_user_id, *[a.data.get(k, "") for k in keys]] for a in answers]
            await _csv_send(runner, bot, chat_id, f"{f['id']}.csv", ["sana", "user_id", *keys], rows, f"📝 {f['title']}: {len(rows)} ta javob")
    elif action == "fty":
        state = await get_state(runner, bot, chat_id) or {}
        if state.get("k") == "form_type" and arg:
            if arg == "choice":
                state.update({"k": "form_opts", "type": "choice"})
                await ask(runner, bot, chat_id, state, "🔘 Variantlarni vergul bilan yuboring:\n<code>Erkak, Ayol</code>")
            else:
                state["steps"].append({"key": state["key"], "question": state["question"], "type": arg, "options": []})
                await form_next(runner, bot, chat_id, state)
    elif action == "fmore":
        state = await get_state(runner, bot, chat_id) or {}
        if state.get("k") == "form_next":
            state["k"] = "form_q"
            await ask(runner, bot, chat_id, state, _question_prompt(len(state["steps"]) + 1))
    elif action == "fdone":
        state = await get_state(runner, bot, chat_id) or {}
        if state.get("k") == "form_next":
            state["k"] = "form_done"
            await ask(runner, bot, chat_id, state, "✅ Forma tugagach foydalanuvchiga yuboriladigan matn (javoblar ham ishlaydi: <code>{ism}</code>).\nStandart matn uchun: -")

    # Referal
    elif action == "ref":
        await view(referral_view(bot))
    elif action in ("rft", "rfn"):
        key = "enabled" if action == "rft" else "notify"

        def flip(m):
            m.setdefault("referral", {})
            m["referral"][key] = not m["referral"].get(key, key == "notify")

        if await save(runner, bot, chat_id, flip):
            await view(referral_view(bot))
    elif action == "rfr":
        await ask(runner, bot, chat_id, {"k": "ref_reward"}, "🎁 Har bir taklif uchun mukofot (son), masalan <code>5</code>. Mukofotsiz: <code>0</code>")
    elif action == "rfv":
        await ask(runner, bot, chat_id, {"k": "ref_var"}, "🔢 Mukofot qaysi o'zgaruvchiga qo'shilsin? Masalan <code>balance</code> yoki <code>ball</code>")
    elif action == "rfx":
        await ask(runner, bot, chat_id, {"k": "ref_text"}, "✍️ Taklif qilgan odamga boradigan xabar. <code>{name}</code> — yangi do'st ismi, <code>{reward}</code> — mukofot.")
    elif action == "rfp":
        await add_referral_page(runner, bot, chat_id, user)

    # Kanallar
    elif action == "ch":
        await view(channels_view(bot))
    elif action == "cha":
        await ask(
            runner,
            bot,
            chat_id,
            {"k": "ch_add"},
            "📢 Kanal <b>@username</b>ini yuboring yoki kanaldan istalgan postni shu yerga <b>forward</b> qiling (yopiq kanallar uchun).\n"
            "Avval botingizni kanalga admin qiling.",
        )
    elif action == "chd" and i is not None:
        if await save(runner, bot, chat_id, lambda m: m["channels"].pop(i)):
            await view(channels_view(bot))
    elif action == "cht":
        await ask(runner, bot, chat_id, {"k": "sub_text"}, "✍️ Obuna bo'lish so'raladigan xabar matnini yuboring.")

    # Adminlar
    elif action == "adm":
        await view(admins_view(bot))
    elif action == "adma":
        if chat_id != bot.owner_chat_id:
            await runner.api(bot, "sendMessage", {"chat_id": chat_id, "text": "⚠️ Adminlarni faqat bot egasi qo'sha oladi."})
            return
        await ask(runner, bot, chat_id, {"k": "admin_add"}, "👮 Yangi admin ID raqamini yuboring yoki uning xabarini forward qiling.\nU avval botingizga /start bosgan bo'lishi kerak.")
    elif action == "admd" and i is not None:
        if chat_id != bot.owner_chat_id:
            return
        if await save(runner, bot, chat_id, lambda m: m["admins"].pop(i)):
            await set_owner_commands(runner, bot)
            await view(admins_view(bot))

    # Qayta aloqa
    elif action in ("fbk", "fwd", "anon"):
        if action != "fbk":
            key = "forward_all" if action == "fwd" else "feedback_anonymous"

            def flip(m):
                m[key] = not m.get(key)

            if not await save(runner, bot, chat_id, flip):
                return
        await view(feedback_view(bot))
    elif action in ("fbp", "fbd", "txt"):
        kind = {"fbp": "feedback_prompt", "fbd": "feedback_done", "txt": "fallback"}[action]
        current = bot.menu.get(kind, "")
        await ask(runner, bot, chat_id, {"k": "text", "field": kind}, f"✍️ Yangi matnni yuboring.\n\nHozirgi: «{esc(current)}»")

    # Foydalanuvchilar
    elif action == "ut":
        await ask(runner, bot, chat_id, {"k": "user_tag", "id": int(arg) if arg and arg.isdigit() else i}, "🏷 Teg nomini yuboring (lotin harf/raqam, 12 belgigacha). Bor bo'lsa — olib tashlanadi, yo'q bo'lsa — qo'shiladi.")
    elif action == "u":
        await set_state(runner, bot, chat_id, None)
        await view(await users_view(bot))
    elif action == "uf":
        await ask(runner, bot, chat_id, {"k": "user_find"}, "🔍 Foydalanuvchi ID raqami yoki @username yuboring (yoki xabarini forward qiling).")
    elif action == "ux":
        async with async_session() as db:
            subs = (await db.scalars(select(BotSubscriber).where(BotSubscriber.bot_id == bot.bot_id).order_by(BotSubscriber.id).limit(100000))).all()
        keys = sorted({k for s in subs for k in (s.data or {})})
        rows = [
            [s.tg_user_id, s.first_name or "", s.username or "", s.started_at.strftime("%d.%m.%Y"), "ha" if s.blocked else "", s.ref_count or 0, *[(s.data or {}).get(k, "") for k in keys]]
            for s in subs
        ]
        await _csv_send(runner, bot, chat_id, "users.csv", ["user_id", "ism", "username", "qo'shilgan", "bloklagan", "takliflar", *keys], rows, f"👤 {len(rows)} ta foydalanuvchi")
    elif action == "um" and i is not None:
        await ask(runner, bot, chat_id, {"k": "user_msg", "id": i}, "✉️ Foydalanuvchiga yuboriladigan xabarni yuboring (istalgan turdagi).")
    elif action == "uv" and i is not None:
        await ask(runner, bot, chat_id, {"k": "user_var", "id": i}, "🔢 O'zgartirish: <code>ball = 100</code>, <code>ball +10</code>, <code>vip = 1</code>, <code>promo tozalash</code>")
    elif action == "ub" and i is not None:
        async with async_session() as db:
            s = await db.scalar(select(BotSubscriber).where(BotSubscriber.bot_id == bot.bot_id, BotSubscriber.tg_user_id == i))
            if s is not None:
                s.banned = not s.banned
                await db.commit()
        await view(await user_card(bot, i))

    # Tarqatish
    elif action == "bc":
        await ask(
            runner,
            bot,
            chat_id,
            {"k": "bc"},
            "📨 Tarqatiladigan xabarni yuboring.\n\nMatn, rasm, video, fayl yoki ovozli xabar bo'lishi mumkin — "
            "u barcha obunachilarga aynan shu ko'rinishda boradi.",
        )
    elif action == "bcs" and i is not None:
        await _bc_confirm(runner, bot, chat_id, i, ":".join(parts[3:]) or "all", message)
    elif action == "bcok" and i is not None:
        await _start_broadcast(runner, bot, chat_id, i, message, ":".join(parts[3:]) or "all")
    elif action == "bcno":
        await runner.api(bot, "editMessageText", {"chat_id": chat_id, "message_id": message["message_id"], "text": "❌ Bekor qilindi."})


def _question_prompt(n: int) -> str:
    return (
        f"❓ {n}-savolni yuboring.\n\n"
        "Javob saqlanadigan o'zgaruvchi nomini oldiga qo'yish mumkin: <code>ism | Ismingiz nima?</code>\n"
        f"(yozilmasa — <code>javob{n}</code>)"
    )


async def form_next(runner: "Runner", bot: "RunningBot", chat_id: int, state: dict) -> None:
    state["k"] = "form_next"
    await set_state(runner, bot, chat_id, state)
    lines = "\n".join(f"{n + 1}. {TYPE_LABELS[s['type']]} {{{s['key']}}} — {esc(html_to_plain(s['question'])[:50])}" for n, s in enumerate(state["steps"]))
    await runner.api(
        bot,
        "sendMessage",
        {
            "chat_id": chat_id,
            "parse_mode": "HTML",
            "text": f"📝 <b>{esc(state['title'])}</b>\n\n{lines}",
            "reply_markup": {"inline_keyboard": [[{"text": "➕ Yana savol", "callback_data": "adm:fmore"}, {"text": "✅ Tugatish", "callback_data": "adm:fdone"}]]},
        },
    )


async def add_referral_page(runner: "Runner", bot: "RunningBot", chat_id: int, user: dict) -> None:
    ref = bot.menu.get("referral") or {}
    var = ref.get("var") or "balance"
    pid = new_page_id()
    page = {
        "id": pid,
        "title": "👥 Do'stlarni taklif qilish",
        "text": "Do'stlarni taklif qiling",
        "media_id": None,
        "messages": [
            {
                "type": "text",
                "text": "👥 <b>Do'stlaringizni taklif qiling!</b>\n\nHar bir taklif qilgan do'stingiz uchun mukofot olasiz.\n\n"
                f"🔗 Sizning havolangiz:\n{{ref_link}}\n\n👤 Taklif qilganlaringiz: <b>{{ref_count}}</b>\n💰 Balans: <b>{{{var}}}</b>",
                "file_id": None,
                "media_id": None,
            }
        ],
        "keyboard": "inline",
        "buttons": [
            [{"text": "📤 Do'stlarga ulashish", "action": "share", "share_text": f"{bot.name} — qo'shiling! {{ref_link}}"}],
            [{"text": "⬅️ Orqaga", "action": "back"}],
        ],
    }

    def add(m):
        m.setdefault("referral", {})["enabled"] = True
        m["pages"].append(page)
        if not any(v["key"] == var for v in m.get("variables") or []):
            m.setdefault("variables", []).append({"key": var, "label": "Balans", "default": "0", "scope": "user"})
        start = page_by_id(m, m["start"])
        start["buttons"].append([{"text": "👥 Do'stlarni taklif qilish", "action": "page", "target": pid}])

    if await save(runner, bot, chat_id, add):
        await runner.api(bot, "sendMessage", {"chat_id": chat_id, "text": "✅ Referal yoqildi va bosh menyuga «👥 Do'stlarni taklif qilish» tugmasi qo'shildi."})
        await editor.reopen(runner, bot, chat_id, pid, user)


# --- Kiritishlar ---


def _forward_chat(message: dict) -> dict | None:
    origin = message.get("forward_origin") or {}
    if origin.get("type") == "channel":
        return origin.get("chat")
    return message.get("forward_from_chat")


def _forward_user(message: dict) -> int | None:
    origin = message.get("forward_origin") or {}
    if origin.get("type") == "user":
        return origin.get("sender_user", {}).get("id")
    return (message.get("forward_from") or {}).get("id")


async def on_message(runner: "Runner", bot: "RunningBot", message: dict) -> bool:
    """Admin xabari panelga tegishli bo'lsa — qayta ishlab True qaytaradi."""
    chat_id = message["chat"]["id"]
    text = (message.get("text") or "").strip()
    if text in ("/admin", "/start admin"):
        await set_state(runner, bot, chat_id, None)
        await set_owner_commands(runner, bot)
        await panel(runner, bot, chat_id)
        return True
    state = await get_state(runner, bot, chat_id)
    if state is None:
        return False
    if text == "/cancel":
        await set_state(runner, bot, chat_id, None)
        await runner.api(bot, "sendMessage", {"chat_id": chat_id, "text": "❌ Bekor qilindi."})
        return True
    kind = state.get("k")
    if kind == "setup":
        import home

        if text:
            await home.wizard_answer(runner, bot, chat_id, message["from"], state, text)
        return True
    if str(kind).startswith("shop_"):
        import shop

        return await shop.admin_input(runner, bot, chat_id, message, state)
    if str(kind).startswith("fl_"):
        import flows

        return await flows.admin_input(runner, bot, chat_id, message, state)
    if str(kind).startswith("wh_"):
        import integrations

        return await integrations.admin_input(runner, bot, chat_id, message, state)
    if str(kind).startswith("pc_"):
        import posting

        return await posting.admin_input(runner, bot, chat_id, message, state)
    if str(kind).startswith("tk_"):
        import tickets

        return await tickets.admin_input(runner, bot, chat_id, message, state)
    if str(kind).startswith("gm_"):
        import games

        return await games.admin_input(runner, bot, chat_id, message, state)
    if str(kind).startswith("au_"):
        import auto

        return await auto.admin_input(runner, bot, chat_id, message, state)
    if str(kind).startswith("bk_"):
        import booking

        return await booking.admin_input(runner, bot, chat_id, message, state)

    async def say(t: str, rows: list | None = None) -> None:
        data = {"chat_id": chat_id, "text": t, "parse_mode": "HTML", "disable_web_page_preview": True}
        if rows:
            data["reply_markup"] = {"inline_keyboard": rows}
        await runner.api(bot, "sendMessage", data)

    # --- Istalgan turdagi xabarni qabul qiladiganlar ---
    if kind == "bc":
        await set_state(runner, bot, chat_id, None)
        await _bc_confirm(runner, bot, chat_id, message["message_id"], "all", None)
        return True
    if str(kind).startswith("tl_"):
        import tables

        return await tables.admin_input(runner, bot, chat_id, message, state)
    if kind == "user_tag" or str(kind).startswith("sg_"):
        import crm

        return await crm.admin_input(runner, bot, chat_id, message, state)
    if kind == "user_msg":
        await set_state(runner, bot, chat_id, None)
        try:
            await runner.api(bot, "copyMessage", {"chat_id": state["id"], "from_chat_id": chat_id, "message_id": message["message_id"]})
            await say("✅ Yuborildi")
        except BotApiError as exc:
            await say(f"⚠️ Yuborilmadi: {esc('foydalanuvchi botni bloklagan' if exc.user_blocked else exc.description)}")
        return True
    if kind == "ch_add":
        chat = _forward_chat(message)
        ref = str(chat["id"]) if chat else text
        if ref and not ref.startswith(("@", "-")):
            ref = "@" + ref.split("/")[-1].lstrip("@") if "t.me/" in ref or ref.isidentifier() else ref
        try:
            info = await runner.api(bot, "getChat", {"chat_id": ref})
        except BotApiError as exc:
            await say(f"⚠️ Kanal topilmadi: {esc(exc.description)}\nBotni kanalga admin qilib, qayta urinib ko'ring.")
            return True
        me_id = int(bot.token.split(":")[0])
        try:
            member = await runner.api(bot, "getChatMember", {"chat_id": info["id"], "user_id": me_id})
            is_admin = member.get("status") in ("administrator", "creator")
        except BotApiError:
            is_admin = False
        chat_ref = f"@{info['username']}" if info.get("username") else str(info["id"])
        url = f"https://t.me/{info['username']}" if info.get("username") else info.get("invite_link")
        item = {"chat": chat_ref, "title": (info.get("title") or chat_ref)[:64], "url": url}
        if any(c["chat"] == chat_ref for c in bot.menu.get("channels") or []):
            await say("ℹ️ Bu kanal allaqachon qo'shilgan.")
            await set_state(runner, bot, chat_id, None)
            return True
        if not await save(runner, bot, chat_id, lambda m: m.setdefault("channels", []).append(item)):
            return True
        warn = "" if is_admin else "\n\n⚠️ Bot bu kanalda admin emas — obunani tekshirish ishlamaydi. Botni kanalga admin qiling."
        if not url:
            warn += "\n⚠️ Kanal havolasi topilmadi (yopiq kanal) — botga «Invite link» huquqini bering."
        await set_state(runner, bot, chat_id, None)
        tr = channels_view(bot)
        await say("✅ Kanal qo'shildi" + warn + "\n\n" + tr[0], tr[1])
        return True
    if kind in ("admin_add", "user_find"):
        fwd = _forward_user(message)
        target_id = None
        if fwd:
            target_id = fwd
        elif text.lstrip("-").isdigit():
            target_id = int(text)
        elif text.startswith("@") and kind == "user_find":
            async with async_session() as db:
                target_id = await db.scalar(
                    select(BotSubscriber.tg_user_id).where(BotSubscriber.bot_id == bot.bot_id, func.lower(BotSubscriber.username) == text[1:].lower())
                )
        if not target_id:
            await say("⚠️ Topilmadi. ID raqam yoki @username yuboring (forward qilingan xabarda yashirin profil bo'lsa, ID kerak).")
            return True
        if kind == "admin_add":
            if not await save(runner, bot, chat_id, lambda m: m.setdefault("admins", []).append(target_id)):
                return True
            await set_owner_commands(runner, bot)
            await set_state(runner, bot, chat_id, None)
            tr = admins_view(bot)
            await say("✅ Admin qo'shildi. U /admin buyrug'i bilan panelga kira oladi.\n\n" + tr[0], tr[1])
            return True
        tr = await user_card(bot, target_id)
        await set_state(runner, bot, chat_id, None)
        if tr is None:
            await say("⚠️ Bu foydalanuvchi botingizdan foydalanmagan.")
        else:
            await say(tr[0], tr[1])
        return True
    if kind == "kw_reply":
        reply_html = entities_to_html(message.get("text") or message.get("caption") or "", message.get("entities") or message.get("caption_entities"))
        if not reply_html.strip():
            await say("✍️ Javobni matn ko'rinishida yuboring")
            return True
        words = state["words"]
        if not await save(runner, bot, chat_id, lambda m: m["keywords"].append({"words": words, "match": "contains", "target": None, "reply": reply_html})):
            return True
        await set_state(runner, bot, chat_id, None)
        tr = keywords_view(bot)
        await say("✅ Saqlandi\n\n" + tr[0], tr[1])
        return True

    if not text:
        await say("✍️ Matn ko'rinishida yuboring yoki /cancel")
        return True

    if kind == "kw_words":
        words = [w.strip().lower() for w in text.split(",") if w.strip()][:30]
        if not words:
            await say("⚠️ Bo'sh")
            return True
        await set_state(runner, bot, chat_id, {"k": "kw_pick", "words": words})
        rows = [[{"text": "💬 Javob matni yozish", "callback_data": "adm:kwr"}]] + _pages_rows(bot, "adm:kwp:", "adm:kw")
        await say(f"🔑 <b>{esc(', '.join(words))}</b>\n\nBu so'z yozilganda nima bo'lsin? Javob matnini yozing yoki ochiladigan sahifani tanlang:", rows)
        return True
    if kind == "cmd_name":
        name, _, desc = text.lstrip("/").partition(" ")
        name = name.lower()
        if not name.replace("_", "").isalnum() or not name.isascii() or name in ("start", "admin", "cancel", "edit"):
            await say("⚠️ Buyruq nomi faqat lotin harf, raqam va _ bo'lsin (start, admin band).")
            return True
        if any(c["command"] == name for c in bot.menu.get("commands") or []):
            await say("⚠️ Bunday buyruq bor.")
            return True
        await set_state(runner, bot, chat_id, {"k": "cmd_pick", "command": name[:32], "description": (desc or name)[:256]})
        await say(f"⌨️ /{esc(name)} qaysi sahifani ochsin?", _pages_rows(bot, "adm:cmdp:", "adm:cmd"))
        return True
    if kind == "var_add":
        parts = text.split()
        key = parts[0].lower().strip("{}")
        scope = "global" if parts[-1].lower() in ("global", "umumiy") and len(parts) > 1 else "user"
        rest = parts[1:-1] if scope == "global" else parts[1:]
        default = " ".join(rest)[:200]
        if key in BUILTIN_VARS:
            await say("⚠️ Bu tizim o'zgaruvchisi — boshqa nom tanlang.")
            return True
        if any(v["key"] == key for v in bot.menu.get("variables") or []):
            await say("⚠️ Bunday o'zgaruvchi bor.")
            return True
        if not await save(runner, bot, chat_id, lambda m: m.setdefault("variables", []).append({"key": key, "label": key, "default": default, "scope": scope})):
            return True
        await set_state(runner, bot, chat_id, None)
        tr = variables_view(bot)
        await say(f"✅ <code>{{{esc(key)}}}</code> qo'shildi. Matnda shu ko'rinishda yozing, tugmaga «🔢 O'zgaruvchi» vazifasini bering.\n\n" + tr[0], tr[1])
        return True
    if kind == "form_title":
        fid = "f" + new_page_id()[1:]
        await set_state(runner, bot, chat_id, {"k": "form_q", "title": text[:64], "id": fid, "steps": []})
        await say(_question_prompt(1))
        return True
    if kind == "form_q":
        key, sep, question = text.partition("|")
        if sep:
            key, question = key.strip().lower(), question.strip()
        else:
            key, question = f"javob{len(state['steps']) + 1}", text
        if not key.replace("_", "").isalnum() or not key.isascii() or not key[0].isalpha():
            await say("⚠️ O'zgaruvchi nomi faqat lotin harf, raqam va _ bo'lsin.")
            return True
        if any(s["key"] == key for s in state["steps"]):
            await say("⚠️ Bu nom shu formada bor.")
            return True
        q_html = entities_to_html(message.get("text") or "", message.get("entities"))
        if sep:
            q_html = esc(question)
        state.update({"k": "form_type", "key": key[:32], "question": q_html})
        await set_state(runner, bot, chat_id, state)
        rows = [
            [{"text": TYPE_LABELS["text"], "callback_data": "adm:fty:text"}, {"text": TYPE_LABELS["number"], "callback_data": "adm:fty:number"}],
            [{"text": TYPE_LABELS["phone"], "callback_data": "adm:fty:phone"}, {"text": TYPE_LABELS["email"], "callback_data": "adm:fty:email"}],
            [{"text": TYPE_LABELS["photo"], "callback_data": "adm:fty:photo"}, {"text": TYPE_LABELS["choice"], "callback_data": "adm:fty:choice"}],
            [{"text": TYPE_LABELS["location"], "callback_data": "adm:fty:location"}],
        ]
        await say("Javob turi qanday?", rows)
        return True
    if kind == "form_opts":
        opts = [o.strip()[:64] for o in text.split(",") if o.strip()][:12]
        if not opts:
            await say("⚠️ Variantlar bo'sh")
            return True
        state["steps"].append({"key": state["key"], "question": state["question"], "type": "choice", "options": opts})
        await form_next(runner, bot, chat_id, state)
        return True
    if kind == "form_done":
        form = {
            "id": state["id"],
            "title": state["title"],
            "steps": state["steps"],
            "done_text": "✅ Rahmat! Javoblaringiz qabul qilindi." if text == "-" else entities_to_html(message.get("text") or "", message.get("entities")),
            "target": None,
            "notify": True,
        }
        if not await save(runner, bot, chat_id, lambda m: m.setdefault("forms", []).append(form)):
            return True
        await set_state(runner, bot, chat_id, None)
        i = len(bot.menu["forms"]) - 1
        tr = form_view(bot, i)
        await say(
            "✅ Forma yaratildi! Endi uni tugmaga ulang: ✏️ Tahrirlash → 🔘 Tugmalar → tugma → 🎯 Vazifasi → 📝 Forma.\n\n" + tr[0],
            tr[1],
        )
        return True
    if kind in ("ref_reward", "ref_var", "ref_text"):
        if kind == "ref_reward" and not text.isdigit():
            await say("⚠️ Son yuboring")
            return True

        def change(m):
            ref = m.setdefault("referral", {})
            if kind == "ref_reward":
                ref["reward"] = int(text)
            elif kind == "ref_var":
                ref["var"] = text.strip("{}").lower()
            else:
                ref["text"] = text[:1000]

        if not await save(runner, bot, chat_id, change):
            return True
        await set_state(runner, bot, chat_id, None)
        tr = referral_view(bot)
        await say("✅ Saqlandi\n\n" + tr[0], tr[1])
        return True
    if kind == "sub_text":
        if not await save(runner, bot, chat_id, lambda m: m.update(sub_text=text[:1000])):
            return True
        await set_state(runner, bot, chat_id, None)
        tr = channels_view(bot)
        await say("✅ Saqlandi\n\n" + tr[0], tr[1])
        return True
    if kind == "text":
        field = state["field"]
        if not await save(runner, bot, chat_id, lambda m: m.update({field: text[:1000]})):
            return True
        await set_state(runner, bot, chat_id, None)
        tr = feedback_view(bot) if field.startswith("feedback") else settings_menu(bot)
        await say("✅ Saqlandi\n\n" + tr[0], tr[1])
        return True
    if kind == "user_var":
        op = parse_op(text)
        if op is None:
            await say("⚠️ Tushunarsiz. Masalan: <code>ball = 100</code>")
            return True
        sub = await runner.subscriber(bot, state["id"])
        value = apply_op(str(sub["data"].get(op["var"], "")), op["op"], op["value"])
        async with async_session() as db:
            s = await db.scalar(select(BotSubscriber).where(BotSubscriber.bot_id == bot.bot_id, BotSubscriber.tg_user_id == state["id"]))
            if s is not None:
                data = dict(s.data or {})
                if op["op"] == "clear":
                    data.pop(op["var"], None)
                else:
                    data[op["var"]] = value
                s.data = data
                await db.commit()
        await set_state(runner, bot, chat_id, None)
        tr = await user_card(bot, state["id"])
        if tr:
            await say("✅ Saqlandi\n\n" + tr[0], tr[1])
        return True
    return False


async def _bc_confirm(runner: "Runner", bot: "RunningBot", chat_id: int, message_id: int, seg: str, confirm: dict | None) -> None:
    """Tarqatish tasdig'i: auditoriya (segment) tanlanadi, soni ko'rsatiladi."""
    import crm
    from core.segments import SEGMENT_RE, conditions, label

    seg = seg if SEGMENT_RE.match(seg) else "all"
    async with async_session() as db:
        n = await db.scalar(select(func.count(BotSubscriber.id)).where(*conditions(seg, bot.bot_id, bot.menu)))
    ok = f"adm:bcok:{message_id}" + ("" if seg == "all" else f":{seg}")
    options = await crm.segment_options(bot)
    seg_rows = [[{"text": ("✔️ " if k == seg else "") + label(k, bot.menu), "callback_data": f"adm:bcs:{message_id}:{k}"} for k in options[i : i + 2]] for i in range(0, len(options), 2)]
    rows = [[{"text": "✅ Yuborish", "callback_data": ok}, {"text": "❌ Bekor", "callback_data": "adm:bcno"}]] + seg_rows
    text = f"☝️ Shu xabar <b>{n}</b> ta obunachiga yuborilsinmi?\n🎯 Auditoriya: {label(seg, bot.menu)}"
    data = {"chat_id": chat_id, "text": text, "parse_mode": "HTML", "reply_markup": {"inline_keyboard": rows}}
    if confirm is not None and "message_id" in confirm and "text" in confirm:
        await runner.api(bot, "editMessageText", {**data, "message_id": confirm["message_id"]})
    else:
        await runner.api(bot, "sendMessage", {**data, "reply_to_message_id": message_id})


async def _start_broadcast(runner: "Runner", bot: "RunningBot", chat_id: int, message_id: int, confirm: dict, segment: str = "all") -> None:
    async with async_session() as db:
        running = await db.scalar(select(BotBroadcast.id).where(BotBroadcast.bot_id == bot.bot_id, BotBroadcast.status == "sending"))
        if running:
            await runner.api(bot, "sendMessage", {"chat_id": chat_id, "text": "⏳ Oldingi xabar hali tarqatilmoqda — tugashini kuting."})
            return
        item = BotBroadcast(bot_id=bot.bot_id, text="", from_chat_id=chat_id, message_id=message_id, segment=segment if SEGMENT_RE_.match(segment) else "all")
        db.add(item)
        await db.commit()
        broadcast_id = item.id
    try:
        pool = await runner.arq()
        await pool.enqueue_job("user_bot_broadcast_job", broadcast_id=broadcast_id, _job_id=f"userbot_broadcast:{broadcast_id}")
    except Exception:  # noqa: BLE001
        async with async_session() as db:
            await db.execute(update(BotBroadcast).where(BotBroadcast.id == broadcast_id).values(status="done"))
            await db.commit()
        await runner.api(bot, "sendMessage", {"chat_id": chat_id, "text": "⚠️ Tarqatishni boshlab bo'lmadi, birozdan keyin qayta urinib ko'ring."})
        return
    await runner.api(
        bot,
        "editMessageText",
        {"chat_id": chat_id, "message_id": confirm["message_id"], "text": "🚀 Tarqatish boshlandi. Tugagach, natijani shu yerga yuboraman."},
    )

