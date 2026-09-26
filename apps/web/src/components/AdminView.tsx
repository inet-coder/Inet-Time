import { useQuery, useQueryClient } from "@tanstack/react-query";
import {
  Ban,
  BadgePercent,
  Check,
  Bot,
  ChevronRight,
  ListMusic,
  RotateCcw,
  Trash2,
  CreditCard,
  Gift,
  Layers,
  LayoutDashboard,
  Minus,
  Plus,
  Search,
  Settings,
  Shuffle,
  Ticket,
  TrendingUp,
  UserCheck,
  Users,
  Wallet,
  X,
  Zap,
} from "lucide-react";
import { useEffect, useState, type ReactNode } from "react";
import {
  adminApi,
  type AdminPayment,
  type AdminPlan,
  type AdminUserRow,
  type Feature,
  type LimitMeta,
  type Pack,
  type PlanInput,
  type Promo,
  type PromoInput,
} from "../api";
import { ServiceIcon } from "../icons";
import { confirmDialog, haptic } from "../tg";
import { dateText, fromDateInput, money, toDateInput } from "../util";
import { Sheet } from "./Sheet";

type Toast = (text: string, kind?: "ok" | "err") => void;
type Section = "home" | "payments" | "plans" | "promos" | "packs" | "users" | "ai" | "settings";

const SECTIONS: [Section, typeof Zap, string][] = [
  ["home", LayoutDashboard, "Umumiy"],
  ["payments", CreditCard, "To'lovlar"],
  ["plans", Layers, "Tariflar"],
  ["promos", Ticket, "Promokodlar"],
  ["packs", ListMusic, "Playlistlar"],
  ["users", Users, "Foydalanuvchilar"],
  ["ai", Bot, "AI"],
  ["settings", Settings, "Sozlamalar"],
];

// Mutatsiyadan keyin tegishli ro'yxatlar va foydalanuvchi holati (narxlar) yangilansin.
function useRefresh() {
  const qc = useQueryClient();
  return () => {
    qc.invalidateQueries({ queryKey: ["admin"] });
    qc.invalidateQueries({ queryKey: ["state"] });
  };
}

async function run(toast: Toast, fn: () => Promise<unknown>, ok: string): Promise<boolean> {
  try {
    await fn();
    haptic("success");
    toast(ok);
    return true;
  } catch (e) {
    haptic("error");
    toast((e as Error).message, "err");
    return false;
  }
}

// --- Kichik UI bo'laklari ---

function Field({ label, hint, children }: { label: string; hint?: string; children: ReactNode }) {
  return (
    <div className="field">
      <label className="label">{label}</label>
      {children}
      {hint && <p className="hint field__hint">{hint}</p>}
    </div>
  );
}

function Toggle({ on, onChange, children }: { on: boolean; onChange: (v: boolean) => void; children: ReactNode }) {
  return (
    <button className="toggle-row" onClick={() => onChange(!on)}>
      <span className="toggle-row__body">{children}</span>
      <span className={`switch ${on ? "is-on" : ""}`}>
        <i />
      </span>
    </button>
  );
}

function Stepper({ value, min, max, onChange }: { value: number; min: number; max: number; onChange: (v: number) => void }) {
  const set = (v: number) => onChange(Math.max(min, Math.min(max, v)));
  return (
    <div className="stepper">
      <button onClick={() => set(value - 1)} disabled={value <= min} aria-label="Kamaytirish">
        <Minus size={16} />
      </button>
      <input inputMode="numeric" value={value} onChange={(e) => set(Number(e.target.value.replace(/\D/g, "")) || min)} />
      <button onClick={() => set(value + 1)} disabled={value >= max} aria-label="Oshirish">
        <Plus size={16} />
      </button>
    </div>
  );
}

function NumberInput({ value, onChange, placeholder, suffix }: { value: string; onChange: (v: string) => void; placeholder?: string; suffix?: string }) {
  return (
    <div className="input-suffix">
      <input className="input" inputMode="numeric" value={value} placeholder={placeholder} onChange={(e) => onChange(e.target.value.replace(/\D/g, ""))} />
      {suffix && <span>{suffix}</span>}
    </div>
  );
}

function Empty({ icon, text }: { icon: ReactNode; text: string }) {
  return (
    <div className="card placeholder">
      {icon}
      <span>{text}</span>
    </div>
  );
}

// --- Umumiy ---

function StatCard({ icon, value, label, tone }: { icon: ReactNode; value: ReactNode; label: string; tone?: string }) {
  return (
    <div className={`stat stat--${tone ?? "default"}`}>
      <span className="stat__icon">{icon}</span>
      <span className="stat__value">{value}</span>
      <span className="stat__label">{label}</span>
    </div>
  );
}

