// Erkin bo'lim (elementlar daraxti) va universal uslub dvigateli.
// Uslub inline emas, generatsiya qilingan <style> orqali beriladi — shunda keng oyna uchun alohida qiymatlar
// (@container) va hover ishlaydi. Qiymatlar har doim tozalanadi (rang — faqat #RRGGBB, son — chegaralangan).
import { ChevronDown, Star } from "lucide-react";
import { useContext, useEffect, useRef, useState, type MouseEvent, type ReactNode, type Ref, type RefObject } from "react";
import { fillTemplate, RecordContext, useRecords, type DataLoader, type Rec } from "./data";
import { WA_ICONS } from "./icons";
import { youtubeId, type Anim, type BoxNode, type ProgressNode, type RatingNode, type TimerNode, type WAAction, type WANode, type WAStyle } from "./types";

export const GOOGLE_FONTS: Record<string, string> = {
  inter: "Inter",
  manrope: "Manrope",
  montserrat: "Montserrat",
  rubik: "Rubik",
  nunito: "Nunito",
  poppins: "Poppins",
  raleway: "Raleway",
  playfair: "Playfair Display",
  lora: "Lora",
  oswald: "Oswald",
  comfortaa: "Comfortaa",
  jetbrains: "JetBrains Mono",
};

const BASE_STACKS: Record<string, string> = {
  system: '-apple-system, BlinkMacSystemFont, "SF Pro Text", "Segoe UI", Roboto, sans-serif',
  rounded: 'ui-rounded, "SF Pro Rounded", "Nunito", -apple-system, "Segoe UI", sans-serif',
  serif: 'ui-serif, "New York", Georgia, "Times New Roman", serif',
  mono: 'ui-monospace, "SF Mono", Menlo, Consolas, monospace',
};

export function fontStack(key: string | null | undefined): string {
  if (!key) return BASE_STACKS.system;
  if (BASE_STACKS[key]) return BASE_STACKS[key];
  const family = GOOGLE_FONTS[key];
  if (!family) return BASE_STACKS.system;
  const fallback = /mono/i.test(key) ? BASE_STACKS.mono : ["playfair", "lora"].includes(key) ? BASE_STACKS.serif : BASE_STACKS.system;
  return `"${family}", ${fallback}`;
}

/** Ishlatilgan Google shriftlarini bir marta yuklaydi. */
export function useGoogleFonts(keys: string[]) {
  const sig = [...new Set(keys.filter((k) => GOOGLE_FONTS[k]))].sort().join(",");
  useEffect(() => {
    for (const key of sig ? sig.split(",") : []) {
      const id = `wa-font-${key}`;
      if (document.getElementById(id)) continue;
      const link = document.createElement("link");
      link.id = id;
      link.rel = "stylesheet";
      link.href = `https://fonts.googleapis.com/css2?family=${encodeURIComponent(GOOGLE_FONTS[key])}:wght@300;400;500;600;700;800&display=swap`;
      document.head.appendChild(link);
    }
  }, [sig]);
}

export function collectFonts(value: unknown, out: string[] = []): string[] {
  if (Array.isArray(value)) value.forEach((v) => collectFonts(v, out));
  else if (value && typeof value === "object") {
    for (const [k, v] of Object.entries(value)) {
      if (k === "font" && typeof v === "string") out.push(v);
      else collectFonts(v, out);
    }
  }
  return out;
}

// --- Uslub → CSS ---

const isHex = (v: unknown): v is string => typeof v === "string" && /^#[0-9a-fA-F]{6}$/.test(v);
export const COLOR_TOKENS: Record<string, string> = {
  $primary: "var(--wa-primary)",
  $on_primary: "var(--wa-on-primary)",
  $bg: "var(--wa-bg)",
  $surface: "var(--wa-surface)",
  $text: "var(--wa-text)",
  $hint: "var(--wa-hint)",
  $line: "var(--wa-line)",
};
/** #RRGGBB yoki mavzu rangi ($primary...) → CSS qiymati */
export function cssColor(v: unknown): string | null {
  if (isHex(v)) return v;
  if (typeof v === "string" && COLOR_TOKENS[v]) return COLOR_TOKENS[v];
  return null;
}
const num = (v: unknown, min: number, max: number): number | null =>
  typeof v === "number" && Number.isFinite(v) ? Math.min(max, Math.max(min, v)) : null;
