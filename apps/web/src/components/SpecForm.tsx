// Blok maydonlarini tavsif (webapp/specs.ts) bo'yicha chizadigan umumiy forma.
import { ArrowDown, ArrowUp, ChevronDown, ChevronRight, ImagePlus, Plus, Trash2, X } from "lucide-react";
import { useRef, useState } from "react";
import { api, mediaUrl } from "../api";
import { fileToJpegBase64 } from "../util";
import { ACTION_TYPES, NO_ACTION, type FieldSpec, type Opt } from "../webapp/specs";
import type { WAAction, WAPage } from "../webapp/types";
import { WA_ICONS, WA_ICON_NAMES } from "../webapp/icons";

type Ctx = { pages: WAPage[]; toast: (text: string, kind?: "ok" | "err") => void };
type Obj = Record<string, any>;

export function SpecForm({ spec, value, onChange, ctx }: { spec: FieldSpec[]; value: Obj; onChange: (next: Obj) => void; ctx: Ctx }) {
  const set = (key: string, v: unknown) => onChange({ ...value, [key]: v });
  return (
    <div className="sf">
      {spec.map((f) => (
        <SpecField key={f.key} f={f} value={value[f.key]} set={(v) => set(f.key, v)} ctx={ctx} />
      ))}
    </div>
  );
}

function Label({ text, hint }: { text: string; hint?: string }) {
  return (
    <span className="sf-label">
      {text}
      {hint && <span className="sf-hint">{hint}</span>}
    </span>
  );
}

function Choice({ options, value, onPick }: { options: Opt[]; value: unknown; onPick: (v: string | number) => void }) {
  if (options.length <= 3)
    return (
      <div className="segmented segmented--small">
        {options.map(([v, label]) => (
          <button key={String(v)} type="button" className={value === v ? "is-selected" : ""} onClick={() => onPick(v)}>
            {label}
          </button>
        ))}
      </div>
    );
  return (
    <select
      className="input"
      value={String(value)}
      onChange={(e) => {
        const opt = options.find(([v]) => String(v) === e.target.value);
        if (opt) onPick(opt[0]);
      }}
    >
      {options.map(([v, label]) => (
        <option key={String(v)} value={String(v)}>
          {label}
        </option>
      ))}
    </select>
  );
}

const EMOJIS = ["⭐", "✨", "🔥", "✅", "📦", "🛍", "🍽", "☕", "🚚", "💳", "📞", "📍", "🎁", "🎓", "💼", "🏠", "❤️", "👍", "🎉", "📝", "⏰", "💎", "🚀", "🛠"];

