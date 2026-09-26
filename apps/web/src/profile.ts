import type { ActiveService, Plan, State } from "./api";

export type ProfileView = {
  name: string;
  bio: string | null;
  emoji: string | null;
  photo: string | null;
  online: boolean;
  username: string | null;
  premium: boolean;
};

export type Mode = "now" | "next";

// Tahrirlash paytida qoralama qiymatlari — profil kartasida "saqlagandan keyin shunday bo'ladi" ko'rinishi uchun.
export type Overrides = Partial<Record<"name" | "bio" | "emoji_status" | "photo" | "online", string | null>>;

function valueFor(service: ActiveService | undefined, mode: Mode): string | null {
  if (!service) return null;
  const { current, next } = service.preview;
  if (mode === "next" && next && next !== "🎲") return next;
  return current;
}

export function buildProfile(state: State, mode: Mode, overrides: Overrides = {}): ProfileView {
  const services = state.services ?? [];
  const byField = (field: string) => services.find((s) => s.field === field && s.status !== "ERROR");
  const originals = state.originals ?? {};
  const account = state.account!;

  const pick = (field: keyof Overrides, fallback: string | null) =>
    field in overrides ? overrides[field] ?? null : valueFor(byField(field), mode) ?? fallback;

  return {
    name: pick("name", account.first_name ?? "") ?? "",
    bio: pick("bio", originals.bio ?? null),
    emoji: pick("emoji_status", originals.emoji_status || null) || null,
    photo: pick("photo", null),
    online: "online" in overrides ? overrides.online === "true" : !!byField("online"),
    username: account.username,
    premium: account.is_premium,
  };
}

// Faqat haqiqatan rejalashtirilgan o'zgarishlar — xatolikdagi xizmat hech narsa o'zgartirmaydi.
export function upcoming(state: State): ActiveService[] {
  return (state.services ?? [])
    .filter((s) => s.status === "ACTIVE" && s.preview.next && s.preview.next_at)
    .sort((a, b) => (a.preview.next_at! < b.preview.next_at! ? -1 : 1));
}

export function nextChangeAt(state: State): string | null {
  const times = upcoming(state)
    .map((s) => s.preview.next_at as string)
    .sort();
  return times[0] ?? null;
}

// Xizmatni ochadigan eng arzon tarif — "PRO" o'rniga aniq nom ko'rsatish uchun.
export function unlockingPlan(state: State, flag: string | null): Plan | undefined {
  if (!flag) return undefined;
  return state.plans.filter((p) => p.flags[flag]).sort((a, b) => a.final_price - b.final_price)[0];
}
