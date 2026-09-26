import { CircleAlert, Film, Image as ImageIcon, Info, Lock, Search, Send, ShieldCheck, WandSparkles } from "lucide-react";
import { useEffect, useState } from "react";
import { api, type AISettings, type AIState, type State, type StoryItem } from "../api";
import { haptic } from "../tg";

type Callbacks = { state: State; onDone: (text: string) => void; onError: (text: string) => void };

function Toggle({ on, onChange, title, hint }: { on: boolean; onChange: (v: boolean) => void; title: string; hint: string }) {
  return (
    <button className="toggle-row" onClick={() => onChange(!on)}>
      <span className="toggle-row__body toggle-row__body--col">
        <b>{title}</b>
        <span className="hint">{hint}</span>
      </span>
      <span className={`switch ${on ? "is-on" : ""}`}>
        <i />
      </span>
    </button>
  );
}

// --- ✨ AI bilan yozish (Studiya muharrirlari ichida) ---

export function AIWriter<T = string>({
  state,
  field,
  onPick,
  render,
}: {
  state: State;
  field: "bio" | "name" | "playlist" | "schedule";
  onPick: (item: T, all: T[]) => void;
  render?: (item: T) => string;
}) {
  const unlocked = state.catalog.find((c) => c.code === "ai_reply")?.unlocked;
  const [open, setOpen] = useState(false);
  const [topic, setTopic] = useState("");
  const [items, setItems] = useState<T[]>([]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  if (!unlocked) return null;

  const generate = async () => {
    setBusy(true);
    setError(null);
    try {
      const res = await api.suggest<T>(field, topic);
      setItems(res.items);
      haptic("success");
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  };

  if (!open) {
    return (
      <button className="ai-writer__open" onClick={() => setOpen(true)}>
        <WandSparkles size={16} /> AI bilan yozish
      </button>
    );
  }
  const multi = field === "playlist" || field === "schedule";
  return (
    <div className="ai-writer">
      <div className="row">
        <input
          className="input"
          placeholder="Mavzu: dasturchi, sport, sayohat…"
          value={topic}
          maxLength={200}
          onChange={(e) => setTopic(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && !busy && generate()}
        />
        <button className="btn btn--primary btn--inline" disabled={busy} onClick={generate}>
          {busy ? "…" : <WandSparkles size={17} />}
        </button>
      </div>
      {error && <div className="field-error">{error}</div>}
      {items.length > 0 && (
        <>
          <div className="ai-writer__list">
            {items.map((item, i) => (
              <button key={i} className="preset" onClick={() => onPick(item, items)}>
                {render ? render(item) : String(item)}
              </button>
            ))}
          </div>
          {multi && (
            <button className="btn btn--ghost btn--compact" onClick={() => onPick(items[0], items)}>
              Hammasini qo'yish
            </button>
          )}
        </>
      )}
      <p className="hint">Har bir yaratish kunlik AI limitidan 1 ta so'rov oladi.</p>
    </div>
  );
}

// --- 🤖 AI avto-javob ---

export function AIReplyEditor({ state, onDone, onError }: Callbacks) {
  const accountId = state.account!.id;
  const [data, setData] = useState<AIState | null>(null);
  const [form, setForm] = useState<AISettings | null>(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    api
      .ai(accountId)
      .then((d) => {
        setData(d);
        setForm(d.settings);
      })
      .catch((e: Error) => onError(e.message));
  }, [accountId, onError]);

  if (!data || !form) return <div className="spinner spinner--center" />;
  const set = (patch: Partial<AISettings>) => setForm({ ...form, ...patch });
  const current = data.presets.find((p) => p.code === form.preset);

  const save = async (enabled: boolean) => {
    setBusy(true);
    try {
      const d = await api.saveAi(accountId, { ...form, enabled });
      setData(d);
      setForm(d.settings);
      haptic("success");
      onDone(enabled ? "AI avto-javob yoqildi" : "AI avto-javob o'chirildi");
    } catch (e) {
      haptic("error");
      onError((e as Error).message);
    } finally {
      setBusy(false);
    }
  };

  return (
    <>
      {!data.available && (
        <div className="notice notice--warn">
          <CircleAlert size={18} />
          <span>AI hali sozlanmagan — admin OpenAI kalitini qo'shgach ishlaydi.</span>
        </div>
      )}
      <div className="notice">
        <Info size={18} />
        <span>Faqat shaxsiy chatlarda javob beradi. Guruh, kanal va botlarga — yo'q.</span>
      </div>

      <label className="label">Uslub</label>
      <div className="style-grid">
        {data.presets.map((p) => (
          <button key={p.code} className={`style-card ${form.preset === p.code ? "is-selected" : ""}`} onClick={() => set({ preset: p.code })}>
            <b>{p.title}</b>
          </button>
        ))}
        <button className={`style-card ${form.preset === "custom" ? "is-selected" : ""}`} onClick={() => set({ preset: "custom" })}>
          <b>✍️ O'zim yozaman</b>
        </button>
      </div>
      {form.preset === "custom" ? (
        <>
          <textarea
            className="input"
            rows={3}
            maxLength={data.max_style_len}
            placeholder="Masalan: Qisqa va do'stona javob ber, ish haqida bo'lsa ertaga javob berishimni ayt."
            value={form.style}
            onChange={(e) => set({ style: e.target.value })}
          />
          <p className="hint field__hint">
            {form.style.length}/{data.max_style_len} — qisqa uslub arzonroq va aniqroq ishlaydi.
          </p>
        </>
      ) : (
        current && <p className="hint field__hint">{current.desc}</p>
      )}

      <label className="label">Sozlamalar</label>
      <div className="card-inset">
        <Toggle
          on={form.only_when_away}
          onChange={(v) => set({ only_when_away: v })}
          title="Faqat men javob bermasam"
          hint="Shu chatda so'nggi 10 daqiqada yozgan bo'lsangiz, AI jim turadi"
        />
        <Toggle
          on={form.signature}
          onChange={(v) => set({ signature: v })}
          title="🤖 belgisi bilan"
          hint="Suhbatdosh avto-javob ekanini biladi"
        />
      </div>

      <div className="usage ai-usage">
        <div className="usage__head">
          <span>Bugun ishlatildi</span>
          <span className="usage__num">
            {data.used_today}
            <small>/{data.daily_limit}</small>
          </span>
        </div>
        <div className="bar">
          <i style={{ width: `${Math.min(100, (data.used_today / Math.max(1, data.daily_limit)) * 100)}%` }} />
        </div>
      </div>

      <button className="btn btn--primary" disabled={busy || !data.available} onClick={() => save(true)}>
        {data.settings.enabled ? "Saqlash" : "Yoqish"}
      </button>
      {data.settings.enabled && (
        <button className="btn btn--danger" disabled={busy} onClick={() => save(false)}>
          O'chirish
        </button>
      )}
    </>
  );
}

// --- 👀 Stories ---

function timeAgo(ts: number): string {
  const minutes = Math.max(1, Math.round((Date.now() / 1000 - ts) / 60));
  return minutes < 60 ? `${minutes} daq oldin` : `${Math.round(minutes / 60)} soat oldin`;
}

export function StoriesEditor({ state, onDone, onError }: Callbacks) {
  const accountId = state.account!.id;
  const [username, setUsername] = useState("");
  const [result, setResult] = useState<{ peer: { name: string; username: string | null }; items: StoryItem[] } | null>(null);
  const [busy, setBusy] = useState(false);

  const search = async () => {
    if (!username.trim()) return;
    setBusy(true);
    setResult(null);
    try {
      setResult(await api.stories(accountId, username));
      haptic("success");
    } catch (e) {
      haptic("error");
      onError((e as Error).message);
    } finally {
      setBusy(false);
    }
  };

  const send = async (ids?: number[]) => {
    setBusy(true);
    try {
      await api.sendStories(accountId, username, ids);
      haptic("success");
      onDone("Hikoyalar bot chatiga yuborilmoqda 📥");
    } catch (e) {
      onError((e as Error).message);
    } finally {
      setBusy(false);
    }
  };

  const downloadable = result?.items.filter((i) => !i.protected && i.kind !== "other") ?? [];
  return (
    <>
      <div className="row">
        <div className="input-icon">
          <Search size={17} />
          <input
            className="input"
            placeholder="@username"
            value={username}
            autoCapitalize="none"
            onChange={(e) => setUsername(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && search()}
          />
        </div>
        <button className="btn btn--primary btn--inline" disabled={busy || !username.trim()} onClick={search}>
          Ko'rish
        </button>
      </div>
      <p className="hint field__hint">
        <ShieldCheck size={13} /> Faqat sizning akkauntingiz ko'ra oladigan hikoyalar. Ko'rganingiz egasiga ko'rinadi. Himoyalangan hikoyalar
        yuklanmaydi.
      </p>
      {busy && !result && <div className="spinner spinner--center" />}
      {result && (
        <>
          <div className="stories-head">
            <b>{result.peer.name}</b>
            <span className="hint">
              {result.peer.username ? `@${result.peer.username} · ` : ""}
              {result.items.length} ta hikoya
            </span>
          </div>
          {result.items.length === 0 ? (
            <div className="placeholder">Hozir faol hikoya yo'q</div>
          ) : (
            <div className="stories">
              {result.items.map((s) => (
                <button key={s.id} className="story" disabled={s.protected || busy} onClick={() => send([s.id])}>
                  {s.thumb ? <img src={s.thumb} alt="" /> : <span className="story__blank" />}
                  <span className="story__kind">{s.kind === "video" ? <Film size={13} /> : <ImageIcon size={13} />}</span>
                  {s.protected ? (
                    <span className="story__lock">
                      <Lock size={16} />
                    </span>
                  ) : (
                    <span className="story__send">
                      <Send size={14} />
                    </span>
                  )}
                  <span className="story__time">{timeAgo(s.date)}</span>
                </button>
              ))}
            </div>
          )}
          {downloadable.length > 0 && (
            <button className="btn btn--primary" disabled={busy} onClick={() => send()}>
              <Send size={17} /> Hammasini botga yuborish ({downloadable.length})
            </button>
          )}
          <p className="hint">Bittasini bossangiz — faqat o'sha yuboriladi. Fayllar bot chatiga keladi, u yerdan saqlaysiz.</p>
        </>
      )}
    </>
  );
}
