// Web App ma'lumotlar bazasi muharriri: to'plamlar, yozuvlar jadvali, bog'lash sozlamalari.
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { ChevronLeft, Database, Download, Pencil, Plus, Search, Settings2, Trash2, Upload } from "lucide-react";
import { createContext, useContext, useEffect, useMemo, useRef, useState } from "react";
import { api, mediaUrl, type DataCollection, type DataField, type DataFieldType, type DataRecord } from "../api";
import { confirmDialog, haptic } from "../tg";
import { clearDataCache } from "../webapp/data";
import type { FormBlock, WAPage, WAQuery } from "../webapp/types";
import { MediaField, SliderField } from "./SpecForm";
import { Sheet } from "./Sheet";

type Toast = (text: string, kind?: "ok" | "err") => void;

// --- Konstruktor bo'ylab to'plamlar ro'yxati ---

type DataCtx = { botId: number; collections: DataCollection[]; refetch: () => void };
const DataContext = createContext<DataCtx>({ botId: 0, collections: [], refetch: () => undefined });
export const useCollections = () => useContext(DataContext);

export function DataProvider({ botId, children }: { botId: number; children: React.ReactNode }) {
  const { data, refetch } = useQuery({ queryKey: ["collections", botId], queryFn: () => api.collections(botId) });
  const value = useMemo(() => ({ botId, collections: data?.items ?? [], refetch: () => void refetch() }), [botId, data, refetch]);
  return <DataContext.Provider value={value}>{children}</DataContext.Provider>;
}

export const FIELD_TYPES: [DataFieldType, string][] = [
  ["text", "Matn"],
  ["longtext", "Katta matn"],
  ["number", "Son"],
  ["money", "Narx (so'm)"],
  ["image", "Rasm"],
  ["date", "Sana"],
  ["bool", "Ha / yo'q"],
  ["select", "Tanlov"],
  ["phone", "Telefon"],
  ["url", "Havola"],
  ["email", "Email"],
];

const READ_MODES: [DataCollection["read"], string, string][] = [
  ["public", "Hamma ko'radi", "Ilovaning barcha foydalanuvchilari (yashirin maydonlarsiz)"],
  ["own", "Faqat o'zinikini", "Har kim faqat o'zi qo'shgan yozuvlarni ko'radi — «Mening arizalarim»"],
  ["none", "Faqat men", "Ilovada ko'rinmaydi, faqat shu yerda"],
];

const PRESETS: { name: string; key: string; read: DataCollection["read"]; create: boolean; fields: Partial<DataField>[] }[] = [
  {
    name: "Mahsulotlar",
    key: "products",
    read: "public",
    create: false,
    fields: [
      { key: "title", label: "Nomi", type: "text", required: true },
      { key: "price", label: "Narx", type: "money" },
      { key: "photo", label: "Rasm", type: "image" },
      { key: "description", label: "Tavsif", type: "longtext" },
      { key: "category", label: "Turkum", type: "select", options: ["Asosiy", "Yangi"] },
    ],
  },
  {
    name: "Xizmatlar",
    key: "services",
    read: "public",
    create: false,
    fields: [
      { key: "title", label: "Xizmat", type: "text", required: true },
      { key: "price", label: "Narx", type: "money" },
      { key: "duration", label: "Davomiyligi", type: "text" },
      { key: "photo", label: "Rasm", type: "image" },
    ],
  },
  {
    name: "Arizalar",
    key: "leads",
    read: "own",
    create: true,
    fields: [
      { key: "name", label: "Ism", type: "text", required: true },
      { key: "phone", label: "Telefon", type: "phone", required: true, private: true },
      { key: "comment", label: "Izoh", type: "longtext" },
    ],
  },
  {
    name: "Jamoa",
    key: "team",
    read: "public",
    create: false,
    fields: [
      { key: "name", label: "Ism", type: "text", required: true },
      { key: "role", label: "Lavozim", type: "text" },
      { key: "photo", label: "Rasm", type: "image" },
    ],
  },
];

const LAT: Record<string, string> = { "o'": "o", "g'": "g", sh: "sh", ch: "ch", ʻ: "", "'": "", "’": "" };
export function slug(text: string, fallback = "field"): string {
  let s = text.toLowerCase();
  for (const [k, v] of Object.entries(LAT)) s = s.split(k).join(v);
  s = s
    .normalize("NFKD")
    .replace(/[^a-z0-9]+/g, "_")
    .replace(/^_+|_+$/g, "")
    .slice(0, 32);
  if (!s || !/^[a-z]/.test(s)) s = `${fallback}_${s}`.replace(/_+$/, "").slice(0, 32);
  return s;
}

