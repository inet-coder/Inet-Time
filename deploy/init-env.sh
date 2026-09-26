#!/usr/bin/env bash
# Serverda birinchi marta: .env.production.example'dan .env yaratadi va barcha maxfiy kalitlarni tasodifiy to'ldiradi.
# Keyin .env ni ochib BOT_TOKEN, TELEGRAM_API_ID/HASH, ADMIN_TELEGRAM_IDS va domen/tunnel qatorlarini to'ldiring.
set -euo pipefail
cd "$(dirname "$0")/.."

if [ -f .env ]; then
  echo "❌ .env allaqachon bor — ustidan yozmayman." >&2
  exit 1
fi

hex() { openssl rand -hex "$1"; }
sed \
  -e "s|__POSTGRES_PASSWORD__|$(hex 24)|" \
  -e "s|__JWT_SECRET__|$(hex 32)|" \
  -e "s|__ADMIN_SECRET__|$(hex 16)|" \
  -e "s|__INTERNAL_API_TOKEN__|$(hex 32)|" \
  -e "s|__SESSION_ENCRYPTION_KEY__|$(openssl rand -base64 32)|" \
  .env.production.example > .env
chmod 600 .env

echo "✅ .env yaratildi (maxfiy kalitlar tasodifiy)."
echo "   Endi to'ldiring: nano .env"
echo "   ❗ Lokal bazani ko'chirsangiz, SESSION_ENCRYPTION_KEY ni eski .env dagi qiymat bilan almashtiring."