const mix = (c: string, p: number) => `color-mix(in srgb, ${c} ${p}%, transparent)`;
function shadow(kind: string, c: string | null): string | null {
  const k = c ?? "#000000";
  switch (kind) {
    case "none":
      return "none";
    case "s":
      return `0 1px 2px ${mix(k, 6)}, 0 2px 8px -2px ${mix(k, 9)}`;
    case "m":
      return `0 4px 12px -2px ${mix(k, 11)}, 0 12px 28px -12px ${mix(k, 20)}`;
    case "l":
      return `0 18px 50px -18px ${mix(k, 38)}`;
    case "xl":
      return `0 30px 80px -24px ${mix(k, 50)}, 0 8px 20px -10px ${mix(k, 20)}`;
    case "glow":
      return c ? `0 0 0 1px ${mix(c, 40)}, 0 10px 40px -8px ${c}` : "0 0 0 1px color-mix(in srgb, var(--wa-primary) 40%, transparent), 0 10px 40px -10px var(--wa-primary)";
    case "inner":
      return `inset 0 2px 10px ${mix(k, 16)}`;
    case "hard":
      return `5px 5px 0 ${c ?? "#111111"}`;
    default:
      return null;
  }
}
const ASPECT: Record<string, string> = { "1:1": "1/1", "4:3": "4/3", "3:2": "3/2", "16:9": "16/9", "21:9": "21/9", "3:4": "3/4", "2:3": "2/3", "9:16": "9/16" };
const SELF: Record<string, string> = { start: "flex-start", center: "center", end: "flex-end", stretch: "stretch" };

