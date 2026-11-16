// Erkin bo'lim (elementlar daraxti) va universal uslub dvigateli.
// Uslub inline emas, generatsiya qilingan <style> orqali beriladi — shunda keng oyna uchun alohida qiymatlar
// (@container) va hover ishlaydi. Qiymatlar har doim tozalanadi (rang — faqat #RRGGBB, son — chegaralangan).
import { useEffect, useRef, type MouseEvent, type ReactNode, type Ref } from "react";
import { WA_ICONS } from "./icons";
import type { Anim, BoxNode, WAAction, WANode, WAStyle } from "./types";

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
const num = (v: unknown, min: number, max: number): number | null =>
  typeof v === "number" && Number.isFinite(v) ? Math.min(max, Math.max(min, v)) : null;
const SHADOWS: Record<string, string> = {
  none: "none",
  s: "0 1px 2px rgba(0,0,0,.06), 0 2px 8px -2px rgba(0,0,0,.08)",
  m: "0 4px 12px -2px rgba(0,0,0,.10), 0 12px 28px -12px rgba(0,0,0,.18)",
  l: "0 18px 50px -18px rgba(0,0,0,.35)",
  glow: "0 0 0 1px color-mix(in srgb, var(--wa-primary) 40%, transparent), 0 10px 40px -10px var(--wa-primary)",
};

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
  const mw = num(st.max_width, 0, 1600);
  if (mw) d.push(`max-width:${mw}px;margin-left:auto;margin-right:auto;width:100%`);
  const mh = num(st.min_height, 0, 1200);
  if (mh) d.push(`min-height:${mh}px`);
  // Fon: rasm (+ qoraytirish) → gradient → rang
  const layers: string[] = [];
  const overlay = num(st.overlay, 0, 90) ?? 0;
  if (typeof st.bg_image === "number" && st.bg_image > 0) {
    if (overlay) layers.push(`linear-gradient(rgba(0,0,0,${overlay / 100}),rgba(0,0,0,${overlay / 100}))`);
    layers.push(`url("${mediaSrc(st.bg_image)}") center/cover no-repeat`);
  }
  if (isHex(st.bg) && isHex(st.bg2)) layers.push(`linear-gradient(${num(st.bg_angle, 0, 360) ?? 160}deg, ${st.bg}, ${st.bg2})`);
  else if (isHex(st.bg)) layers.push(st.bg);
  if (layers.length) d.push(`background:${layers.join(",")}`);
  // Ichidagi xira matnlar (izoh) ham shu rangga moslashadi
  if (isHex(st.color)) d.push(`color:${st.color};--wa-text:${st.color};--wa-hint:color-mix(in srgb, ${st.color} 72%, transparent)`);
  const bw = num(st.border, 0, 12);
  if (bw !== null) d.push(`border:${bw}px solid ${isHex(st.border_color) ? st.border_color : "var(--wa-line)"}`);
  const r = num(st.radius, 0, 80);
  if (r !== null) d.push(`border-radius:${r}px;overflow:hidden`);
  if (st.shadow && SHADOWS[st.shadow]) d.push(`box-shadow:${SHADOWS[st.shadow]}`);
  const op = num(st.opacity, 5, 100);
  if (op !== null) d.push(`opacity:${op / 100}`);
  if (st.font) d.push(`font-family:${fontStack(st.font)}`);
  const size = num(st.size, 8, 120);
  if (size !== null) d.push(`font-size:${size}px`);
  const w = num(st.weight, 100, 900);
  if (w !== null) d.push(`font-weight:${Math.round(w / 100) * 100}`);
  if (st.align === "left" || st.align === "center" || st.align === "right") d.push(`text-align:${st.align}`);
  const lh = num(st.line, 0.8, 3);
  if (lh !== null) d.push(`line-height:${lh}`);
  const ls = num(st.letter, -10, 40);
  if (ls !== null) d.push(`letter-spacing:${ls / 100}em`);
  if (st.uppercase) d.push("text-transform:uppercase");
  // Foydalanuvchi tanlagan uslub har doim standart uslubdan ustun turadi (masalan tugma rangi)
  return d
    .join(";")
    .split(";")
    .filter(Boolean)
    .map((x) => `${x} !important`)
    .join(";");
}

const safeId = (s: string) => s.replace(/[^A-Za-z0-9_-]/g, "");

