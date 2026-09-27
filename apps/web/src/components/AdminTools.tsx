import { useQuery } from "@tanstack/react-query";
import {
  Activity,
  Bold,
  Check,
  Download,
  ImagePlus,
  Italic,
  Link as LinkIcon,
  Megaphone,
  Plus,
  Send,
  Square,
  Trash2,
  UserRound,
  X,
} from "lucide-react";
import { useEffect, useMemo, useRef, useState } from "react";
import {
  adminApi,
  api,
  mediaUrl,
  type BroadcastButton,
  type BroadcastInput,
  type Milestone,
  type ReferralSettings,
  type Segment,
} from "../api";
import { confirmDialog, haptic, tg } from "../tg";
import { dateText, fileToJpegBase64, money } from "../util";
import { Empty, Field, NumberInput, StatCard, Stepper, Toggle, run, useRefresh, type Toast } from "./AdminKit";

// --- 14 kunlik mini diagramma (bitta ko'rsatkich — bitta diagramma, ikki o'q yo'q) ---

type Point = { date: string; users: number; revenue: number };

function shortDate(iso: string): string {
  const [, m, d] = iso.split("-");
  return `${d}.${m}`;
}

export function TrendChart() {
  const { data } = useQuery({ queryKey: ["admin", "timeseries"], queryFn: adminApi.timeseries });
  const [metric, setMetric] = useState<"users" | "revenue">("users");
  const [active, setActive] = useState<number | null>(null);
  if (!data) return null;
  const points: Point[] = data.points;
  const values = points.map((p) => p[metric]);
  const max = Math.max(1, ...values);
  const total = values.reduce((a, b) => a + b, 0);
  const format = (v: number) => (metric === "users" ? `${v} ta` : money(v));
  const shown = active !== null ? points[active] : null;

  return (
    <section className="card trend">
      <div className="trend__head">
        <div>
          <div className="trend__label">{metric === "users" ? "Yangi foydalanuvchilar" : "Kirim (to'ldirishlar)"} · 14 kun</div>
          <div className="trend__value">{shown ? format(shown[metric]) : format(total)}</div>
          <div className="hint">{shown ? dateText(shown.date) : "jami"}</div>
        </div>
        <div className="segmented segmented--small">
          <button className={metric === "users" ? "is-selected" : ""} onClick={() => setMetric("users")}>
            Odamlar
          </button>
          <button className={metric === "revenue" ? "is-selected" : ""} onClick={() => setMetric("revenue")}>
            Kirim
          </button>
        </div>
      </div>
      <div className="trend__bars" role="img" aria-label={`${metric === "users" ? "Yangi foydalanuvchilar" : "Kirim"}, 14 kun, jami ${format(total)}`}>
        {points.map((p, i) => (
          <button
            key={p.date}
            className={`trend__bar ${active === i ? "is-active" : ""}`}
            onMouseEnter={() => setActive(i)}
            onMouseLeave={() => setActive(null)}
            onClick={() => setActive(active === i ? null : i)}
            aria-label={`${shortDate(p.date)}: ${format(p[metric])}`}
          >
            <i style={{ height: `${Math.max(p[metric] ? 6 : 2, (p[metric] / max) * 100)}%` }} />
          </button>
        ))}
      </div>
      <div className="trend__axis">
        <span>{shortDate(points[0].date)}</span>
        <span>{shortDate(points[Math.floor(points.length / 2)].date)}</span>
        <span>{shortDate(points[points.length - 1].date)}</span>
      </div>
    </section>
  );
}

// --- 📣 Ommaviy xabarlar ---

const ALLOWED_TAGS = ["b", "strong", "i", "em", "u", "s", "a", "code", "tg-spoiler", "blockquote"];

