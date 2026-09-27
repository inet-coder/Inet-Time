import { Check, CircleCheck, Crown, Layers, Lock, Percent, Sparkles, Star, Tag, Ticket, Users, Wallet, X, type LucideIcon } from "lucide-react";
import { useState } from "react";
import { api, type Flags, type Plan, type Quote, type State } from "../api";
import { ServiceIcon } from "../icons";
import { haptic } from "../tg";
import { dateText, daysLeft, money } from "../util";
import { ReferralCard } from "./ReferralCard";
import { Sheet } from "./Sheet";

const PLAN_ICONS: Record<string, LucideIcon> = { free: Sparkles, starter: Star, pro: Crown };

function planIcon(code: string): LucideIcon {
  return PLAN_ICONS[code] ?? Star;
}

function Features({ state, flags }: { state: State; flags: Flags }) {
  return (
    <ul className="features">
      <li>
        <Users size={16} className="features__icon" /> {flags.account_limit} ta akkaunt
      </li>
      <li>
        <Layers size={16} className="features__icon" /> bir vaqtda {flags.scheduler_limit} ta xizmat
      </li>
      <li>
        <Check size={16} className="features__icon features__icon--ok" /> Soat, avto bio va avto ism
      </li>
      {state.features.map((f) => (
        <li key={f.key} className={flags[f.key] ? "" : "is-off"}>
          {flags[f.key] ? <Check size={16} className="features__icon features__icon--ok" /> : <Lock size={15} className="features__icon" />}
          {f.title}
        </li>
      ))}
    </ul>
  );
}

