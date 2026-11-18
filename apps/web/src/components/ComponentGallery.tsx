// Komponentlar kutubxonasi: har bir komponent haqiqiy ko'rinishda (jonli kichik nusxa) ko'rsatiladi —
// foydalanuvchi qanday chiqishini ko'rib tanlaydi va kerakli joyga qo'yadi.
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Library, Search, Trash2 } from "lucide-react";
import { useEffect, useLayoutEffect, useMemo, useRef, useState } from "react";
import { api, type SavedComponent } from "../api";
import { CATEGORIES, cloneNode, searchLibrary, type LibraryItem } from "../webapp/library";
import { NodePreview } from "../webapp/Runtime";
import type { BoxNode, WATheme } from "../webapp/types";
import { confirmDialog } from "../tg";
import { Sheet } from "./Sheet";

const BASE_W = 390;

/** Komponentni kichraytirib ko'rsatadi; ekranga kirgandagina chiziladi (tezlik uchun). */
export function LivePreview({ root, theme, mediaSrc, height = 200 }: { root: BoxNode; theme: WATheme; mediaSrc: (id: number) => string; height?: number }) {
  const wrap = useRef<HTMLDivElement>(null);
  const inner = useRef<HTMLDivElement>(null);
  const [visible, setVisible] = useState(false);
  const [scale, setScale] = useState(0.6);
  const [tall, setTall] = useState(false);

  useEffect(() => {
    const el = wrap.current;
    if (!el) return;
    if (typeof IntersectionObserver === "undefined") return setVisible(true);
    const io = new IntersectionObserver((es) => es.some((e) => e.isIntersecting) && (setVisible(true), io.disconnect()), { rootMargin: "200px" });
    io.observe(el);
    return () => io.disconnect();
  }, []);

  useLayoutEffect(() => {
    const el = wrap.current;
    if (!el || !visible) return;
    const measure = () => {
      const s = Math.min(1, el.clientWidth / BASE_W);
      setScale(s);
      const h = inner.current?.scrollHeight ?? 0;
      setTall(h * s > height - 8);
    };
    measure();
    const ro = new ResizeObserver(measure);
    ro.observe(el);
    if (inner.current) ro.observe(inner.current);
    return () => ro.disconnect();
  }, [visible, height]);

  return (
    <div ref={wrap} className={`cg-preview ${tall ? "is-tall" : ""}`} style={{ height }}>
      {visible && (
        <div ref={inner} className="cg-preview__inner" style={{ width: BASE_W, transform: `scale(${scale})` }}>
          <NodePreview root={root} theme={theme} mediaSrc={mediaSrc} />
        </div>
      )}
    </div>
  );
}

function LibraryCard({ item, theme, mediaSrc, onPick }: { item: LibraryItem; theme: WATheme; mediaSrc: (id: number) => string; onPick: () => void }) {
  // Ko'rinish uchun bir marta yasaladi; qo'yishda esa yangi nusxa (yangi id) olinadi
  const root = useMemo(() => item.make(), [item]);
  return (
    <button type="button" className="cg-card" onClick={onPick}>
      <LivePreview root={root} theme={theme} mediaSrc={mediaSrc} />
      <span className="cg-card__meta">
        <b>{item.title}</b>
        <span className="hint">{item.desc}</span>
      </span>
    </button>
  );
}

export function ComponentGallery({
  theme,
  mediaSrc,
  target,
  onPick,
  onClose,
}: {
  theme: WATheme;
  mediaSrc: (id: number) => string;
  /** Qayerga qo'yilishi (foydalanuvchiga ko'rsatiladi) */
  target: string;
  onPick: (root: BoxNode, title: string) => void;
  onClose: () => void;
}) {
  const [q, setQ] = useState("");
  const [cat, setCat] = useState<string | null>(null);
  const qc = useQueryClient();
  const mine = useQuery({ queryKey: ["components"], queryFn: api.components, staleTime: 60_000 });
  const remove = useMutation({
    mutationFn: (id: number) => api.deleteComponent(id),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["components"] }),
  });
  const items = useMemo(() => (cat === "mine" ? [] : searchLibrary(q, cat)), [q, cat]);
  const saved = (mine.data?.items ?? []).filter((c) => !q.trim() || c.name.toLowerCase().includes(q.trim().toLowerCase()));
  const showMine = cat === "mine" || (cat === null && saved.length > 0);

  const pickSaved = (c: SavedComponent) => onPick(cloneNode(c.node), c.name);

  return (
    <Sheet title="Komponentlar kutubxonasi" icon={<Library size={20} />} onClose={onClose} wide>
      <div className="cg">
        <div className="cg-top">
          <label className="cg-search">
            <Search size={16} />
            <input className="input" placeholder="Qidirish: karta, banner, narx…" value={q} onChange={(e) => setQ(e.target.value)} autoFocus />
          </label>
          <span className="hint cg-target">{target}</span>
        </div>
        <div className="cg-cats">
          <button type="button" className={cat === null ? "is-on" : ""} onClick={() => setCat(null)}>
            Hammasi
          </button>
          <button type="button" className={cat === "mine" ? "is-on" : ""} onClick={() => setCat("mine")}>
            ⭐ Mening komponentlarim{mine.data?.items.length ? ` · ${mine.data.items.length}` : ""}
          </button>
          {CATEGORIES.map((c) => (
            <button key={c.key} type="button" className={cat === c.key ? "is-on" : ""} onClick={() => setCat(c.key)}>
              {c.icon} {c.title}
            </button>
          ))}
        </div>

        {showMine && (
          <section className="cg-section">
            <span className="label">Mening komponentlarim</span>
            {saved.length ? (
              <div className="cg-grid">
                {saved.map((c) => (
                  <div key={c.id} className="cg-card cg-card--mine">
                    <button type="button" className="cg-card__hit" onClick={() => pickSaved(c)} aria-label={c.name} />
                    <LivePreview root={c.node} theme={theme} mediaSrc={mediaSrc} />
                    <span className="cg-card__meta">
                      <b>{c.name}</b>
                      <button
                        type="button"
                        className="icon-btn icon-btn--soft cg-card__del"
                        aria-label="O'chirish"
                        onClick={async () => {
                          if (await confirmDialog(`«${c.name}» komponenti o'chirilsinmi?`)) remove.mutate(c.id);
                        }}
                      >
                        <Trash2 size={15} />
                      </button>
                    </span>
                  </div>
                ))}
              </div>
            ) : (
              <p className="hint cg-empty">
                Hali saqlangan komponent yo'q. Erkin bo'limdagi istalgan konteynerni tanlab, «⭐ Komponent sifatida saqlash» tugmasini bosing —
                keyin uni istalgan ilovada qayta ishlatasiz.
              </p>
            )}
          </section>
        )}

        {cat !== "mine" &&
          (cat
            ? [CATEGORIES.find((c) => c.key === cat)!]
            : CATEGORIES.filter((c) => items.some((i) => i.cat === c.key))
          ).map((c) => (
            <section key={c.key} className="cg-section">
              <span className="label">
                {c.icon} {c.title}
              </span>
              <div className="cg-grid">
                {items
                  .filter((i) => i.cat === c.key)
                  .map((item) => (
                    <LibraryCard key={item.key} item={item} theme={theme} mediaSrc={mediaSrc} onPick={() => onPick(item.make(), item.title)} />
                  ))}
              </div>
            </section>
          ))}
        {cat !== "mine" && !items.length && <p className="hint cg-empty">Hech narsa topilmadi — boshqa so'z bilan qidirib ko'ring.</p>}
      </div>
    </Sheet>
  );
}
