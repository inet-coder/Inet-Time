# Inet-Time — Telegram profil avtomatlashtirish platformasi

Telegram akkauntingiz profilini avtomatik boshqaradigan platforma: bot + Mini App (Studiya) + admin panel.

## Imkoniyatlar

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
| `apps/listener` | AI avto-javob uchun doimiy Telegram ulanishi |
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
