#!/usr/bin/env bash
# Lokal kompyuterda: hozirgi bazani faylga saqlaydi (serverga ko'chirish uchun).
set -euo pipefail
cd "$(dirname "$0")/.."
mkdir -p backups
file="backups/local-$(date +%Y%m%d-%H%M).dump"
docker compose exec -T postgres pg_dump -U postgres -d userbots -Fc > "$file"
echo "✅ $file ($(du -h "$file" | cut -f1))"
echo "   Serverga: scp $file root@SERVER:/opt/userbots/backups/"