const fullField = (f: Partial<DataField>): DataField => ({
  key: f.key ?? "field",
  label: f.label ?? "Maydon",
  type: f.type ?? "text",
  required: !!f.required,
  private: !!f.private,
  options: f.options ?? [],
});

// ============================================================
// To'plamlar paneli
// ============================================================

export function CollectionsPanel({ selected, onSelect, toast }: { selected: number | null; onSelect: (id: number | null) => void; toast: Toast }) {
  const { collections, botId, refetch } = useCollections();
  const [editing, setEditing] = useState<DataCollection | "new" | null>(null);
  return (
    <div className="stack">
      <p className="hint">
        To'plam — o'z jadvalingiz: mahsulotlar, xizmatlar, arizalar… Sahifalarda «Ma'lumotlar ro'yxati» bloki yoki erkin bo'limning takrorlovchi
        konteyneri bilan ko'rsatiladi.
      </p>
      {collections.length > 0 && (
        <section className="card card--list">
          {collections.map((c) => (
            <button key={c.id} className={`list-item ${selected === c.id ? "is-current" : ""}`} onClick={() => onSelect(c.id)}>
              <span className="de-coll-icon">
                <Database size={17} />
              </span>
              <span className="list-item__body">
                <span className="list-item__title">{c.name}</span>
                <span className="list-item__sub">
                  <code>{c.key}</code> · {c.count} yozuv · {READ_MODES.find((m) => m[0] === c.read)?.[1]}
                </span>
              </span>
            </button>
          ))}
        </section>
      )}
      <button className="btn btn--primary btn--compact" onClick={() => setEditing("new")}>
        <Plus size={16} /> Yangi to'plam
      </button>
      {editing && (
        <CollectionSheet
          botId={botId}
          collection={editing === "new" ? null : editing}
          toast={toast}
          onClose={() => setEditing(null)}
          onSaved={(c) => {
            setEditing(null);
            refetch();
            onSelect(c.id);
          }}
        />
      )}
    </div>
  );
}

