import { useState } from "react";
import { api, type Flags, type State } from "../api";
import { confirmDialog, haptic } from "../tg";
import { daysLeft, money } from "../util";

const PRO_FEATURES: [string, string][] = [
  ["online_service", "🟢 24/7 Online"],
  ["playlist_service", "🔁 Bio playlist"],
  ["schedule_service", "🗓 Jadval"],
  ["emoji_service", "😀 Emoji status"],
  ["photo_service", "🖼 Rasm almashtirish"],
];

const FREE_FLAGS: Flags = { account_limit: 1, scheduler_limit: 1 };

function Features({ flags }: { flags: Flags }) {
  return (
    <ul className="features">
      <li>👤 {flags.account_limit} ta akkaunt</li>
      <li>⚙️ bir vaqtda {flags.scheduler_limit} ta xizmat</li>
      {PRO_FEATURES.map(([flag, label]) => (
        <li key={flag} className={flags[flag] ? "" : "is-off"}>
          {flags[flag] ? label : `🔒 ${label.split(" ").slice(1).join(" ")}`}
        </li>
      ))}
    </ul>
  );
}

function Usage({ label, used, limit }: { label: string; used: number; limit: number }) {
  return (
    <div className="usage">
      <div className="usage__head">
        <span>{label}</span>
        <span>
          {used}/{limit}
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
  const [instructions, setInstructions] = useState<{ id: number; text: string } | null>(null);
  const current = state.plans.find((p) => p.code === state.plan.code);
  const flags = state.plan.flags;
  const left = daysLeft(state.plan.expires_at);
  const balance = state.user.balance;

  const buy = async (code: string, name: string, price: number) => {
    if (balance < price) {
      toast(`Balans yetarli emas: ${money(balance)} / ${money(price)}. Avval to'ldiring.`, "err");
      document.getElementById("topup")?.scrollIntoView({ behavior: "smooth" });
      return;
    }
    if (!(await confirmDialog(`${name} tarifi — balansdan ${money(price)} yechiladi. Tasdiqlaysizmi?`))) return;
    setBusy(true);
    try {
      await api.buy(code);
      haptic("success");
      toast(`🎉 ${name} faollashdi!`);
      refresh();
    } catch (e) {
      haptic("error");
      toast((e as Error).message, "err");
    } finally {
      setBusy(false);
    }
  };

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
      <section className="card plan-hero">
        <div className="plan-hero__label">Sizning tarifingiz</div>
        <div className="plan-hero__name">{state.plan.name}</div>
        {state.plan.expires_at ? (
          <>
            <div className="plan-hero__sub">
              {new Date(state.plan.expires_at).toLocaleDateString("ru-RU")} gacha · {left} kun qoldi
            </div>
            <div className="bar bar--light">
              <i style={{ width: `${Math.min(100, (left / (current?.duration_days ?? 30)) * 100)}%` }} />
            </div>
          </>
        ) : (
          <div className="plan-hero__sub">Pullik tarif yo'q</div>
        )}
      </section>

      <section className="card">
        <Usage label="Faol xizmatlar" used={state.usage.automations} limit={Number(flags.scheduler_limit)} />
        <Usage label="Akkauntlar" used={state.usage.accounts} limit={Number(flags.account_limit)} />
        <Features flags={flags} />
      </section>

      <h3 className="section-title">Tariflar</h3>
      <section className={`card plan ${state.plan.code === "free" ? "is-current" : ""}`}>
        <div className="plan__head">
          <span className="plan__name">🆓 Bepul</span>
          <span className="plan__price">tekin</span>
        </div>
        <Features flags={FREE_FLAGS} />
      </section>
      {state.plans.map((p) => {
        const isCurrent = p.code === state.plan.code;
        const lower = current && p.price < current.price;
        return (
          <section key={p.code} className={`card plan ${isCurrent ? "is-current" : ""} ${p.code === "pro" ? "plan--pro" : ""}`}>
            <div className="plan__head">
              <span className="plan__name">{p.code === "pro" ? "🚀" : "⭐"} {p.name}</span>
              <span className="plan__price">
                {money(p.price)} <small>/ {p.duration_days} kun</small>
              </span>
            </div>
            <Features flags={p.flags} />
            <button className="btn btn--primary" disabled={busy || !!lower} onClick={() => buy(p.code, p.name, p.price)}>
              {lower ? "Sizda yuqoriroq tarif bor" : isCurrent ? "Uzaytirish" : "Olish"}
            </button>
          </section>
        );
      })}

      <h3 className="section-title" id="topup">
        Balans
      </h3>
      <section className="card">
        <div className="balance">{money(balance)}</div>
        <p className="hint">Balansni to'ldirasiz, keyin tarifni bir tugma bilan olasiz. So'rovni admin tasdiqlaydi.</p>
        <div className="chips">
          {[...new Set(state.plans.map((p) => p.price))].map((price) => (
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
          <div className="notice">
            ✅ So'rov #{instructions.id} yuborildi.
            <br />
            {instructions.text ? (
              <>
                To'lov uchun: {instructions.text}
                <br />
                Izohga #{instructions.id} ni yozing.
              </>
            ) : (
              "Admin siz bilan bog'lanib, to'lovni tasdiqlaydi."
            )}
            <br />
            Tasdiqlangach botda xabar olasiz.
          </div>
        )}
      </section>
    </div>
  );
}
