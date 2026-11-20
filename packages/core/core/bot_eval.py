"""Sifat to'plami: 40 ta turli brif bo'yicha InetTime AI quruvchisini avtomatik baholash.

Har bir brif uchun bot quriladi (reja → mazmun → yig'ish → linter) va natija qoidalar bo'yicha tekshiriladi:
tekshiruvdan o'tishi, yetib borish, joy tutuvchilar yo'qligi, kutilgan modullar (do'kon, yozilish, viktorina...),
bo'limlar soni, mazmun sifati, tugmalar, o'zgaruvchilar, uslub. Ball 0–100. Promptlar yoki modellarni o'zgartirgach
`python tools/run_bot_eval.py` bilan regressiya tekshiriladi; haqiqiy model uchun OPENAI_API_KEY kerak."""

import re
from dataclasses import dataclass, field

from core import bot_ai
from core.botbuilder import BUILTIN_VARS, MenuError, html_to_plain, validate_menu


@dataclass
class Brief:
    id: str
    prompt: str
    modules: tuple = ()
    pages: tuple = (6, 40)
    style: str | None = None  # "reply" | "inline" | "hybrid" — brifda aniq so'ralgan bo'lsa


BRIEFS: list[Brief] = [
    Brief("flowers", "Toshkentda gul do'koni uchun bot: guldastalar katalogi, savat, yetkazib berish 20 000 so'm, 300 000 dan bepul.", ("shop", "contacts")),
    Brief("cafe", "Samarqanddagi 'Osh Markazi' uchun bot: menyu, buyurtma, stol band qilish, aksiyalar, manzil.", ("shop", "contacts")),
    Brief("pizza", "Pitsa yetkazib berish boti: pitsalar, ichimliklar, souslar, savat, promokod, to'lov naqd yoki karta.", ("shop",)),
    Brief("clothes", "Ayollar kiyim do'koni: yangi kolleksiya, o'lchamlar jadvali, savat, qaytarish shartlari.", ("shop", "faq")),
    Brief("pharmacy", "Dorixona boti: dori kategoriyalari, narxlar, yetkazish, ish vaqti, farmatsevtga savol.", ("shop", "contacts")),
    Brief("bakery", "Tort va pirogli: tortlar katalogi, buyurtma sanasi, bezak turlari, narxlar.", ("shop",)),
    Brief("electronics", "Telefon va aksessuarlar do'koni: markalar bo'yicha katalog, kafolat, bo'lib to'lash haqida ma'lumot.", ("shop", "faq")),
    Brief("salon", "'Nur' go'zallik saloni: soch olish, manikyur, ustalar Aziza va Dilnoza, har kuni 10:00-20:00, yozilishni o'zim tasdiqlayman.", ("booking", "contacts")),
    Brief("barber", "Barbershop: soch, soqol, kombo xizmatlar, onlayn yozilish, eslatma.", ("booking",)),
    Brief("clinic", "Stomatologiya klinikasi: shifokorlar, xizmatlar narxi bilan, qabulga yozilish, manzil va xarita.", ("booking", "faq")),
    Brief("autoservice", "Avtoservis: moy almashtirish, diagnostika, balansirovka; navbat olish; narxlar.", ("booking",)),
    Brief("tutor", "Ingliz tili repetitori: individual va guruh darslari, sinov darsi, yozilish, narxlar.", ("booking", "faq")),
    Brief("gym", "Sport zal: abonementlar, trenerlar, guruh mashg'ulotlari jadvali, sinov mashg'uloti.", ("booking",)),
    Brief("photographer", "Fotograf: portfolio, paketlar, narxlar, suratga olish uchun band qilish.", ("booking",)),
    Brief("course", "Dasturlash kursi: kurslar, jadval, narxlar, ro'yxatdan o'tish, bitiruvchilar fikri, FAQ.", ("forms", "faq")),
    Brief("school", "Xususiy maktab: qabul shartlari, sinflar, ariza topshirish formasi, aloqa.", ("forms", "contacts")),
    Brief("realty", "Ko'chmas mulk agentligi: kvartiralar sotuvi va ijarasi, filtr bo'yicha tanlash, ariza qoldirish.", ("forms", "contacts")),
    Brief("travel", "Sayohat agentligi: tur paketlar, narxlar, vizalar, ariza, referal bonus.", ("forms", "referral")),
    Brief("event", "Konferensiya uchun bot: dastur, spikerlar, ro'yxatdan o'tish, joy xaritasi, savol-javob.", ("forms",)),
    Brief("vacancy", "HR bot: vakansiyalar, nomzod anketasi (CV rasmi bilan), jarayon haqida.", ("forms",)),
    Brief("quiz_en", "Ingliz tili o'quv markazi uchun o'yin boti: 8 ta savolli viktorina, reyting, kunlik bonus va do'st taklif qilish (har biri 10 ball).", ("quiz", "top", "bonus", "referral")),
    Brief("quiz_hist", "Tarix bo'yicha bilimdonlar o'yini: 10 ta savol, ball yig'ish, TOP-10 reyting.", ("quiz", "top")),
    Brief("loyalty", "Kafe uchun sodiqlik dasturi: har tashrif uchun ball, referal, kunlik bonus, mukofotlar ro'yxati.", ("bonus", "referral")),
    Brief("channel_help", "Kripto yangiliklar kanalim uchun yordamchi bot: majburiy obuna, do'st taklif qilish uchun ball, adminga savol.", ("referral",)),
    Brief("support", "Internet provayder yordam xizmati: tiketlar, tez-tez so'raladigan savollar, operatorlar bilan aloqa.", ("tickets", "faq")),
    Brief("telecom", "Mobil operator mijozlar xizmati: tariflar, balansni tekshirish yo'riqnomasi, murojaat qoldirish.", ("tickets",)),
    Brief("anon", "Jamoa uchun anonim savol-javob boti: xabarlar menga anonim keladi.", ()),
    Brief("portfolio", "Dizayner portfolio boti: ishlar, xizmatlar, narx paketlari, buyurtma berish, aloqa.", ("contacts",)),
    Brief("lawyer", "Yuridik maslahat: xizmatlar, narxlar, konsultatsiyaga yozilish, hujjatlar ro'yxati.", ("booking", "faq")),
    Brief("translation", "Tarjima byurosi: tillar, narx hisoblash, buyurtma formasi, muddatlar.", ("forms",)),
    Brief("print", "Bosmaxona: vizitka, banner, stiker; narxlar; buyurtma qoldirish; ish namunalari.", ("forms",)),
    Brief("kids", "Bolalar markazi: to'garaklar, jadval, yoshga qarab tanlash, sinov darsiga yozilish.", ("booking",)),
    Brief("wedding", "To'yxona: zallar, sig'imi, narxlar, band qilish sanasi, menyu variantlari, aloqa.", ("forms", "contacts")),
    Brief("grocery", "Oziq-ovqat do'koni yetkazib berish: kategoriyalar, savat, minimal buyurtma 100 000, aksiya promokodlari.", ("shop",)),
    Brief("books", "Kitob do'koni: janrlar bo'yicha katalog, yangi kitoblar, savat, kitob klubi.", ("shop",)),
    Brief("inline_only", "Faqat inline tugmali bot: kofe do'koni menyusi, narxlar va manzil. Klaviatura tugmalari bo'lmasin.", ("contacts",), style="inline"),
    Brief("reply_only", "Faqat klaviatura tugmali oddiy vizitka boti: biz haqimizda, xizmatlar, aloqa.", ("contacts",), style="reply"),
    Brief("giveaway", "Instagram blogerim uchun konkurs boti: qatnashish shartlari, do'st taklif qilish, g'oliblar e'loni.", ("referral",)),
    Brief("autos", "Mashina savdo markazi: markalar, narxlar, test-drayvga yozilish, kredit sharoitlari.", ("booking", "faq")),
    Brief("mixed", "Salon + do'kon: xizmatlarga yozilish va kosmetika sotish, referal bonus, aksiyalar, savat.", ("booking", "shop", "referral")),
]


