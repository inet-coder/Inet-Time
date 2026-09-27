import { useQuery } from "@tanstack/react-query";
import { Check, Copy, Gift, Send } from "lucide-react";
import { useState } from "react";
import { api, type State } from "../api";
import { haptic, tg } from "../tg";
import { money } from "../util";

export function ReferralCard({ state }: { state: State }) {
  const { data } = useQuery({ queryKey: ["referral"], queryFn: api.referral });
  const [copied, setCopied] = useState(false);
  if (!data || !state.bot_username) return null;
  const link = `https://t.me/${state.bot_username}?start=ref_${data.code}`;
  const share = () => {
    const text = "Telegram profilingni avtomatlashtir: ismda soat, avto bio, AI javob 👇";
    const url = `https://t.me/share/url?url=${encodeURIComponent(link)}&text=${encodeURIComponent(text)}`;
    haptic();
    if (tg) tg.openTelegramLink(url);
    else window.open(url, "_blank");
  };
  const copy = async () => {
    try {
      await navigator.clipboard.writeText(link);
      setCopied(true);
      haptic("success");
      setTimeout(() => setCopied(false), 2000);
    } catch {
      /* clipboard ruxsat berilmagan */
    }
  };
  const next = data.next;
  const progress = next ? Math.min(100, (data.qualified / next.count) * 100) : 100;

  return (
    <section className="card referral">
      <div className="referral__head">
        <span className="referral__icon">
          <Gift size={22} />
        </span>
        <div>
          <b>Do'stlarni taklif qiling</b>
          <div className="hint">
            {data.mode === "account" ? "Do'stingiz akkaunt ulasa hisoblanadi" : "Do'stingiz havola orqali kirsa hisoblanadi"}
          </div>
        </div>
      </div>

      <div className="referral__stats">
        <div>
          <b>{data.qualified}</b>
          <span className="hint">hisoblangan</span>
        </div>
        <div>
          <b>{data.pending}</b>
          <span className="hint">kutilmoqda</span>
        </div>
        {data.bonus_per_referral > 0 && (
          <div>
            <b>+{money(data.bonus_per_referral).replace(" so'm", "")}</b>
            <span className="hint">so'm har biri</span>
          </div>
        )}
      </div>

      {next && (
        <div className="usage">
          <div className="usage__head">
            <span>
              Keyingi sovg'a: {next.plan_name} {next.days} kun
            </span>
            <span className="usage__num">
              {data.qualified}
              <small>/{next.count}</small>
            </span>
          </div>
          <div className="bar">
            <i style={{ width: `${progress}%` }} />
          </div>
        </div>
      )}
      {data.milestones.length > 0 && (
        <ul className="features">
          {data.milestones.map((m) => (
            <li key={m.count} className={m.reached ? "" : "is-off"}>
              {m.reached ? <Check size={16} className="features__icon features__icon--ok" /> : <Gift size={15} className="features__icon" />}
              {m.count} do'st — {m.plan_name} {m.days} kun
            </li>
          ))}
        </ul>
      )}
      {data.friend_reward.days > 0 && (
        <p className="hint field__hint">
          🎁 Do'stingiz ham {data.friend_reward.plan_name} {data.friend_reward.days} kun oladi.
        </p>
      )}

      <div className="referral__link" onClick={copy}>
        <span>{link.replace("https://", "")}</span>
        {copied ? <Check size={16} /> : <Copy size={16} />}
      </div>
      <button className="btn btn--gold" onClick={share}>
        <Send size={17} /> Do'stlarga ulashish
      </button>
    </section>
  );
}
