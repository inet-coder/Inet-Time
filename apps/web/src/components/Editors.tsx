import {
  ArrowUp,
  CircleAlert,
  Eye,
  FileText,
  ImagePlus,
  Info,
  ListOrdered,
  LoaderCircle,
  Plus,
  Shuffle,
  Star,
  Type,
  X,
} from "lucide-react";
import { useEffect, useMemo, useRef, useState, type ReactNode } from "react";
import { api, emojiUrl, mediaUrl, type ActiveService, type CatalogService, type ScheduleSuggestion, type State } from "../api";
import type { Overrides } from "../profile";
import { AIWriter } from "./AIEditors";
import { openBot } from "../tg";
import { fileToJpegBase64, intervalText } from "../util";

export type EditorProps = {
  state: State;
  service: CatalogService;
  active?: ActiveService;
  setOverrides: (o: Overrides) => void;
  save: (body: { items: { template: string; at_time?: string }[]; interval_seconds?: number; selection_strategy?: string; field?: string }) => Promise<void>;
  busy: boolean;
};

type Preview = { ok: boolean; now?: string; later?: string; error?: string; limit: number; length?: number };

// Yozish paytida jonli ko'rinish: 300ms kutib, server bilan aynan qanday chiqishini hisoblaymiz.
function useLivePreview(accountId: number, field: string, template: string): Preview | null {
  const [preview, setPreview] = useState<Preview | null>(null);
  useEffect(() => {
    if (!template.trim()) {
      setPreview(null);
      return;
    }
    const timer = setTimeout(() => {
      api.preview(accountId, field, template).then(setPreview).catch(() => setPreview(null));
    }, 300);
    return () => clearTimeout(timer);
  }, [accountId, field, template]);
  return preview;
}

function IntervalPicker({ options, value, onChange }: { options: number[]; value: number; onChange: (v: number) => void }) {
  return (
    <div className="chips">
      {options.map((s) => (
        <button key={s} className={`chip-btn ${s === value ? "is-selected" : ""}`} onClick={() => onChange(s)}>
          har {intervalText(s)}
        </button>
      ))}
    </div>
  );
}

function Segmented<T extends string>({ options, value, onChange }: { options: [T, ReactNode][]; value: T; onChange: (v: T) => void }) {
  return (
    <div className="segmented">
      {options.map(([v, label]) => (
        <button key={v} className={v === value ? "is-selected" : ""} onClick={() => onChange(v)}>
          {label}
        </button>
      ))}
    </div>
  );
}

function ErrorLine({ children }: { children: ReactNode }) {
  return (
    <div className="preview preview--err">
      <CircleAlert size={16} className="preview__icon" />
      <span>{children}</span>
    </div>
  );
}

function PreviewLine({ preview }: { preview: Preview | null }) {
  if (!preview) return null;
  if (!preview.ok) return <ErrorLine>{preview.error}</ErrorLine>;
  const pct = Math.min(100, ((preview.length ?? 0) / preview.limit) * 100);
  return (
    <div className="preview">
      <div className="preview__head">
        <Eye size={14} /> Natija
        <span className={`preview__count ${pct > 90 ? "is-near" : ""}`}>
          {preview.length}/{preview.limit}
        </span>
      </div>
      <div className="preview__row">
        <span className="preview__tag">Hozir</span>
        <span>{preview.now}</span>
      </div>
      {preview.later !== preview.now && (
        <div className="preview__row">
          <span className="preview__tag preview__tag--muted">+1 daq</span>
          <span>{preview.later}</span>
        </div>
      )}
      <div className="meter">
        <i style={{ width: `${pct}%` }} />
      </div>
    </div>
  );
}

function AddButton({ onClick, children }: { onClick: () => void; children: ReactNode }) {
  return (
    <button className="btn btn--ghost" onClick={onClick}>
      <Plus size={18} /> {children}
    </button>
  );
}

// --- Oddiy shablon (Soat ismda, Avto bio, Avto ism) ---