export function cssDecl(st: WAStyle | null | undefined, mediaSrc: (id: number) => string): string {
  if (!st) return "";
  const d: string[] = [];
  const px = num(st.px, 0, 160);
  const py = num(st.py, 0, 200);
  if (px !== null) d.push(`padding-left:${px}px;padding-right:${px}px`);
  if (py !== null) d.push(`padding-top:${py}px;padding-bottom:${py}px`);
  const mt = num(st.mt, -80, 200);
  const mb = num(st.mb, -80, 200);
  if (mt !== null) d.push(`margin-top:${mt}px`);
  if (mb !== null) d.push(`margin-bottom:${mb}px`);
  if (st.width === "full") d.push("width:100%;align-self:stretch");
  else if (st.width === "fit") d.push("width:fit-content;align-self:auto");
  const w = num(st.w, 0, 1600);
  if (w !== null) d.push(`width:${w}px;max-width:100%;flex-shrink:0`);
  const wp = num(st.w_pct, 1, 100);
  if (wp !== null) d.push(`width:${wp}%`);
  const mw = num(st.max_width, 0, 1600);
  if (mw) d.push(`max-width:${mw}px;margin-left:auto;margin-right:auto;width:100%`);
  const mh = num(st.min_height, 0, 1200);
  if (mh) d.push(`min-height:${mh}px`);
  const h = num(st.h, 0, 1600);
  if (h !== null) d.push(`height:${h}px`);
  if (st.aspect && ASPECT[st.aspect]) d.push(`aspect-ratio:${ASPECT[st.aspect]}`);
  if (st.grow) d.push("flex:1 1 0");
  if (st.self_align && SELF[st.self_align]) d.push(`align-self:${SELF[st.self_align]}`);
  const gap = num(st.gap, 0, 120);
  if (gap !== null) d.push(`gap:${gap}px`);
  const span = num(st.span, 1, 8);
  if (span !== null) d.push(`grid-column:span ${span}`);
  const rspan = num(st.row_span, 1, 8);
  if (rspan !== null) d.push(`grid-row:span ${rspan}`);
  // Joylashuv
  if (st.pos === "relative" || st.pos === "absolute" || st.pos === "sticky" || st.pos === "fixed") d.push(`position:${st.pos}`);
  for (const side of ["top", "right", "bottom", "left"] as const) {
    const v = num(st[side], -800, 2000);
    if (v !== null) d.push(`${side}:${v}px`);
  }
  const z = num(st.z, -10, 100);
  if (z !== null) d.push(`z-index:${z}`);
  // Transform: alohida xususiyatlar — animatsiyalar (transform) bilan qo'shiladi
  const rot = num(st.rotate, -360, 360);
  if (rot) d.push(`rotate:${rot}deg`);
  const sc = num(st.scale, 10, 400);
  if (sc !== null && sc !== 100) d.push(`scale:${sc / 100}`);
  const tx = num(st.tx, -800, 800) ?? 0;
  const ty = num(st.ty, -800, 800) ?? 0;
  if (tx || ty) d.push(`translate:${tx}px ${ty}px`);
  const sk = num(st.skew, -45, 45);
  if (sk) d.push(`transform:skewX(${sk}deg)`);
  // Fon: rasm (+ qoraytirish) → gradient → rang
  const layers: string[] = [];
  const overlay = num(st.overlay, 0, 90) ?? 0;
  const alpha = num(st.bg_alpha, 0, 100);
  const b1 = cssColor(st.bg);
  const b2 = cssColor(st.bg2);
  const c1 = b1 ? (alpha !== null && alpha < 100 ? mix(b1, alpha) : b1) : null;
  const c2 = b2 ? (alpha !== null && alpha < 100 ? mix(b2, alpha) : b2) : null;
  const angle = num(st.bg_angle, 0, 360) ?? 160;
  if (typeof st.bg_image === "number" && st.bg_image > 0) {
    if (overlay) layers.push(`linear-gradient(rgba(0,0,0,${overlay / 100}),rgba(0,0,0,${overlay / 100}))`);
    const size = st.bg_size === "contain" ? "center/contain no-repeat" : st.bg_size === "tile" ? "0 0/auto repeat" : "center/cover no-repeat";
    layers.push(`url("${mediaSrc(st.bg_image)}") ${size}`);
  }
  if (c1 && c2) {
    if (st.bg_type === "radial") layers.push(`radial-gradient(circle at 30% 20%, ${c1}, ${c2})`);
    else if (st.bg_type === "conic") layers.push(`conic-gradient(from ${angle}deg, ${c1}, ${c2}, ${c1})`);
    else layers.push(`linear-gradient(${angle}deg, ${c1}, ${c2})`);
  } else if (c1) layers.push(c1);
  if (layers.length) d.push(`background:${layers.join(",")}`);
  // Ichidagi xira matnlar (izoh) ham shu rangga moslashadi
  const col = cssColor(st.color);
  if (col && st.color === "$text") d.push(`color:${col}`);
  else if (col) d.push(`color:${col};--wa-text:${col};--wa-hint:color-mix(in srgb, ${col} 72%, transparent)`);
  const tg1 = cssColor(st.text_grad);
  if (tg1) {
    const t2 = cssColor(st.text_grad2) ?? tg1;
    d.push(`background-image:linear-gradient(${angle}deg, ${tg1}, ${t2});-webkit-background-clip:text;background-clip:text;-webkit-text-fill-color:transparent;color:transparent`);
  }
  const bw = num(st.border, 0, 12);
  const bs = st.border_style && ["solid", "dashed", "dotted", "double"].includes(st.border_style) ? st.border_style : "solid";
  if (bw !== null) d.push(`border:${bw}px ${bs} ${cssColor(st.border_color) ?? "var(--wa-line)"}`);
  const r = num(st.radius, 0, 999);
  if (r !== null) d.push(`border-radius:${r}px;overflow:hidden`);
  if (st.overflow === "hidden" || st.overflow === "visible") d.push(`overflow:${st.overflow}`);
  else if (st.overflow === "scroll") d.push("overflow:auto");
  if (st.shadow) {
    const sh = shadow(st.shadow, cssColor(st.shadow_color));
    if (sh) d.push(`box-shadow:${sh}`);
  }
  const op = num(st.opacity, 5, 100);
  if (op !== null) d.push(`opacity:${op / 100}`);
  const filters: string[] = [];
  const blur = num(st.blur, 0, 60);
  if (blur) filters.push(`blur(${blur}px)`);
  const bright = num(st.bright, 0, 200);
  if (bright !== null && bright !== 100) filters.push(`brightness(${bright / 100})`);
  const gray = num(st.gray, 0, 100);
  if (gray) filters.push(`grayscale(${gray / 100})`);
  if (filters.length) d.push(`filter:${filters.join(" ")}`);
  const bd = num(st.backdrop, 0, 60);
  if (bd) d.push(`backdrop-filter:blur(${bd}px) saturate(1.6);-webkit-backdrop-filter:blur(${bd}px) saturate(1.6)`);
  // Matn
  if (st.font) d.push(`font-family:${fontStack(st.font)}`);
  const size = num(st.size, 8, 120);
  if (size !== null) d.push(`font-size:${size}px`);
  const fw = num(st.weight, 100, 900);
  if (fw !== null) d.push(`font-weight:${Math.round(fw / 100) * 100}`);
  if (st.align === "left" || st.align === "center" || st.align === "right") d.push(`text-align:${st.align}`);
  const lh = num(st.line, 0.8, 3);
  if (lh !== null) d.push(`line-height:${lh}`);
  const ls = num(st.letter, -10, 40);
  if (ls !== null) d.push(`letter-spacing:${ls / 100}em`);
  if (st.uppercase) d.push("text-transform:uppercase");
  if (st.italic) d.push("font-style:italic");
  if (st.decoration === "underline" || st.decoration === "line-through") d.push(`text-decoration:${st.decoration};text-underline-offset:3px`);
  const clamp = num(st.clamp, 1, 12);
  if (clamp !== null) d.push(`display:-webkit-box;-webkit-line-clamp:${clamp};-webkit-box-orient:vertical;overflow:hidden`);
  if (st.nowrap) d.push("white-space:nowrap;overflow:hidden;text-overflow:ellipsis");
  // Foydalanuvchi tanlagan uslub har doim standart uslubdan ustun turadi (masalan tugma rangi)
  return d
    .join(";")
    .split(";")
    .filter(Boolean)
    .map((x) => `${x} !important`)
    .join(";");
}

