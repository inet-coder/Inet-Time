# Inet-Time — Telegram botlar konstruktori

Kod yozmasdan Telegram bot yaratish platformasi va Telegram profilni avtomatlashtirish: bot + Mini App + admin panel.

## Imkoniyatlar

- 🧩 **Bot konstruktori** — asosiy bot orqali kod yozmasdan Telegram bot yaratish: shablon tanlanadi, @BotFather
  tokeni yuboriladi (yoki BotFather xabari forward qilinadi) — bot darhol ishlaydi. Sozlash yaratilgan botning
  o'zida (`/admin`): menyu va tugmalar muharriri (Mini App), istalgan turdagi xabarni tarqatish, murojaatlar
  rejimi (har bir xabar egasiga, «Reply» bilan javob), statistika. 15 ta tayyor shablon: qayta aloqa, do'kon,
  restoran, go'zallik saloni, klinika, avtoservis, ko'chmas mulk, turizm, o'quv markazi, tadbir, kanal,
  FAQ, anonim savollar, portfolio, bo'sh
  - **Botning o'zida tuzish** (MenuBuilder uslubi, klaviatura orqali): egasining klaviaturasida faqat unga
    ko'rinadigan «🎛 Tugmalar muharriri», «📝 Postlar muharriri», «⚙️ Admin panel».
    Tugmalar muharriri: tugmani bosish — tanlanadi (`[ Katalog ]`) va xossalar paneli chiqadi (⬅️⬆️⬇️➡️✳️
    ko'chirish, nomi, o'chirish, ✂️ kesish → 📋 qo'yish, vazifa, ko'rinish sharti, buyruq, faqat admin,
    ko'rinmas, obuna talabi, tasodifiy post, navigatsiya); yana bosish — ichiga kirish; «➕ Tugma qo'shish» —
    `📦 Katalog | 🛒 Savat` ko'rinishida qatorlar bilan. Postlar muharriri: har bir post o'z boshqaruvi bilan
    (⬆️⬇️ ✏️ 🗑 ➕ inline tugma), «➕ Post qo'shish» (istalgan xabar, formatlash saqlanadi), «➕ Savol qo'shish»
    (javob o'zgaruvchiga saqlanadi va keyingi postlarda ishlatiladi). Tugmasi yo'q bo'lim — faqat postlari
    chiqadi, ichiga tugma qo'shilsa menyu bo'ladi («⬅️ Orqaga | 🏠 Bosh menyu» avtomatik)
  - **Istalgan uslub**: har bir bo'lim ⌨️ klaviatura, 💬 inline (xabar ostida, joyida almashadi) yoki 🔀 aralash;
    bot bo'yicha standart uslub (/admin → Sozlamalar → 🎨) va har bir bo'limni alohida almashtirish (🔁)
  - **🤖 InetTime AI**: egasi botning o'zida AI bilan suhbatlashadi («restoran uchun bot: menyu, buyurtma formasi,
    referal…») — AI to'liq botni loyihalaydi (bo'limlar, postlar, tugmalar, formalar, o'zgaruvchilar, kalit so'zlar,
    buyruqlar, referal), tuzilma daraxti ko'rsatiladi, «✅ Qo'llash» → darhol ishlaydi, «↩️ Oldingi holat» bilan
    qaytariladi; suhbatni davom ettirib o'zgartiriladi. Quruvchi v2 dasturchi kabi ishlaydi: kerak bo'lsa aniqlashtiruvchi savollar → arxitektura → har bo'lim
    uchun matnlar (parallel) → navigatsiya va uslub kod bilan yig'iladi → sifat tekshiruvi (linter) → 🧪 sinov rejimi
    (egasi yangi botni foydalanuvchilarga ko'rsatmasdan sinaydi) → ✅ qo'llash. Alohida «quruvchi modeli» (admin → AI).
    To'liq reja: [docs/bot-builder-roadmap.md](docs/bot-builder-roadmap.md)
    Web App konstruktorida ham «✨ AI» — butun tizimni tasvirlab yaratish: reja → sahifalar parallel, ma'lumotlar
    to'plamlari (boshlang'ich yozuvlar bilan), ro'yxatlar, batafsil sahifalar, to'plamga yozadigan formalar. Kunlik limit tarif bo'yicha (`builder_ai_daily`).
    OpenAI kaliti admin panelda kiritiladi (Admin → AI): saqlashdan oldin tekshiriladi, bazada shifrlangan holda turadi
  - **Tayyor tizimlar (AI'siz, 30 soniya)**: onlayn do'kon, kafe/restoran, yozilish (salon/klinika/servis), kanal
    yordamchisi, yordam xizmati, ariza, bonus/referal, kurs, vizitka. Bot yaratilgach uning o'zida 4 ta qisqa savol
    (nom, telefon, manzil, ish vaqti) — javoblar hamma matnlarga o'zi joylashadi. Admin panel botdagi modullarga
    qarab chiziladi (Do'kon, Arizalar, Referal...), 📊 statistika (start, eng ko'p ochilgan bo'limlar, savdo
    voronkasi, tushum), 🧩 modullar ro'yxati va «🚀 Birinchi 5 daqiqa» yo'riqnomasi
  - **🛒 Do'kon moduli**: katalog (ro'yxat/kartalar), mahsulot kartasi ➖/➕, savatcha (yetkazish narxi, bepul
    yetkazish chegarasi, minimal summa), rasmiylashtirish, raqamli buyurtmalar va holatlar (egasi tugma bilan
    o'zgartiradi — mijozga xabar boradi), «📦 Buyurtmalarim». Boshqaruv chatda: /admin → 🛒 Do'kon (rasm + izoh
    bilan mahsulot qo'shish). AI sotuvchi bizneslarga do'konni avtomatik quradi
  - **15 xil tugma vazifasi**: sahifa, havola, orqaga, bosh menyu, adminga yozish, Web App, ogohlantirish
    (alert), forma, o'zgaruvchi (`ball +1`), ulashish/referal, obunani tekshirish, telefon va joylashuv so'rash,
    adminga bildirish, tasodifiy sahifa
  - **O'zgaruvchilar** — har bir foydalanuvchi uchun ID bo'yicha eslab qolinadi (yoki bot uchun umumiy) va
    matnda `{ball}` ko'rinishida qayta yuboriladi; tizim o'zgaruvchilari `{name}` `{user_id}` `{ref_link}`
    `{ref_count}` `{date}`...
  - `/admin`: kalit so'zlar (aynan / ichida / boshida), buyruqlar (`/katalog`), formalar (matn, son, telefon,
    email, rasm, tanlov, joylashuv; javoblar egasiga keladi, CSV), referal tizimi (mukofot, tayyor taklif
    sahifasi), majburiy obuna (kanallar), adminlar, foydalanuvchilarni topish / xabar yuborish / bloklash /
    o'zgaruvchilarini tahrirlash, ro'yxatni CSV yuklash, xabar tarqatish
- 🌐 **Web App konstruktori** — har bir bot uchun kodsiz Telegram Mini App: sahifalar va 17 xil blok (banner,
  matn, rasm, galereya, video, tugma, afzalliklar, ro'yxat, mahsulotlar + savatcha, tariflar, raqamlar, FAQ,
  kontaktlar, ortga sanash, forma, ajratgich), 8 ta mavzu + istalgan rang, burchak va shrift, 6 ta shablon
  (do'kon, restoran, xizmatlar, tadbir, portfolio, bo'sh). Qoralama/e'lon alohida; buyurtma narxi serverda
  qayta hisoblanadi; formalar va buyurtmalar egasiga botda keladi («Reply» bilan javob), arizalar qutisi;
  ilova bot menyu tugmasi va bot tugmalaridan ochiladi (`/app/<id>`)
  - **Erkin dizayn**: «Erkin bo'lim» — konteyner (ustun/qator/to'r), matn, rasm, tugma, ikonka (120+),
    bo'sh joy, chiziq; istalgan chuqurlikda (8 qavat). Har bir element va blokka uslub: fon, gradient, fon
    rasmi va qoraytirish, masofalar, kenglik, chegara, burchak, soya, shaffoflik, shrift (12 Google Fonts),
    o'lcham, qalinlik, tekislash; keng oyna uchun alohida qiymatlar; paydo bo'lish animatsiyalari
  - Muharrir: elementlar daraxti, ko'rinishdan bosib tanlash (Tahrirlash / Sinash rejimi), bekor qilish /
    qaytarish (Ctrl+Z / Ctrl+Y), nusxa olish / qo'yish (Ctrl+C / Ctrl+V), 9 ta tayyor erkin bo'lim,
    versiyalar tarixi va tiklash
  - **Ma'lumotlar bazasi**: har ilovaga 20 tagacha to'plam (o'z jadvallari: mahsulotlar, xizmatlar,
    arizalar, jamoa…), 11 maydon turi (matn, son, narx, rasm, sana, ha/yo'q, tanlov, telefon, havola,
    email…), yashirin maydonlar, o'qish rejimi (hamma / faqat o'z yozuvlari / yopiq). Yozuvlar jadvali:
    qidirish, tahrirlash, ommaviy o'chirish, CSV eksport/import. «Ma'lumotlar ro'yxati» bloki (kartalar /
    ro'yxat / to'r, saralash, filtr, qidiruv), erkin konteynerni to'plamdan takrorlash, `{{maydon}}`
    o'zgaruvchilari, rasmni maydonga bog'lash, batafsil sahifalar (bir bosishda yaratiladi), formalar
    to'plamga yozadi
  - **Komponentlar kutubxonasi**: 75 ta tayyor komponent (15 toifa) — jonli ko'rinishda tanlanadi, istalgan
    joyga qo'yiladi va har bir qismi o'zgaradi; «Mening komponentlarim» — o'z dizayningizni saqlab, istalgan
    ilovada qayta ishlatish. Karusel, qatlamlar, yorliqlar, akkordeon, yuguruvchi lenta; video, progress,
    reyting, taymer, xarita. Mavzu ranglari, erkin joylashuv, transformatsiya, filtrlar, «shisha» effekti,
    matn gradienti, hover holati, 11 paydo bo'lish va 8 doimiy animatsiya; qatlamlarni sudrab ko'chirish.
    Reja: [docs/webapp-roadmap.md](docs/webapp-roadmap.md)