@dataclass
class Check:
    name: str
    ok: bool
    detail: str = ""
    weight: int = 1


@dataclass
class Result:
    brief: Brief
    checks: list = field(default_factory=list)
    error: str = ""

    @property
    def score(self) -> int:
        if self.error:
            return 0
        total = sum(c.weight for c in self.checks) or 1
        return round(100 * sum(c.weight for c in self.checks if c.ok) / total)


_EMOJI = re.compile(r"[\U0001F000-\U0001FAFF☀-➿⭐⬆⬅➡✅]")
_VAR = re.compile(r"\{(\w+)\}")


def _has(menu: dict, token: str) -> bool:
    pages = menu.get("pages") or []
    mods = {(p.get("module") or {}).get("type") for p in pages}
    titles = " ".join(p["title"].lower() for p in pages)
    return {
        "shop": bool((menu.get("shop") or {}).get("enabled")) and len((menu.get("shop") or {}).get("items") or []) >= 3 and "catalog" in mods,
        "booking": bool((menu.get("booking") or {}).get("enabled")) and bool((menu.get("booking") or {}).get("services")) and "booking" in mods,
        "quiz": bool(menu.get("quizzes")) and "quiz" in mods,
        "top": "top" in mods,
        "bonus": bool((menu.get("bonus") or {}).get("enabled")) and "bonus" in mods,
        "referral": bool((menu.get("referral") or {}).get("enabled")),
        "tickets": bool((menu.get("tickets") or {}).get("enabled")),
        "forms": bool(menu.get("forms")),
        "auto": bool(menu.get("auto")),
        "faq": bool(re.search(r"faq|savol|so'ra", titles)),
        "contacts": bool(re.search(r"aloqa|manzil|kontakt|bog'lan", titles)),
    }.get(token, False)