// Barcha tariflar yonma-yon — nima qo'shilishini bir qarashda ko'rish uchun.
function Compare({ state }: { state: State }) {
  const columns = [state.free_plan, ...state.plans];
  const cell = (on: unknown) =>
    on ? <Check size={16} className="compare__yes" strokeWidth={2.6} /> : <X size={15} className="compare__no" />;
  return (
    <div className="card card--flush compare-wrap">
      <table className="compare">
        <thead>
          <tr>
            <th />
            {columns.map((p) => (
              <th key={p.code} className={p.code === state.plan.code ? "is-current" : ""}>
                {p.name}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          <tr>
            <td>Akkaunt</td>
            {columns.map((p) => (
              <td key={p.code}>{String(p.flags.account_limit)}</td>
            ))}
          </tr>
          <tr>
            <td>Xizmatlar</td>
            {columns.map((p) => (
              <td key={p.code}>{String(p.flags.scheduler_limit)}</td>
            ))}
          </tr>
          {state.features.map((f) => (
            <tr key={f.key}>
              <td>
                <span className="compare__feature">
                  <ServiceIcon code={f.service} size={20} /> {f.title}
                </span>
              </td>
              {columns.map((p) => (
                <td key={p.code}>{cell(p.flags[f.key])}</td>
              ))}
            </tr>
          ))}
          <tr>
            <td>Narx</td>
            {columns.map((p) => (
              <td key={p.code} className="compare__price">
                {p.code === "free" ? "tekin" : money(p.final_price).replace(" so'm", "")}
              </td>
            ))}
          </tr>
        </tbody>
      </table>
    </div>
  );
}

function Price({ plan }: { plan: Plan }) {
  const discounted = plan.final_price < plan.price;
  return (
    <div className="price">
      {discounted && <s className="price__old">{money(plan.price)}</s>}
      <span className="price__now">{money(plan.final_price)}</span>
      <small> / {plan.duration_days} kun</small>
    </div>
  );
}

function Checkout({
  state,
  plan,
  onClose,
  onDone,
  toast,
}: {
  state: State;
  plan: Plan;
  onClose: () => void;
  onDone: () => void;
  toast: (text: string, kind?: "ok" | "err") => void;
}) {
  const [promo, setPromo] = useState("");
  const [applied, setApplied] = useState<Quote | null>(null);
  const [promoError, setPromoError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const balance = state.user.balance;
  const total = applied?.final_price ?? plan.final_price;
  const extend = plan.code === state.plan.code;
  const Icon = planIcon(plan.code);

  const apply = async () => {
    setBusy(true);
    setPromoError(null);
    try {
      const q = await api.quote(plan.code, promo);
      if (q.ok) {
        haptic("success");
        setApplied(q);
      } else {
        haptic("error");
        setApplied(null);
        setPromoError(q.error ?? "Promokod yaroqsiz");
      }
    } finally {
      setBusy(false);
    }
  };

  const pay = async () => {
    setBusy(true);
    try {
      await api.buy(plan.code, applied?.promo_code ?? undefined);
      haptic("success");
      toast(`${plan.name} ${extend ? "uzaytirildi" : "faollashdi"}!`);
      onDone();
    } catch (e) {
      haptic("error");
      toast((e as Error).message, "err");
    } finally {
      setBusy(false);
    }
  };

  return (
    <Sheet
      title={`${plan.name} — ${plan.duration_days} kun`}
      icon={
        <span className={`checkout__icon checkout__icon--${plan.code}`}>
          <Icon size={20} />
        </span>
      }
      onClose={onClose}
    >
      {plan.description && <p className="hint">{plan.description}</p>}
      <Features state={state} flags={plan.flags} />

      <label className="label">Promokod</label>
      <div className="row">
        <div className="input-icon">
          <Ticket size={17} />
          <input
            className="input"
            placeholder="Masalan: BAHOR20"
            value={promo}
            autoCapitalize="characters"
            onChange={(e) => {
              setPromo(e.target.value.toUpperCase());
              setApplied(null);
              setPromoError(null);
            }}
          />
        </div>
        <button className="btn btn--ghost btn--inline" disabled={busy || promo.trim().length < 3} onClick={apply}>
          Qo'llash
        </button>
      </div>
      {promoError && <div className="field-error">{promoError}</div>}

      <div className="receipt">
        <div className="receipt__row">
          <span>Tarif narxi</span>
          <span>{money(plan.price)}</span>
        </div>
        {plan.final_price < plan.price && (
          <div className="receipt__row receipt__row--discount">
            <span>
              <Percent size={14} /> Aksiya −{plan.discount_percent}%
            </span>
            <span>−{money(plan.price - plan.final_price)}</span>
          </div>
        )}
        {applied?.promo_code && (
          <div className="receipt__row receipt__row--discount">
            <span>
              <Tag size={14} /> {applied.promo_code}
            </span>
            <span>−{money(applied.promo_discount ?? 0)}</span>
          </div>
        )}
        <div className="receipt__row receipt__row--total">
          <span>Jami</span>
          <span>{money(total)}</span>
        </div>
        <div className="receipt__row receipt__row--muted">
          <span>Balansingiz</span>
          <span>{money(balance)}</span>
        </div>
      </div>

      {balance < total ? (
        <>
          <div className="notice notice--warn">
            <Wallet size={18} />
            <span>Balans yetarli emas — yana {money(total - balance)} kerak. «Balans» bo'limidan to'ldiring.</span>
          </div>
          <button
            className="btn btn--primary"
            onClick={() => {
              onClose();
              setTimeout(() => document.getElementById("topup")?.scrollIntoView({ behavior: "smooth" }), 250);
            }}
          >
            Balansni to'ldirish
          </button>
        </>
      ) : (
        <button className={`btn ${plan.code === "pro" ? "btn--gold" : "btn--primary"}`} disabled={busy} onClick={pay}>
          {total === 0 ? "Bepul faollashtirish" : `${money(total)} to'lash`}
        </button>
      )}
    </Sheet>
  );
}

function Usage({ label, used, limit }: { label: string; used: number; limit: number }) {
  return (
    <div className="usage">
      <div className="usage__head">
        <span>{label}</span>
        <span className="usage__num">
          {used}
          <small>/{limit}</small>
        </span>
      </div>
      <div className="bar">
        <i style={{ width: `${Math.min(100, (used / Math.max(1, limit)) * 100)}%` }} />
      </div>
    </div>
  );
}

type Props = { state: State; refresh: () => void; toast: (text: string, kind?: "ok" | "err") => void };

export function PlansView({ state, refresh, toast }: Props) {
  const [busy, setBusy] = useState(false);
  const [custom, setCustom] = useState("");
  const [checkout, setCheckout] = useState<Plan | null>(null);
  const [instructions, setInstructions] = useState<{ id: number; text: string } | null>(null);
  const current = state.plans.find((p) => p.code === state.plan.code);
  const flags = state.plan.flags;
  const left = daysLeft(state.plan.expires_at);
  const balance = state.user.balance;
  const HeroIcon = planIcon(state.plan.code);

  const topup = async (amount: number) => {
    setBusy(true);
    try {
      const result = await api.topup(amount);
      haptic("success");
      setInstructions({ id: result.payment_id, text: result.instructions });
    } catch (e) {
      toast((e as Error).message, "err");
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="stack">
      <section className={`plan-hero plan-hero--${state.plan.code}`}>
        <div className="plan-hero__glow" />
        <div className="plan-hero__top">
          <div>
            <div className="plan-hero__label">Sizning tarifingiz</div>
            <div className="plan-hero__name">{state.plan.name}</div>
          </div>
          <span className="plan-hero__icon">
            <HeroIcon size={26} strokeWidth={2} />
          </span>
        </div>
        {state.plan.expires_at ? (
          <>
            <div className="plan-hero__sub">
              {dateText(state.plan.expires_at)} gacha · {left} kun qoldi
            </div>
            <div className="bar bar--light">
              <i style={{ width: `${Math.min(100, (left / (current?.duration_days ?? 30)) * 100)}%` }} />
            </div>
          </>
        ) : (
          <div className="plan-hero__sub">Tarifni yangilab ko'proq xizmat oching</div>
        )}
        <div className="plan-hero__services">
          {state.features.map((f) => (
            <span key={f.key} className={flags[f.key] ? "" : "is-off"}>
              <ServiceIcon code={f.service} size={30} />
            </span>
          ))}
        </div>
      </section>

      <section className="card">
        <Usage label="Faol xizmatlar" used={state.usage.automations} limit={Number(flags.scheduler_limit)} />
        <Usage label="Akkauntlar" used={state.usage.accounts} limit={Number(flags.account_limit)} />
      </section>

      <h3 className="section-title">Solishtirish</h3>
      <Compare state={state} />

      <h3 className="section-title">Tariflar</h3>
      <section className={`card plan ${state.plan.code === "free" ? "is-current" : ""}`}>
        <div className="plan__head">
          <span className="plan__name">
            <Sparkles size={18} /> {state.free_plan.name}
          </span>
          <span className="plan__price">tekin</span>
        </div>
        {state.plan.code === "free" && <span className="plan__current">Joriy tarif</span>}
        {state.free_plan.description && <p className="hint plan__desc">{state.free_plan.description}</p>}
        <Features state={state} flags={state.free_plan.flags} />
      </section>
      {state.plans.map((p) => {
        const isCurrent = p.code === state.plan.code;
        const lower = current && p.price < current.price;
        const Icon = planIcon(p.code);
        return (
          <section key={p.code} className={`card plan ${isCurrent ? "is-current" : ""} ${p.badge ? "plan--featured" : ""}`}>
            {p.badge && <span className="plan__ribbon">{p.badge}</span>}
            <div className="plan__head">
              <span className="plan__name">
                <Icon size={18} /> {p.name}
              </span>
              <Price plan={p} />
            </div>
            <div className="plan__tags">
              {isCurrent && <span className="plan__current">Joriy tarif</span>}
              {p.discount_percent > 0 && (
                <span className="sale">
                  <Tag size={12} strokeWidth={2.6} /> −{p.discount_percent}%
                  {p.discount_until && <> · {dateText(p.discount_until)} gacha</>}
                </span>
              )}
            </div>
            {p.description && <p className="hint plan__desc">{p.description}</p>}
            <Features state={state} flags={p.flags} />
            <button
              className={`btn ${p.badge ? "btn--gold" : "btn--primary"}`}
              disabled={busy || !!lower}
              onClick={() => {
                haptic();
                setCheckout(p);
              }}
            >
              {lower ? "Sizda yuqoriroq tarif bor" : isCurrent ? "Uzaytirish" : `${p.name} olish`}
            </button>
          </section>
        );
      })}

      <h3 className="section-title" id="topup">
        Balans
      </h3>
      <section className="card">
        <div className="balance">
          <span className="balance__icon">
            <Wallet size={22} />
          </span>
          <div>
            <div className="balance__label">Hisobingizda</div>
            <div className="balance__value">{money(balance)}</div>
          </div>
        </div>
        <p className="hint">Balansni to'ldirasiz, keyin tarifni bir tugma bilan olasiz. So'rovni admin tasdiqlaydi.</p>
        <div className="chips">
          {[...new Set(state.plans.map((p) => p.final_price))].map((price) => (
            <button key={price} className="chip-btn" disabled={busy} onClick={() => topup(price)}>
              + {money(price)}
            </button>
          ))}
        </div>
        <div className="row">
          <input
            className="input"
            inputMode="numeric"
            placeholder="Boshqa summa"
            value={custom}
            onChange={(e) => setCustom(e.target.value.replace(/\D/g, ""))}
          />
          <button className="btn btn--primary btn--inline" disabled={busy || Number(custom) < 1000} onClick={() => topup(Number(custom))}>
            So'rov
          </button>
        </div>
        {instructions && (
          <div className="notice notice--ok">
            <CircleCheck size={18} />
            <span>
              So'rov #{instructions.id} yuborildi.
              <br />
              {instructions.text ? (
                <>
                  To'lov uchun: <b className="pre">{instructions.text}</b>
                  <br />
                  Izohga #{instructions.id} ni yozing.
                </>
              ) : (
                "Admin siz bilan bog'lanib, to'lovni tasdiqlaydi."
              )}
              <br />
              Tasdiqlangach botda xabar olasiz.
            </span>
          </div>
        )}
      </section>

      <h3 className="section-title">Taklif qilish</h3>
      <ReferralCard state={state} />

      {checkout && (
        <Checkout
          state={state}
          plan={checkout}
          onClose={() => setCheckout(null)}
          onDone={() => {
            setCheckout(null);
            refresh();
          }}
          toast={toast}
        />
      )}
    </div>
  );
}