**👤 Profil xizmatlari** (asosiy menyuda alohida bo'lim):

- 🕐 **Soat ismda**, 📝 **Avto bio**, ✏️ **Avto ism** — profil matnlari o'zi yangilanadi (soat, sana, hafta kuni, tug'ilgan kun sanog'i va h.k.)
- 🔁 **Bio playlist** — matnlar navbat bilan yoki tasodifiy almashadi (14 ta tayyor to'plam)
- 🗓 **Jadval** — bio/ism belgilangan vaqtlarda o'zgaradi
- 🟢 **24/7 Online** va 👁 **Faollik holati** (onlayn / yaqinda / kontaktlar / standart)
- 😀 **Emoji status**, 🖼 **Rasm almashtirish**
- 🎂 **Tug'ilgan kun** sanog'i, 👀 **Stories** yuklab olish
- 🤖 **AI avto-javob** (OpenAI) — shaxsiy chatlarda siz nomingizdan javob; **AI bilan yozish** (bio, ism, jadval matnlari)
- 💎 **Tariflar**, promokodlar, chegirmalar, balans
- 🎁 **Referal tizimi** — bosqichli sovg'alar, ikki hisoblash rejimi
- 🛠 **Admin panel** (Mini App ichida): foydalanuvchilar, to'lovlar, tariflar, ommaviy xabarlar, statistika, jurnal

## Arxitektura

Monorepo (Docker Compose):

| Servis | Vazifasi |
|---|---|
| `apps/api` | FastAPI — ichki API va Mini App (`/webapp/*`) |
| `apps/bot` | aiogram 3 — Telegram bot |
| `apps/worker` | arq — profilni qo'llash, stories, ommaviy xabar |
| `apps/scheduler` | rejalashtirilgan vazifalar, obuna tugashi |
| `apps/listener` | doimiy Telegram ulanishi: AI avto-javob va 24/7 Online (worker — zaxira) |
| `apps/botrunner` | foydalanuvchilar ulagan botlarni long-polling bilan ishga tushiradi (bot konstruktori) |
| `apps/web` | React + Vite — Mini App (Studiya + admin) |
| `packages/core` | SQLAlchemy modellar, Alembic, Telethon adapterlari, biznes-mantiq |

Telethon (real MTProto), sessiyalar AES-256-GCM bilan shifrlanadi, Redis lease/lock, idempotent worker.

## Ishga tushirish

```bash
cp .env.example .env   # BOT_TOKEN, TELEGRAM_API_ID/HASH va boshqalarni to'ldiring
docker compose up -d --build
```

Serverga o'rnatish: **[DEPLOY.md](DEPLOY.md)**.

## Konfiguratsiya

Barcha maxfiy kalitlar `.env` faylida (git'ga kirmaydi). Namuna: `.env.example`.