function SpecField({ f, value, set, ctx }: { f: FieldSpec; value: any; set: (v: unknown) => void; ctx: Ctx }) {
  switch (f.kind) {
    case "text":
      return (
        <label className="sf-field">
          <Label text={f.label} hint={f.hint} />
          <input className="input" maxLength={f.max} placeholder={f.placeholder} value={value ?? ""} onChange={(e) => set(e.target.value)} />
        </label>
      );
    case "textarea":
      return (
        <label className="sf-field">
          <Label text={`${f.label} · ${(value ?? "").length}/${f.max}`} hint={f.hint} />
          <textarea className="input" rows={f.rows ?? 3} maxLength={f.max} placeholder={f.placeholder} value={value ?? ""} onChange={(e) => set(e.target.value)} />
        </label>
      );
    case "number":
      return (
        <label className="sf-field">
          <Label text={f.label} hint={f.hint} />
          <input
            className="input"
            inputMode="numeric"
            value={value === null || value === undefined ? "" : String(value)}
            placeholder={f.optional ? "—" : "0"}
            onChange={(e) => {
              const raw = e.target.value.replace(/[^\d]/g, "");
              if (raw === "") set(f.optional ? null : 0);
              else set(Math.min(Number(raw), f.max ?? Number.MAX_SAFE_INTEGER));
            }}
          />
        </label>
      );
    case "select":
      return (
        <div className="sf-field">
          <Label text={f.label} />
          <Choice options={f.options} value={value} onPick={set} />
        </div>
      );
    case "toggle":
      return (
        <button type="button" className="sf-toggle" onClick={() => set(!value)}>
          <span>
            {f.label}
            {f.hint && <span className="sf-hint">{f.hint}</span>}
          </span>
          <span className={`switch ${value ? "is-on" : ""}`}>
            <i />
          </span>
        </button>
      );
    case "emoji":
      return <EmojiField label={f.label} value={value ?? ""} set={set} />;
    case "media":
      return <MediaField label={f.label} value={value ?? null} set={set} optional={f.optional} ctx={ctx} />;
    case "medias":
      return <MediasField label={f.label} value={value ?? []} set={set} max={f.max} ctx={ctx} />;
    case "action":
      return <ActionField label={f.label} value={value ?? NO_ACTION} set={set} ctx={ctx} />;
    case "btn":
      return (
        <div className="sf-field">
          <button type="button" className="sf-toggle" onClick={() => set(value ? null : { text: "Batafsil", action: { ...NO_ACTION } })}>
            <span>{f.label}</span>
            <span className={`switch ${value ? "is-on" : ""}`}>
              <i />
            </span>
          </button>
          {value && (
            <div className="sf-nested">
              <label className="sf-field">
                <Label text="Tugma matni" />
                <input className="input" maxLength={40} value={value.text} onChange={(e) => set({ ...value, text: e.target.value })} />
              </label>
              <ActionField label="Bosilganda" value={value.action} set={(a) => set({ ...value, action: a })} ctx={ctx} />
            </div>
          )}
        </div>
      );
    case "date": {
      const d = value ? new Date(value) : null;
      const local = d && !Number.isNaN(d.getTime()) ? new Date(d.getTime() - d.getTimezoneOffset() * 60000).toISOString().slice(0, 16) : "";
      return (
        <label className="sf-field">
          <Label text={f.label} />
          <input className="input" type="datetime-local" value={local} onChange={(e) => e.target.value && set(new Date(e.target.value).toISOString())} />
        </label>
      );
    }
    case "lines":
      return (
        <label className="sf-field">
          <Label text={f.label} hint={f.hint} />
          <textarea
            className="input"
            rows={3}
            value={(value ?? []).join("\n")}
            onChange={(e) => set(e.target.value.split("\n").slice(0, f.max))}
            onBlur={(e) => set(e.target.value.split("\n").map((s) => s.trim()).filter(Boolean).slice(0, f.max))}
          />
        </label>
      );
    case "list":
      return <ListField f={f} value={value ?? []} set={set} ctx={ctx} />;
    case "slider":
      return <SliderField label={f.label} value={value ?? null} set={set} min={f.min} max={f.max} step={f.step} suffix={f.suffix} optional={f.optional} />;
    case "icon":
      return <IconField label={f.label} value={value ?? null} set={set} optional={f.optional} />;
  }
}

export function SliderField({
  label,
  value,
  set,
  min,
  max,
  step = 1,
  suffix = "",
  optional,
}: {
  label: string;
  value: number | null;
  set: (v: number | null) => void;
  min: number;
  max: number;
  step?: number;
  suffix?: string;
  optional?: boolean;
}) {
  return (
    <div className="sf-field">
      <span className="sf-slider__head">
        <span className="sf-label">{label}</span>
        <span className="sf-slider__val">
          {value === null ? "avto" : `${value}${suffix}`}
          {optional && value !== null && (
            <button type="button" className="sf-reset" onClick={() => set(null)} aria-label="Avto" title="Avto">
              <X size={12} />
            </button>
          )}
        </span>
      </span>
      <input type="range" min={min} max={max} step={step} value={value ?? min} onChange={(e) => set(Number(e.target.value))} />
    </div>
  );
}

