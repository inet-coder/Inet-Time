import { tg } from "./tg";

export type Flags = Record<string, number | boolean>;

export type Plan = { code: string; name: string; price: number; duration_days: number; flags: Flags };

export type CatalogService = {
  code: string;
  kind: "template" | "online" | "playlist" | "schedule" | "emoji" | "photo";
  field: string;
  title: string;
  icon: string;
  desc: string;
  flag: string | null;
  default?: string;
  presets?: string[];
  intervals?: number[];
  unlocked: boolean;
};

export type Action = { field: string; template: string; at_time: string | null };

export type ActiveService = {
  id: number;
  service_code: string;
  status: "ACTIVE" | "STARTING" | "ERROR";
  field: string;
  template: string;
  selection_strategy: "NONE" | "SEQUENTIAL" | "RANDOM" | "BY_TIME";
  interval_seconds: number | null;
  error_message: string | null;
  actions: Action[];
  preview: { field: string; current: string; next: string | null; next_at: string | null };
};

export type Account = { id: number; username: string | null; first_name: string | null; status: string; is_premium: boolean };

export type State = {
  user: { id: number; balance: number; is_banned: boolean; referral_code: string };
  plan: { code: string; name: string; expires_at: string | null; flags: Flags };
  usage: { accounts: number; automations: number };
  plans: Plan[];
  catalog: CatalogService[];
  variables: { key: string; label: string }[];
  limits: Record<string, number>;
  timezone: string;
  payment_instructions: string;
  bot_username: string | null;
  accounts: Account[];
  account: Account | null;
  services?: ActiveService[];
  originals?: Record<string, string | null>;
};

export class ApiError extends Error {
  constructor(public status: number, message: string) {
    super(message);
  }
}

let token: string | null = null;

export function mediaUrl(id: string | number): string {
  return `/api/webapp/media/${id}?t=${token}`;
}

export function emojiUrl(id: string): string {
  return `/api/webapp/emoji/${id}?t=${token}`;
}

async function request<T>(method: string, path: string, body?: unknown): Promise<T> {
  const resp = await fetch(`/api${path}`, {
    method,
    headers: { "Content-Type": "application/json", ...(token ? { Authorization: `Bearer ${token}` } : {}) },
    body: body === undefined ? undefined : JSON.stringify(body),
  });
  if (!resp.ok) {
    let message = "Xatolik yuz berdi, qaytadan urinib ko'ring";
    try {
      const data = await resp.json();
      if (typeof data.detail === "string") message = data.detail;
      else if (data.detail?.message) message = data.detail.message;
    } catch {
      /* javob JSON emas */
    }
    throw new ApiError(resp.status, message);
  }
  return resp.json();
}

export async function authenticate(): Promise<void> {
  const initData = tg?.initData;
  if (!initData) throw new ApiError(401, "Ilovani Telegram bot ichidan oching");
  const result = await request<{ token: string }>("POST", "/webapp/auth", { init_data: initData });
  token = result.token;
}

export const api = {
  state: (accountId?: number) => request<State>("GET", `/webapp/state${accountId ? `?account_id=${accountId}` : ""}`),
  preview: (accountId: number, field: string, template: string) =>
    request<{ ok: boolean; now?: string; later?: string; error?: string; limit: number; length?: number }>(
      "POST",
      "/webapp/preview",
      { account_id: accountId, field, template },
    ),
  enable: (body: {
    account_id: number;
    service_code: string;
    field?: string;
    items: { template: string; at_time?: string }[];
    interval_seconds?: number;
    selection_strategy?: string;
  }) => request<{ ok: boolean }>("POST", "/webapp/services", body),
  stop: (automationId: number, restore = true) =>
    request<{ ok: boolean }>("POST", `/webapp/services/${automationId}/stop?restore=${restore}`),
  uploadMedia: (dataB64: string) => request<{ id: number }>("POST", "/webapp/media", { data_b64: dataB64, mime: "image/jpeg" }),
  buy: (code: string) => request<{ ok: boolean; expires_at: string }>("POST", `/webapp/plans/${code}/buy`),
  topup: (amount: number) =>
    request<{ ok: boolean; payment_id: number; instructions: string }>("POST", "/webapp/topup", { amount }),
};
