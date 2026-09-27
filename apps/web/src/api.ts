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
  kind: "template" | "online" | "playlist" | "schedule" | "emoji" | "photo" | "ai_reply" | "stories" | "birthday" | "presence";
  field: string;
  title: string;
  icon: string;
  desc: string;
  flag: string | null;
  default?: string;
  presets?: string[];
  intervals?: number[];
  packs?: { code: string; title: string; items: string[] }[];
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
  ai_reply?: { enabled: boolean };
};

export type AISettings = { enabled: boolean; preset: string; style: string; only_when_away: boolean; signature: boolean };

export type AIState = {
  available: boolean;
  unlocked: boolean;
  daily_limit: number;
  used_today: number;
  presets: { code: string; title: string; desc: string }[];
  max_style_len: number;
  settings: AISettings;
};

export type StoryItem = {
  id: number;
  date: number;
  expire_date: number;
  kind: "photo" | "video" | "other";
  protected: boolean;
  caption: string;
  thumb: string | null;
};

export type BirthdayState = {
  birthday: string | null;
  day: number | null;
  month: number | null;
  year: number | null;
  templates: { template: string; preview: string | null; error?: string }[];
};

export type ReferralState = {
  enabled: boolean;
  mode: "start" | "account";
  code: string;
  qualified: number;
  pending: number;
  bonus_per_referral: number;
  friend_reward: { plan_name: string; days: number };
  milestones: (Milestone & { plan_name: string; reached: boolean; rewarded: boolean })[];
  next: (Milestone & { plan_name: string }) | null;
};

export type PresenceMode = "online" | "recently" | "contacts" | "default";
export type PresenceState = { mode: PresenceMode; online_unlocked: boolean };

export type ScheduleSuggestion = { time: string; text: string };

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
  ai: (accountId: number) => request<AIState>("GET", `/webapp/ai?account_id=${accountId}`),
  saveAi: (accountId: number, body: AISettings) => request<AIState>("PUT", `/webapp/ai?account_id=${accountId}`, body),
  suggest: <T = string>(field: string, topic: string) =>
    request<{ items: T[]; used_today: number }>("POST", "/webapp/ai/suggest", { field, topic }),
  stories: (accountId: number, username: string) =>
    request<{ peer: { name: string; username: string | null }; items: StoryItem[] }>("POST", "/webapp/stories/list", {
      account_id: accountId,
      username,
    }),
  sendStories: (accountId: number, username: string, storyIds?: number[]) =>
    request<{ ok: boolean }>("POST", "/webapp/stories/send", { account_id: accountId, username, story_ids: storyIds ?? null }),
  referral: () => request<ReferralState>("GET", "/webapp/referral"),
  birthday: (accountId: number) => request<BirthdayState>("GET", `/webapp/birthday?account_id=${accountId}`),
  saveBirthday: (accountId: number, body: { day: number; month: number; year: number | null }) =>
    request<BirthdayState>("PUT", `/webapp/birthday?account_id=${accountId}`, body),
  importBirthday: (accountId: number) => request<BirthdayState>("POST", `/webapp/birthday/import?account_id=${accountId}`),
  presence: (accountId: number) => request<PresenceState>("GET", `/webapp/presence?account_id=${accountId}`),
  savePresence: (accountId: number, mode: PresenceMode) =>
    request<PresenceState>("PUT", `/webapp/presence?account_id=${accountId}`, { mode }),
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

type Usage = { calls: number; input_tokens: number; output_tokens: number; cost_usd: number; cost_known: boolean };

export type AdminAI = {
  model: string;
  enabled: boolean;
  configured: boolean;
  models: { id: string; price_in: number | null; price_out: number | null }[];
  enabled_accounts: number;
  usage: { today: Usage; month: Usage };
};

