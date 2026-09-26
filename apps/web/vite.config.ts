import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

// Brauzer API'ga shu domen orqali murojaat qiladi (/api -> api:8000) — bitta tunnel yetarli, CORS kerak emas.
const apiProxy = {
  "/api": {
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
