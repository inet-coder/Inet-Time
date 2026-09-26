FROM node:20-slim

WORKDIR /app

COPY apps/web/package.json ./package.json
RUN npm install

COPY apps/web ./
RUN npm run build

# Tunnel orqali telefonda tez ochilishi uchun dev-server emas, yig'ilgan (build) versiya beriladi.
CMD ["npm", "run", "preview"]