export type Milestone = { count: number; plan_code: string; days: number };
export type ReferralSettings = {
  enabled: boolean;
  mode: "start" | "account";
  bonus_per_referral: number;
  milestones: Milestone[];
  friend_plan_code: string;
  friend_days: number;
};
export type ReferralAdmin = {
  settings: ReferralSettings;
  plans: { code: string; name: string }[];
  stats: { qualified: number; pending: number; rejected: number; rewards: number; bonus_paid: number };
  top: { user_id: number; name: string; count: number }[];
  recent: { id: number; status: string; created_at: string; referrer: string; referred: string }[];
};
export type Segment = { code: string; plan_code?: string };
export type BroadcastButton = { type: "url" | "webapp" | "copy" | "plans" | "home" | "ref"; text: string; value: string };
export type BroadcastInput = { text: string; segment: Segment; media_id: number | null; buttons: BroadcastButton[] };
export type Broadcast = BroadcastInput & {
  id: number;
  status: "draft" | "sending" | "done" | "cancelled";
  total: number;
  sent: number;
  failed: number;
  blocked: number;
  created_at: string;
  started_at: string | null;
  finished_at: string | null;
};
export type BroadcastMeta = {
  broadcasts: Broadcast[];
  styles: { code: string; title: string; text: string }[];
  segments: { code: string; title: string }[];
  plans: { code: string; name: string }[];
  promos: { code: string; label: string }[];
};
export type UserDetails = {
  accounts: { id: number; name: string; status: string; premium: boolean; services: string[] }[];
  payments: { id: number; amount: number; status: string; created_at: string }[];
  referral: { qualified: number; pending: number; referred_by: string | null };
};
export type SystemStatus = {
  jobs: Record<string, number>;
  errors: { task: string | null; error: string; at: string | null }[];
  active_automations: number;
  error_automations: number;
  ai_accounts: number;
  pending_payments: number;
  webapp_url: string | null;
};

export type Pack = { code?: string; title: string; items: string[] };
export type PacksAdmin = { packs: Pack[]; is_default: boolean; max_items: number; item_max_len: number };

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
  ai: () => request<AdminAI>("GET", `${A}/ai`),
  saveAi: (model: string, enabled: boolean) => request<AdminAI>("PUT", `${A}/ai`, { model, enabled }),
  testAi: () => request<{ ok: boolean; reply?: string; model?: string; ms?: number; error?: string }>("POST", `${A}/ai/test`),
  referrals: () => request<ReferralAdmin>("GET", `${A}/referrals`),
  saveReferralSettings: (body: ReferralSettings) => request<ReferralAdmin>("PUT", `${A}/referrals/settings`, body),
  referralAction: (id: number, action: "qualify" | "reject") => request<{ ok: boolean }>("POST", `${A}/referrals/${id}/${action}`),
  broadcasts: () => request<BroadcastMeta>("GET", `${A}/broadcasts`),
  countRecipients: (segment: Segment) => request<{ total: number }>("POST", `${A}/broadcasts/count`, segment),
  testBroadcast: (body: BroadcastInput) => request<{ ok: boolean }>("POST", `${A}/broadcasts/test`, body),
  startBroadcast: (body: BroadcastInput) => request<Broadcast>("POST", `${A}/broadcasts`, body),
  cancelBroadcast: (id: number) => request<Broadcast>("POST", `${A}/broadcasts/${id}/cancel`),
  userDetails: (id: number) => request<UserDetails>("GET", `${A}/users/${id}/details`),
  messageUser: (id: number, text: string) => request<{ ok: boolean }>("POST", `${A}/users/${id}/message`, { text }),
  timeseries: () => request<{ points: { date: string; users: number; revenue: number }[] }>("GET", `${A}/timeseries`),
  audit: () => request<{ id: number; action: string; actor: string; entity: string; created_at: string }[]>("GET", `${A}/audit`),
  system: () => request<SystemStatus>("GET", `${A}/system`),
  exportUrl: () => `/api${A}/export/users.csv?t=${token}`,
  packs: () => request<PacksAdmin>("GET", `${A}/packs`),
  savePacks: (packs: Pack[]) => request<PacksAdmin>("PUT", `${A}/packs`, { packs }),
  resetPacks: () => request<PacksAdmin>("DELETE", `${A}/packs`),
  paymentSettings: () => request<{ instructions: string }>("GET", `${A}/settings/payment`),
  savePaymentSettings: (instructions: string) => request<{ instructions: string }>("PUT", `${A}/settings/payment`, { instructions }),
};