export function IconField({ label, value, set, optional }: { label: string; value: string | null; set: (v: string | null) => void; optional?: boolean }) {
  const [open, setOpen] = useState(false);
  const [q, setQ] = useState("");
  const Current = value ? WA_ICONS[value] : null;
  const list = WA_ICON_NAMES.filter((n) => n.toLowerCase().includes(q.toLowerCase()));
  return (
    <div className="sf-field">
      <Label text={label} />
      <div className="row">
        <span className="sf-icon-cur">{Current ? <Current size={22} /> : "—"}</span>
        <button type="button" className="btn btn--ghost btn--compact btn--inline" onClick={() => setOpen(!open)}>
          {open ? "Yopish" : "Tanlash"}
        </button>
        {optional && value && (
          <button type="button" className="icon-btn" onClick={() => set(null)} aria-label="Olib tashlash">
            <X size={18} />
          </button>
        )}
      </div>
      {open && (
        <div className="sf-icons">
          <input className="input" placeholder="Qidirish (inglizcha): star, phone…" value={q} onChange={(e) => setQ(e.target.value)} />
          <div className="sf-icons__grid">
            {list.map((n) => {
              const I = WA_ICONS[n];
              return (
                <button key={n} type="button" title={n} className={value === n ? "is-selected" : ""} onClick={() => (set(n), setOpen(false))}>
                  <I size={20} />
                </button>
              );
            })}
          </div>
        </div>
      )}
    </div>
  );
}

function EmojiField({ label, value, set }: { label: string; value: string; set: (v: string) => void }) {
  const [open, setOpen] = useState(false);
  return (
    <div className="sf-field">
      <Label text={label} />
      <div className="row">
        <input className="input sf-emoji" maxLength={8} value={value} onChange={(e) => set(e.target.value)} />
        <button type="button" className="btn btn--ghost btn--compact btn--inline" onClick={() => setOpen(!open)}>
          Tanlash
        </button>
      </div>
      {open && (
        <div className="sf-emojis">
          {EMOJIS.map((e) => (
            <button key={e} type="button" onClick={() => (set(e), setOpen(false))}>
              {e}
            </button>
          ))}
        </div>
      )}
    </div>
  );
}

async function upload(file: File): Promise<number> {
  return (await api.uploadMedia(await fileToJpegBase64(file))).id;
}

export function MediaField({ label, value, set, optional, ctx }: { label: string; value: number | null; set: (v: number | null) => void; optional?: boolean; ctx: Ctx }) {
  const ref = useRef<HTMLInputElement>(null);
  const [busy, setBusy] = useState(false);
  return (
    <div className="sf-field">
      <Label text={label} hint={optional ? "ixtiyoriy" : undefined} />
      <div className="row">
        {value ? (
          <img className="sf-thumb" src={mediaUrl(value)} alt="" />
        ) : (
          <span className="sf-thumb sf-thumb--empty">
            <ImagePlus size={20} />
          </span>
        )}
        <button type="button" className="btn btn--ghost btn--compact btn--inline" disabled={busy} onClick={() => ref.current?.click()}>
          {busy ? "Yuklanmoqda…" : value ? "Almashtirish" : "Yuklash"}
        </button>
        {value && (
          <button type="button" className="icon-btn" onClick={() => set(null)} aria-label="Olib tashlash">
            <X size={18} />
          </button>
        )}
      </div>
      <input
        ref={ref}
        type="file"
        accept="image/*"
        hidden
        onChange={async (e) => {
          const file = e.target.files?.[0];
          e.target.value = "";
          if (!file) return;
          setBusy(true);
          try {
            set(await upload(file));
          } catch (err) {
            ctx.toast((err as Error).message, "err");
          } finally {
            setBusy(false);
          }
        }}
      />
    </div>
  );
}

function MediasField({ label, value, set, max, ctx }: { label: string; value: number[]; set: (v: number[]) => void; max: number; ctx: Ctx }) {
  const ref = useRef<HTMLInputElement>(null);
  const [busy, setBusy] = useState(0);
  return (
    <div className="sf-field">
      <Label text={`${label} · ${value.length}/${max}`} />
      <div className="sf-medias">
        {value.map((id, i) => (
          <div key={`${id}-${i}`} className="sf-medias__item">
            <img src={mediaUrl(id)} alt="" />
            <button type="button" onClick={() => set(value.filter((_, j) => j !== i))} aria-label="O'chirish">
              <X size={14} />
            </button>
          </div>
        ))}
        {value.length < max && (
          <button type="button" className="sf-medias__add" disabled={busy > 0} onClick={() => ref.current?.click()}>
            {busy ? `${busy}…` : <Plus size={20} />}
          </button>
        )}
      </div>
      <input
        ref={ref}
        type="file"
        accept="image/*"
        multiple
        hidden
        onChange={async (e) => {
          const files = Array.from(e.target.files ?? []).slice(0, max - value.length);
          e.target.value = "";
          let ids = [...value];
          setBusy(files.length);
          for (const file of files) {
            try {
              ids = [...ids, await upload(file)];
              set(ids);
            } catch (err) {
              ctx.toast((err as Error).message, "err");
            }
            setBusy((n) => n - 1);
          }
        }}
      />
    </div>
  );
}

