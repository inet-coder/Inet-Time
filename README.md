# Inet-Time — Telegram botlar konstruktori

Kod yozmasdan Telegram bot yaratish platformasi va Telegram profilni avtomatlashtirish: bot + Mini App + admin panel.

## Imkoniyatlar

- 🧩 **Bot konstruktori** — asosiy bot orqali kod yozmasdan Telegram bot yaratish: shablon tanlanadi, @BotFather
  tokeni yuboriladi (yoki BotFather xabari forward qilinadi) — bot darhol ishlaydi. Sozlash yaratilgan botning
  o'zida (`/admin`): menyu va tugmalar muharriri (Mini App), istalgan turdagi xabarni tarqatish, murojaatlar
  rejimi (har bir xabar egasiga, «Reply» bilan javob), statistika. 15 ta tayyor shablon: qayta aloqa, do'kon,
  restoran, go'zallik saloni, klinika, avtoservis, ko'chmas mulk, turizm, o'quv markazi, tadbir, kanal,
  FAQ, anonim savollar, portfolio, bo'sh
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