def score(menu: dict, brief: Brief, report: dict | None = None) -> Result:
    """Tayyor bot hujjatini brif bo'yicha baholaydi (modeldan mustaqil — testlanadi)."""
    res = Result(brief)
    add = lambda name, ok, detail="", weight=1: res.checks.append(Check(name, bool(ok), detail, weight))  # noqa: E731
    pages = menu.get("pages") or []
    # 1) tuzilma
    try:
        validate_menu(menu, 200)
        add("tekshiruvdan o'tadi", True, weight=3)
    except MenuError as exc:
        add("tekshiruvdan o'tadi", False, str(exc), weight=3)
    lo, hi = brief.pages
    add("bo'limlar soni", lo <= len(pages) <= hi, f"{len(pages)} (kutilgan {lo}–{hi})")
    warn = (report or {}).get("warn") or []
    add("hamma bo'limga yetib borish mumkin", not any("yetib" in w or "ochilmaydigan" in w for w in warn), "; ".join(w for w in warn if "ochilmaydigan" in w), weight=2)
    add("matnlarda joy tutuvchi yo'q", not any("to'ldirilmagan" in w for w in warn), "; ".join(w for w in warn if "to'ldirilmagan" in w), weight=3)
    # 2) modullar
    for token in brief.modules:
        add(f"modul: {token}", _has(menu, token), weight=3)
    if brief.style:
        add(f"uslub: {brief.style}", menu.get("style") == brief.style, f"hozir: {menu.get('style')}", weight=2)
        if brief.style == "inline":
            add("klaviatura bo'limlari yo'q", not any(p.get("keyboard") == "reply" and p.get("buttons") and p["id"] != menu.get("start") for p in pages), weight=1)
    # 3) mazmun sifati
    posts = [m for p in pages for m in p.get("messages") or [] if m.get("type") == "text"]
    lengths = [len(html_to_plain(m.get("text", ""))) for m in posts]
    avg = sum(lengths) / len(lengths) if lengths else 0
    add("postlar mazmunli (o'rtacha ≥ 70 belgi)", avg >= 70, f"o'rtacha {avg:.0f}")
    add("hech bir post juda qisqa emas (≥ 15 belgi)", all(n >= 15 for n in lengths), f"eng qisqa {min(lengths) if lengths else 0}")
    add("postlarda emoji bor", sum(1 for m in posts if _EMOJI.search(m.get("text", ""))) >= 0.7 * max(1, len(posts)))
    # 4) tugmalar
    labels = [b["text"] for p in pages for row in p.get("buttons") or [] for b in row if b.get("action") not in ("back", "home")]
    add("tugma nomlari qisqa (≤ 28)", all(len(t) <= 28 for t in labels), "; ".join(t for t in labels if len(t) > 28)[:80])
    add("tugmalarda emoji bor (≥ 70%)", not labels or sum(1 for t in labels if _EMOJI.search(t)) >= 0.7 * len(labels))
    inline_pages = [p for p in pages if p.get("keyboard") == "inline" and p["id"] != menu.get("start") and not (p.get("module") or {}).get("type") in ("catalog", "cart", "orders", "booking", "mybookings", "quiz", "top", "bonus", "contest")]
    add("inline bo'limlarda «Orqaga» bor", all(any(b.get("action") in ("back", "home") for row in p.get("buttons") or [] for b in row) for p in inline_pages), weight=2)
    # 5) o'zgaruvchilar
    declared = {v["key"] for v in menu.get("variables") or []} | set(BUILTIN_VARS) | {k for f in menu.get("forms") or [] for k in [s["key"] for s in f["steps"]]} | {"order", "total", "booking", "service", "when", "staff"}
    declared |= {m["var"] for p in pages for m in p.get("messages") or [] if m.get("type") == "question" and m.get("var")}
    declared |= {"ball", "streak", "telefon", "ism"}
    used = {v for p in pages for m in p.get("messages") or [] for v in _VAR.findall(m.get("text", ""))}
    missing = sorted(v for v in used if v not in declared)
    add("ishlatilgan o'zgaruvchilar e'lon qilingan", not missing, ", ".join(missing))
    # 6) modul sifati
    shop = menu.get("shop") or {}
    if shop.get("items"):
        add("mahsulotlarda narx va tavsif bor", all(i["price"] > 0 and len(i.get("text", "")) >= 10 for i in shop["items"]), weight=2)
        per: dict = {}
        for i in shop["items"]:
            per[i["category"]] = per.get(i["category"], 0) + 1
        add("har kategoriyada ≥ 3 mahsulot", all(n >= 3 for n in per.values()), str(per))
    book = menu.get("booking") or {}
    if book.get("enabled"):
        add("xizmatlarda davomiylik va nom bor", all(s["minutes"] >= 5 and s["title"] for s in book["services"]) and len(book["services"]) >= 2, f"{len(book['services'])} xizmat", weight=2)
    for q in menu.get("quizzes") or []:
        add(f"viktorina «{q['title'][:20]}» ≥ 5 savol", len(q["questions"]) >= 5, f"{len(q['questions'])} savol", weight=2)
    # 7) xavfsizlik: AI sirlarga tegmaydi
    add("adminlar/operatorlar/webhooklar bo'sh", not menu.get("admins") and not menu.get("operators") and not menu.get("webhooks") and not (shop.get("pay") or {}).get("enabled"), weight=3)
    return res