function CollectionSheet({
  botId,
  collection,
  toast,
  onClose,
  onSaved,
}: {
  botId: number;
  collection: DataCollection | null;
  toast: Toast;
  onClose: () => void;
  onSaved: (c: DataCollection) => void;
}) {
  const [name, setName] = useState(collection?.name ?? "");
  const [key, setKey] = useState(collection?.key ?? "");
  const [keyTouched, setKeyTouched] = useState(!!collection);
  const [read, setRead] = useState<DataCollection["read"]>(collection?.read ?? "public");
  const [create, setCreate] = useState(collection?.create ?? false);
  const [fields, setFields] = useState<DataField[]>(collection?.fields ?? [fullField({ key: "title", label: "Nomi", required: true })]);
  const [open, setOpen] = useState<number | null>(null);
  const [busy, setBusy] = useState(false);

  const applyPreset = (p: (typeof PRESETS)[number]) => {
    setName(p.name);
    setKey(p.key);
    setRead(p.read);
    setCreate(p.create);
    setFields(p.fields.map(fullField));
  };

  const setField = (i: number, patch: Partial<DataField>) =>
    setFields((fs) =>
      fs.map((f, j) => {
        if (j !== i) return f;
        const next = { ...f, ...patch };
        // Yangi maydonda kalit nomdan avtomatik
        if (patch.label !== undefined && !collection?.fields.some((cf) => cf.key === f.key)) next.key = slug(patch.label);
        return next;
      }),
    );

  const save = async () => {
    setBusy(true);
    try {
      const body = { key: key || slug(name, "data"), name, read, create, fields };
      const res = collection ? await api.updateCollection(botId, collection.id, body) : await api.createCollection(botId, body);
      haptic("success");
      toast(collection ? "To'plam saqlandi" : "To'plam yaratildi");
      clearDataCache();
      onSaved(res);
    } catch (e) {
      toast((e as Error).message, "err");
    } finally {
      setBusy(false);
    }
  };

  return (
    <Sheet title={collection ? "To'plam tuzilmasi" : "Yangi to'plam"} icon={<Database size={20} />} onClose={onClose}>
      <div className="stack">
        {!collection && (
          <div className="chips">
            <span className="hint">Tayyor:</span>
            {PRESETS.map((p) => (
              <button key={p.key} className="chip-btn" onClick={() => applyPreset(p)}>
                {p.name}
              </button>
            ))}
          </div>
        )}
        <label className="sf-field">
          <span className="sf-label">Nomi</span>
          <input
            className="input"
            maxLength={64}
            value={name}
            onChange={(e) => {
              setName(e.target.value);
              if (!keyTouched) setKey(slug(e.target.value, "data"));
            }}
          />
        </label>
        <label className="sf-field">
          <span className="sf-label">
            Kalit (lotincha){collection && <span className="sf-hint">ilova bog'langani uchun o'zgarmaydi</span>}
          </span>
          <input className="input input--code" maxLength={32} disabled={!!collection} value={key} onChange={(e) => (setKey(e.target.value), setKeyTouched(true))} />
        </label>
        <div className="sf-field">
          <span className="sf-label">Kim ko'radi</span>
          {READ_MODES.map(([v, t, d]) => (
            <button key={v} type="button" className={`mode ${read === v ? "is-selected" : ""}`} onClick={() => setRead(v)}>
              <span className="mode__body">
                <b>{t}</b>
                <span className="hint">{d}</span>
              </span>
              <span className={`mode__check ${read === v ? "is-on" : ""}`} />
            </button>
          ))}
        </div>
        <button type="button" className="sf-toggle" onClick={() => setCreate(!create)}>
          <span>
            Foydalanuvchilar yozuv qo'sha oladi
            <span className="sf-hint">Ilovadagi forma «to'plamga saqlash» orqali</span>
          </span>
          <span className={`switch ${create ? "is-on" : ""}`}>
            <i />
          </span>
        </button>

        <span className="sf-label">Maydonlar · {fields.length}/40</span>
        <div className="sf-list">
          {fields.map((f, i) => (
            <div key={i} className={`sf-list__item ${open === i ? "is-open" : ""}`}>
              <div className="sf-list__head">
                <button type="button" className="sf-list__title" onClick={() => setOpen(open === i ? null : i)}>
                  <span>
                    {f.required ? "* " : ""}
                    {f.label} <code>{f.key}</code> · {FIELD_TYPES.find((t) => t[0] === f.type)?.[1]}
                    {f.private ? " · 🔒" : ""}
                  </span>
                </button>
                <button type="button" className="icon-btn" onClick={() => setFields(fields.filter((_, j) => j !== i))} aria-label="O'chirish">
                  <Trash2 size={15} color="var(--danger)" />
                </button>
              </div>
              {open === i && (
                <div className="sf-list__body sf">
                  <label className="sf-field">
                    <span className="sf-label">Nomi</span>
                    <input className="input" maxLength={64} value={f.label} onChange={(e) => setField(i, { label: e.target.value })} />
                  </label>
                  <label className="sf-field">
                    <span className="sf-label">Kalit — {"{{"}
                      {f.key}
                      {"}}"} ko'rinishida ishlatiladi</span>
                    <input className="input input--code" maxLength={32} value={f.key} onChange={(e) => setField(i, { key: e.target.value })} />
                  </label>
                  <label className="sf-field">
                    <span className="sf-label">Turi</span>
                    <select className="input" value={f.type} onChange={(e) => setField(i, { type: e.target.value as DataFieldType })}>
                      {FIELD_TYPES.map(([v, l]) => (
                        <option key={v} value={v}>
                          {l}
                        </option>
                      ))}
                    </select>
                  </label>
                  {f.type === "select" && (
                    <label className="sf-field">
                      <span className="sf-label">Variantlar (har biri yangi qatorda)</span>
                      <textarea className="input" rows={3} value={f.options.join("\n")} onChange={(e) => setField(i, { options: e.target.value.split("\n") })} />
                    </label>
                  )}
                  <button type="button" className="sf-toggle" onClick={() => setField(i, { required: !f.required })}>
                    <span>Majburiy</span>
                    <span className={`switch ${f.required ? "is-on" : ""}`}>
                      <i />
                    </span>
                  </button>
                  <button type="button" className="sf-toggle" onClick={() => setField(i, { private: !f.private })}>
                    <span>
                      Yashirin
                      <span className="sf-hint">Ilovada boshqalarga ko'rinmaydi (masalan telefon)</span>
                    </span>
                    <span className={`switch ${f.private ? "is-on" : ""}`}>
                      <i />
                    </span>
                  </button>
                </div>
              )}
            </div>
          ))}
        </div>
        {fields.length < 40 && (
          <button
            type="button"
            className="btn btn--ghost btn--compact"
            onClick={() => {
              setFields([...fields, fullField({ key: `field_${fields.length + 1}`, label: "Yangi maydon" })]);
              setOpen(fields.length);
            }}
          >
            <Plus size={16} /> Maydon qo'shish
          </button>
        )}
        <button className="btn btn--primary" disabled={busy || !name.trim() || !fields.length} onClick={save}>
          {busy ? "Saqlanmoqda…" : "Saqlash"}
        </button>
      </div>
    </Sheet>
  );
}