export function TemplateEditor({ state, service, active, setOverrides, save, busy }: EditorProps) {
  const [template, setTemplate] = useState(active?.template ?? service.default ?? "");
  const inputRef = useRef<HTMLTextAreaElement>(null);
  const preview = useLivePreview(state.account!.id, service.field, template);

  useEffect(() => {
    if (preview?.ok) setOverrides({ [service.field]: preview.now } as Overrides);
  }, [preview, service.field, setOverrides]);

  const insert = (key: string) => {
    const el = inputRef.current;
    const pos = el?.selectionStart ?? template.length;
    setTemplate(template.slice(0, pos) + key + template.slice(pos));
    requestAnimationFrame(() => {
      el?.focus();
      el?.setSelectionRange(pos + key.length, pos + key.length);
    });
  };

  const unchanged = active && active.template === template;
  return (
    <>
      <label className="label">Shablon</label>
      <textarea ref={inputRef} className="input" rows={2} value={template} onChange={(e) => setTemplate(e.target.value)} />
      <div className="chips chips--scroll">
        {state.variables.map((v) => (
          <button key={v.key} className="chip-btn" onClick={() => insert(v.key)}>
            <Plus size={13} strokeWidth={2.5} /> {v.label}
          </button>
        ))}
      </div>
      <AIWriter state={state} field={service.field === "name" ? "name" : "bio"} onPick={(item) => setTemplate(String(item))} />
      <PreviewLine preview={preview} />
      {service.presets && (
        <>
          <label className="label">Tayyor namunalar</label>
          <div className="presets">
            {service.presets.map((p) => (
              <button key={p} className={`preset ${p === template ? "is-selected" : ""}`} onClick={() => setTemplate(p)}>
                {p}
              </button>
            ))}
          </div>
        </>
      )}
      <button className="btn btn--primary" disabled={busy || !preview?.ok || !!unchanged} onClick={() => save({ items: [{ template }] })}>
        {active ? (unchanged ? "Saqlangan" : "Saqlash") : "Yoqish"}
      </button>
    </>
  );
}

// --- Bio playlist ---

