import React from "react";
import ReactDOM from "react-dom/client";

const root = ReactDOM.createRoot(document.getElementById("root")!);

// /app/<id> — kodsiz yaratilgan Web App (foydalanuvchilar uchun): faqat ilova kodi yuklanadi, Studiya emas.
const publicAppId = Number(window.location.pathname.match(/^\/app\/(\d+)/)?.[1]) || null;

if (publicAppId) {
  import("./webapp/PublicApp").then(({ default: PublicApp }) =>
    root.render(
      <React.StrictMode>
        <PublicApp appId={publicAppId} />
      </React.StrictMode>,
    ),
  );
} else {
  Promise.all([import("@tanstack/react-query"), import("./App")]).then(([rq, { App }]) => {
    const queryClient = new rq.QueryClient({ defaultOptions: { queries: { retry: 1, refetchOnWindowFocus: true } } });
    root.render(
      <React.StrictMode>
        <rq.QueryClientProvider client={queryClient}>
          <App />
        </rq.QueryClientProvider>
      </React.StrictMode>,
    );
  });
}
