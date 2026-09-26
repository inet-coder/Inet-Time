# Serverga o'rnatish (production)

Ubuntu 22.04/24.04, kamida **2 GB RAM, 2 CPU, 20 GB disk**. Hamma buyruqlar serverda `root` (yoki `sudo`) bilan.

Tashqariga faqat Mini App sahifasi (Caddy) chiqadi. Postgres, Redis va ichki API faqat Docker ichki tarmog'ida.
Ichki API qo'shimcha `INTERNAL_API_TOKEN` bilan himoyalangan.

---

## 1. Docker o'rnatish

```bash
curl -fsSL https://get.docker.com | sh
```

## 2. Kodni yuklash

```bash
mkdir -p /opt/userbots && cd /opt/userbots
git clone <REPO_URL> .
```

(Git server bo'lmasa, lokal kompyuterdan: `rsync -a --exclude node_modules --exclude .env --exclude backups ./ root@SERVER:/opt/userbots/`)

## 3. `.env` yaratish

```bash
./deploy/init-env.sh
nano .env
```

`init-env.sh` barcha maxfiy kalitlarni tasodifiy yaratadi. Qo'lda to'ldirasiz:

| O'zgaruvchi | Nima |
|---|---|
| `BOT_TOKEN`, `TELEGRAM_API_ID`, `TELEGRAM_API_HASH` | lokal `.env` dagi qiymatlar |
| `ADMIN_TELEGRAM_IDS` | sizning Telegram ID (`6209960731`) |
| `DEPLOY_MODE`, `SITE_ADDRESS`, `WEBAPP_URL` | pastdagi 4-bosqich |

> ❗ **`SESSION_ENCRYPTION_KEY`** — ulangan Telegram akkauntlar shu kalit bilan shifrlangan.
> Lokal bazani ko'chirsangiz, eski `.env` dagi qiymatni qo'ying. Kalitni xavfsiz joyda (parol menejerida) saqlang:
> yo'qolsa, barcha akkauntlar qaytadan ulanishi kerak bo'ladi.

## 4. Manzil: domen yoki tunnel

**A) O'z domeningiz (tavsiya)** — masalan `app.inettime.uz`:

1. Domen DNS'ida `A` yozuv: `app` → server IP.
2. Serverda 80 va 443 portlar ochiq bo'lsin (`ufw allow 80,443/tcp`).
3. `.env`:
   ```
   DEPLOY_MODE=domain
   SITE_ADDRESS=app.inettime.uz
   WEBAPP_URL=https://app.inettime.uz
   ```

HTTPS sertifikatini Caddy o'zi oladi va yangilaydi.

**B) Cloudflare Tunnel** — domen Cloudflare'da bo'lsa, server portlarini umuman ochmasdan:

1. Cloudflare → Zero Trust → Networks → Tunnels → **Create tunnel** → token'ni nusxalang.
2. Public hostname: `app.sizningdomen.uz` → Service: `http://web:80`.
3. `.env`:
   ```
   DEPLOY_MODE=tunnel
   SITE_ADDRESS=:80
   WEBAPP_URL=https://app.sizningdomen.uz
   CLOUDFLARE_TUNNEL_TOKEN=eyJ...
   ```

## 5. Ishga tushirish

```bash
./deploy/deploy.sh
```

Tekshirish:

```bash
./deploy/deploy.sh ps                 # hammasi "Up (healthy)"
./deploy/deploy.sh logs --tail 30 bot # "Mini App manzili: https://..."
curl -I https://app.inettime.uz       # 200
```

Botda `/start` → pastdagi **✨ Studiya** tugmasi.

## 6. Lokal ma'lumotlarni ko'chirish (ixtiyoriy)

Hozirgi foydalanuvchilar, ulangan akkauntlar, tariflar va to'lovlarni ko'chirish:

```bash
# lokal kompyuterda
./deploy/export-local.sh
scp backups/local-*.dump root@SERVER:/opt/userbots/backups/
docker compose down            # ❗ lokal botni to'xtating — bitta bot ikki joyda ishlamasin

# serverda
./deploy/restore.sh backups/local-XXXX.dump
```

`SESSION_ENCRYPTION_KEY` lokal bilan bir xil bo'lishi shart (3-bosqich).

---

## Kundalik ishlar

| Vazifa | Buyruq |
|---|---|
| Yangi versiyani o'rnatish | `git pull && ./deploy/deploy.sh` |
| Loglar | `./deploy/deploy.sh logs -f --tail 100 bot` |
| Holat | `./deploy/deploy.sh ps` |
| To'xtatish | `./deploy/deploy.sh down` (ma'lumotlar saqlanadi) |
| Qayta ishga tushirish | `./deploy/deploy.sh restart bot` |

## Zaxira nusxalar

- Har kuni avtomatik: `backups/userbots-YYYYMMDD-HHMM.dump`, 14 kundan eskisi o'chadi (`BACKUP_KEEP_DAYS`).
- Qo'lda: `./deploy/deploy.sh restart backup` (darhol yangi zaxira).
- Tiklash: `./deploy/restore.sh backups/FAYL.dump`.
- Serverdan tashqariga ham nusxa oling (masalan har hafta `scp` bilan kompyuterga) — server yo'qolsa ham ma'lumot qoladi.

## Xavfsizlik ro'yxati

- [ ] `.env` faqat serverda (`chmod 600`), git'ga tushmaydi.
- [ ] `SESSION_ENCRYPTION_KEY` nusxasi xavfsiz joyda.
- [ ] Faqat kerakli portlar ochiq: `ufw allow OpenSSH && ufw allow 80,443/tcp && ufw enable` (tunnel rejimida 80/443 ham shart emas).
- [ ] SSH parol bilan emas, kalit bilan.
- [ ] Admin → Sozlamalar'da to'lov rekvizitlari kiritilgan.
