// Ilovadagi ma'lumotlar: to'plamdan yozuvlarni olish, {{maydon}} o'zgaruvchilari, «Ma'lumotlar ro'yxati» bloki.
import { Search } from "lucide-react";
import { createContext, useContext, useEffect, useState } from "react";
import type { WAQuery } from "./types";

export type Rec = { id: number; [key: string]: unknown };
export type DataParams = {
  limit?: number;
  sort?: string | null;
  dir?: "asc" | "desc";
  filter_field?: string | null;
  filter_value?: string | null;
  q?: string;
  record?: number;
};
export type DataLoader = (collection: string, params: DataParams) => Promise<Rec[]>;

/** Joriy yozuv (batafsil sahifa yoki takrorlovchi ichida) */
export const RecordContext = createContext<Rec | null>(null);
export const useRecord = () => useContext(RecordContext);

function show(value: unknown): string {
  if (value === null || value === undefined) return "";
  if (typeof value === "boolean") return value ? "Ha" : "Yo'q";
  if (typeof value === "number") return value.toLocaleString("ru-RU").replace(/,/g, " ");
  return String(value);
}

/** «{{title}} — {{price}} so'm» → yozuv qiymatlari bilan. Yozuv bo'lmasa o'zgarishsiz. */
export function fillTemplate(text: string, rec: Rec | null): string {
  if (!rec || !text.includes("{{")) return text;
  return text.replace(/\{\{\s*([a-z][a-z0-9_]*)\s*\}\}/g, (_, key: string) => show(key === "id" ? rec.id : rec[key]));
}

export function useFill() {
  const rec = useRecord();
  return (text: string) => fillTemplate(text, rec);
}

// Bir xil so'rov qayta-qayta yuborilmasin (konstruktorda har tahrirda qayta chiziladi)
const cache = new Map<string, { at: number; data: Promise<Rec[]> }>();

export function useRecords(load: DataLoader | undefined, query: WAQuery | null | undefined, q = "") {
  const [state, setState] = useState<{ items: Rec[]; loading: boolean; error: string | null }>({ items: [], loading: true, error: null });
  const sig = query
    ? JSON.stringify([query.collection, query.limit, query.sort_field, query.sort_dir, query.filter_field, query.filter_value, q])
    : "";
  useEffect(() => {
    if (!load || !query || !query.collection) {
      setState({ items: [], loading: false, error: null });
      return;
    }
    let alive = true;
    const hit = cache.get(sig);
    let promise: Promise<Rec[]>;
    if (hit && Date.now() - hit.at < 8000) promise = hit.data;
    else {
      promise = load(query.collection, {
        limit: query.limit,
        sort: query.sort_field,
        dir: query.sort_dir,
        filter_field: query.filter_field,
        filter_value: query.filter_value,
        q: q || undefined,
      });
      cache.set(sig, { at: Date.now(), data: promise });
      promise.catch(() => cache.delete(sig));
    }
    setState((s) => ({ ...s, loading: true, error: null }));
    promise
      .then((items) => alive && setState({ items, loading: false, error: null }))
      .catch((e: Error) => alive && setState({ items: [], loading: false, error: e.message }));
    return () => {
      alive = false;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [sig, load]);
  return state;
}

export function clearDataCache() {
  cache.clear();
}

export function SearchBox({ value, onChange }: { value: string; onChange: (v: string) => void }) {
  return (
    <label className="wa-search">
      <Search size={17} />
      <input className="wa-input" placeholder="Qidirish…" value={value} onChange={(e) => onChange(e.target.value)} />
    </label>
  );
}

export function useDebounced<T>(value: T, ms = 300): T {
  const [v, setV] = useState(value);
  useEffect(() => {
    const t = setTimeout(() => setV(value), ms);
    return () => clearTimeout(t);
  }, [value, ms]);
  return v;
}
