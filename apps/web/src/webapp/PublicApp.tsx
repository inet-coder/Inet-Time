// Foydalanuvchilar ochadigan ilova: /app/<id>. Telegram ichida (bot menyu tugmasi yoki tugma orqali) ochiladi.
import { useCallback, useEffect, useState } from "react";
import type { DataLoader } from "./data";
import { api, type PublicAppData } from "../api";
import { tg, versionAtLeast } from "../tg";
import { WebAppRuntime, themeStyle } from "./Runtime";

export default function PublicApp({ appId }: { appId: number }) {
  const [data, setData] = useState<PublicAppData | null>(null);
  // Telegram imzosi bilan — «faqat o'z yozuvlari» to'plamlari uchun kerak
  const loadData = useCallback<DataLoader>(
    (key, params) => api.publicData(appId, key, params as Record<string, unknown>, tg?.initData || undefined).then((r) => r.items),
    [appId],
  );
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    try {
      tg?.ready();
      tg?.expand();
      // Ro'yxatni aylantirganda ilova tasodifan yopilmasin (Bot API 7.7+)
      if (tg && versionAtLeast(tg.version, "7.7")) tg.disableVerticalSwipes?.();
    } catch {
      /* eski Telegram */
    }
    api
      .publicApp(appId)
      .then((d) => {
        setData(d);
        if (d.doc.settings.title) document.title = d.doc.settings.title;
        // Telegram sarlavhasi ilova foniga mos bo'lsin
        try {
          if (tg && !d.doc.theme.adaptive && versionAtLeast(tg.version, "6.9")) {
            tg.setHeaderColor?.(d.doc.theme.background);
            tg.setBackgroundColor?.(d.doc.theme.background);
          }
        } catch {
          /* eski Telegram */
        }
      })
      .catch((e: Error) => setError(e.message));
  }, [appId]);

  if (error)
    return (
      <div className="wa-fallback">
        <p>😕</p>
        <p>{error}</p>
      </div>
    );
  if (!data)
    return (
      <div className="wa-fallback">
        <div className="wa-spinner" />
      </div>
    );
  return (
    <div style={themeStyle(data.doc.theme, true)} className="wa-shell">
      <WebAppRuntime
        doc={data.doc}
        appId={appId}
        mode="live"
        botUsername={data.bot_username}
        branding={data.branding}
        mediaSrc={(id) => `/api/webapp/apps/${appId}/media/${id}`}
        recordMedia={(id) => `/api/webapp/apps/${appId}/records-media/${id}`}
        loadData={loadData}
        onSubmit={async (payload) => {
          if (!tg?.initData) throw new Error("Yuborish uchun ilovani Telegram ichida, bot orqali oching");
          const res = await api.submitApp(appId, { ...payload, init_data: tg.initData });
          return { message: res.message };
        }}
      />
    </div>
  );
}
