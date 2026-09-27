#!/usr/bin/env bash
# Production boshqaruvi. .env'dagi DEPLOY_MODE (domain | tunnel) bo'yicha to'g'ri compose fayllarini tanlaydi.
#   ./deploy/deploy.sh              — yig'ish va ishga tushirish (yangilashda ham shu)
#   ./deploy/deploy.sh ps           — holat
#   ./deploy/deploy.sh logs -f bot  — loglar
#   ./deploy/deploy.sh down         — to'xtatish (ma'lumotlar saqlanadi)
set -euo pipefail
cd "$(dirname "$0")/.."

if [ ! -f .env ]; then
  echo "❌ .env yo'q. Avval: ./deploy/init-env.sh" >&2
  exit 1
fi

mode="$(grep -E '^DEPLOY_MODE=' .env | tail -1 | cut -d= -f2- | tr -d '"'"'"' ')"
args=(-f docker-compose.prod.yml)
case "$mode" in
  domain) args+=(-f deploy/compose.domain.yml) ;;
  proxy) args+=(-f deploy/compose.proxy.yml) ;;
  tunnel) args+=(--profile tunnel) ;;
  *)
    echo "❌ .env da DEPLOY_MODE=domain | proxy | tunnel bo'lishi kerak (hozir: '$mode')" >&2
    exit 1
    ;;
esac

mkdir -p backups
if [ "$#" -eq 0 ]; then
  docker compose "${args[@]}" up -d --build --remove-orphans
  docker compose "${args[@]}" ps
else
  docker compose "${args[@]}" "$@"
fi
