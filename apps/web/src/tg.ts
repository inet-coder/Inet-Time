// Telegram WebApp SDK'ning biz ishlatadigan qismi (telegram-web-app.js index.html'da yuklanadi).
type Haptic = {
  impactOccurred: (style: "light" | "medium" | "heavy") => void;
  notificationOccurred: (type: "success" | "error" | "warning") => void;
};

type TelegramWebApp = {
  initData: string;
  initDataUnsafe: { user?: { id: number; first_name?: string; username?: string; photo_url?: string } };
  ready: () => void;
  expand: () => void;
  close: () => void;
  openTelegramLink: (url: string) => void;
  showConfirm: (message: string, callback: (ok: boolean) => void) => void;
  HapticFeedback?: Haptic;
  BackButton: { show: () => void; hide: () => void; onClick: (cb: () => void) => void; offClick: (cb: () => void) => void };
  setHeaderColor?: (color: string) => void;
  version: string;
};

declare global {
  interface Window {
    Telegram?: { WebApp: TelegramWebApp };
  }
}

export const tg: TelegramWebApp | undefined = window.Telegram?.WebApp;

export function haptic(kind: "light" | "success" | "error" = "light") {
  const h = tg?.HapticFeedback;
  if (!h) return;
  if (kind === "light") h.impactOccurred("light");
  else h.notificationOccurred(kind);
}

function versionAtLeast(version: string, min: string): boolean {
  const a = version.split(".").map(Number);
  const b = min.split(".").map(Number);
  for (let i = 0; i < Math.max(a.length, b.length); i++) {
    if ((a[i] ?? 0) !== (b[i] ?? 0)) return (a[i] ?? 0) > (b[i] ?? 0);
  }
  return true;
}

export function confirmDialog(message: string): Promise<boolean> {
  // showConfirm eski Telegram versiyalarida yo'q — oddiy confirm'ga tushamiz.
  if (tg && versionAtLeast(tg.version, "6.2")) return new Promise((resolve) => tg.showConfirm(message, resolve));
  return Promise.resolve(window.confirm(message));
}

export function backButtonSupported(): boolean {
  return !!tg && versionAtLeast(tg.version, "6.1");
}

export function openBot(username: string | null, start?: string) {
  if (!username) return;
  const url = `https://t.me/${username}${start ? `?start=${start}` : ""}`;
  if (tg) {
    tg.openTelegramLink(url);
    tg.close();
  } else window.open(url, "_blank");
}
