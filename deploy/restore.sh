#!/usr/bin/env bash
# Serverda: zaxira faylidan bazani tiklaydi. Ilova to'xtatiladi, baza almashtiriladi, qayta ishga tushadi.
#   ./deploy/restore.sh backups/userbots-20260101-0300.dump
set -euo pipefail
cd "$(dirname "$0")/.."
dump="${1:?Foydalanish: ./deploy/restore.sh backups/FAYL.dump}"
[ -f "$dump" ] || { echo "❌ $dump topilmadi" >&2; exit 1; }

read -r -p "Hozirgi baza $dump bilan almashtiriladi. Davom etamizmi? [y/N] " ok
[ "$ok" = "y" ] || exit 1

./deploy/deploy.sh stop api bot worker scheduler
./deploy/deploy.sh exec -T postgres pg_restore -U userbots -d userbots --clean --if-exists --no-owner --no-privileges < "$dump" || true
./deploy/deploy.sh up -d
echo "✅ Tiklandi. Tekshiring: ./deploy/deploy.sh logs --tail 50 api"
