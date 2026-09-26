import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

// Brauzer API'ga shu domen orqali murojaat qiladi (/api/webapp -> api:8000/webapp) — bitta tunnel yetarli, CORS kerak emas.
// Faqat Mini App endpointlari tashqariga ochiq: qolgan API (users, payments, accounts...) ichki — bot uchun.
const apiProxy = {
  "/api/webapp/": {
    target: process.env.API_URL ?? "http://api:8000",
    changeOrigin: true,
    rewrite: (path: string) => path.replace(/^\/api/, ""),
  },
};

export default defineConfig({
  plugins: [react()],
  server: { host: "0.0.0.0", port: 5173, allowedHosts: true, proxy: apiProxy },
  preview: { host: "0.0.0.0", port: 5173, allowedHosts: true, proxy: apiProxy },
});