const safeId = (s: string) => s.replace(/[^A-Za-z0-9_-]/g, "");

export function cssRule(
  selector: string,
  base: WAStyle | null | undefined,
  wide: WAStyle | null | undefined,
  mediaSrc: (id: number) => string,
  hover?: WAStyle | null,
): string {
  let css = "";
  const b = cssDecl(base, mediaSrc);
  if (b) css += `${selector}{${b}}`;
  const w = cssDecl(wide, mediaSrc);
  if (w) css += `@container (min-width:560px){${selector}{${w}}}`;
  const h = cssDecl(hover, mediaSrc);
  if (h) css += `@media (hover:hover){${selector}:hover{${h}}}${selector}:active{${h}}`;
  return css;
}

const JUSTIFY: Record<string, string> = { start: "flex-start", center: "center", end: "flex-end", between: "space-between", around: "space-around" };
const ALIGN: Record<string, string> = { start: "flex-start", center: "center", end: "flex-end", stretch: "stretch" };

function boxCss(sel: string, n: BoxNode): string {
  const justify = JUSTIFY[n.justify] ?? "flex-start";
  const align = ALIGN[n.align] ?? "stretch";
  const gap = num(n.gap, 0, 96) ?? 12;
  const items = `${sel}>*:not(.wa-rep--single),${sel}>.wa-rep--single>*`;
  switch (n.layout) {
    case "grid": {
      const cols = num(n.columns, 1, 6) ?? 2;
      let css = `${sel}{display:grid;grid-template-columns:repeat(${cols},minmax(0,1fr));gap:${gap}px;align-items:${align}}`;
      const cw = num(n.columns_wide, 1, 8);
      if (cw) css += `@container (min-width:560px){${sel}{grid-template-columns:repeat(${cw},minmax(0,1fr))}}`;
      return css;
    }
    case "scroll": {
      const iw = num(n.item_w, 40, 1200);
      return (
        `${sel}{display:flex;flex-direction:row;flex-wrap:nowrap;gap:${gap}px;overflow-x:auto;scroll-snap-type:x mandatory;scrollbar-width:none;align-items:${align};-webkit-overflow-scrolling:touch;overscroll-behavior-x:contain}` +
        `${sel}::-webkit-scrollbar{display:none}` +
        `${items}{flex:0 0 ${iw ? `${iw}px` : "82%"};max-width:${iw ? "92%" : "82%"};scroll-snap-align:start}`
      );
    }
    case "stack": {
      const ji = { start: "start", center: "center", end: "end", between: "stretch", around: "stretch" }[n.justify] ?? "stretch";
      const ai = { start: "start", center: "center", end: "end", stretch: "stretch" }[n.align] ?? "stretch";
      // Qatlamlar: konteyner-qatlamlar butun maydonni egallaydi; matn/tugma kabilar — tekislash bo'yicha joylashadi
      return `${sel}{display:grid;grid-template-columns:minmax(0,1fr);grid-template-rows:minmax(0,1fr);align-items:${ji};justify-items:${ai}}${items}{grid-area:1/1}${sel}>.wa-n--box{align-self:stretch;justify-self:stretch}`;
    }
    case "marquee":
      return `${sel}{display:block;overflow:hidden}${sel}>.wa-mq{display:flex;width:max-content;animation:wa-mq var(--wa-mq,20s) linear infinite}${sel}>.wa-mq>div{display:flex;gap:${gap}px;padding-right:${gap}px;align-items:center}`;
    case "tabs":
    case "accordion":
      return `${sel}{display:flex;flex-direction:column;gap:${gap}px}`;
    default:
      return `${sel}{display:flex;flex-direction:${n.layout === "row" ? "row" : "column"};flex-wrap:${n.wrap ? "wrap" : "nowrap"};gap:${gap}px;justify-content:${justify};align-items:${align}}`;
  }
}

