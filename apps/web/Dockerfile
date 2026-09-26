FROM node:20-slim AS build

WORKDIR /app

COPY apps/web/package.json ./package.json
RUN npm install

COPY apps/web ./
RUN npm run build

# Yig'ilgan statik fayllarni Caddy beradi (HTTPS, gzip, kesh, /api/webapp proxy).
FROM caddy:2-alpine

COPY deploy/Caddyfile /etc/caddy/Caddyfile
COPY --from=build /app/dist /srv