// ============================================================
// Yozuvlar
// ============================================================

export function RecordsPanel({ collectionId, onBack, toast, wide }: { collectionId: number; onBack?: () => void; toast: Toast; wide: boolean }) {
  const { collections, botId, refetch: refetchCollections } = useCollections();
  const qc = useQueryClient();
  const c = collections.find((x) => x.id === collectionId);
  const [q, setQ] = useState("");
  const [limit, setLimit] = useState(50);
  const [editing, setEditing] = useState<DataRecord | "new" | null>(null);
  const [structure, setStructure] = useState(false);
  const [checked, setChecked] = useState<number[]>([]);
  const fileRef = useRef<HTMLInputElement>(null);
  const { data, refetch } = useQuery({
    queryKey: ["records", botId, collectionId, q, limit],
    queryFn: () => api.records(botId, collectionId, { q, limit }),
    enabled: !!c,
  });
  useEffect(() => setChecked([]), [collectionId]);
  if (!c) return <div className="spinner spinner--center" />;

  const reload = () => {
    clearDataCache();
    refetch();
    refetchCollections();
    qc.invalidateQueries({ queryKey: ["records", botId, collectionId] });
  };
  const cols = c.fields.filter((f) => f.type !== "longtext").slice(0, wide ? 6 : 2);
  const titleField = c.fields.find((f) => f.type === "text") ?? c.fields[0];

  const removeChecked = async () => {
    if (!(await confirmDialog(`${checked.length} ta yozuv o'chirilsinmi?`))) return;
    await api.deleteRecords(botId, c.id, checked);
    setChecked([]);
    toast("O'chirildi");
    reload();
  };

  return (
    <div className="stack de-records">
      <div className="de-records__head">
        {onBack && (
          <button className="icon-btn icon-btn--round" onClick={onBack} aria-label="Orqaga">
            <ChevronLeft size={18} />
          </button>
        )}
        <div className="de-records__title">
          <b>{c.name}</b>
          <span className="hint">
            <code>{c.key}</code> · {data?.total ?? c.count} yozuv
          </span>
        </div>
        <button className="icon-btn icon-btn--soft" onClick={() => setStructure(true)} title="Tuzilma" aria-label="Tuzilma">
          <Settings2 size={18} />
        </button>
      </div>
      <div className="row de-records__tools">
        <label className="de-search">
          <Search size={16} />
          <input className="input" placeholder="Qidirish…" value={q} onChange={(e) => setQ(e.target.value)} />
        </label>
        <button className="btn btn--primary btn--compact btn--inline" onClick={() => setEditing("new")}>
          <Plus size={16} /> Yozuv
        </button>
      </div>
      <div className="row de-records__tools">
        <a className="btn btn--ghost btn--compact btn--inline" href={api.exportCsvUrl(botId, c.id)} download>
          <Download size={15} /> CSV
        </a>
        <button className="btn btn--ghost btn--compact btn--inline" onClick={() => fileRef.current?.click()}>
          <Upload size={15} /> Import
        </button>
        {checked.length > 0 && (
          <button className="btn btn--danger btn--compact btn--inline" onClick={removeChecked}>
            <Trash2 size={15} /> {checked.length} tasini o'chirish
          </button>
        )}
        <input
          ref={fileRef}
          type="file"
          accept=".csv,text/csv"
          hidden
          onChange={async (e) => {
            const file = e.target.files?.[0];
            e.target.value = "";
            if (!file) return;
            try {
              const res = await api.importCsv(botId, c.id, await file.text());
              toast(`${res.imported} ta yozuv qo'shildi`);
              reload();
            } catch (err) {
              toast((err as Error).message, "err");
            }
          }}
        />
      </div>

      {!data ? (
        <div className="spinner spinner--center" />
      ) : data.items.length === 0 ? (
        <p className="hint center">{q ? "Hech narsa topilmadi." : "Hali yozuv yo'q — «+ Yozuv» bilan qo'shing yoki CSV import qiling."}</p>
      ) : wide ? (
        <div className="de-table-wrap">
          <table className="de-table">
            <thead>
              <tr>
                <th className="de-table__check">
                  <input
                    type="checkbox"
                    checked={checked.length === data.items.length}
                    onChange={(e) => setChecked(e.target.checked ? data.items.map((r) => r.id) : [])}
                  />
                </th>
                {cols.map((f) => (
                  <th key={f.key}>{f.label}</th>
                ))}
                <th />
              </tr>
            </thead>
            <tbody>
              {data.items.map((r) => (
                <tr key={r.id} onClick={() => setEditing(r)}>
                  <td className="de-table__check" onClick={(e) => e.stopPropagation()}>
                    <input
                      type="checkbox"
                      checked={checked.includes(r.id)}
                      onChange={(e) => setChecked(e.target.checked ? [...checked, r.id] : checked.filter((x) => x !== r.id))}
                    />
                  </td>
                  {cols.map((f) => (
                    <td key={f.key}>
                      <Cell field={f} value={r[f.key]} />
                    </td>
                  ))}
                  <td className="de-table__edit">
                    <Pencil size={14} />
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : (
        <section className="card card--list">
          {data.items.map((r) => (
            <button key={r.id} className="list-item" onClick={() => setEditing(r)}>
              {c.fields.some((f) => f.type === "image") && (
                <span className="de-thumb">
                  <Cell field={c.fields.find((f) => f.type === "image")!} value={r[c.fields.find((f) => f.type === "image")!.key]} />
                </span>
              )}
              <span className="list-item__body">
                <span className="list-item__title">{String(r[titleField.key] ?? `#${r.id}`)}</span>
                <span className="list-item__sub">
                  {cols
                    .filter((f) => f.key !== titleField.key && f.type !== "image")
                    .map((f) => <Cell key={f.key} field={f} value={r[f.key]} />)}
                </span>
              </span>
            </button>
          ))}
        </section>
      )}
      {data && data.total > data.items.length && (
        <button className="btn btn--ghost btn--compact" onClick={() => setLimit(limit + 50)}>
          Yana ko'rsatish ({data.total - data.items.length})
        </button>
      )}

      {editing && (
        <RecordSheet
          collection={c}
          record={editing === "new" ? null : editing}
          toast={toast}
          onClose={() => setEditing(null)}
          onSaved={() => {
            setEditing(null);
            reload();
          }}
        />
      )}
      {structure && (
        <CollectionSheet
          botId={botId}
          collection={c}
          toast={toast}
          onClose={() => setStructure(false)}
          onSaved={() => {
            setStructure(false);
            reload();
          }}
        />
      )}
    </div>
  );
}

function Cell({ field, value }: { field: DataField; value: unknown }) {
  if (value === undefined || value === null || value === "") return <span className="hint">—</span>;
  if (field.type === "image") return <img className="de-cell-img" src={mediaUrl(Number(value))} alt="" />;
  if (field.type === "bool") return <span>{value ? "✅" : "—"}</span>;
  if (field.type === "money" || field.type === "number") return <span>{Number(value).toLocaleString("ru-RU").replace(/,/g, " ")}</span>;
  return <span className="de-cell-text">{String(value)}</span>;
}

function RecordSheet({
  collection,
  record,
  toast,
  onClose,
  onSaved,
}: {
  collection: DataCollection;
  record: DataRecord | null;
  toast: Toast;
  onClose: () => void;
  onSaved: () => void;
}) {
  const { botId } = useCollections();
  const [values, setValues] = useState<Record<string, unknown>>(() => {
    const v: Record<string, unknown> = {};
    for (const f of collection.fields) v[f.key] = record?.[f.key] ?? (f.type === "bool" ? false : "");
    return v;
  });
  const [busy, setBusy] = useState(false);
  const set = (k: string, v: unknown) => setValues((s) => ({ ...s, [k]: v }));

  const save = async () => {
    setBusy(true);
    try {
      if (record) await api.updateRecord(botId, collection.id, record.id, values);
      else await api.createRecord(botId, collection.id, values);
      haptic("success");
      toast("Saqlandi");
      onSaved();
    } catch (e) {
      toast((e as Error).message, "err");
    } finally {
      setBusy(false);
    }
  };

  return (
    <Sheet title={record ? `${collection.name} · #${record.id}` : `Yangi yozuv · ${collection.name}`} icon={<Database size={20} />} onClose={onClose}>
      <div className="stack sf">
        {collection.fields.map((f) => {
          const label = `${f.label}${f.required ? " *" : ""}${f.private ? " 🔒" : ""}`;
          const v = values[f.key];
          if (f.type === "image")
            return <MediaField key={f.key} label={label} value={(v as number) || null} set={(id) => set(f.key, id)} optional ctx={{ pages: [], toast }} />;
          if (f.type === "bool")
            return (
              <button key={f.key} type="button" className="sf-toggle" onClick={() => set(f.key, !v)}>
                <span>{label}</span>
                <span className={`switch ${v ? "is-on" : ""}`}>
                  <i />
                </span>
              </button>
            );
          return (
            <label key={f.key} className="sf-field">
              <span className="sf-label">{label}</span>
              {f.type === "longtext" ? (
                <textarea className="input" rows={4} maxLength={5000} value={String(v ?? "")} onChange={(e) => set(f.key, e.target.value)} />
              ) : f.type === "select" ? (
                <select className="input" value={String(v ?? "")} onChange={(e) => set(f.key, e.target.value)}>
                  <option value="">—</option>
                  {f.options.map((o) => (
                    <option key={o} value={o}>
                      {o}
                    </option>
                  ))}
                </select>
              ) : (
                <input
                  className="input"
                  type={f.type === "date" ? "date" : f.type === "email" ? "email" : "text"}
                  inputMode={f.type === "number" || f.type === "money" ? "decimal" : f.type === "phone" ? "tel" : f.type === "url" ? "url" : undefined}
                  value={String(v ?? "")}
                  onChange={(e) => set(f.key, e.target.value)}
                />
              )}
            </label>
          );
        })}
        {record?._by ? <p className="hint">Foydalanuvchi qo'shgan · Telegram ID {record._by}</p> : null}
        <button className="btn btn--primary" disabled={busy} onClick={save}>
          {busy ? "Saqlanmoqda…" : "Saqlash"}
        </button>
        {record && (
          <button
            className="btn btn--danger btn--compact"
            onClick={async () => {
              if (!(await confirmDialog("Yozuv o'chirilsinmi?"))) return;
              await api.deleteRecords(botId, collection.id, [record.id]);
              toast("O'chirildi");
              onSaved();
            }}
          >
            <Trash2 size={16} /> O'chirish
          </button>
        )}
      </div>
    </Sheet>
  );
}

// ============================================================
// Bog'lash sozlamalari (bloklar, takrorlovchi, rasm, forma)
// ============================================================

export function CollectionSelect({ value, onChange, label = "To'plam" }: { value: string | null | undefined; onChange: (key: string) => void; label?: string }) {
  const { collections } = useCollections();
  return (
    <label className="sf-field">
      <span className="sf-label">{label}</span>
      <select className="input" value={value ?? ""} onChange={(e) => onChange(e.target.value)}>
        <option value="">— to'plamni tanlang —</option>
        {collections.map((c) => (
          <option key={c.key} value={c.key}>
            {c.name} ({c.count})
          </option>
        ))}
      </select>
      {collections.length === 0 && <span className="sf-hint">Avval «Ma'lumot» bo'limida to'plam yarating.</span>}
    </label>
  );
}

function FieldSelect({
  collection,
  value,
  onChange,
  label,
  types,
}: {
  collection: string | null | undefined;
  value: string | null | undefined;
  onChange: (key: string | null) => void;
  label: string;
  types?: DataFieldType[];
}) {
  const { collections } = useCollections();
  const fields = (collections.find((c) => c.key === collection)?.fields ?? []).filter((f) => !types || types.includes(f.type));
  return (
    <label className="sf-field">
      <span className="sf-label">{label}</span>
      <select className="input" value={value ?? ""} onChange={(e) => onChange(e.target.value || null)}>
        <option value="">—</option>
        {fields.map((f) => (
          <option key={f.key} value={f.key}>
            {f.label}
          </option>
        ))}
      </select>
    </label>
  );
}

export function FieldChips({ collection, onPick }: { collection: string | null | undefined; onPick?: (token: string) => void }) {
  const { collections } = useCollections();
  const c = collections.find((x) => x.key === collection);
  if (!c) return null;
  return (
    <div className="chips">
      <span className="hint">Maydonlar:</span>
      {c.fields
        .filter((f) => f.type !== "image")
        .map((f) => (
          <button
            key={f.key}
            type="button"
            className="chip-btn"
            title="Nusxa olish"
            onClick={() => {
              const t = `{{${f.key}}}`;
              if (onPick) onPick(t);
              else void navigator.clipboard?.writeText(t);
            }}
          >
            {`{{${f.key}}}`} <span className="hint">{f.label}</span>
          </button>
        ))}
    </div>
  );
}

export const emptyQuery = (collection = ""): WAQuery => ({
  collection,
  limit: 20,
  sort_field: null,
  sort_dir: "desc",
  filter_field: null,
  filter_value: null,
  search: false,
  empty_text: "Hozircha hech narsa yo'q",
});

export function QueryEditor({ query, onChange, allowSearch = true }: { query: WAQuery; onChange: (q: WAQuery) => void; allowSearch?: boolean }) {
  const set = (patch: Partial<WAQuery>) => onChange({ ...query, ...patch });
  return (
    <div className="sf">
      <CollectionSelect value={query.collection} onChange={(collection) => set({ collection, sort_field: null, filter_field: null })} />
      <SliderField label="Nechta yozuv" value={query.limit} set={(v) => set({ limit: v ?? 20 })} min={1} max={100} />
      <div className="row">
        <FieldSelect collection={query.collection} value={query.sort_field} onChange={(sort_field) => set({ sort_field })} label="Saralash" />
        <label className="sf-field">
          <span className="sf-label">Tartib</span>
          <select className="input" value={query.sort_dir} onChange={(e) => set({ sort_dir: e.target.value as "asc" | "desc" })}>
            <option value="desc">{query.sort_field ? "Kamayish" : "Yangilari"}</option>
            <option value="asc">{query.sort_field ? "O'sish" : "Eskilari"}</option>
          </select>
        </label>
      </div>
      <div className="row">
        <FieldSelect collection={query.collection} value={query.filter_field} onChange={(filter_field) => set({ filter_field })} label="Filtr maydoni" />
        <label className="sf-field">
          <span className="sf-label">qiymati</span>
          <input className="input" maxLength={200} value={query.filter_value ?? ""} onChange={(e) => set({ filter_value: e.target.value || null })} />
        </label>
      </div>
      {allowSearch && (
        <button type="button" className="sf-toggle" onClick={() => set({ search: !query.search })}>
          <span>Qidiruv maydoni</span>
          <span className={`switch ${query.search ? "is-on" : ""}`}>
            <i />
          </span>
        </button>
      )}
      <label className="sf-field">
        <span className="sf-label">Bo'sh bo'lsa</span>
        <input className="input" maxLength={200} value={query.empty_text} onChange={(e) => set({ empty_text: e.target.value })} />
      </label>
    </div>
  );
}

type CollectionBlockT = Extract<import("../webapp/types").WABlock, { type: "collection" }>;

export function CollectionBlockEditor({
  block,
  onChange,
  pages,
  onCreateDetail,
}: {
  block: CollectionBlockT;
  onChange: (b: CollectionBlockT) => void;
  pages: WAPage[];
  onCreateDetail: (collection: string) => string;
}) {
  const set = (patch: Partial<CollectionBlockT>) => onChange({ ...block, ...patch });
  const key = block.query.collection;
  const { collections } = useCollections();
  const coll = collections.find((c) => c.key === key);
  // Yangi to'plam tanlanganda maydonlarni avtomatik moslaymiz
  const autoMap = (collection: string) => {
    const c = collections.find((x) => x.key === collection);
    const pick = (types: DataFieldType[]) => c?.fields.find((f) => types.includes(f.type))?.key ?? null;
    const text = c?.fields.filter((f) => f.type === "text" || f.type === "longtext") ?? [];
    return {
      title_field: text[0]?.key ?? null,
      subtitle_field: text[1]?.key ?? null,
      image_field: pick(["image"]),
      price_field: pick(["money", "number"]),
      badge_field: pick(["select"]),
    };
  };
  return (
    <div className="sf">
      <label className="sf-field">
        <span className="sf-label">Sarlavha (ixtiyoriy)</span>
        <input className="input" maxLength={80} value={block.title} onChange={(e) => set({ title: e.target.value })} />
      </label>
      <QueryEditor
        query={block.query}
        onChange={(query) => (query.collection !== key ? set({ query, ...autoMap(query.collection) }) : set({ query }))}
      />
      <div className="sf-field">
        <span className="sf-label">Ko'rinish</span>
        <div className="segmented segmented--small">
          {(
            [
              ["cards", "Kartalar"],
              ["list", "Ro'yxat"],
              ["grid", "To'r"],
            ] as const
          ).map(([v, l]) => (
            <button key={v} type="button" className={block.layout === v ? "is-selected" : ""} onClick={() => set({ layout: v })}>
              {l}
            </button>
          ))}
        </div>
      </div>
      {block.layout !== "list" && <SliderField label="Ustunlar (keng oynada)" value={block.columns} set={(v) => set({ columns: v ?? 2 })} min={1} max={4} />}
      {coll && (
        <>
          <FieldSelect collection={key} value={block.title_field} onChange={(title_field) => set({ title_field })} label="Sarlavha maydoni" />
          <FieldSelect collection={key} value={block.subtitle_field} onChange={(subtitle_field) => set({ subtitle_field })} label="Izoh maydoni" />
          <FieldSelect collection={key} value={block.image_field} onChange={(image_field) => set({ image_field })} label="Rasm maydoni" types={["image"]} />
          <FieldSelect collection={key} value={block.price_field} onChange={(price_field) => set({ price_field })} label="Narx maydoni" types={["money", "number", "text"]} />
          <FieldSelect collection={key} value={block.badge_field} onChange={(badge_field) => set({ badge_field })} label="Belgi maydoni" />
        </>
      )}
      <label className="sf-field">
        <span className="sf-label">Bosilganda ochiladigan batafsil sahifa</span>
        <select className="input" value={block.detail_page ?? ""} onChange={(e) => set({ detail_page: e.target.value || null })}>
          <option value="">— ochilmaydi —</option>
          {pages
            .filter((p) => p.collection === key)
            .map((p) => (
              <option key={p.id} value={p.id}>
                {p.emoji} {p.title}
              </option>
            ))}
        </select>
      </label>
      {key && !pages.some((p) => p.collection === key) && (
        <button type="button" className="btn btn--ghost btn--compact" onClick={() => set({ detail_page: onCreateDetail(key) })}>
          <Plus size={16} /> Batafsil sahifa yaratish
        </button>
      )}
    </div>
  );
}

/** Formadan to'plam yaratish: maydonlar formadagi savollardan olinadi. */
export async function collectionFromForm(botId: number, form: FormBlock): Promise<DataCollection> {
  const map: Record<string, DataFieldType> = {
    text: "text",
    textarea: "longtext",
    phone: "phone",
    email: "email",
    number: "number",
    select: "select",
    radio: "select",
    checkbox: "bool",
    date: "date",
  };
  const base = slug(form.title || "arizalar", "form");
  return api.createCollection(botId, {
    key: `${base}_${Math.random().toString(36).slice(2, 5)}`.slice(0, 32),
    name: form.title || "Arizalar",
    read: "own",
    create: true,
    fields: form.fields.map((f) => ({
      key: f.id,
      label: f.label,
      type: map[f.type] ?? "text",
      required: f.required,
      private: f.type === "phone" || f.type === "email",
      options: f.options,
    })),
  });
}

export function ImageBindField({ collection, value, onChange }: { collection: string | null; value: string | null | undefined; onChange: (v: string | null) => void }) {
  return (
    <div className="sf">
      <FieldSelect collection={collection} value={value} onChange={onChange} label="Rasm yozuvdan (maydon)" types={["image"]} />
      {value && <span className="sf-hint">Har bir yozuvning o'z rasmi ko'rsatiladi; yuqoridagi yuklangan rasm ishlatilmaydi.</span>}
    </div>
  );
}