export function cssRule(selector: string, base: WAStyle | null | undefined, wide: WAStyle | null | undefined, mediaSrc: (id: number) => string): string {
  let css = "";
  const b = cssDecl(base, mediaSrc);
  if (b) css += `${selector}{${b}}`;
  const w = cssDecl(wide, mediaSrc);
  if (w) css += `@container (min-width:560px){${selector}{${w}}}`;
  return css;
}

function boxCss(sel: string, n: BoxNode): string {
  const justify = { start: "flex-start", center: "center", end: "flex-end", between: "space-between", around: "space-around" }[n.justify] ?? "flex-start";
  const align = { start: "flex-start", center: "center", end: "flex-end", stretch: "stretch" }[n.align] ?? "stretch";
  const gap = num(n.gap, 0, 96) ?? 12;
  if (n.layout === "grid") {
    const cols = num(n.columns, 1, 6) ?? 2;
    let css = `${sel}{display:grid;grid-template-columns:repeat(${cols},minmax(0,1fr));gap:${gap}px;align-items:${align === "stretch" ? "stretch" : align}}`;
    const cw = num(n.columns_wide, 1, 8);
    if (cw) css += `@container (min-width:560px){${sel}{grid-template-columns:repeat(${cw},minmax(0,1fr))}}`;
    return css;
  }
  return `${sel}{display:flex;flex-direction:${n.layout === "row" ? "row" : "column"};flex-wrap:${n.wrap ? "wrap" : "nowrap"};gap:${gap}px;justify-content:${justify};align-items:${align}}`;
}

/** Butun daraxt uchun CSS (bitta <style>). */
export function treeCss(blockId: string, root: BoxNode, mediaSrc: (id: number) => string): string {
  let css = "";
  const walk = (n: WANode) => {
    const sel = `[data-n="${safeId(blockId)}-${safeId(n.id)}"]`;
    if (n.kind === "box") css += boxCss(sel, n);
    css += cssRule(sel, n.style, n.wide, mediaSrc);
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

export type NodeCtx = {
  blockId: string;
  mediaSrc: (id: number) => string;
  runAction: (a: WAAction | null | undefined) => void;
  /** Konstruktor: bosilganda element tanlanadi (amal bajarilmaydi) */
  selectMode?: boolean;
  selected?: string | null;
  onSelect?: (nodeId: string) => void;
  Rich: (p: { text: string }) => JSX.Element;
};

export function NodeView({ node, ctx }: { node: WANode; ctx: NodeCtx }): JSX.Element | null {
  const ref = useAppear<HTMLElement>(node.anim);
  if (node.hidden) return null;
  const action = "action" in node ? node.action : null;
  const clickable = !!action && action.type !== "none";
  const common = {
    "data-n": `${safeId(ctx.blockId)}-${safeId(node.id)}`,
    className: [
      "wa-n",
      `wa-n--${node.kind}`,
      node.anim && node.anim !== "none" ? `wa-anim wa-anim--${node.anim}` : "",
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
        ctx.runAction(action);
      }
    },
    ref: ref as Ref<never>,
  };

  switch (node.kind) {
    case "box":
      return (
        <div {...common}>
          {node.children.map((c) => (
            <NodeView key={c.id} node={c} ctx={ctx} />
          ))}
          {ctx.selectMode && node.children.length === 0 && <span className="wa-n-empty">Bo'sh konteyner</span>}
        </div>
      );
    case "text": {
      const Tag = node.tag === "small" ? "p" : node.tag;
      return (
        <Tag {...common} className={`${common.className} wa-t wa-t--${node.tag}`}>
          <ctx.Rich text={node.text} />
        </Tag>
      );
    }
    case "image":
      if (!node.media_id)
        return ctx.selectMode ? (
          <div {...common} className={`${common.className} wa-n-placeholder`}>
            🖼 Rasm tanlanmagan
          </div>
        ) : null;
      return (
        <img
          {...common}
          src={ctx.mediaSrc(node.media_id)}
          alt=""
          loading="lazy"
          style={{ objectFit: node.fit, aspectRatio: node.ratio === "auto" ? undefined : node.ratio.replace(":", " / ") }}
        />
      );
    case "button": {
      const Icon = node.icon ? WA_ICONS[node.icon] : null;
      return (
        <button
          {...common}
          className={`${common.className} wa-btn wa-btn--${node.variant === "ghost" || node.variant === "link" ? node.variant : node.variant}`}
          onClick={(e) => {
            if (ctx.selectMode) common.onClick(e);
            else ctx.runAction(node.action);
          }}
        >
          {node.text}
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