export function ActionField({ label, value, set, ctx }: { label: string; value: WAAction; set: (v: WAAction) => void; ctx: Ctx }) {
  const a = { ...NO_ACTION, ...value };
  return (
    <div className="sf-field">
      <Label text={label} />
      <select className="input" value={a.type} onChange={(e) => set({ ...NO_ACTION, type: e.target.value as WAAction["type"], page: e.target.value === "page" ? ctx.pages[0]?.id ?? null : null })}>
        {ACTION_TYPES.map(([v, l]) => (
          <option key={v} value={v}>
            {l}
          </option>
        ))}
      </select>
      {a.type === "page" && (
        <select className="input" value={a.page ?? ""} onChange={(e) => set({ ...a, page: e.target.value })}>
          {ctx.pages.map((p) => (
            <option key={p.id} value={p.id}>
              {p.emoji} {p.title}
            </option>
          ))}
        </select>
      )}
      {a.type === "url" && <input className="input" inputMode="url" placeholder="https://..." value={a.url ?? ""} onChange={(e) => set({ ...a, url: e.target.value.trim() })} />}
      {a.type === "phone" && <input className="input" inputMode="tel" placeholder="+998 90 123 45 67" value={a.phone ?? ""} onChange={(e) => set({ ...a, phone: e.target.value })} />}
      {a.type === "bot" && <span className="sf-hint">Ilova yopiladi va bot chati ochiladi</span>}
      {a.type === "share" && <span className="sf-hint">Bot havolasini do'stlarga ulashish oynasi ochiladi</span>}
    </div>
  );
}

function ListField({ f, value, set, ctx }: { f: Extract<FieldSpec, { kind: "list" }>; value: Obj[]; set: (v: Obj[]) => void; ctx: Ctx }) {
  const [open, setOpen] = useState<number | null>(value.length === 1 ? 0 : null);
  const move = (i: number, d: number) => {
    const j = i + d;
    if (j < 0 || j >= value.length) return;
    const next = [...value];
    [next[i], next[j]] = [next[j], next[i]];
    set(next);
    setOpen(j);
  };
  return (
    <div className="sf-field">
      <Label text={`${f.label} · ${value.length}/${f.max}`} />
      <div className="sf-list">
        {value.map((item, i) => (
          <div key={i} className={`sf-list__item ${open === i ? "is-open" : ""}`}>
            <div className="sf-list__head">
              <button type="button" className="sf-list__title" onClick={() => setOpen(open === i ? null : i)}>
                {open === i ? <ChevronDown size={16} /> : <ChevronRight size={16} />}
                <span>{f.title(item) || `#${i + 1}`}</span>
              </button>
              <button type="button" className="icon-btn" disabled={i === 0} onClick={() => move(i, -1)} aria-label="Yuqoriga">
                <ArrowUp size={15} />
              </button>
              <button type="button" className="icon-btn" disabled={i === value.length - 1} onClick={() => move(i, 1)} aria-label="Pastga">
                <ArrowDown size={15} />
              </button>
              <button
                type="button"
                className="icon-btn"
                onClick={() => {
                  set(value.filter((_, j) => j !== i));
                  setOpen(null);
                }}
                aria-label="O'chirish"
              >
                <Trash2 size={15} color="var(--danger)" />
              </button>
            </div>
            {open === i && (
              <div className="sf-list__body">
                <SpecForm spec={f.item} value={item} onChange={(next) => set(value.map((x, j) => (j === i ? next : x)))} ctx={ctx} />
              </div>
            )}
          </div>
        ))}
      </div>
      {value.length < f.max && (
        <button
          type="button"
          className="btn btn--ghost btn--compact"
          onClick={() => {
            set([...value, f.make()]);
            setOpen(value.length);
          }}
        >
          <Plus size={16} /> Qo'shish
        </button>
      )}
    </div>
  );
}