async def run_brief(model: str, brief: Brief, *, max_pages: int = 60) -> Result:
    """Haqiqiy konveyer: reja → bot (savollarsiz, hammasini AI o'zi hal qiladi)."""
    current = {"start": "main", "pages": [{"id": "main", "title": "Bosh menyu", "text": "Salom", "messages": [{"type": "text", "text": "Salom", "buttons": []}], "keyboard": "reply", "buttons": []}]}
    try:
        data, _ = await bot_ai.plan_request(model, current, [], brief.prompt, allow_questions=False, max_pages=max_pages)
        if data["mode"] != "new":
            return Result(brief, error=f"reja rejimi: {data['mode']}")
        menu, report, _ = await bot_ai.build_new(model, current, data.get("brief") or {}, data["plan"], max_pages)
    except Exception as exc:  # noqa: BLE001 — bitta brif butun to'plamni to'xtatmasin
        return Result(brief, error=f"{type(exc).__name__}: {str(exc)[:200]}")
    return score(menu, brief, report)


def render_report(results: list[Result], model: str) -> str:
    done = [r for r in results if not r.error]
    avg = sum(r.score for r in results) / max(1, len(results))
    lines = [f"# Sifat hisoboti · {model}", "", f"**O'rtacha ball: {avg:.1f}/100** · brif: {len(results)} · xatolik bilan: {len(results) - len(done)}", "", "| Brif | Ball | Muammolar |", "|---|---|---|"]
    for r in results:
        fails = r.error or "; ".join(f"{c.name}" + (f" ({c.detail})" if c.detail else "") for c in r.checks if not c.ok) or "—"
        lines.append(f"| {r.brief.id} | {r.score} | {fails[:160]} |")
    common: dict = {}
    for r in results:
        for c in r.checks:
            if not c.ok:
                common[c.name.split(":")[0]] = common.get(c.name.split(":")[0], 0) + 1
    if common:
        lines += ["", "## Eng ko'p uchragan muammolar", ""] + [f"- {name}: {n} ta brifda" for name, n in sorted(common.items(), key=lambda x: -x[1])[:8]]
    return "\n".join(lines)