function Home({ toast, go }: { toast: Toast; go: (s: Section) => void }) {
  const { data } = useQuery({ queryKey: ["admin", "stats"], queryFn: adminApi.stats, refetchInterval: 30000 });
  if (!data) return <div className="spinner spinner--center" />;
  return (
    <div className="stack">
      <div className="stat-grid">
        <StatCard icon={<Users size={16} />} value={data.users} label={`foydalanuvchi · +${data.users_week} hafta`} />
        <StatCard icon={<UserCheck size={16} />} value={data.paid_users} label="pullik tarifda" tone="ok" />
        <StatCard icon={<TrendingUp size={16} />} value={money(data.revenue_month).replace(" so'm", "")} label="so'm kirim · 30 kun" tone="premium" />
        <StatCard icon={<Zap size={16} />} value={data.active_services} label={`faol xizmat · ${data.accounts} akkaunt`} />
      </div>
      <button className="card row-card" onClick={() => go("payments")}>
        <span className={`row-card__icon ${data.pending_payments ? "is-alert" : ""}`}>
          <CreditCard size={18} />
        </span>
        <span className="row-card__body">
          <b>Kutilayotgan to'lovlar</b>
          <span className="hint">{data.pending_payments ? `${data.pending_payments} ta so'rov tasdiq kutmoqda` : "Hammasi ko'rib chiqilgan"}</span>
        </span>
        {data.pending_payments > 0 && <span className="count-badge">{data.pending_payments}</span>}
        <ChevronRight size={18} className="list-item__chev" />
      </button>
      <h3 className="section-title">Tezkor</h3>
      <div className="quick-grid">
        <button className="quick" onClick={() => go("promos")}>
          <Ticket size={20} /> Promokod yaratish
        </button>
        <button className="quick" onClick={() => go("plans")}>
          <BadgePercent size={20} /> Aksiya e'lon qilish
        </button>
        <button className="quick" onClick={() => go("users")}>
          <Gift size={20} /> Tarif sovg'a qilish
        </button>
        <button className="quick" onClick={() => go("settings")}>
          <Wallet size={20} /> To'lov rekvizitlari
        </button>
      </div>
      <p className="hint center">Oxirgi 30 kunda {data.sales_month} ta tarif sotildi.</p>
      <PendingInline toast={toast} />
    </div>
  );
}

function PendingInline({ toast }: { toast: Toast }) {
  const { data } = useQuery({ queryKey: ["admin", "payments", "PENDING"], queryFn: () => adminApi.payments("PENDING") });
  if (!data?.length) return null;
  return (
    <>
      <h3 className="section-title">Tasdiq kutmoqda</h3>
      <PaymentList items={data.slice(0, 3)} toast={toast} />
    </>
  );
}

// --- To'lovlar ---

const PAY_STATUS: Record<string, [string, string]> = {
  PENDING: ["Kutilmoqda", "wait"],
  PAID: ["Tasdiqlangan", "ok"],
  CANCELLED: ["Rad etilgan", "err"],
  FAILED: ["Xato", "err"],
  REFUNDED: ["Qaytarilgan", "wait"],
};

function PaymentList({ items, toast }: { items: AdminPayment[]; toast: Toast }) {
  const refresh = useRefresh();
  const [busy, setBusy] = useState<number | null>(null);
  const act = async (p: AdminPayment, confirm: boolean) => {
    const question = confirm
      ? `${p.user.name} balansiga ${money(p.amount)} qo'shilsinmi? Pul kelganini tekshirdingizmi?`
      : `So'rov #${p.id} rad etilsinmi?`;
    if (!(await confirmDialog(question))) return;
    setBusy(p.id);
    const ok = await run(
      toast,
      () => (confirm ? adminApi.confirmPayment(p.id) : adminApi.rejectPayment(p.id)),
      confirm ? `#${p.id} tasdiqlandi` : `#${p.id} rad etildi`,
    );
    setBusy(null);
    if (ok) refresh();
  };
  return (
    <section className="card card--list">
      {items.map((p) => {
        const [label, tone] = PAY_STATUS[p.status] ?? [p.status, "wait"];
        return (
          <div key={p.id} className="pay">
            <div className="pay__main">
              <div className="pay__top">
                <b>{money(p.amount)}</b>
                <span className={`status status--${tone}`}>{label}</span>
              </div>
              <span className="hint">
                #{p.id} · {p.user.name} · {p.plan_name ? `${p.plan_name} tarifi` : "balans to'ldirish"} · {dateText(p.created_at)}
              </span>
            </div>
            {p.status === "PENDING" && (
              <div className="pay__actions">
                <button className="mini-btn mini-btn--ok" disabled={busy === p.id} onClick={() => act(p, true)} aria-label="Tasdiqlash">
                  <Check size={18} />
                </button>
                <button className="mini-btn mini-btn--err" disabled={busy === p.id} onClick={() => act(p, false)} aria-label="Rad etish">
                  <X size={18} />
                </button>
              </div>
            )}
          </div>
        );
      })}
    </section>
  );
}

function Payments({ toast }: { toast: Toast }) {
  const [status, setStatus] = useState<"PENDING" | "all">("PENDING");
  const { data } = useQuery({ queryKey: ["admin", "payments", status], queryFn: () => adminApi.payments(status) });
  return (
    <div className="stack">
      <div className="segmented">
        <button className={status === "PENDING" ? "is-selected" : ""} onClick={() => setStatus("PENDING")}>
          Kutilayotgan
        </button>
        <button className={status === "all" ? "is-selected" : ""} onClick={() => setStatus("all")}>
          Barchasi
        </button>
      </div>
      {!data ? (
        <div className="spinner spinner--center" />
      ) : data.length === 0 ? (
        <Empty icon={<CreditCard size={22} />} text={status === "PENDING" ? "Kutilayotgan to'lov yo'q" : "To'lovlar yo'q"} />
      ) : (
        <PaymentList items={data} toast={toast} />
      )}
      <p className="hint">Tasdiqlashdan oldin pul kartangizga kelganini tekshiring. Foydalanuvchiga botda xabar boradi.</p>
    </div>
  );
}

// --- Tariflar ---

function emptyPlan(features: Feature[]): PlanInput & { code: string } {
  return {
    code: "",
    name: "",
    price: 0,
    duration_days: 30,
    flags: { account_limit: 1, scheduler_limit: 3, ...Object.fromEntries(features.map((f) => [f.key, false])) },
    is_active: true,
    description: "",
    badge: "",
    sort_order: 5,
    discount_percent: 0,
    discount_until: null,
  };
}

