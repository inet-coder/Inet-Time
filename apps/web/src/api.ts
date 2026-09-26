import { tg } from "./tg";

export type Flags = Record<string, number | boolean>;

export type Plan = {
  code: string;
  name: string;
  price: number;
  final_price: number;
  discount_percent: number;
  discount_until: string | null;
  duration_days: number;
  flags: Flags;
  badge: string | null;
  description: string | null;
};

export type Feature = { key: string; title: string; service: string };
export type LimitMeta = { key: string; title: string; min: number; max: number };

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
  free_plan: Plan;
  features: Feature[];
  is_admin: boolean;
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
  if (!initData) throw new ApiError(401, "Studiyani Telegram bot ichidan oching");
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
  quote: (code: string, promo: string) => request<Quote>("POST", `/webapp/plans/${code}/quote`, { promo_code: promo || null }),
  buy: (code: string, promo?: string) =>
    request<{ ok: boolean; expires_at: string }>("POST", `/webapp/plans/${code}/buy`, { promo_code: promo || null }),
  topup: (amount: number) =>
    request<{ ok: boolean; payment_id: number; instructions: string }>("POST", "/webapp/topup", { amount }),
};

export type Quote = {
  ok: boolean;
  error?: string;
  plan_code?: string;
  base_price?: number;
  price?: number;
  promo_code?: string | null;
  promo_discount?: number;
  final_price?: number;
};

// --- Admin ---

export type AdminStats = {
  users: number;
  users_week: number;
  paid_users: number;
  accounts: number;
  active_services: number;
  pending_payments: number;
  revenue_month: number;
  sales_month: number;
};

export type AdminPlan = {
  id: number;
  code: string;
  name: string;
  price: number;
  duration_days: number;
  flags: Flags;
  is_active: boolean;
  description: string | null;
  badge: string | null;
  sort_order: number;
  discount_percent: number;
  discount_until: string | null;
  subscribers?: number;
};

export type PlanInput = Omit<AdminPlan, "id" | "code" | "subscribers"> & { code?: string };

export type Promo = {
  id: number;
  code: string;
  discount_percent: number | null;
  discount_amount: number | null;
  plan_codes: string[];
  max_uses: number | null;
  used_count: number;
  valid_until: string | null;
  is_active: boolean;
  note: string | null;
};

export type PromoInput = Omit<Promo, "id" | "used_count">;

export type AdminPayment = {
  id: number;
  amount: number;
  status: string;
  plan_name: string | null;
  created_at: string;
  confirmed_at: string | null;
  user: { id: number; telegram_user_id: number; name: string };
};

export type AdminUserRow = {
  id: number;
  telegram_user_id: number;
  name: string;
  first_name: string | null;
  balance: number;
  is_banned: boolean;
  is_admin: boolean;
  created_at: string | null;
  plan: { code: string; name: string; expires_at: string | null };
  usage: { accounts: number; automations: number };
};

const A = "/webapp/admin";

export const adminApi = {
  stats: () => request<AdminStats>("GET", `${A}/stats`),
  plans: () => request<{ plans: AdminPlan[]; limits: LimitMeta[]; features: Feature[] }>("GET", `${A}/plans`),
  createPlan: (body: PlanInput & { code: string }) => request<AdminPlan>("POST", `${A}/plans`, body),
  updatePlan: (id: number, body: PlanInput) => request<AdminPlan>("PUT", `${A}/plans/${id}`, body),
  promos: () => request<Promo[]>("GET", `${A}/promos`),
  createPromo: (body: PromoInput) => request<Promo>("POST", `${A}/promos`, body),
  updatePromo: (id: number, body: PromoInput) => request<Promo>("PUT", `${A}/promos/${id}`, body),
  deletePromo: (id: number) => request<{ ok: boolean }>("DELETE", `${A}/promos/${id}`),
  payments: (status: string) => request<AdminPayment[]>("GET", `${A}/payments?status=${status}`),
  confirmPayment: (id: number) => request<{ ok: boolean }>("POST", `${A}/payments/${id}/confirm`),
  rejectPayment: (id: number) => request<{ ok: boolean }>("POST", `${A}/payments/${id}/reject`, {}),
  users: (q: string) => request<AdminUserRow[]>("GET", `${A}/users?q=${encodeURIComponent(q)}`),
  adjustBalance: (id: number, amount: number, reason: string) =>
    request<{ user: AdminUserRow }>("POST", `${A}/users/${id}/balance`, { amount, reason }),
  grant: (id: number, plan_code: string, days: number) => request<{ user: AdminUserRow }>("POST", `${A}/users/${id}/grant`, { plan_code, days }),
  ban: (id: number, banned: boolean) => request<{ user: AdminUserRow }>("POST", `${A}/users/${id}/ban`, { banned }),
  paymentSettings: () => request<{ instructions: string }>("GET", `${A}/settings/payment`),
  savePaymentSettings: (instructions: string) => request<{ instructions: string }>("PUT", `${A}/settings/payment`, { instructions }),
};