/** Butun daraxt uchun CSS (bitta <style>). */
export function treeCss(blockId: string, root: BoxNode, mediaSrc: (id: number) => string): string {
  let css = "";
  const walk = (n: WANode) => {
    const sel = `[data-n="${safeId(blockId)}-${safeId(n.id)}"]`;
    if (n.kind === "box") css += boxCss(sel, n);
    css += cssRule(sel, n.style, n.wide, mediaSrc, n.hover);
    const delay = num(n.delay, 0, 5000);
    if (delay) css += `${sel}.wa-anim{transition-delay:${delay}ms}${sel}.wa-loop{animation-delay:${delay}ms}`;
    if (n.kind === "box") n.children.forEach(walk);
  };
  walk(root);
  return css;
}

// --- Paydo bo'lish animatsiyasi ---

export function useAppear<T extends HTMLElement>(anim: Anim | undefined) {
  const ref = useRef<T>(null);
  useEffect(() => {
    const el = ref.current;
    if (!el || !anim || anim === "none") return;
    if (typeof IntersectionObserver === "undefined" || window.matchMedia("(prefers-reduced-motion: reduce)").matches) {
      el.classList.add("is-in");
      return;
    }
    el.classList.remove("is-in");
    const io = new IntersectionObserver(
      (entries) => {
        for (const e of entries)
          if (e.isIntersecting) {
            el.classList.add("is-in");
            io.disconnect();
          }
      },
      { threshold: 0.12 },
    );
    io.observe(el);
    return () => io.disconnect();
  }, [anim]);
  return ref;
}

// --- Elementlarni chizish ---

export function useNow(ms: number): number {
  const [now, setNow] = useState(Date.now());
  useEffect(() => {
    const t = setInterval(() => setNow(Date.now()), ms);
    return () => clearInterval(t);
  }, [ms]);
  return now;
}

export type NodeCtx = {
  blockId: string;
  mediaSrc: (id: number) => string;
  /** To'plam yozuvidagi rasmlar (ommaviy manzil boshqacha) */
  recordMedia: (id: number) => string;
  loadData?: DataLoader;
  runAction: (a: WAAction | null | undefined, rec?: Rec | null) => void;
  /** Konstruktor: bosilganda element tanlanadi (amal bajarilmaydi) */
  selectMode?: boolean;
  /** Kutubxona ko'rinishi: bo'sh rasm/video joylari ko'rsatilsin */
  placeholders?: boolean;
  selected?: string | null;
  onSelect?: (nodeId: string) => void;
  Rich: (p: { text: string }) => JSX.Element;
};

function RepeatChildren({ node, ctx }: { node: BoxNode; ctx: NodeCtx }) {
  const { items, loading, error } = useRecords(ctx.loadData, node.repeat);
  if (loading && !items.length) return <span className="wa-n-empty">Yuklanmoqda…</span>;
  if (error) return <span className="wa-n-empty">{error}</span>;
  if (!items.length) return <span className="wa-n-empty">{node.repeat?.empty_text || "Hozircha hech narsa yo'q"}</span>;
  const single = node.children.length === 1;
  return (
    <>
      {items.map((rec) => (
        <RecordContext.Provider key={rec.id} value={rec}>
          <div className={single ? "wa-rep wa-rep--single" : "wa-rep"}>
            {node.children.map((c) => (
              <NodeView key={c.id} node={c} ctx={ctx} />
            ))}
          </div>
        </RecordContext.Provider>
      ))}
    </>
  );
}

function contains(node: WANode, id: string | null | undefined): boolean {
  if (!id) return false;
  if (node.id === id) return true;
  return node.kind === "box" && node.children.some((c) => contains(c, id));
}

const panelTitle = (n: WANode, i: number) => n.name?.trim() || `Bo'lim ${i + 1}`;