// Oldindan ko'rish uchun: faqat Telegram qo'llaydigan teglar qoladi, qolgani matnga aylanadi.
function sanitize(html: string): string {
  const doc = new DOMParser().parseFromString(`<div>${html}</div>`, "text/html");
  const walk = (node: Element) => {
    for (const child of [...node.children]) {
      walk(child);
      const tag = child.tagName.toLowerCase();
      if (!ALLOWED_TAGS.includes(tag)) {
        child.replaceWith(...child.childNodes);
        continue;
      }
      for (const attr of [...child.attributes]) {
        if (!(tag === "a" && attr.name === "href" && /^https?:\/\//.test(attr.value))) child.removeAttribute(attr.name);
      }
    }
  };
  const root = doc.body.firstElementChild as Element;
  walk(root);
  return root.innerHTML;
}

const BUTTON_TYPES: { type: BroadcastButton["type"]; label: string; text: string }[] = [
  { type: "copy", label: "🎟 Promokod (nusxa)", text: "🎟 Promokodni nusxalash" },
  { type: "webapp", label: "✨ Studiya", text: "✨ Studiyani ochish" },
  { type: "plans", label: "💎 Tariflar", text: "💎 Tariflarni ko'rish" },
  { type: "url", label: "🔗 Havola", text: "🔗 Batafsil" },
  { type: "ref", label: "🎁 Taklif", text: "🎁 Do'stlarni taklif qilish" },
  { type: "home", label: "🏠 Bosh sahifa", text: "🏠 Bosh sahifa" },
];

const STATUS: Record<string, [string, string]> = {
  sending: ["Yuborilmoqda", "wait"],
  done: ["Tugadi", "ok"],
  cancelled: ["To'xtatildi", "err"],
  draft: ["Qoralama", "wait"],
};

export function Broadcasts({ toast }: { toast: Toast }) {
  const { data } = useQuery({
    queryKey: ["admin", "broadcasts"],
    queryFn: adminApi.broadcasts,
    refetchInterval: (q) => (q.state.data?.broadcasts.some((b) => b.status === "sending") ? 2500 : false),
  });
  const refresh = useRefresh();
  const [text, setText] = useState("");
  const [segment, setSegment] = useState<Segment>({ code: "all" });
  const [buttons, setButtons] = useState<BroadcastButton[]>([]);
  const [mediaId, setMediaId] = useState<number | null>(null);
  const [count, setCount] = useState<number | null>(null);
  const [busy, setBusy] = useState(false);
  const area = useRef<HTMLTextAreaElement>(null);

  useEffect(() => {
    let alive = true;
    adminApi.countRecipients(segment).then((r) => alive && setCount(r.total)).catch(() => alive && setCount(null));
    return () => {
      alive = false;
    };
  }, [segment]);

  const preview = useMemo(() => sanitize(text.split("{first_name}").join("Sardor")), [text]);
  if (!data) return <div className="spinner spinner--center" />;

  const wrap = (open: string, close: string) => {
    const el = area.current;
    if (!el) return;
    const [a, b] = [el.selectionStart, el.selectionEnd];
    setText(text.slice(0, a) + open + text.slice(a, b) + close + text.slice(b));
    requestAnimationFrame(() => {
      el.focus();
      el.setSelectionRange(a + open.length, b + open.length);
    });
  };
  const body = (): BroadcastInput => ({ text, segment, media_id: mediaId, buttons });
  const valid = text.trim().length > 0 && buttons.every((b) => b.text.trim() && (!["url", "copy"].includes(b.type) || b.value.trim()));

  const upload = async (file: File | undefined) => {
    if (!file) return;
    setBusy(true);
    try {
      const { id } = await api.uploadMedia(await fileToJpegBase64(file));
      setMediaId(id);
    } catch (e) {
      toast((e as Error).message, "err");
    } finally {
      setBusy(false);
    }
  };

  const send = async () => {
    if (!(await confirmDialog(`Xabar ${count ?? "?"} kishiga yuborilsinmi? Bu amalni ortga qaytarib bo'lmaydi.`))) return;
    setBusy(true);
    if (await run(toast, () => adminApi.startBroadcast(body()), "Yuborish boshlandi 📣")) {
      setText("");
      setButtons([]);
      setMediaId(null);
      refresh();
    }
    setBusy(false);
  };

  return (
    <div className="stack">
      <section className="card">
        <label className="label" style={{ marginTop: 0 }}>
          Uslub
        </label>
        <div className="chips chips--scroll">
          {data.styles.map((s) => (
            <button key={s.code} className="chip-btn" onClick={() => setText(s.text)}>
              {s.title}
            </button>
          ))}
        </div>

        <label className="label">Matn</label>
        <div className="toolbar">
          <button onClick={() => wrap("<b>", "</b>")} aria-label="Qalin">
            <Bold size={16} />
          </button>
          <button onClick={() => wrap("<i>", "</i>")} aria-label="Kursiv">
            <Italic size={16} />
          </button>
          <button onClick={() => wrap('<a href="https://">', "</a>")} aria-label="Havola">
            <LinkIcon size={16} />
          </button>
          <button onClick={() => wrap("<tg-spoiler>", "</tg-spoiler>")}>spoiler</button>
          <button onClick={() => wrap("{first_name}", "")}>
            <UserRound size={15} /> ism
          </button>
        </div>
        <textarea ref={area} className="input" rows={6} maxLength={4000} value={text} onChange={(e) => setText(e.target.value)} />
        <p className="hint field__hint">{"{first_name}"} — har odamga o'z ismi qo'yiladi. {text.length}/4000</p>

        <label className="label">Rasm (ixtiyoriy)</label>
        {mediaId ? (
          <div className="bc-photo">
            <img src={mediaUrl(mediaId)} alt="" />
            <button className="photos__remove" onClick={() => setMediaId(null)} aria-label="O'chirish">
              <X size={14} />
            </button>
          </div>
        ) : (
          <label className="photos__add bc-photo-add">
            <input type="file" accept="image/*" hidden onChange={(e) => upload(e.target.files?.[0])} />
            <ImagePlus size={22} /> <span>Rasm qo'shish</span>
          </label>
        )}

        <label className="label">Tugmalar</label>
        {buttons.map((b, i) => (
          <div key={i} className={`bc-button ${b.type === "url" || b.type === "copy" ? "" : "bc-button--single"}`}>
            <input className="input" value={b.text} maxLength={64} onChange={(e) => setButtons(buttons.map((x, j) => (j === i ? { ...x, text: e.target.value } : x)))} />
            {b.type === "url" && (
              <input className="input" placeholder="https://..." value={b.value} onChange={(e) => setButtons(buttons.map((x, j) => (j === i ? { ...x, value: e.target.value } : x)))} />
            )}
            {b.type === "copy" && (
              <select
                className="input"
                value={b.value}
                onChange={(e) => setButtons(buttons.map((x, j) => (j === i ? { ...x, value: e.target.value, text: `🎟 ${e.target.value} — nusxalash` } : x)))}
              >
                <option value="">Promokodni tanlang</option>
                {data.promos.map((p) => (
                  <option key={p.code} value={p.code}>
                    {p.label}
                  </option>
                ))}
              </select>
            )}
            <button className="icon-btn" onClick={() => setButtons(buttons.filter((_, j) => j !== i))} aria-label="O'chirish">
              <Trash2 size={16} />
            </button>
          </div>
        ))}
        {buttons.length < 6 && (
          <div className="chips">
            {BUTTON_TYPES.map((t) => (
              <button key={t.type} className="chip-btn" onClick={() => setButtons([...buttons, { type: t.type, text: t.text, value: "" }])}>
                <Plus size={13} /> {t.label}
              </button>
            ))}
          </div>
        )}
        {data.promos.length === 0 && <p className="hint field__hint">Faol promokod yo'q — «Promokodlar» bo'limida yarating.</p>}

        <label className="label">Kimga</label>
        <div className="chips">
          {data.segments.map((s) => (
            <button
              key={s.code}
              className={`chip-btn ${segment.code === s.code ? "is-selected" : ""}`}
              onClick={() => setSegment(s.code === "plan" ? { code: "plan", plan_code: data.plans.find((p) => p.code !== "free")?.code } : { code: s.code })}
            >
              {s.title}
            </button>
          ))}
        </div>
        {segment.code === "plan" && (
          <div className="chips">
            {data.plans
              .filter((p) => p.code !== "free")
              .map((p) => (
                <button key={p.code} className={`chip-btn ${segment.plan_code === p.code ? "is-selected" : ""}`} onClick={() => setSegment({ code: "plan", plan_code: p.code })}>
                  {p.name}
                </button>
              ))}
          </div>
        )}
        <p className="hint field__hint">Qabul qiluvchilar: {count ?? "…"} kishi (bloklanganlar hisobga olinmaydi)</p>

        {text.trim() && (
          <>
            <label className="label">Ko'rinishi</label>
            <div className="bc-preview">
              {mediaId && <img src={mediaUrl(mediaId)} alt="" />}
              <div className="bc-preview__text" dangerouslySetInnerHTML={{ __html: preview }} />
              {buttons.map((b, i) => (
                <div key={i} className="bc-preview__btn">
                  {b.text}
                </div>
              ))}
            </div>
          </>
        )}

        <div className="grid2">
          <button className="btn btn--ghost btn--compact" disabled={busy || !valid} onClick={() => run(toast, () => adminApi.testBroadcast(body()), "Sizga yuborildi — botni tekshiring")}>
            Menga sinov
          </button>
          <button className="btn btn--primary btn--compact" disabled={busy || !valid || !count} onClick={send}>
            <Send size={16} /> Yuborish
          </button>
        </div>
      </section>

      <h3 className="section-title">Tarix</h3>
      {data.broadcasts.length === 0 ? (
        <Empty icon={<Megaphone size={22} />} text="Hali xabar yuborilmagan" />
      ) : (
        data.broadcasts.map((b) => {
          const [label, tone] = STATUS[b.status] ?? [b.status, "wait"];
          const done = b.sent + b.failed + b.blocked;
          return (
            <div key={b.id} className="card bc-item">
              <div className="bc-item__head">
                <span className={`status status--${tone}`}>{label}</span>
                <span className="hint">{dateText(b.created_at)}</span>
              </div>
              <div className="bc-item__text">{b.text.replace(/<[^>]+>/g, "").slice(0, 120)}</div>
              <div className="bar">
                <i style={{ width: `${b.total ? (done / b.total) * 100 : 100}%` }} />
              </div>
              <div className="bc-item__stats">
                <span>✅ {b.sent}</span>
                <span>🚫 {b.blocked} bloklagan</span>
                <span>⚠️ {b.failed}</span>
                <span>
                  {done}/{b.total}
                </span>
              </div>
              {b.status === "sending" && (
                <button className="btn btn--danger btn--compact" onClick={() => run(toast, () => adminApi.cancelBroadcast(b.id), "To'xtatildi").then(refresh)}>
                  <Square size={14} /> To'xtatish
                </button>
              )}
            </div>
          );
        })
      )}
    </div>
  );
}

// --- 🎁 Referal ---

export function Referrals({ toast }: { toast: Toast }) {
  const { data } = useQuery({ queryKey: ["admin", "referrals"], queryFn: adminApi.referrals });
  const refresh = useRefresh();
  const [form, setForm] = useState<ReferralSettings | null>(null);
  useEffect(() => {
    if (data && !form) setForm(data.settings);
  }, [data, form]);
  if (!data || !form) return <div className="spinner spinner--center" />;
  const set = (patch: Partial<ReferralSettings>) => setForm({ ...form, ...patch });
  const setMilestone = (i: number, patch: Partial<Milestone>) => set({ milestones: form.milestones.map((m, j) => (j === i ? { ...m, ...patch } : m)) });

  const save = async () => {
    if (await run(toast, () => adminApi.saveReferralSettings(form), "Referal sozlamalari saqlandi")) refresh();
  };
  const act = async (id: number, action: "qualify" | "reject") => {
    if (await run(toast, () => adminApi.referralAction(id, action), action === "qualify" ? "Tasdiqlandi" : "Rad etildi")) refresh();
  };

  return (
    <div className="stack">
      <div className="stat-grid">
        <StatCard icon={<Check size={16} />} value={data.stats.qualified} label="hisoblangan" tone="ok" />
        <StatCard icon={<Activity size={16} />} value={data.stats.pending} label="kutilmoqda" />
        <StatCard icon={<Megaphone size={16} />} value={data.stats.rewards} label="sovg'a berilgan" tone="premium" />
        <StatCard icon={<Plus size={16} />} value={money(data.stats.bonus_paid).replace(" so'm", "")} label="so'm bonus to'langan" />
      </div>

      <section className="card">
        <div className="card-inset">
          <Toggle on={form.enabled} onChange={(v) => set({ enabled: v })}>
            Referal sovg'alari yoqilgan
          </Toggle>
        </div>
        <Field label="Qachon hisoblanadi">
          <div className="segmented">
            <button className={form.mode === "start" ? "is-selected" : ""} onClick={() => set({ mode: "start" })}>
              Botni ochsa
            </button>
            <button className={form.mode === "account" ? "is-selected" : ""} onClick={() => set({ mode: "account" })}>
              Akkaunt ulasa
            </button>
          </div>
        </Field>
        <p className="hint field__hint">
          {form.mode === "start"
            ? "Do'st havola orqali /start bossa darhol hisoblanadi — tez o'sadi, lekin soxta akkauntlar bilan aldash oson."
            : "Do'st o'z Telegram akkauntini ulagandagina hisoblanadi (ilgari hech kim ulamagan akkaunt) — haqiqiy foydalanuvchilar."}
        </p>

        <label className="label">Bosqichli sovg'alar</label>
        {form.milestones.length > 0 && (
          <div className="milestone milestone--head hint">
            <span>Do'stlar</span>
            <span>Tarif</span>
            <span>Muddat</span>
            <span />
          </div>
        )}
        {form.milestones.map((m, i) => (
          <div key={i} className="milestone">
            <Stepper value={m.count} min={1} max={10000} onChange={(v) => setMilestone(i, { count: v })} />
            <select className="input" value={m.plan_code} onChange={(e) => setMilestone(i, { plan_code: e.target.value })}>
              {data.plans.map((p) => (
                <option key={p.code} value={p.code}>
                  {p.name}
                </option>
              ))}
            </select>
            <NumberInput value={String(m.days)} suffix="kun" onChange={(v) => setMilestone(i, { days: Number(v) || 1 })} />
            <button className="icon-btn" onClick={() => set({ milestones: form.milestones.filter((_, j) => j !== i) })} aria-label="O'chirish">
              <Trash2 size={16} />
            </button>
          </div>
        ))}
        <button
          className="btn btn--ghost btn--compact"
          onClick={() => {
            const last = form.milestones[form.milestones.length - 1];
            set({ milestones: [...form.milestones, { count: (last?.count ?? 0) + 5, plan_code: data.plans[data.plans.length - 1]?.code ?? "pro", days: 30 }] });
          }}
        >
          <Plus size={16} /> Bosqich qo'shish
        </button>

        <div className="grid2">
          <Field label="Har do'st uchun bonus" hint="0 — bonussiz">
            <NumberInput value={String(form.bonus_per_referral)} suffix="so'm" onChange={(v) => set({ bonus_per_referral: Number(v) || 0 })} />
          </Field>
          <Field label="Do'stga sovg'a" hint="0 kun — sovg'asiz">
            <NumberInput value={String(form.friend_days)} suffix="kun" onChange={(v) => set({ friend_days: Number(v) || 0 })} />
          </Field>
        </div>
        {form.friend_days > 0 && (
          <div className="chips">
            {data.plans.map((p) => (
              <button key={p.code} className={`chip-btn ${form.friend_plan_code === p.code ? "is-selected" : ""}`} onClick={() => set({ friend_plan_code: p.code })}>
                {p.name}
              </button>
            ))}
          </div>
        )}
        <button className="btn btn--primary" onClick={save}>
          Saqlash
        </button>
      </section>

      {data.top.length > 0 && (
        <>
          <h3 className="section-title">Eng ko'p taklif qilganlar</h3>
          <section className="card card--list">
            {data.top.map((t, i) => (
              <div key={t.user_id} className="list-item">
                <span className="rank">{i + 1}</span>
                <span className="list-item__body">
                  <span className="list-item__title">{t.name}</span>
                </span>
                <b>{t.count}</b>
              </div>
            ))}
          </section>
        </>
      )}

      <h3 className="section-title">So'nggi referallar</h3>
      {data.recent.length === 0 ? (
        <Empty icon={<UserRound size={22} />} text="Hali referal yo'q" />
      ) : (
        <section className="card card--list">
          {data.recent.map((r) => (
            <div key={r.id} className="pay">
              <div className="pay__main">
                <div className="pay__top">
                  <b>{r.referred}</b>
                  <span className={`status status--${r.status === "qualified" ? "ok" : r.status === "rejected" ? "err" : "wait"}`}>
                    {r.status === "qualified" ? "hisoblangan" : r.status === "rejected" ? "rad etilgan" : "kutilmoqda"}
                  </span>
                </div>
                <span className="hint">
                  taklif qilgan: {r.referrer} · {dateText(r.created_at)}
                </span>
              </div>
              {r.status === "pending" && (
                <div className="pay__actions">
                  <button className="mini-btn mini-btn--ok" onClick={() => act(r.id, "qualify")} aria-label="Tasdiqlash">
                    <Check size={18} />
                  </button>
                  <button className="mini-btn mini-btn--err" onClick={() => act(r.id, "reject")} aria-label="Rad etish">
                    <X size={18} />
                  </button>
                </div>
              )}
            </div>
          ))}
        </section>
      )}
    </div>
  );
}

// --- 📜 Jurnal va ⚙️ Tizim ---

export function AuditLog() {
  const { data } = useQuery({ queryKey: ["admin", "audit"], queryFn: adminApi.audit });
  if (!data) return <div className="spinner spinner--center" />;
  return (
    <section className="card card--list">
      {data.map((row) => (
        <div key={row.id} className="list-item">
          <span className="list-item__body">
            <span className="list-item__title">{row.action}</span>
            <span className="list-item__sub">
              {row.actor === "ADMIN" ? "admin" : row.actor === "USER" ? "foydalanuvchi" : row.actor.toLowerCase()} · {row.entity}
            </span>
          </span>
          <span className="hint">{new Date(row.created_at).toLocaleString("ru-RU", { day: "2-digit", month: "2-digit", hour: "2-digit", minute: "2-digit" })}</span>
        </div>
      ))}
    </section>
  );
}

export function SystemView() {
  const { data } = useQuery({ queryKey: ["admin", "system"], queryFn: adminApi.system, refetchInterval: 15000 });
  if (!data) return <div className="spinner spinner--center" />;
  const download = () => {
    const url = `${location.origin}${adminApi.exportUrl()}`;
    if (tg?.openLink) tg.openLink(url);
    else window.open(url, "_blank");
    haptic();
  };
  return (
    <div className="stack">
      <div className="stat-grid">
        <StatCard icon={<Activity size={16} />} value={data.active_automations} label="faol xizmat" tone="ok" />
        <StatCard icon={<X size={16} />} value={data.error_automations} label="xatolikdagi xizmat" />
        <StatCard icon={<Check size={16} />} value={data.jobs.DONE ?? 0} label="vazifa bajarildi · 24 soat" />
        <StatCard icon={<X size={16} />} value={data.jobs.FAILED ?? 0} label="vazifa xato · 24 soat" />
      </div>
      <p className="hint">
        AI yoqilgan akkauntlar: {data.ai_accounts} · kutilayotgan to'lovlar: {data.pending_payments}
        <br />
        Mini App: {data.webapp_url ?? "aniqlanmagan"}
      </p>
      {data.errors.length > 0 && (
        <>
          <h3 className="section-title">So'nggi xatolar</h3>
          <section className="card card--list">
            {data.errors.map((e, i) => (
              <div key={i} className="list-item">
                <span className="list-item__body">
                  <span className="list-item__title">{e.task ?? "vazifa"}</span>
                  <span className="list-item__sub is-err">{e.error}</span>
                </span>
              </div>
            ))}
          </section>
        </>
      )}
      <button className="btn btn--ghost" onClick={download}>
        <Download size={16} /> Foydalanuvchilar ro'yxati (CSV / Excel)
      </button>
    </div>
  );
}

// --- Foydalanuvchi oynasi uchun: tafsilotlar va shaxsiy xabar ---

const SERVICE_NAMES: Record<string, string> = {
  clock_name: "🕐",
  auto_bio: "📝",
  auto_name: "✏️",
  online: "🟢",
  playlist: "🔁",
  schedule: "🗓",
  emoji: "😀",
  photo: "🖼",
  ai_reply: "🤖",
};

export function UserExtras({ userId, toast }: { userId: number; toast: Toast }) {
  const { data } = useQuery({ queryKey: ["admin", "user", userId], queryFn: () => adminApi.userDetails(userId) });
  const [text, setText] = useState("");
  const [busy, setBusy] = useState(false);
  if (!data) return <div className="spinner spinner--center" />;
  return (
    <>
      <label className="label">Akkauntlar</label>
      {data.accounts.length === 0 ? (
        <p className="hint">Akkaunt ulanmagan</p>
      ) : (
        <div className="card-inset">
          {data.accounts.map((a) => (
            <div key={a.id} className="limit-row">
              <span>
                {a.name} {a.premium && "⭐"} <span className="hint">· {a.status.toLowerCase()}</span>
              </span>
              <span>{a.services.map((s) => SERVICE_NAMES[s] ?? "•").join(" ") || <span className="hint">xizmat yo'q</span>}</span>
            </div>
          ))}
        </div>
      )}
      <p className="hint field__hint">
        🎁 Taklif qilgan: {data.referral.qualified} ta (kutilmoqda {data.referral.pending})
        {data.referral.referred_by && <> · uni taklif qilgan: {data.referral.referred_by}</>}
      </p>
      {data.payments.length > 0 && (
        <p className="hint field__hint">💳 So'nggi to'lovlar: {data.payments.map((p) => `${money(p.amount)} (${p.status.toLowerCase()})`).join(", ")}</p>
      )}
      <label className="label">Shaxsiy xabar</label>
      <textarea className="input" rows={3} placeholder="Bot orqali shu foydalanuvchiga boradi. <b>qalin</b>, <i>kursiv</i> ishlaydi." value={text} onChange={(e) => setText(e.target.value)} />
      <button
        className="btn btn--primary btn--compact"
        disabled={busy || !text.trim()}
        onClick={async () => {
          setBusy(true);
          if (await run(toast, () => adminApi.messageUser(userId, text), "Xabar yuborildi")) setText("");
          setBusy(false);
        }}
      >
        <Send size={16} /> Yuborish
      </button>
    </>
  );
}
