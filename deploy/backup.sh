#!/bin/sh
# Har kuni bazaning to'liq zaxirasi (pg_dump custom format). Tiklash: DEPLOY.md -> "Zaxiradan tiklash".
set -eu
KEEP="${BACKUP_KEEP_DAYS:-14}"
mkdir -p /backups

while true; do
  file="/backups/userbots-$(date +%Y%m%d-%H%M).dump"
  if pg_dump -Fc -f "$file.tmp"; then
    mv "$file.tmp" "$file"
    echo "backup: $file ($(du -h "$file" | cut -f1))"
  else
    rm -f "$file.tmp"
    echo "backup: XATO — pg_dump bajarilmadi" >&2
  fi
  find /backups -name 'userbots-*.dump' -mtime +"$KEEP" -delete
  sleep 86400
done