export function PlaylistEditor({ state, service, active, setOverrides, save, busy }: EditorProps) {
  const [items, setItems] = useState<string[]>(active ? active.actions.map((a) => a.template) : ["", ""]);
  const [order, setOrder] = useState<"SEQUENTIAL" | "RANDOM">(active?.selection_strategy === "RANDOM" ? "RANDOM" : "SEQUENTIAL");
  const intervals = service.intervals ?? [3600];
  const [intervalSec, setIntervalSec] = useState(active?.interval_seconds ?? intervals[2] ?? intervals[0]);
  const [focus, setFocus] = useState(0);
  const preview = useLivePreview(state.account!.id, "bio", items[focus] ?? "");

  useEffect(() => {
    if (preview?.ok) setOverrides({ bio: preview.now });
  }, [preview, setOverrides]);

  const filled = items.filter((i) => i.trim());
  const update = (i: number, value: string) => setItems(items.map((x, j) => (j === i ? value : x)));
  const move = (i: number, dir: -1 | 1) => {
    const j = i + dir;
    if (j < 0 || j >= items.length) return;
    const copy = [...items];
    [copy[i], copy[j]] = [copy[j], copy[i]];
    setItems(copy);
  };

  const [pack, setPack] = useState<string | null>(null);

  return (
    <>
      {service.packs && (
        <>
          <label className="label">Tayyor to'plamlar</label>
          <div className="chips chips--scroll">
            {service.packs.map((p) => (
              <button
                key={p.code}
                className={`chip-btn ${pack === p.code ? "is-selected" : ""}`}
                onClick={() => {
                  setPack(p.code);
                  setItems(p.items);
                  setFocus(0);
                }}
              >
                {p.title}
              </button>
            ))}
          </div>
        </>
      )}
      <label className="label">Matnlar ({filled.length}/10) — navbat bilan bio bo'ladi</label>
      <div className="list">
        {items.map((item, i) => (
          <div key={i} className="list__row">
            <span className="list__num">{i + 1}</span>
            <input
              className="input"
              value={item}
              placeholder="Bio matni"
              onFocus={() => setFocus(i)}
              onChange={(e) => {
                setPack(null);
                update(i, e.target.value);
              }}
            />
            <button className="icon-btn" onClick={() => move(i, -1)} disabled={i === 0} aria-label="Yuqoriga">
              <ArrowUp size={17} />
            </button>
            <button className="icon-btn" onClick={() => setItems(items.filter((_, j) => j !== i))} disabled={items.length <= 2} aria-label="O'chirish">
              <X size={17} />
            </button>
          </div>
        ))}
      </div>
      {items.length < 10 && <AddButton onClick={() => setItems([...items, ""])}>Matn qo'shish</AddButton>}
      <AIWriter state={state} field="playlist" onPick={(_, all) => setItems(all.map(String).slice(0, 10))} />
      <PreviewLine preview={preview} />
      <label className="label">Tartib</label>
      <Segmented
        options={[
          ["SEQUENTIAL", <><ListOrdered size={16} /> Ketma-ket</>],
          ["RANDOM", <><Shuffle size={16} /> Tasodifiy</>],
        ]}
        value={order}
        onChange={setOrder}
      />
      <label className="label">Qanchada bir almashsin</label>
      <IntervalPicker options={intervals} value={intervalSec} onChange={setIntervalSec} />
      <button
        className="btn btn--primary"
        disabled={busy || filled.length < 2}
        onClick={() => save({ items: filled.map((template) => ({ template })), interval_seconds: intervalSec, selection_strategy: order })}
      >
        {active ? "Saqlash" : "Yoqish"}
      </button>
    </>
  );
}

// --- Jadval ---

type Slot = { at_time: string; template: string };

const HOURS = Array.from({ length: 24 }, (_, h) => String(h).padStart(2, "0"));
const MINUTES = Array.from({ length: 12 }, (_, i) => String(i * 5).padStart(2, "0"));

// <input type="time"> telefon tiliga qarab 12 soatlik (AM/PM) chiqishi mumkin — shuning uchun o'zimizning 24 soatlik tanlagich.
function TimeSelect({ value, onChange }: { value: string; onChange: (v: string) => void }) {
  const [hour, minute] = value.split(":");
  const minutes = MINUTES.includes(minute) ? MINUTES : [...MINUTES, minute].sort();
  return (
    <div className="time-select">
      <select value={hour} onChange={(e) => onChange(`${e.target.value}:${minute}`)}>
        {HOURS.map((h) => (
          <option key={h}>{h}</option>
        ))}
      </select>
      <span>:</span>
      <select value={minute} onChange={(e) => onChange(`${hour}:${e.target.value}`)}>
        {minutes.map((m) => (
          <option key={m}>{m}</option>
        ))}
      </select>
    </div>
  );
}

function currentSlot(slots: Slot[], timezone: string): number {
  const now = new Date().toLocaleTimeString("ru-RU", { hour: "2-digit", minute: "2-digit", timeZone: timezone });
  const sorted = slots.map((s, i) => [s.at_time, i] as const).filter(([t]) => t).sort();
  const past = sorted.filter(([t]) => t <= now);
  return (past.length ? past[past.length - 1] : sorted[sorted.length - 1])?.[1] ?? 0;
}

export function ScheduleEditor({ state, active, setOverrides, save, busy }: EditorProps) {
  const [field, setField] = useState<"bio" | "name">((active?.field as "bio" | "name") ?? "bio");
  const [slots, setSlots] = useState<Slot[]>(
    active
      ? active.actions.map((a) => ({ at_time: a.at_time ?? "", template: a.template }))
      : [
          { at_time: "09:00", template: "Ishdaman 💼" },
          { at_time: "18:00", template: "Uydaman 🏠" },
          { at_time: "23:00", template: "Uxlayapman 😴" },
        ],
  );
  const nowIndex = useMemo(() => currentSlot(slots, state.timezone), [slots, state.timezone]);
  const preview = useLivePreview(state.account!.id, field, slots[nowIndex]?.template ?? "");

  useEffect(() => {
    if (preview?.ok) setOverrides({ [field]: preview.now } as Overrides);
  }, [preview, field, setOverrides]);

  const update = (i: number, patch: Partial<Slot>) => setSlots(slots.map((s, j) => (j === i ? { ...s, ...patch } : s)));
  const times = slots.map((s) => s.at_time);
  const valid = slots.length >= 2 && slots.every((s) => s.at_time && s.template.trim()) && new Set(times).size === times.length;

  return (
    <>
      <label className="label">Nima o'zgarsin</label>
      <Segmented
        options={[
          ["bio", <><FileText size={16} /> Bio</>],
          ["name", <><Type size={16} /> Ism</>],
        ]}
        value={field}
        onChange={setField}
      />
      <label className="label">Jadval ({state.timezone} vaqti bilan)</label>
      <div className="list">
        {slots.map((slot, i) => (
          <div key={i} className={`list__row ${i === nowIndex ? "is-current" : ""}`}>
            <TimeSelect value={slot.at_time} onChange={(at_time) => update(i, { at_time })} />
            <input className="input" value={slot.template} placeholder="Matn" onChange={(e) => update(i, { template: e.target.value })} />
            <button className="icon-btn" onClick={() => setSlots(slots.filter((_, j) => j !== i))} disabled={slots.length <= 2} aria-label="O'chirish">
              <X size={17} />
            </button>
          </div>
        ))}
      </div>
      <p className="hint">Yashil qator — hozir amal qiladigani. Har vaqtda matn o'zgaradi va keyingi vaqtgacha turadi.</p>
      {slots.length < 10 && <AddButton onClick={() => setSlots([...slots, { at_time: "12:00", template: "" }])}>Vaqt qo'shish</AddButton>}
      <AIWriter<ScheduleSuggestion>
        state={state}
        field="schedule"
        render={(item) => `${item.time} → ${item.text}`}
        onPick={(_, all) =>
          setSlots(
            all
              .filter((i) => /^\d{2}:\d{2}$/.test(i.time))
              .map((i) => ({ at_time: i.time, template: i.text }))
              .slice(0, 10),
          )
        }
      />
      {!valid && <ErrorLine>Kamida 2 ta vaqt, matnlar to'ldirilgan va vaqtlar takrorlanmagan bo'lsin.</ErrorLine>}
      <PreviewLine preview={preview} />
      <button
        className="btn btn--primary"
        disabled={busy || !valid}
        onClick={() =>
          save({
            field,
            items: [...slots].sort((a, b) => (a.at_time < b.at_time ? -1 : 1)),
            selection_strategy: "BY_TIME",
          })
        }
      >
        {active ? "Saqlash" : "Yoqish"}
      </button>
    </>
  );
}

// --- Rasm almashtirish ---

export function PhotoEditor({ service, active, setOverrides, save, busy }: EditorProps) {
  const [photos, setPhotos] = useState<string[]>(active ? active.actions.map((a) => a.template) : []);
  const intervals = service.intervals ?? [3600];
  const [intervalSec, setIntervalSec] = useState(active?.interval_seconds ?? intervals[0]);
  const [uploading, setUploading] = useState(0);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    setOverrides({ photo: photos[0] ?? null });
  }, [photos, setOverrides]);

  const onFiles = async (files: FileList | null) => {
    if (!files) return;
    setError(null);
    const list = Array.from(files).slice(0, 10 - photos.length);
    setUploading(list.length);
    const ids: string[] = [];
    for (const file of list) {
      try {
        const { id } = await api.uploadMedia(await fileToJpegBase64(file));
        ids.push(String(id));
      } catch (e) {
        setError((e as Error).message);
      }
      setUploading((n) => n - 1);
    }
    setPhotos((prev) => [...prev, ...ids]);
  };

  return (
    <>
      <label className="label">Rasmlar ({photos.length}/10) — birinchisi hozir qo'yiladi</label>
      <div className="photos">
        {photos.map((id, i) => (
          <div key={id} className="photos__item">
            <img src={mediaUrl(id)} alt="" />
            <span className="photos__num">{i + 1}</span>
            <button className="photos__remove" onClick={() => setPhotos(photos.filter((p) => p !== id))} aria-label="O'chirish">
              <X size={14} />
            </button>
            {i > 0 && (
              <button className="photos__first" onClick={() => setPhotos([id, ...photos.filter((p) => p !== id)])} aria-label="Birinchi qilish">
                <Star size={13} />
              </button>
            )}
          </div>
        ))}
        {photos.length < 10 && (
          <label className="photos__add">
            <input type="file" accept="image/*" multiple onChange={(e) => onFiles(e.target.files)} hidden />
            {uploading ? <LoaderCircle size={24} className="spin" /> : <ImagePlus size={24} />}
            <span>{uploading ? `Yuklanmoqda (${uploading})` : "Rasm qo'shish"}</span>
          </label>
        )}
      </div>
      {error && <ErrorLine>{error}</ErrorLine>}
      {photos.length > 1 && (
        <>
          <label className="label">Qanchada bir almashsin</label>
          <IntervalPicker options={intervals} value={intervalSec} onChange={setIntervalSec} />
        </>
      )}
      <p className="hint">O'chirsangiz — biz qo'ygan rasm o'chadi va asl rasmingiz qaytadi.</p>
      <button
        className="btn btn--primary"
        disabled={busy || uploading > 0 || photos.length === 0}
        onClick={() =>
          save({
            items: photos.map((template) => ({ template })),
            interval_seconds: photos.length > 1 ? intervalSec : 3600,
            selection_strategy: photos.length > 1 ? "SEQUENTIAL" : "NONE",
          })
        }
      >
        {active ? "Saqlash" : "Yoqish"}
      </button>
    </>
  );
}

