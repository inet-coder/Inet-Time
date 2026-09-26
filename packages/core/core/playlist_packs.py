"""Bio playlist uchun tayyor to'plamlar. Standart to'plamlar shu yerda; admin paneldan o'zgartirilsa —
system_settings["playlist_packs"] ga yoziladi va shu ro'yxat o'rniga ishlatiladi."""

import random
import re

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.db.models import SystemSetting

SETTING_KEY = "playlist_packs"
MAX_PACKS = 30
MAX_PACK_ITEMS = 20
PLAYLIST_MAX_ITEMS = 10  # bitta playlistda ko'pi bilan
ITEM_MAX_LEN = 70  # Telegram bio (Premium'siz)

DEFAULT_PACKS = [
    {
        "code": "hazil",
        "title": "😂 Hazil",
        "items": [
            "Pulim yo‘q, lekin rejalarim million dollarlik 💸",
            "Hozir bandman, o‘zim bilan maslahatlashyapman 🤔",
            "Meni tushunish uchun tarjimon ham yetmaydi 😂",
            "Choy damlab keling, gap katta ☕",
            "Ko‘nglim tog‘dek, cho‘ntagim tekis 🥲",
            "Hozircha hayot meni sinayapti, men esa internetni 📶",
            "Uyqu bilan jiddiy munosabatdamiz 😴",
            "Gap ko‘p, lekin aytishga dangasaman 🤐",
            "Ishlar joyida, faqat joyi noma'lum 😂",
            "O‘zimga o‘zim xo‘jayinman, lekin uyda emas 🫠",
        ],
    },
    {
        "code": "dasturchi",
        "title": "💻 Dasturchi",
        "items": [
            "Kod yozdim, endi o‘zim ham tushunmayman 🤯",
            "Bugun ham bitta xato bilan do‘stlashdim 🐛",
            "Dasturchining eng katta orzusi — ishlayotgan kodga tegmaslik 😂",
            "Kompyuter aybdor, men emas 💻",
            "Kod ishlayapti, savol bermang 🤫",
            "Bir qator kod, uch soat asab 😭",
            "Stack Overflow ham mendan charchadi 🤝",
            "Bugun kod yozmayman degandim, yana aldandim.",
            "Dasturchi uxlaydi, server uxlamaydi 🌐",
            "Xatoni topdim, endi nega ishlaganini aniqlash qoldi 🧐",
        ],
    },
    {
        "code": "kayfiyat",
        "title": "☕ Kayfiyat",
        "items": [
            "Bugun kayfiyatim choyga o‘xshaydi, issiq ☕",
            "Hamma narsa yaxshi, faqat biroz hammasi chatoq 😂",
            "Ko‘ngil tinch bo‘lsa, qolganiga choy bor.",
            "Bugun hech kimga qarzdor emasman, faqat uyquga 😴",
            "Kayfiyat: telefon 100%, men 2% 🔋",
            "Hayot davom etadi, men esa choy ichaman.",
            "O‘zimni topishga chiqqandim, yo‘lda somsa oldim 🥟",
            "Bugun dunyoni qutqarmayman, dam olaman.",
            "Bir piyola choy va mingta xayol ☕",
            "Kayfiyatimni so‘ramang, o‘zi ham bilmayapti 😂",
        ],
    },
    {
        "code": "ish",
        "title": "💼 Ish va pul",
        "items": [
            "Ishlayapmiz, boyib ketish hali rejalarda 💰",
            "Maosh tushdi, pul bilan xayrlashdik 👋",
            "Ish ko‘p, vaqt kam, maosh esa sirli.",
            "Bugun ham pul topish yo‘lida pul sarfladim 😂",
            "Rahbarim meni qidiryapti, men esa ilhomni.",
            "Ishxonada jismonan bor, ruhan ta'tildaman 🏖",
            "Dam olish kuni — eng sevimli kasbim.",
            "Rejalar katta, budjet kichkina.",
            "Ishni boshlash oson, tugatish boshqa masala.",
            "Pul baxt emas deyishadi, lekin sinab ko‘rmoqchiman 💸",
        ],
    },
    {
        "code": "talaba",
        "title": "🎓 Talaba",
        "items": [
            "Darsga borish niyatim bor, uyg‘onishim yo‘q.",
            "Diplom yaqin, bilim hali yo‘lda 🎓",
            "Sessiya kelmoqda, duo qilinglar 🤲",
            "Bugun ham bilim olishga harakat qildim, bilim qochib ketdi.",
            "Davomat bor, tushuncha yo‘q 😂",
            "Ustoz savol berdi, men esa hayot haqida o‘yladim.",
            "Imtihonga tayyorman, faqat savollarni bilmayman.",
            "Talabalik: oy boshida boy, oy oxirida faylasuf.",
            "Konspekt bor, uni o‘qish uchun vaqt yo‘q.",
            "Stipendiya tushsa, o‘zimni millioner his qilaman 💸",
        ],
    },
    {
        "code": "sevgi",
        "title": "❤️ Sevgi",
        "items": [
            "Yurak joyida, faqat egasi biroz adashgan ❤️",
            "Sevgi yaxshi, lekin internet ham kerak 📶",
            "Ko‘ngil bitta, tashvishlar mingta.",
            "Kimdir yuragimni oldi, qaytarishga va'da bergan edi 😂",
            "Sevgi izlamayman, Wi-Fi izlayapman.",
            "Hali ham o‘sha odamni kutyapman... balki adashgandir.",
            "Yurakda joy bor, lekin ijara qimmat.",
            "Ko‘nglim bo‘sh, lekin vaqtim band.",
            "Sevgi ko‘r bo‘lsa, men ham ko‘zoynak taqmayman.",
            "Hamma narsa vaqtinchalik, skrinshotlar abadiy 📸",
        ],
    },
    {
        "code": "sport",
        "title": "🏋️ Sport",
        "items": [
            "Sportni yaxshi ko‘raman, ayniqsa televizorda.",
            "Bugun yuguraman degandim, tushimda yugurdim 🏃",
            "Zalga borish uchun avval kayfiyat kerak.",
            "Mushaklar dam olyapti, men ham.",
            "Ertadan sog‘lom hayot boshlanadi. Qachonligini aytmayman 😂",
            "Sport kiyimim tayyor, faqat men tayyor emasman.",
            "Kaloriyalar bilan muzokara olib boryapman.",
            "Bugungi mashq: muzlatkichgacha 10 metr.",
            "Harakatda baraka bor, lekin hozircha o‘tirib turibman.",
            "Maqsad katta, gantel kichkina 💪",
        ],
    },
    {
        "code": "hikmat",
        "title": "🌿 Hikmat",
        "items": [
            "Har kimning o‘z vaqti bor, shoshilmaslik kerak.",
            "Jimlik ham ba'zan eng to‘g‘ri javob.",
            "Bugungi mehnat — ertangi natija.",
            "O‘zingni boshqalar bilan emas, kechagi o‘zing bilan solishtir.",
            "Har bir kun yangi imkoniyat.",
            "Ba'zi eshiklar yopilsa, boshqa yo‘l ochiladi.",
            "Kam gapir, ko‘p ish qil.",
            "Qiyinchiliklar ham bir kun xotiraga aylanadi.",
            "Sabr qilgan odam yo‘lini topadi.",
            "Kichik yutuqlar ham katta natijaning boshlanishi.",
        ],
    },
    {
        "code": "taom",
        "title": "🍚 Taomlar",
        "items": [
            "Palov bo‘lsa, barcha muammolar unutiladi 🍚",
            "Somsa hidi kelsa, rejalar o‘zgaradi.",
            "Osh damlanayotgan bo‘lsa, men tayyorman.",
            "Choy bor joyda suhbat tugamaydi ☕",
            "Manti yeb, dunyoni unutish mumkin.",
            "Bugungi kayfiyat: issiq non va qaymoq.",
            "Parhez qilayotgan edim, osh ko‘rib fikrim o‘zgardi.",
            "Och qoringa katta qarorlar qabul qilinmaydi.",
            "Bitta somsa bilan boshlangan kun...",
            "O‘zbekning yuragi palov bilan uradi ❤️",
        ],
    },
    {
        "code": "oila",
        "title": "🏡 Oila va mahalla",
        "items": [
            "Onam chaqirdi, barcha rejalar bekor.",
            "Uyda mehmon bor, men esa xizmatdaman 😂",
            "Mahallada hamma meni taniydi, men esa ba'zilarini tanimayman.",
            "Onamning duosi — eng katta boyligim.",
            "Uyga kech qolsam, tergov boshlanadi.",
            "Qo‘shnining to‘yi — mening dam olish kunim.",
            "Onam ovqatga chaqirdi, dunyodagi eng muhim xabar.",
            "Uyda hamma gapni biladi, faqat men bilmayman.",
            "Mehmon keladi degan gapning o‘zi yetarli.",
            "Oila davrasidagi bir piyola choyning qadri boshqa.",
        ],
    },
    {
        "code": "jonli",
        "title": "🌙 Jonli",
        "items": [
            "🕒 Hozirgi vaqt: {time}",
            "📅 Bugun: {date}",
            "🌙 Xayrli tun! Ertaga yana yangi rejalar.",
            "☀️ Xayrli tong! Bugun ham imkoniyat bor.",
            "📆 Yil tugashiga {newyear_days} kun qoldi.",
            "⏳ Vaqt kutmaydi, men esa hali tayyor emasman.",
            "🌤 Bugungi ob-havo: kayfiyatga qarab.",
            "💤 Uyqu rejimi: faollashtirilmoqda.",
            "📱 Onlaynman, lekin hamma uchun emas.",
            "🔋 Yil zaryadi: {year_percent}%",
        ],
    },
    {
        "code": "telegram",
        "title": "📱 Telegram",
        "items": [
            "Onlaynman, lekin javob berish shart emas.",
            "Xabarni ko‘rdim, javobni o‘ylayapman.",
            "Internet bor, suhbatdosh yo‘q.",
            "Telegram ochiq, hayot yopiq 😂",
            "Oxirgi marta ko‘rildi: hozirgina.",
            "Telefon qo‘limda, fikrlarim boshqa joyda.",
            "Bildirishnomalar ko‘p, muhim xabar yo‘q.",
            "Wi-Fi bor, baxt ham bo‘lsa edi.",
            "Xabar yuborish oson, javob kutish qiyin.",
            "Onlayn holatimga aldanmang, men ham uxlayman.",
        ],
    },
    {
        "code": "orzu",
        "title": "🚀 Orzular",
        "items": [
            "Hali hammasi oldinda.",
            "Bugun kichik qadam, ertaga katta natija.",
            "Rejalarim ko‘p, vaqtim bilan kelisholmayapman.",
            "Bir kun kelib bugungi kunlarimni eslayman.",
            "Orzular katta bo‘lsa, harakat ham katta bo‘lsin.",
            "Maqsad aniq, yo‘l hali chizilmoqda.",
            "Sekin bo‘lsa ham, oldinga.",
            "O‘z yo‘limdaman, boshqalarning fikri xarita emas.",
            "Hali o‘zimni ko‘rsatishga ulguraman.",
            "Bugungi sabr — ertangi muvaffaqiyat.",
        ],
    },
    {
        "code": "qisqa",
        "title": "🤣 Qisqa",
        "items": [
            "Tirikmiz, shukr 😂",
            "Hamma gap pulda 💸",
            "Reja bor, vaqt yo‘q.",
            "Men ham hayronman 🤷",
            "Shunchaki yashayapmiz.",
            "Gap yo‘q, faqat choy bor ☕",
            "Hozir emas, keyinroq.",
            "Miyamda 47 ta ochiq oyna 🧠",
            "Kayfiyat: noma'lum.",
            "Hali ham loading... ⏳",
            "Ishlar: kutilmoqda.",
            "Rejim: tejamkor 🔋",
            "Hammasi nazorat ostida. Deyarli.",
            "Bugun ham omonmiz.",
            "Hayot davom etmoqda...",
        ],
    },
]


async def get_packs(db: AsyncSession) -> list[dict]:
    row = await db.scalar(select(SystemSetting).where(SystemSetting.key == SETTING_KEY))
    if row is not None and isinstance(row.value, dict) and row.value.get("packs"):
        return row.value["packs"]
    return DEFAULT_PACKS


def pick_items(pack: dict) -> list[str]:
    """Playlistga ko'pi bilan 10 ta: to'plam katta bo'lsa — har safar tasodifiy 10 tasi."""
    items = list(pack["items"])
    if len(items) <= PLAYLIST_MAX_ITEMS:
        return items
    return random.sample(items, PLAYLIST_MAX_ITEMS)


def slugify(title: str, taken: set[str]) -> str:
    base = re.sub(r"[^a-z0-9]+", "_", title.lower()).strip("_")[:24] or "pack"
    code, n = base, 2
    while code in taken:
        code = f"{base}_{n}"
        n += 1
    return code