function TabsView({ node, ctx }: { node: BoxNode; ctx: NodeCtx }) {
  const panels = node.children.filter((c) => !c.hidden);
  const [active, setActive] = useState(0);
  // Konstruktorda ichidagi element tanlansa — o'sha yorliq ochiladi
  useEffect(() => {
    const i = panels.findIndex((p) => contains(p, ctx.selected));
    if (i >= 0) setActive(i);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [ctx.selected]);
  const cur = Math.min(active, Math.max(0, panels.length - 1));
  if (!panels.length) return ctx.selectMode ? <span className="wa-n-empty">Yorliqlar bo'sh — ichiga konteyner qo'shing</span> : null;
  return (
    <>
      <div className={`wa-tabs wa-tabs--${node.tabs_style ?? "pills"}`} role="tablist">
        {panels.map((p, i) => (
          <button
            key={p.id}
            type="button"
            role="tab"
            aria-selected={i === cur}
            className={i === cur ? "is-on" : ""}
            onClick={(e) => {
              e.stopPropagation();
              setActive(i);
            }}
          >
            {panelTitle(p, i)}
          </button>
        ))}
      </div>
      <NodeView key={panels[cur].id} node={panels[cur]} ctx={ctx} />
    </>
  );
}

function AccordionView({ node, ctx }: { node: BoxNode; ctx: NodeCtx }) {
  const panels = node.children.filter((c) => !c.hidden);
  const [open, setOpen] = useState<Set<string>>(() => new Set(node.open_first !== false && panels[0] ? [panels[0].id] : []));
  useEffect(() => {
    const p = panels.find((x) => contains(x, ctx.selected));
    if (p) setOpen((s) => (s.has(p.id) ? s : new Set([...s, p.id])));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [ctx.selected]);
  if (!panels.length) return ctx.selectMode ? <span className="wa-n-empty">Akkordeon bo'sh — ichiga konteyner qo'shing</span> : null;
  return (
    <>
      {panels.map((p, i) => {
        const on = open.has(p.id);
        return (
          <div key={p.id} className={`wa-acc ${on ? "is-open" : ""}`}>
            <button
              type="button"
              className="wa-acc__head"
              aria-expanded={on}
              onClick={(e) => {
                e.stopPropagation();
                setOpen((s) => {
                  const next = new Set(s);
                  if (next.has(p.id)) next.delete(p.id);
                  else next.add(p.id);
                  return next;
                });
              }}
            >
              <span>{panelTitle(p, i)}</span>
              <ChevronDown size={18} />
            </button>
            {on && (
              <div className="wa-acc__body">
                <NodeView node={p} ctx={ctx} />
              </div>
            )}
          </div>
        );
      })}
    </>
  );
}

/** Karusel: avtomatik aylanish va nuqtalar */
function useCarousel(node: BoxNode, ref: RefObject<HTMLElement>, count: number, selectMode?: boolean) {
  const [index, setIndex] = useState(0);
  useEffect(() => {
    const el = ref.current;
    if (!el || node.layout !== "scroll") return;
    const onScroll = () => {
      const first = el.firstElementChild as HTMLElement | null;
      const step = first ? first.getBoundingClientRect().width + (node.gap ?? 12) : el.clientWidth;
      setIndex(Math.round(el.scrollLeft / Math.max(1, step)));
    };
    el.addEventListener("scroll", onScroll, { passive: true });
    return () => el.removeEventListener("scroll", onScroll);
  }, [ref, node.layout, node.gap]);
  useEffect(() => {
    const el = ref.current;
    const sec = node.autoplay ?? 0;
    if (!el || node.layout !== "scroll" || !sec || selectMode || count < 2) return;
    let paused = false;
    const pause = () => (paused = true);
    const resume = () => (paused = false);
    el.addEventListener("pointerdown", pause);
    el.addEventListener("pointerup", resume);
    const t = setInterval(() => {
      if (paused || document.hidden) return;
      const atEnd = el.scrollLeft + el.clientWidth >= el.scrollWidth - 4;
      const first = el.firstElementChild as HTMLElement | null;
      const step = first ? first.getBoundingClientRect().width + (node.gap ?? 12) : el.clientWidth;
      el.scrollTo({ left: atEnd ? 0 : el.scrollLeft + step, behavior: "smooth" });
    }, sec * 1000);
    return () => {
      clearInterval(t);
      el.removeEventListener("pointerdown", pause);
      el.removeEventListener("pointerup", resume);
    };
  }, [ref, node.layout, node.autoplay, node.gap, selectMode, count]);
  const go = (i: number) => {
    const el = ref.current;
    const target = el?.children[i] as HTMLElement | undefined;
    if (el && target) el.scrollTo({ left: target.offsetLeft - el.offsetLeft, behavior: "smooth" });
  };
  return { index, go };
}

function VideoView({ url }: { url: string }) {
  const id = youtubeId(url);
  if (!id) return <span className="wa-n-placeholder">▶ YouTube havolasini kiriting</span>;
  return (
    <iframe
      src={`https://www.youtube-nocookie.com/embed/${id}`}
      title="video"
      allow="accelerometer; encrypted-media; gyroscope; picture-in-picture; fullscreen"
      allowFullScreen
      loading="lazy"
    />
  );
}

function ProgressView({ node }: { node: ProgressNode }) {
  const v = Math.max(0, Math.min(100, node.value));
  const color = cssColor(node.bar) ?? "var(--wa-primary)";
  if (node.shape === "ring") {
    const r = 42;
    const c = 2 * Math.PI * r;
    const sw = Math.min(20, node.thickness);
    return (
      <>
        <svg viewBox="0 0 100 100" className="wa-ring">
          <circle cx="50" cy="50" r={r} fill="none" stroke="color-mix(in srgb, currentColor 12%, transparent)" strokeWidth={sw} />
          <circle
            cx="50"
            cy="50"
            r={r}
            fill="none"
            stroke={color}
            strokeWidth={sw}
            strokeLinecap="round"
            strokeDasharray={`${(c * v) / 100} ${c}`}
            transform="rotate(-90 50 50)"
          />
          {node.show_value && (
            <text x="50" y="50" textAnchor="middle" dominantBaseline="central" className="wa-ring__val">
              {v}%
            </text>
          )}
        </svg>
        {node.label && <span className="wa-progress__label">{node.label}</span>}
      </>
    );
  }
  return (
    <>
      {(node.label || node.show_value) && (
        <span className="wa-progress__top">
          <span>{node.label}</span>
          {node.show_value && <b>{v}%</b>}
        </span>
      )}
      <span className="wa-progress__track" style={{ height: node.thickness }}>
        <span style={{ width: `${v}%`, background: color }} />
      </span>
    </>
  );
}

function RatingView({ node }: { node: RatingNode }) {
  const v = Math.max(0, Math.min(5, node.value));
  const color = cssColor(node.star) ?? "#f5b301";
  return (
    <>
      <span className="wa-stars" aria-label={`${v} / 5`}>
        {[0, 1, 2, 3, 4].map((i) => {
          const fill = Math.max(0, Math.min(1, v - i));
          return (
            <span key={i} className="wa-star" style={{ width: node.size, height: node.size }}>
              <Star size={node.size} color="color-mix(in srgb, currentColor 22%, transparent)" fill="color-mix(in srgb, currentColor 14%, transparent)" />
              <span style={{ width: `${fill * 100}%` }}>
                <Star size={node.size} color={color} fill={color} />
              </span>
            </span>
          );
        })}
      </span>
      {node.show_value && <b className="wa-stars__val">{v.toFixed(1)}</b>}
    </>
  );
}

function TimerView({ node }: { node: TimerNode }) {
  const now = useNow(1000);
  const target = new Date(node.until).getTime();
  if (Number.isNaN(target)) return null;
  const left = Math.max(0, target - now);
  if (!left) return <span className="wa-timer__done">{node.done_text}</span>;
  const parts = [
    [Math.floor(left / 86400000), "kun"],
    [Math.floor(left / 3600000) % 24, "soat"],
    [Math.floor(left / 60000) % 60, "daqiqa"],
    [Math.floor(left / 1000) % 60, "soniya"],
  ] as const;
  return (
    <>
      {parts.map(([n, l]) => (
        <span key={l} className="wa-timer__cell">
          <b>{String(n).padStart(2, "0")}</b>
          {node.labels && <small>{l}</small>}
        </span>
      ))}
    </>
  );
}

export function NodeView({ node, ctx }: { node: WANode; ctx: NodeCtx }): JSX.Element | null {
  const ref = useAppear<HTMLElement>(node.anim);
  const rec = useContext(RecordContext);
  const isScroll = node.kind === "box" && node.layout === "scroll" && !!(node.dots || node.autoplay);
  const carousel = useCarousel(
    node.kind === "box" ? node : ({ layout: "column" } as BoxNode),
    ref as RefObject<HTMLElement>,
    node.kind === "box" ? node.children.length : 0,
    ctx.selectMode,
  );
  if (node.hidden) return null;
  const action = "action" in node ? node.action : null;
  const clickable = !!action && action.type !== "none";
  const common = {
    "data-n": `${safeId(ctx.blockId)}-${safeId(node.id)}`,
    className: [
      "wa-n",
      `wa-n--${node.kind}`,
      node.kind === "box" ? `wa-box--${node.layout}` : "",
      node.anim && node.anim !== "none" ? `wa-anim wa-anim--${node.anim}` : "",
      node.loop && node.loop !== "none" ? `wa-loop wa-loop--${node.loop}` : "",
      node.hover ? "has-hover" : "",
      clickable ? "is-clickable" : "",
      ctx.selectMode ? "is-editable" : "",
      ctx.selected === node.id ? "is-sel" : "",
    ]
      .filter(Boolean)
      .join(" "),
    onClick: (e: MouseEvent) => {
      if (ctx.selectMode) {
        e.preventDefault();
        e.stopPropagation();
        ctx.onSelect?.(node.id);
        return;
      }
      if (clickable && node.kind !== "button") {
        e.stopPropagation();
        ctx.runAction(action, rec);
      }
    },
    ref: ref as Ref<never>,
  };

  switch (node.kind) {
    case "box": {
      let inner: ReactNode;
      if (node.repeat) inner = <RepeatChildren node={node} ctx={ctx} />;
      else if (node.layout === "tabs") inner = <TabsView node={node} ctx={ctx} />;
      else if (node.layout === "accordion") inner = <AccordionView node={node} ctx={ctx} />;
      else inner = node.children.map((c) => <NodeView key={c.id} node={c} ctx={ctx} />);
      if (node.layout === "marquee" && !node.repeat) {
        inner = (
          <div className="wa-mq" style={{ ["--wa-mq" as string]: `${node.speed ?? 20}s` }}>
            <div>{inner}</div>
            <div aria-hidden>{node.children.map((c) => <NodeView key={c.id} node={c} ctx={{ ...ctx, selectMode: false }} />)}</div>
          </div>
        );
      }
      const box = (
        <div {...common}>
          {inner}
          {ctx.selectMode && node.children.length === 0 && <span className="wa-n-empty">Bo'sh konteyner</span>}
        </div>
      );
      if (!isScroll || !node.dots || node.children.length < 2) return box;
      return (
        <>
          {box}
          <div className="wa-dots">
            {node.children
              .filter((c) => !c.hidden)
              .map((c, i) => (
                <button key={c.id} type="button" aria-label={`${i + 1}`} className={i === carousel.index ? "is-on" : ""} onClick={() => carousel.go(i)} />
              ))}
          </div>
        </>
      );
    }
    case "text": {
      const Tag = node.tag === "small" ? "p" : node.tag;
      return (
        <Tag {...common} className={`${common.className} wa-t wa-t--${node.tag}`}>
          <ctx.Rich text={node.text} />
        </Tag>
      );
    }
    case "image": {
      const bound = node.bind && rec ? Number(rec[node.bind]) || null : null;
      const src = bound ? ctx.recordMedia(bound) : node.media_id ? ctx.mediaSrc(node.media_id) : null;
      if (!src)
        return ctx.selectMode || ctx.placeholders ? (
          <div {...common} className={`${common.className} wa-n-placeholder`}>
            🖼 {node.bind ? `Rasm: {{${node.bind}}}` : "Rasm tanlanmagan"}
          </div>
        ) : null;
      return (
        <img
          {...common}
          src={src}
          alt=""
          loading="lazy"
          style={{ objectFit: node.fit, aspectRatio: node.ratio === "auto" ? undefined : node.ratio.replace(":", " / ") }}
        />
      );
    }
    case "button": {
      const Icon = node.icon ? WA_ICONS[node.icon] : null;
      return (
        <button
          {...common}
          className={`${common.className} wa-btn wa-btn--${node.variant}`}
          onClick={(e) => {
            if (ctx.selectMode) common.onClick(e);
            else ctx.runAction(node.action, rec);
          }}
        >
          {fillTemplate(node.text, rec)}
          {Icon && <Icon size={17} />}
        </button>
      );
    }
    case "icon": {
      const Icon = WA_ICONS[node.icon];
      return (
        <span {...common} className={`${common.className} wa-icon`} style={{ fontSize: node.size }}>
          {node.emoji ? node.emoji : Icon ? <Icon size={node.size} strokeWidth={1.9} /> : null}
        </span>
      );
    }
    case "spacer":
      return <div {...common} style={{ height: node.size }} />;
    case "divider":
      return <hr {...common} className={`${common.className} wa-divider`} />;
    case "video":
      if (!youtubeId(node.url) && !ctx.selectMode && !ctx.placeholders) return null;
      return (
        <div {...common} className={`${common.className} wa-n-video ${ctx.selectMode ? "is-locked" : ""}`}>
          <VideoView url={node.url} />
        </div>
      );
    case "progress":
      return (
        <div {...common} className={`${common.className} wa-progress wa-progress--${node.shape}`}>
          <ProgressView node={node} />
        </div>
      );
    case "rating":
      return (
        <div {...common} className={`${common.className} wa-rating`}>
          <RatingView node={node} />
        </div>
      );
    case "timer":
      return (
        <div {...common} className={`${common.className} wa-timer`}>
          <TimerView node={node} />
        </div>
      );
    case "map":
      return (
        <div {...common} className={`${common.className} wa-n-map ${ctx.selectMode ? "is-locked" : ""}`} style={{ height: node.height }}>
          <iframe
            title="xarita"
            loading="lazy"
            referrerPolicy="no-referrer-when-downgrade"
            src={`https://maps.google.com/maps?q=${encodeURIComponent(fillTemplate(node.query, rec))}&z=${node.zoom}&output=embed`}
          />
        </div>
      );
    default:
      return null;
  }
}

export function CustomView({ blockId, root, ctx, extraCss }: { blockId: string; root: BoxNode; ctx: NodeCtx; extraCss?: string }): ReactNode {
  return (
    <>
      <style>{treeCss(blockId, root, ctx.mediaSrc) + (extraCss ?? "")}</style>
      <NodeView node={root} ctx={ctx} />
    </>
  );
}