// --- Emoji status ---

export function EmojiEditor({ state, service, active, setOverrides, save, busy }: EditorProps) {
  const [emojis, setEmojis] = useState<string[]>(active ? active.actions.map((a) => a.template) : []);
  const intervals = service.intervals ?? [3600];
  const [intervalSec, setIntervalSec] = useState(active?.interval_seconds ?? intervals[1] ?? intervals[0]);

  useEffect(() => {
    setOverrides({ emoji_status: emojis[0] ?? null });
  }, [emojis, setOverrides]);

  if (!state.account!.is_premium) {
    return (
      <div className="notice notice--warn">
        <CircleAlert size={18} />
        <span>Bu akkauntda Telegram Premium yo'q — emoji status faqat Premium akkauntlarda ishlaydi.</span>
      </div>
    );
  }
  return (
    <>
      <label className="label">Emojilar ({emojis.length}/10)</label>
      <div className="emojis">
        {emojis.map((id, i) => (
          <div key={id} className="emojis__item">
            <img src={emojiUrl(id)} alt="" />
            <button onClick={() => setEmojis(emojis.filter((_, j) => j !== i))} aria-label="O'chirish">
              <X size={12} strokeWidth={3} />
            </button>
          </div>
        ))}
        <button className="emojis__item emojis__add" onClick={() => openBot(state.bot_username, "emoji")} aria-label="Emoji qo'shish">
          <Plus size={22} />
        </button>
      </div>
      <p className="hint">Premium emojini faqat Telegram chatida yuborish mumkin — «+» bosilganda bot ochiladi, emojilarni o'sha yerga yuboring.</p>
      {emojis.length > 1 && (
        <>
          <label className="label">Qanchada bir almashsin</label>
          <IntervalPicker options={intervals} value={intervalSec} onChange={setIntervalSec} />
        </>
      )}
      {emojis.length > 0 && (
        <button
          className="btn btn--primary"
          disabled={busy}
          onClick={() =>
            save({
              items: emojis.map((template) => ({ template })),
              interval_seconds: emojis.length > 1 ? intervalSec : 60,
              selection_strategy: emojis.length > 1 ? "SEQUENTIAL" : "NONE",
            })
          }
        >
          Saqlash
        </button>
      )}
    </>
  );
}

// --- 24/7 Online ---

export function OnlineEditor({ active, setOverrides, save, busy }: EditorProps) {
  useEffect(() => {
    setOverrides({ online: "true" });
  }, [setOverrides]);
  return (
    <>
      <div className="notice">
        <Info size={18} />
        <span>
          Akkauntingiz doim «online» ko'rinadi. Telefoningizda Telegram'ni yopsangiz holat qisqa vaqtga o'zgarishi mumkin; boshqalar buni
          faqat maxfiylik sozlamalaringiz ruxsat bersa ko'radi.
        </span>
      </div>
      {!active && (
        <button className="btn btn--primary" disabled={busy} onClick={() => save({ items: [{ template: "true" }] })}>
          Yoqish
        </button>
      )}
    </>
  );
}