function PlanEditor({
  plan,
  limits,
  features,
  onClose,
  toast,
}: {
  plan: AdminPlan | null;
  limits: LimitMeta[];
  features: Feature[];
  onClose: () => void;
  toast: Toast;
}) {
  const refresh = useRefresh();
  const [form, setForm] = useState<PlanInput & { code: string }>(() => (plan ? { ...plan, code: plan.code } : emptyPlan(features)));
  const [busy, setBusy] = useState(false);
  const isFree = form.code === "free";
  const set = (patch: Partial<typeof form>) => setForm({ ...form, ...patch });
  const setFlag = (key: string, value: number | boolean) => set({ flags: { ...form.flags, [key]: value } });
  const finalPrice = Math.round((form.price * (100 - (form.discount_percent || 0))) / 100);

  const save = async () => {
    setBusy(true);
    const body = { ...form, description: form.description || null, badge: form.badge || null };
    const ok = await run(toast, () => (plan ? adminApi.updatePlan(plan.id, body) : adminApi.createPlan(body)), `${form.name} saqlandi`);
    setBusy(false);
    if (ok) {
      refresh();
      onClose();
    }
  };

  return (
    <Sheet title={plan ? plan.name : "Yangi tarif"} onClose={onClose}>
      {!plan && (
        <Field label="Kod" hint="Lotin harflarda, keyin o'zgarmaydi. Masalan: premium, yearly">
          <input className="input" value={form.code} onChange={(e) => set({ code: e.target.value.toLowerCase().replace(/[^a-z0-9_]/g, "") })} />
        </Field>
      )}
      <Field label="Nomi">
        <input className="input" value={form.name} onChange={(e) => set({ name: e.target.value })} />
      </Field>
      {!isFree && (
        <div className="grid2">
          <Field label="Narx">
            <NumberInput value={form.price ? String(form.price) : ""} suffix="so'm" onChange={(v) => set({ price: Number(v) })} />
          </Field>
          <Field label="Muddat">
            <NumberInput value={String(form.duration_days)} suffix="kun" onChange={(v) => set({ duration_days: Number(v) })} />
          </Field>
        </div>
      )}
      <Field label="Tavsif" hint="Tarif kartasida ko'rinadi (ixtiyoriy)">
        <textarea className="input" rows={2} value={form.description ?? ""} onChange={(e) => set({ description: e.target.value })} />
      </Field>

      <label className="label">Limitlar</label>
      <div className="card-inset">
        {limits.map((l) => (
          <div key={l.key} className="limit-row">
            <span>{l.title}</span>
            <Stepper value={Number(form.flags[l.key] ?? l.min)} min={l.min} max={l.max} onChange={(v) => setFlag(l.key, v)} />
          </div>
        ))}
      </div>

      <label className="label">Xizmatlar</label>
      <div className="card-inset">
        <div className="toggle-row is-static">
          <span className="toggle-row__body">
            <ServiceIcon code="clock_name" size={28} /> Soat, avto bio, avto ism
          </span>
          <span className="hint">doim</span>
        </div>
        {features.map((f) => (
          <Toggle key={f.key} on={!!form.flags[f.key]} onChange={(v) => setFlag(f.key, v)}>
            <ServiceIcon code={f.service} size={28} /> {f.title}
          </Toggle>
        ))}
      </div>

      {!isFree && (
        <>
          <label className="label">Aksiya (chegirma)</label>
          <div className="card-inset card-inset--pad">
            <div className="chips">
              {[0, 10, 20, 30, 50].map((d) => (
                <button key={d} className={`chip-btn ${form.discount_percent === d ? "is-selected" : ""}`} onClick={() => set({ discount_percent: d })}>
                  {d ? `−${d}%` : "Yo'q"}
                </button>
              ))}
            </div>
            <NumberInput
              value={form.discount_percent ? String(form.discount_percent) : ""}
              placeholder="Boshqa foiz"
              suffix="%"
              onChange={(v) => set({ discount_percent: Math.min(95, Number(v)) })}
            />
            {form.discount_percent > 0 && (
              <>
                <Field label="Qaysi kungacha" hint="Bo'sh qoldirsangiz — o'chirmaguningizcha amal qiladi">
                  <input
                    className="input"
                    type="date"
                    value={toDateInput(form.discount_until)}
                    onChange={(e) => set({ discount_until: fromDateInput(e.target.value) })}
                  />
                </Field>
                <div className="price-preview">
                  Foydalanuvchi ko'radi: <s>{money(form.price)}</s> <b>{money(finalPrice)}</b>
                </div>
              </>
            )}
          </div>
          <Field label="Belgi (lenta)" hint="Masalan: Eng ko'p imkoniyat, Tavsiya etiladi. Bo'sh — belgisiz">
            <input className="input" value={form.badge ?? ""} onChange={(e) => set({ badge: e.target.value })} />
          </Field>
          <div className="card-inset">
            <Toggle on={form.is_active} onChange={(v) => set({ is_active: v })}>
              Sotuvda (foydalanuvchilarga ko'rinadi)
            </Toggle>
          </div>
        </>
      )}
      <Field label="Tartib raqami" hint="Kichigi oldin turadi">
        <Stepper value={form.sort_order} min={0} max={99} onChange={(v) => set({ sort_order: v })} />
      </Field>
      <button className="btn btn--primary" disabled={busy || !form.name.trim() || (!plan && form.code.length < 2)} onClick={save}>
        Saqlash
      </button>
      {plan && plan.subscribers ? <p className="hint center">Hozir {plan.subscribers} ta faol obunachi. O'zgarishlar ularga ham darhol ta'sir qiladi.</p> : null}
    </Sheet>
  );
}

function Plans({ toast }: { toast: Toast }) {
  const { data } = useQuery({ queryKey: ["admin", "plans"], queryFn: adminApi.plans });
  const [editing, setEditing] = useState<AdminPlan | "new" | null>(null);
  if (!data) return <div className="spinner spinner--center" />;
  return (
    <div className="stack">
      {data.plans.map((p) => {
        const discount = p.discount_percent > 0 && (!p.discount_until || new Date(p.discount_until) > new Date());
        return (
          <button key={p.id} className={`card admin-plan ${p.is_active ? "" : "is-off"}`} onClick={() => setEditing(p)}>
            <div className="admin-plan__head">
              <b>{p.name}</b>
              <span className="admin-plan__price">
                {p.code === "free" ? "tekin" : discount ? (
                  <>
                    <s>{money(p.price)}</s> {money(Math.round((p.price * (100 - p.discount_percent)) / 100))}
                  </>
                ) : (
                  money(p.price)
                )}
              </span>
            </div>
            <div className="admin-plan__meta">
              <span>{String(p.flags.account_limit)} akk · {String(p.flags.scheduler_limit)} xizmat</span>
              {p.code !== "free" && <span>{p.duration_days} kun</span>}
              {p.code !== "free" && <span>{p.subscribers} obunachi</span>}
              {discount && <span className="sale">−{p.discount_percent}%</span>}
              {!p.is_active && <span className="status status--err">sotuvda emas</span>}
            </div>
            <div className="admin-plan__icons">
              {data.features.map((f) => (
                <span key={f.key} className={p.flags[f.key] ? "" : "is-off"}>
                  <ServiceIcon code={f.service} size={24} />
                </span>
              ))}
            </div>
          </button>
        );
      })}
      <button className="btn btn--ghost" onClick={() => setEditing("new")}>
        <Plus size={18} /> Yangi tarif
      </button>
      {editing && (
        <PlanEditor
          plan={editing === "new" ? null : editing}
          limits={data.limits}
          features={data.features}
          onClose={() => setEditing(null)}
          toast={toast}
        />
      )}
    </div>
  );
}

// --- Promokodlar ---

function randomCode(): string {
  const chars = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789";
  return Array.from({ length: 8 }, () => chars[Math.floor(Math.random() * chars.length)]).join("");
}

function promoText(p: Promo): string {
  return p.discount_percent ? `−${p.discount_percent}%` : `−${money(p.discount_amount ?? 0)}`;
}

function PromoEditor({ promo, planOptions, onClose, toast }: { promo: Promo | null; planOptions: AdminPlan[]; onClose: () => void; toast: Toast }) {
  const refresh = useRefresh();
  const [code, setCode] = useState(promo?.code ?? randomCode());
  const [kind, setKind] = useState<"percent" | "amount">(promo?.discount_amount ? "amount" : "percent");
  const [value, setValue] = useState(String(promo?.discount_percent ?? promo?.discount_amount ?? 20));
  const [plans, setPlans] = useState<string[]>(promo?.plan_codes ?? []);
  const [maxUses, setMaxUses] = useState(promo?.max_uses ? String(promo.max_uses) : "");
  const [until, setUntil] = useState<string | null>(promo?.valid_until ?? null);
  const [note, setNote] = useState(promo?.note ?? "");
  const [active, setActive] = useState(promo?.is_active ?? true);
  const [busy, setBusy] = useState(false);
  const num = Number(value);
  const valid = code.length >= 3 && num > 0 && (kind === "amount" || num <= 100);

  const body = (): PromoInput => ({
    code,
    discount_percent: kind === "percent" ? num : null,
    discount_amount: kind === "amount" ? num : null,
    plan_codes: plans,
    max_uses: maxUses ? Number(maxUses) : null,
    valid_until: until,
    is_active: active,
    note: note || null,
  });

  const save = async () => {
    setBusy(true);
    const ok = await run(toast, () => (promo ? adminApi.updatePromo(promo.id, body()) : adminApi.createPromo(body())), `${code} saqlandi`);
    setBusy(false);
    if (ok) {
      refresh();
      onClose();
    }
  };

  const remove = async () => {
    if (!promo || !(await confirmDialog(`${promo.code} o'chirilsinmi?`))) return;
    if (await run(toast, () => adminApi.deletePromo(promo.id), `${promo.code} o'chirildi`)) {
      refresh();
      onClose();
    }
  };

  return (
    <Sheet title={promo ? promo.code : "Yangi promokod"} onClose={onClose}>
      <Field label="Kod" hint="Foydalanuvchi to'lov oynasida kiritadi">
        <div className="row">
          <input
            className="input input--code"
            value={code}
            disabled={!!promo}
            onChange={(e) => setCode(e.target.value.toUpperCase().replace(/[^A-Z0-9_-]/g, ""))}
          />
          {!promo && (
            <button className="icon-btn icon-btn--soft" onClick={() => setCode(randomCode())} aria-label="Tasodifiy kod">
              <Shuffle size={18} />
            </button>
          )}
        </div>
      </Field>
      <Field label="Chegirma">
        <div className="segmented">
          <button className={kind === "percent" ? "is-selected" : ""} onClick={() => setKind("percent")}>
            Foiz, %
          </button>
          <button className={kind === "amount" ? "is-selected" : ""} onClick={() => setKind("amount")}>
            Summa, so'm
          </button>
        </div>
        <div className="spaced">
          <NumberInput value={value} suffix={kind === "percent" ? "%" : "so'm"} onChange={setValue} />
        </div>
      </Field>
      {kind === "percent" && (
        <div className="chips">
          {[10, 20, 30, 50, 100].map((d) => (
            <button key={d} className={`chip-btn ${num === d ? "is-selected" : ""}`} onClick={() => setValue(String(d))}>
              {d === 100 ? "Tekin (100%)" : `${d}%`}
            </button>
          ))}
        </div>
      )}
      <Field label="Qaysi tariflarga" hint={plans.length ? undefined : "Hech biri tanlanmasa — barcha pullik tariflarga"}>
        <div className="chips">
          {planOptions.map((p) => {
            const on = plans.includes(p.code);
            return (
              <button
                key={p.code}
                className={`chip-btn ${on ? "is-selected" : ""}`}
                onClick={() => setPlans(on ? plans.filter((c) => c !== p.code) : [...plans, p.code])}
              >
                {on && <Check size={13} strokeWidth={2.6} />} {p.name}
              </button>
            );
          })}
        </div>
      </Field>
      <div className="grid2">
        <Field label="Necha marta" hint="Bo'sh — cheksiz">
          <NumberInput value={maxUses} placeholder="∞" onChange={setMaxUses} />
        </Field>
        <Field label="Muddati" hint="Bo'sh — muddatsiz">
          <input className="input" type="date" value={toDateInput(until)} onChange={(e) => setUntil(fromDateInput(e.target.value))} />
        </Field>
      </div>
      <Field label="Izoh (faqat admin uchun)">
        <input className="input" value={note} placeholder="Masalan: Instagram aksiyasi" onChange={(e) => setNote(e.target.value)} />
      </Field>
      <div className="card-inset">
        <Toggle on={active} onChange={setActive}>
          Faol
        </Toggle>
      </div>
      <p className="hint">Har bir foydalanuvchi promokodni bir marta ishlata oladi.</p>
      <button className="btn btn--primary" disabled={busy || !valid} onClick={save}>
        Saqlash
      </button>
      {promo && promo.used_count === 0 && (
        <button className="btn btn--danger" onClick={remove}>
          O'chirish
        </button>
      )}
    </Sheet>
  );
}

function Promos({ toast }: { toast: Toast }) {
  const { data } = useQuery({ queryKey: ["admin", "promos"], queryFn: adminApi.promos });
  const plans = useQuery({ queryKey: ["admin", "plans"], queryFn: adminApi.plans });
  const refresh = useRefresh();
  const [editing, setEditing] = useState<Promo | "new" | null>(null);
  const paidPlans = (plans.data?.plans ?? []).filter((p) => p.code !== "free");
  const planName = (code: string) => paidPlans.find((p) => p.code === code)?.name ?? code;

  const toggle = async (p: Promo) => {
    const { id, used_count, ...rest } = p;
    void used_count;
    if (await run(toast, () => adminApi.updatePromo(id, { ...rest, is_active: !p.is_active }), p.is_active ? "O'chirildi" : "Yoqildi")) refresh();
  };

  return (
    <div className="stack">
      <button className="btn btn--primary" style={{ marginTop: 0 }} onClick={() => setEditing("new")}>
        <Plus size={18} /> Yangi promokod
      </button>
      {!data ? (
        <div className="spinner spinner--center" />
      ) : data.length === 0 ? (
        <Empty icon={<Ticket size={22} />} text="Hali promokod yo'q" />
      ) : (
        data.map((p) => {
          const expired = p.valid_until && new Date(p.valid_until) < new Date();
          const exhausted = p.max_uses !== null && p.used_count >= p.max_uses;
          return (
            <div key={p.id} className={`card promo ${p.is_active && !expired && !exhausted ? "" : "is-off"}`}>
              <button className="promo__main" onClick={() => setEditing(p)}>
                <div className="promo__top">
                  <span className="promo__code">{p.code}</span>
                  <span className="promo__value">{promoText(p)}</span>
                </div>
                <div className="promo__meta">
                  <span>{p.plan_codes.length ? p.plan_codes.map(planName).join(", ") : "barcha tariflar"}</span>
                  <span>
                    {p.used_count}/{p.max_uses ?? "∞"} ishlatilgan
                  </span>
                  {p.valid_until && <span className={expired ? "is-err" : ""}>{dateText(p.valid_until)} gacha</span>}
                  {p.note && <span>{p.note}</span>}
                </div>
                {p.max_uses !== null && (
                  <div className="bar">
                    <i style={{ width: `${Math.min(100, (p.used_count / p.max_uses) * 100)}%` }} />
                  </div>
                )}
              </button>
              <button className={`switch ${p.is_active ? "is-on" : ""}`} onClick={() => toggle(p)} aria-label="Faol">
                <i />
              </button>
            </div>
          );
        })
      )}
      {editing && <PromoEditor promo={editing === "new" ? null : editing} planOptions={paidPlans} onClose={() => setEditing(null)} toast={toast} />}
    </div>
  );
}

// --- Playlist to'plamlari ---

function PackEditor({
  pack,
  maxItems,
  maxLen,
  onSave,
  onDelete,
  onClose,
}: {
  pack: Pack | null;
  maxItems: number;
  maxLen: number;
  onSave: (pack: Pack) => Promise<boolean>;
  onDelete?: () => Promise<boolean>;
  onClose: () => void;
}) {
  const [title, setTitle] = useState(pack?.title ?? "");
  const [text, setText] = useState((pack?.items ?? []).join("\n"));
  const [busy, setBusy] = useState(false);
  const lines = text.split("\n").map((l) => l.trim()).filter(Boolean);
  const long = lines.filter((l) => l.length > maxLen);
  const valid = title.trim() && lines.length >= 2 && lines.length <= maxItems && long.length === 0;

  const save = async () => {
    setBusy(true);
    const ok = await onSave({ code: pack?.code, title: title.trim(), items: lines });
    setBusy(false);
    if (ok) onClose();
  };

  return (
    <Sheet title={pack ? pack.title : "Yangi to'plam"} onClose={onClose}>
      <Field label="Nomi" hint="Boshida emoji bo'lsa chiroyli: 😂 Hazil">
        <input className="input" maxLength={40} value={title} onChange={(e) => setTitle(e.target.value)} />
      </Field>
      <Field
        label={`Matnlar (${lines.length}/${maxItems}) — har biri yangi qatorda`}
        hint={`Har matn ${maxLen} belgigacha. {time}, {weekday}, {newyear_days} kabi o'zgaruvchilar ishlaydi. 10 tadan ko'p bo'lsa, foydalanuvchiga tasodifiy 10 tasi tushadi.`}
      >
        <textarea className="input pack-textarea" rows={12} value={text} onChange={(e) => setText(e.target.value)} />
      </Field>
      {long.length > 0 && (
        <div className="preview preview--err">
          <span>
            Juda uzun ({long.length} ta): «{long[0].slice(0, 40)}…» — {long[0].length}/{maxLen}
          </span>
        </div>
      )}
      <button className="btn btn--primary" disabled={busy || !valid} onClick={save}>
        Saqlash
      </button>
      {onDelete && (
        <button
          className="btn btn--danger"
          disabled={busy}
          onClick={async () => {
            if (await confirmDialog(`«${pack?.title}» o'chirilsinmi?`)) {
              setBusy(true);
              if (await onDelete()) onClose();
              setBusy(false);
            }
          }}
        >
          <Trash2 size={16} /> O'chirish
        </button>
      )}
    </Sheet>
  );
}

function PacksAdmin({ toast }: { toast: Toast }) {
  const { data } = useQuery({ queryKey: ["admin", "packs"], queryFn: adminApi.packs });
  const refresh = useRefresh();
  const [editing, setEditing] = useState<number | "new" | null>(null);
  if (!data) return <div className="spinner spinner--center" />;

  const persist = (packs: Pack[], ok: string) =>
    run(toast, () => adminApi.savePacks(packs), ok).then((done) => {
      if (done) refresh();
      return done;
    });

  return (
    <div className="stack">
      <p className="hint">
        Foydalanuvchilar Bio playlist sozlaganda shu to'plamlardan birini bir bosishda tanlaydi.
        {data.is_default ? " Hozir standart to'plamlar." : " To'plamlar siz tomondan o'zgartirilgan."}
      </p>
      <button className="btn btn--primary" style={{ marginTop: 0 }} onClick={() => setEditing("new")}>
        <Plus size={18} /> Yangi to'plam
      </button>
      {data.packs.map((pack, i) => (
        <button key={pack.code ?? i} className="card pack-card" onClick={() => setEditing(i)}>
          <div className="pack-card__head">
            <b>{pack.title}</b>
            <span className="tag">{pack.items.length} ta</span>
          </div>
          <span className="hint">{pack.items.slice(0, 2).join(" · ")}</span>
        </button>
      ))}
      {!data.is_default && (
        <button
          className="btn btn--ghost"
          onClick={async () => {
            if (await confirmDialog("Barcha to'plamlar standart holatga qaytarilsinmi? O'zgarishlaringiz o'chadi.")) {
              if (await run(toast, adminApi.resetPacks, "Standart to'plamlar qaytarildi")) refresh();
            }
          }}
        >
          <RotateCcw size={16} /> Standartga qaytarish
        </button>
      )}
      {editing !== null && (
        <PackEditor
          pack={editing === "new" ? null : data.packs[editing]}
          maxItems={data.max_items}
          maxLen={data.item_max_len}
          onClose={() => setEditing(null)}
          onSave={(pack) =>
            persist(
              editing === "new" ? [...data.packs, pack] : data.packs.map((p, j) => (j === editing ? pack : p)),
              `${pack.title} saqlandi`,
            )
          }
          onDelete={
            editing === "new" || data.packs.length <= 1
              ? undefined
              : () => persist(data.packs.filter((_, j) => j !== editing), "To'plam o'chirildi")
          }
        />
      )}
    </div>
  );
}

// --- Foydalanuvchilar ---

function UserSheet({ user: initial, onClose, toast }: { user: AdminUserRow; onClose: () => void; toast: Toast }) {
  const refresh = useRefresh();
  const plans = useQuery({ queryKey: ["admin", "plans"], queryFn: adminApi.plans });
  const [user, setUser] = useState(initial);
  const [amount, setAmount] = useState("");
  const [reason, setReason] = useState("");
  const [planCode, setPlanCode] = useState("pro");
  const [days, setDays] = useState(30);
  const [busy, setBusy] = useState(false);
  const paid = (plans.data?.plans ?? []).filter((p) => p.code !== "free" && p.is_active);

  const doAction = async (fn: () => Promise<{ user: AdminUserRow }>, ok: string) => {
    setBusy(true);
    try {
      const res = await fn();
      setUser(res.user);
      haptic("success");
      toast(ok);
      refresh();
    } catch (e) {
      haptic("error");
      toast((e as Error).message, "err");
    } finally {
      setBusy(false);
    }
  };

  const adjust = (sign: 1 | -1) => doAction(() => adminApi.adjustBalance(user.id, sign * Number(amount), reason || "Admin"), "Balans o'zgardi");

  return (
    <Sheet title={user.name} onClose={onClose}>
      <p className="hint">
        Telegram ID {user.telegram_user_id} · #{user.id} · {dateText(user.created_at)} dan beri
      </p>
      <div className="stat-grid">
        <StatCard icon={<Wallet size={16} />} value={money(user.balance).replace(" so'm", "")} label="so'm balans" />
        <StatCard
          icon={<Layers size={16} />}
          value={user.plan.name}
          label={user.plan.expires_at ? `${dateText(user.plan.expires_at)} gacha` : "pullik tarif yo'q"}
          tone={user.plan.code === "free" ? undefined : "premium"}
        />
      </div>
      <p className="hint">
        {user.usage.accounts} ta akkaunt · {user.usage.automations} ta faol xizmat
      </p>

      <label className="label">Balans</label>
      <div className="card-inset card-inset--pad">
        <NumberInput value={amount} placeholder="Summa" suffix="so'm" onChange={setAmount} />
        <input className="input" style={{ marginTop: 8 }} placeholder="Sabab (masalan: bonus, qaytarish)" value={reason} onChange={(e) => setReason(e.target.value)} />
        <div className="grid2" style={{ marginTop: 8 }}>
          <button className="btn btn--ghost btn--compact" disabled={busy || !Number(amount)} onClick={() => adjust(1)}>
            <Plus size={16} /> Qo'shish
          </button>
          <button className="btn btn--danger btn--compact" disabled={busy || !Number(amount)} onClick={() => adjust(-1)}>
            <Minus size={16} /> Ayirish
          </button>
        </div>
      </div>

      <label className="label">Tarif sovg'a qilish / uzaytirish</label>
      <div className="card-inset card-inset--pad">
        <div className="chips">
          {paid.map((p) => (
            <button key={p.code} className={`chip-btn ${planCode === p.code ? "is-selected" : ""}`} onClick={() => setPlanCode(p.code)}>
              {p.name}
            </button>
          ))}
        </div>
        <div className="chips">
          {[3, 7, 30, 90, 365].map((d) => (
            <button key={d} className={`chip-btn ${days === d ? "is-selected" : ""}`} onClick={() => setDays(d)}>
              {d} kun
            </button>
          ))}
        </div>
        <button
          className="btn btn--gold btn--compact"
          disabled={busy || !paid.some((p) => p.code === planCode)}
          onClick={() => doAction(() => adminApi.grant(user.id, planCode, days), "Tarif berildi")}
        >
          <Gift size={16} /> {paid.find((p) => p.code === planCode)?.name ?? ""} · {days} kun berish
        </button>
      </div>

      {!user.is_admin && (
        <button
          className={`btn ${user.is_banned ? "btn--ghost" : "btn--danger"}`}
          disabled={busy}
          onClick={async () => {
            if (!(await confirmDialog(user.is_banned ? "Blokdan chiqarilsinmi?" : "Foydalanuvchi bloklansinmi? U ilova va botdan foydalana olmaydi."))) return;
            doAction(() => adminApi.ban(user.id, !user.is_banned), user.is_banned ? "Blokdan chiqarildi" : "Bloklandi");
          }}
        >
          <Ban size={16} /> {user.is_banned ? "Blokdan chiqarish" : "Bloklash"}
        </button>
      )}
    </Sheet>
  );
}

function UsersAdmin({ toast }: { toast: Toast }) {
  const [q, setQ] = useState("");
  const [query, setQuery] = useState("");
  const [open, setOpen] = useState<AdminUserRow | null>(null);
  useEffect(() => {
    const t = setTimeout(() => setQuery(q), 300);
    return () => clearTimeout(t);
  }, [q]);
  const { data } = useQuery({ queryKey: ["admin", "users", query], queryFn: () => adminApi.users(query) });

  return (
    <div className="stack">
      <div className="input-icon">
        <Search size={17} />
        <input className="input" placeholder="Username, ism yoki Telegram ID" value={q} onChange={(e) => setQ(e.target.value)} />
      </div>
      {!data ? (
        <div className="spinner spinner--center" />
      ) : data.length === 0 ? (
        <Empty icon={<Users size={22} />} text="Hech kim topilmadi" />
      ) : (
        <section className="card card--list">
          {data.map((u) => (
            <button key={u.id} className="list-item" onClick={() => setOpen(u)}>
              <span className={`avatar-sm ${u.is_banned ? "is-banned" : ""}`}>{(u.first_name || u.name).replace("@", "").slice(0, 1).toUpperCase()}</span>
              <span className="list-item__body">
                <span className="list-item__title">
                  {u.name} {u.is_admin && <span className="tag">admin</span>} {u.is_banned && <span className="tag tag--err">blok</span>}
                </span>
                <span className="list-item__sub">
                  {u.plan.name} · {money(u.balance)} · {u.usage.automations} xizmat
                </span>
              </span>
              <ChevronRight size={18} className="list-item__chev" />
            </button>
          ))}
        </section>
      )}
      {open && <UserSheet user={open} onClose={() => setOpen(null)} toast={toast} />}
    </div>
  );
}

// --- AI ---

function tokens(n: number): string {
  return n < 1000 ? String(n) : `${Math.round(n / 1000)}k`;
}

function usd(value: number): string {
  return value < 0.01 ? `$${value.toFixed(4)}` : `$${value.toFixed(2)}`;
}

function AIAdmin({ toast }: { toast: Toast }) {
  const { data } = useQuery({ queryKey: ["admin", "ai"], queryFn: adminApi.ai });
  const refresh = useRefresh();
  const [testing, setTesting] = useState(false);
  const [testResult, setTestResult] = useState<string | null>(null);
  if (!data) return <div className="spinner spinner--center" />;

  const save = async (model: string, enabled: boolean) => {
    if (await run(toast, () => adminApi.saveAi(model, enabled), "AI sozlamalari saqlandi")) refresh();
  };
  const test = async () => {
    setTesting(true);
    setTestResult(null);
    const r = await adminApi.testAi().catch((e: Error) => ({ ok: false, error: e.message }) as { ok: boolean; error?: string });
    setTestResult(r.ok ? `✅ Ishlayapti: «${"reply" in r ? r.reply : ""}» · ${"ms" in r ? r.ms : "?"} ms` : `❌ ${r.error}`);
    setTesting(false);
  };
  const usage = (label: string, u: typeof data.usage.today) => (
    <StatCard
      icon={<Bot size={16} />}
      value={u.cost_known ? usd(u.cost_usd) : `${usd(u.cost_usd)}+`}
      label={`${label} · ${u.calls} so'rov · ${tokens(u.input_tokens + u.output_tokens)} token`}
    />
  );

  return (
    <div className="stack">
      {!data.configured && (
        <div className="notice notice--warn">
          <Bot size={18} />
          <span>
            OpenAI kaliti yo'q. Serverdagi <b>.env</b> fayliga <b>OPENAI_API_KEY=sk-…</b> qo'shing va qayta ishga tushiring.
          </span>
        </div>
      )}
      <div className="stat-grid">
        {usage("bugun", data.usage.today)}
        {usage("30 kun", data.usage.month)}
      </div>
      <p className="hint">AI yoqilgan akkauntlar: {data.enabled_accounts}. Kunlik limit har tarifda alohida (Tariflar → AI so'rovlar / kun).</p>

      <section className="card">
        <label className="label" style={{ marginTop: 0 }}>
          Model
        </label>
        <div className="model-list">
          {data.models.map((m) => (
            <button key={m.id} className={`model ${data.model === m.id ? "is-selected" : ""}`} onClick={() => save(m.id, data.enabled)}>
              <b>{m.id}</b>
              <span className="hint">{m.price_in !== null ? `$${m.price_in} / $${m.price_out} · 1M token` : "narx: OpenAI saytida"}</span>
            </button>
          ))}
        </div>
        <p className="hint field__hint">Avto-javob uchun gpt-4o-mini yoki gpt-4.1-nano yetarli va eng arzon.</p>
        <div className="card-inset" style={{ marginTop: 12 }}>
          <Toggle on={data.enabled} onChange={(v) => save(data.model, v)}>
            AI xizmatlari yoqilgan
          </Toggle>
        </div>
        <button className="btn btn--ghost" disabled={testing || !data.configured} onClick={test}>
          <Zap size={16} /> Kalit va modelni tekshirish
        </button>
        {testResult && <p className="hint field__hint">{testResult}</p>}
      </section>
    </div>
  );
}

// --- Sozlamalar ---

function SettingsAdmin({ toast }: { toast: Toast }) {
  const { data } = useQuery({ queryKey: ["admin", "payment-settings"], queryFn: adminApi.paymentSettings });
  const refresh = useRefresh();
  const [text, setText] = useState<string | null>(null);
  const value = text ?? data?.instructions ?? "";
  return (
    <div className="stack">
      <section className="card">
        <label className="label" style={{ marginTop: 0 }}>
          To'lov rekvizitlari
        </label>
        <textarea
          className="input"
          rows={4}
          placeholder={"Masalan:\nUzcard 8600 1234 5678 9012\nIsm Familiya\nClick/Payme: +998 90 123 45 67"}
          value={value}
          onChange={(e) => setText(e.target.value)}
        />
        <p className="hint field__hint">Foydalanuvchi balans to'ldirish so'rovini yuborganda shu matnni ko'radi. Karta, ism va izoh tartibini yozing.</p>
        <button
          className="btn btn--primary"
          disabled={text === null || text === data?.instructions}
          onClick={async () => {
            if (await run(toast, () => adminApi.savePaymentSettings(value), "Rekvizitlar saqlandi")) {
              setText(null);
              refresh();
            }
          }}
        >
          Saqlash
        </button>
      </section>
      {value && (
        <div className="notice notice--ok">
          <Check size={18} />
          <span>
            Foydalanuvchi ko'radi: «To'lov uchun: <b className="pre">{value}</b>. Izohga #so'rov raqamini yozing.»
          </span>
        </div>
      )}
    </div>
  );
}

export function AdminView({ toast }: { toast: Toast }) {
  const [section, setSection] = useState<Section>("home");
  const pending = useQuery({ queryKey: ["admin", "stats"], queryFn: adminApi.stats }).data?.pending_payments ?? 0;
  return (
    <div className="stack">
      <div className="admin-nav">
        {SECTIONS.map(([key, Icon, label]) => (
          <button
            key={key}
            className={section === key ? "is-selected" : ""}
            onClick={(e) => {
              haptic("select");
              setSection(key);
              e.currentTarget.scrollIntoView({ behavior: "smooth", inline: "center", block: "nearest" });
            }}
          >
            <Icon size={16} /> {label}
            {key === "payments" && pending > 0 && <span className="count-badge count-badge--sm">{pending}</span>}
          </button>
        ))}
      </div>
      {section === "home" && <Home toast={toast} go={setSection} />}
      {section === "payments" && <Payments toast={toast} />}
      {section === "plans" && <Plans toast={toast} />}
      {section === "promos" && <Promos toast={toast} />}
      {section === "packs" && <PacksAdmin toast={toast} />}
      {section === "users" && <UsersAdmin toast={toast} />}
      {section === "ai" && <AIAdmin toast={toast} />}
      {section === "settings" && <SettingsAdmin toast={toast} />}
    </div>
  );
}
