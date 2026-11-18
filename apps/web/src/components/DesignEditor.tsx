// Dizayn muharriri: uslub (fon, matn, masofa, chegara...) va erkin bo'limning elementlar daraxti.
import {
  ArrowDown,
  ArrowUp,
  ChevronDown,
  ChevronRight,
  ClipboardPaste,
  Copy,
  CopyPlus,
  Eye,
  EyeOff,
  GripVertical,
  Group as Group2,
  IndentDecrease,
  IndentIncrease,
  Library,
  Plus,
  Star,
  Trash2,
  X,
} from "lucide-react";
import { useState, type ReactNode } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { api } from "../api";
import { cloneNode } from "../webapp/library";
import { ComponentGallery } from "./ComponentGallery";
import { NO_ACTION, type FieldSpec } from "../webapp/specs";
import { uid, type Anim, type BoxLayout, type BoxNode, type CustomBlock, type Loop, type NodeKind, type WANode, type WAPage, type WAStyle, type WATheme } from "../webapp/types";
import { MediaField, SliderField, SpecForm } from "./SpecForm";
import { emptyQuery, FieldChips, ImageBindField, QueryEditor } from "./DataEditor";

type Ctx = { pages: WAPage[]; toast: (text: string, kind?: "ok" | "err") => void };

function clone<T>(v: T): T {
  return JSON.parse(JSON.stringify(v));
}

// ============================================================
// Uslub muharriri
// ============================================================

function Group({ title, open: initial = false, children }: { title: string; open?: boolean; children: ReactNode }) {
  const [open, setOpen] = useState(initial);
  return (
    <div className={`de-group ${open ? "is-open" : ""}`}>
      <button type="button" className="de-group__head" onClick={() => setOpen(!open)}>
        {open ? <ChevronDown size={16} /> : <ChevronRight size={16} />}
        {title}
      </button>
      {open && <div className="de-group__body">{children}</div>}
    </div>
  );
}

const TOKENS: [string, string][] = [
  ["$primary", "Asosiy"],
  ["$on_primary", "Asosiy ustida"],
  ["$surface", "Karta"],
  ["$bg", "Fon"],
  ["$text", "Matn"],
  ["$hint", "Xira"],
];
const TOKEN_LABEL = Object.fromEntries(TOKENS);

function ColorRow({ label, value, set, tokens = true }: { label: string; value: string | null | undefined; set: (v: string | null) => void; tokens?: boolean }) {
  const isToken = !!value && value.startsWith("$");
  const [open, setOpen] = useState(false);
  return (
    <div className="de-color-wrap">
      <div className="de-color">
        <span className="sf-label">{label}</span>
        <label className={`de-color__swatch ${isToken ? "is-token" : ""}`} style={{ background: !isToken ? value ?? "transparent" : undefined }}>
          <input type="color" value={value && !isToken ? value : "#ffffff"} onChange={(e) => set(e.target.value)} />
          {!value && <span>—</span>}
          {isToken && <span>◎</span>}
        </label>
        <input
          className="input de-color__hex"
          maxLength={11}
          value={isToken ? TOKEN_LABEL[value!] ?? value! : value ?? ""}
          placeholder="avto"
          onChange={(e) => {
            const v = e.target.value.trim();
            if (v === "") set(null);
            else if (/^#[0-9a-fA-F]{6}$/.test(v)) set(v);
          }}
        />
        {tokens && (
          <button type="button" className={`sf-reset de-color__tok ${open ? "is-on" : ""}`} onClick={() => setOpen(!open)} title="Mavzu ranglari">
            ◎
          </button>
        )}
        {value && (
          <button type="button" className="sf-reset" onClick={() => set(null)} aria-label="Tozalash">
            <X size={12} />
          </button>
        )}
      </div>
      {open && (
        <div className="de-tokens">
          {TOKENS.map(([t, l]) => (
            <button key={t} type="button" className={value === t ? "is-on" : ""} onClick={() => (set(t), setOpen(false))}>
              {l}
            </button>
          ))}
          <span className="hint">Mavzu rangi — mavzu yoki tun rejimi o'zgarsa, element ham moslashadi</span>
        </div>
      )}
    </div>
  );
}

function Seg<T extends string | number>({ label, value, options, set }: { label: string; value: T | null | undefined; options: [T | null, string][]; set: (v: T | null) => void }) {
  return (
    <div className="sf-field">
      <span className="sf-label">{label}</span>
      <div className="segmented segmented--small de-seg">
        {options.map(([v, l]) => (
          <button key={String(v)} type="button" className={(value ?? null) === v ? "is-selected" : ""} onClick={() => set(v)}>
            {l}
          </button>
        ))}
      </div>
    </div>
  );
}

function Toggle({ label, on, set, hint }: { label: string; on: boolean; set: (v: boolean) => void; hint?: string }) {
  return (
    <button type="button" className="sf-toggle" onClick={() => set(!on)}>
      <span>
        {label}
        {hint && <span className="sf-hint">{hint}</span>}
      </span>
      <span className={`switch ${on ? "is-on" : ""}`}>
        <i />
      </span>
    </button>
  );
}

/** Guruhda o'zgartirilgan qiymatlar soni — yopiq guruhda ham ko'rinib tursin */
function count(st: WAStyle, keys: (keyof WAStyle)[]): number {
  return keys.filter((k) => st[k] !== undefined && st[k] !== null && st[k] !== false).length;
}

export function StyleEditor({
  value,
  onChange,
  fonts,
  ctx,
  compact = false,
  hover = false,
}: {
  value: WAStyle | null | undefined;
  onChange: (next: WAStyle | null) => void;
  fonts: Record<string, string>;
  ctx: Ctx;
  compact?: boolean;
  /** Hover holati uchun — faqat mantiqiy xususiyatlar */
  hover?: boolean;
}) {
  const st: WAStyle = value ?? {};
  const set = <K extends keyof WAStyle>(key: K, v: WAStyle[K] | null) => {
    const next: WAStyle = { ...st, [key]: v };
    // Bo'sh qiymatlar saqlanmaydi — hujjat toza qoladi
    for (const k of Object.keys(next) as (keyof WAStyle)[]) if (next[k] === null || next[k] === undefined || next[k] === false) delete next[k];
    onChange(Object.keys(next).length ? next : null);
  };
  const gradient = !!st.bg2;
  const textGrad = !!st.text_grad;
  // Guruh sarlavhasida o'zgartirilgan qiymatlar soni
  const gt = (title: string, keys: (keyof WAStyle)[]) => {
    const n = count(st, keys);
    return n ? `${title} · ${n}` : title;
  };
  if (hover)
    return (
      <div className="de-style">
        <p className="hint">Sichqoncha ustiga kelganda (kompyuter) yoki bosilganda (telefon) shu qiymatlar silliq o'tish bilan qo'llanadi.</p>
        <ColorRow label="Fon" value={st.bg} set={(v) => set("bg", v)} />
        <ColorRow label="Matn rangi" value={st.color} set={(v) => set("color", v)} />
        <ColorRow label="Chegara rangi" value={st.border_color} set={(v) => set("border_color", v)} />
        <SliderField label="Kattalashish" value={st.scale ?? null} set={(v) => set("scale", v)} min={80} max={130} suffix="%" optional />
        <SliderField label="Yuqoriga ko'tarilish" value={st.ty ?? null} set={(v) => set("ty", v)} min={-20} max={20} suffix="px" optional />
        <SliderField label="Burish" value={st.rotate ?? null} set={(v) => set("rotate", v)} min={-20} max={20} suffix="°" optional />
        <Seg label="Soya" value={st.shadow ?? null} set={(v) => set("shadow", v)} options={[[null, "—"], ["s", "S"], ["m", "M"], ["l", "L"], ["xl", "XL"], ["glow", "Nur"]]} />
        <SliderField label="Shaffoflik" value={st.opacity ?? null} set={(v) => set("opacity", v)} min={10} max={100} suffix="%" optional />
        <SliderField label="Yorqinlik" value={st.bright ?? null} set={(v) => set("bright", v)} min={50} max={150} suffix="%" optional />
        {value && (
          <button type="button" className="btn btn--ghost btn--compact" onClick={() => onChange(null)}>
            Hover uslubini tozalash
          </button>
        )}
      </div>
    );

  return (
    <div className="de-style">
      <Group title={gt("Fon", ["bg", "bg2", "bg_image", "bg_alpha", "backdrop"])} open={!compact}>
        <ColorRow label="Rang" value={st.bg} set={(v) => set("bg", v)} />
        <Toggle label="Gradient" on={gradient} set={(on) => set("bg2", on ? (st.bg && !st.bg.startsWith("$") ? "#06b6d4" : "#4f46e5") : null)} />
        {gradient && (
          <>
            <ColorRow label="Ikkinchi rang" value={st.bg2} set={(v) => set("bg2", v)} />
            <Seg label="Gradient turi" value={st.bg_type ?? null} set={(v) => set("bg_type", v)} options={[[null, "Chiziqli"], ["radial", "Doiraviy"], ["conic", "Konus"]]} />
            <SliderField label="Yo'nalish" value={st.bg_angle ?? 160} set={(v) => set("bg_angle", v ?? 160)} min={0} max={360} suffix="°" />
          </>
        )}
        {st.bg && <SliderField label="Fon shaffofligi" value={st.bg_alpha ?? null} set={(v) => set("bg_alpha", v)} min={0} max={100} suffix="%" optional />}
        <MediaField label="Fon rasmi" value={st.bg_image ?? null} set={(v) => set("bg_image", v)} optional ctx={ctx} />
        {st.bg_image ? (
          <>
            <SliderField label="Qoraytirish" value={st.overlay ?? 0} set={(v) => set("overlay", v ?? 0)} min={0} max={90} suffix="%" />
            <Seg label="Rasm o'lchami" value={st.bg_size ?? null} set={(v) => set("bg_size", v)} options={[[null, "To'ldirish"], ["contain", "Sig'dirish"], ["tile", "Takror"]]} />
          </>
        ) : null}
        <SliderField label="Shisha effekti (orqa fonni xiralash)" value={st.backdrop ?? null} set={(v) => set("backdrop", v)} min={0} max={40} suffix="px" optional />
      </Group>
      <Group title={gt("Matn", ["color", "font", "size", "weight", "align", "line", "letter", "uppercase", "italic", "decoration", "clamp", "nowrap", "text_grad"])}>
        <ColorRow label="Rang" value={st.color} set={(v) => set("color", v)} />
        <Toggle label="Matn gradienti" on={textGrad} set={(on) => (on ? onChange({ ...st, text_grad: "$primary", text_grad2: "#ec4899" }) : onChange({ ...st, text_grad: null, text_grad2: null }))} />
        {textGrad && (
          <>
            <ColorRow label="1-rang" value={st.text_grad} set={(v) => set("text_grad", v)} />
            <ColorRow label="2-rang" value={st.text_grad2} set={(v) => set("text_grad2", v)} />
          </>
        )}
        <div className="sf-field">
          <span className="sf-label">Shrift</span>
          <select className="input" value={st.font ?? ""} onChange={(e) => set("font", e.target.value || null)}>
            <option value="">Ilova shrifti</option>
            {Object.entries(fonts).map(([k, l]) => (
              <option key={k} value={k}>
                {{ system: "Tizim", rounded: "Yumaloq", serif: "Klassik", mono: "Texnik" }[k] ?? l}
              </option>
            ))}
          </select>
        </div>
        <SliderField label="O'lcham" value={st.size ?? null} set={(v) => set("size", v)} min={10} max={96} suffix="px" optional />
        <Seg label="Qalinlik" value={st.weight ?? null} set={(v) => set("weight", v)} options={[[null, "Avto"], [300, "Ingichka"], [400, "Oddiy"], [600, "Qalin"], [800, "Juda"]]} />
        <Seg label="Tekislash" value={st.align ?? null} set={(v) => set("align", v)} options={[[null, "Avto"], ["left", "Chap"], ["center", "Markaz"], ["right", "O'ng"]]} />
        <SliderField label="Qator oralig'i" value={st.line ?? null} set={(v) => set("line", v)} min={0.8} max={2.4} step={0.05} optional />
        <SliderField label="Harf oralig'i" value={st.letter ?? null} set={(v) => set("letter", v)} min={-8} max={40} optional />
        <Toggle label="KATTA HARFLAR" on={!!st.uppercase} set={(v) => set("uppercase", v)} />
        <Toggle label="Kursiv" on={!!st.italic} set={(v) => set("italic", v)} />
        <Seg label="Chiziq" value={st.decoration ?? null} set={(v) => set("decoration", v)} options={[[null, "Yo'q"], ["underline", "Tagi"], ["line-through", "Ustidan"]]} />
        <SliderField label="Qatorlar soni (ortig'i «…»)" value={st.clamp ?? null} set={(v) => set("clamp", v)} min={1} max={8} optional />
        <Toggle label="Bir qatorda (sig'masa «…»)" on={!!st.nowrap} set={(v) => set("nowrap", v)} />
      </Group>
      <Group title={gt("O'lcham va joy", ["px", "py", "mt", "mb", "width", "w", "w_pct", "max_width", "min_height", "h", "aspect", "grow", "self_align", "gap", "span", "row_span", "overflow"])}>
        <SliderField label="Ichki masofa (yon)" value={st.px ?? null} set={(v) => set("px", v)} min={0} max={80} suffix="px" optional />
        <SliderField label="Ichki masofa (tepa/past)" value={st.py ?? null} set={(v) => set("py", v)} min={0} max={120} suffix="px" optional />
        <SliderField label="Tepadan bo'shliq" value={st.mt ?? null} set={(v) => set("mt", v)} min={-80} max={120} suffix="px" optional />
        <SliderField label="Pastdan bo'shliq" value={st.mb ?? null} set={(v) => set("mb", v)} min={-80} max={120} suffix="px" optional />
        <Seg label="Kenglik" value={st.width ?? null} set={(v) => set("width", v)} options={[[null, "Avto"], ["full", "To'liq"], ["fit", "Kontentcha"]]} />
        <SliderField label="Aniq kenglik" value={st.w ?? null} set={(v) => set("w", v)} min={8} max={800} suffix="px" optional />
        <SliderField label="Kenglik (foiz)" value={st.w_pct ?? null} set={(v) => set("w_pct", v)} min={5} max={100} suffix="%" optional />
        <SliderField label="Aniq balandlik" value={st.h ?? null} set={(v) => set("h", v)} min={2} max={900} suffix="px" optional />
        <SliderField label="Maksimal kenglik" value={st.max_width ?? null} set={(v) => set("max_width", v)} min={80} max={1200} step={10} suffix="px" optional />
        <SliderField label="Minimal balandlik" value={st.min_height ?? null} set={(v) => set("min_height", v)} min={0} max={800} step={10} suffix="px" optional />
        <div className="sf-field">
          <span className="sf-label">Proporsiya</span>
          <select className="input" value={st.aspect ?? ""} onChange={(e) => set("aspect", (e.target.value || null) as WAStyle["aspect"])}>
            <option value="">Erkin</option>
            {["1:1", "4:3", "3:2", "16:9", "21:9", "3:4", "2:3", "9:16"].map((a) => (
              <option key={a} value={a}>
                {a}
              </option>
            ))}
          </select>
        </div>
        <Toggle label="Bo'sh joyni egallash" hint="Qator ichida qolgan kenglikni to'ldiradi" on={!!st.grow} set={(v) => set("grow", v)} />
        <Seg label="O'zini tekislash" value={st.self_align ?? null} set={(v) => set("self_align", v)} options={[[null, "Avto"], ["start", "Boshi"], ["center", "Markaz"], ["end", "Oxiri"], ["stretch", "Cho'z"]]} />
        <SliderField label="Ichidagilar orasi" value={st.gap ?? null} set={(v) => set("gap", v)} min={0} max={80} suffix="px" optional />
        <SliderField label="To'rda ustun egallash" value={st.span ?? null} set={(v) => set("span", v)} min={1} max={6} optional />
        <SliderField label="To'rda qator egallash" value={st.row_span ?? null} set={(v) => set("row_span", v)} min={1} max={6} optional />
        <Seg label="Sig'magan qism" value={st.overflow ?? null} set={(v) => set("overflow", v)} options={[[null, "Avto"], ["hidden", "Kesish"], ["visible", "Ko'rsatish"], ["scroll", "Surish"]]} />
      </Group>
      <Group title={gt("Burchak, chegara, soya", ["radius", "border", "border_style", "border_color", "shadow", "shadow_color", "opacity"])}>
        <SliderField label="Burchak" value={st.radius ?? null} set={(v) => set("radius", v)} min={0} max={120} suffix="px" optional />
        <div className="de-quick">
          {[
            [0, "To'g'ri"],
            [12, "Yumshoq"],
            [24, "Yumaloq"],
            [999, "Doira / kapsula"],
          ].map(([v, l]) => (
            <button key={v} type="button" className={st.radius === v ? "is-on" : ""} onClick={() => set("radius", v as number)}>
              {l}
            </button>
          ))}
        </div>
        <SliderField label="Chegara qalinligi" value={st.border ?? null} set={(v) => set("border", v)} min={0} max={8} suffix="px" optional />
        {st.border ? (
          <>
            <Seg label="Chegara turi" value={st.border_style ?? null} set={(v) => set("border_style", v)} options={[[null, "━"], ["dashed", "╍"], ["dotted", "┉"], ["double", "═"]]} />
            <ColorRow label="Chegara rangi" value={st.border_color} set={(v) => set("border_color", v)} />
          </>
        ) : null}
        <Seg label="Soya" value={st.shadow ?? null} set={(v) => set("shadow", v)} options={[[null, "Yo'q"], ["s", "S"], ["m", "M"], ["l", "L"], ["xl", "XL"], ["glow", "Nur"], ["hard", "Qattiq"], ["inner", "Ichki"]]} />
        {st.shadow && st.shadow !== "none" ? <ColorRow label="Soya rangi" value={st.shadow_color} set={(v) => set("shadow_color", v)} /> : null}
        <SliderField label="Shaffoflik" value={st.opacity ?? null} set={(v) => set("opacity", v)} min={5} max={100} suffix="%" optional />
      </Group>
      <Group title={gt("Joylashuv (qatlam)", ["pos", "top", "right", "bottom", "left", "z"])}>
        <Seg
          label="Joylashuv"
          value={st.pos ?? null}
          set={(v) => set("pos", v)}
          options={[[null, "Oqimda"], ["absolute", "Erkin"], ["sticky", "Yopishqoq"], ["fixed", "Ekranga"]]}
        />
        <p className="hint">
          «Erkin» — ota konteyner ichida istalgan joyga (masalan rasm ustidagi belgi). «Yopishqoq» — aylantirganda chetga yopishib qoladi. «Ekranga» —
          doim ko'rinib turadi (suzuvchi tugma, pastki menyu).
        </p>
        {st.pos && (
          <>
            <SliderField label="Tepadan" value={st.top ?? null} set={(v) => set("top", v)} min={-200} max={600} suffix="px" optional />
            <SliderField label="Pastdan" value={st.bottom ?? null} set={(v) => set("bottom", v)} min={-200} max={600} suffix="px" optional />
            <SliderField label="Chapdan" value={st.left ?? null} set={(v) => set("left", v)} min={-200} max={600} suffix="px" optional />
            <SliderField label="O'ngdan" value={st.right ?? null} set={(v) => set("right", v)} min={-200} max={600} suffix="px" optional />
          </>
        )}
        <SliderField label="Qatlam tartibi (yuqoriroq — ustda)" value={st.z ?? null} set={(v) => set("z", v)} min={-5} max={50} optional />
      </Group>
      <Group title={gt("Transformatsiya", ["rotate", "scale", "tx", "ty", "skew"])}>
        <SliderField label="Burish" value={st.rotate ?? null} set={(v) => set("rotate", v)} min={-180} max={180} suffix="°" optional />
        <SliderField label="Masshtab" value={st.scale ?? null} set={(v) => set("scale", v)} min={20} max={250} suffix="%" optional />
        <SliderField label="Gorizontal siljitish" value={st.tx ?? null} set={(v) => set("tx", v)} min={-300} max={300} suffix="px" optional />
        <SliderField label="Vertikal siljitish" value={st.ty ?? null} set={(v) => set("ty", v)} min={-300} max={300} suffix="px" optional />
        <SliderField label="Qiyshaytirish" value={st.skew ?? null} set={(v) => set("skew", v)} min={-30} max={30} suffix="°" optional />
      </Group>
      <Group title={gt("Filtrlar", ["blur", "bright", "gray"])}>
        <SliderField label="Xiralash" value={st.blur ?? null} set={(v) => set("blur", v)} min={0} max={40} suffix="px" optional />
        <SliderField label="Yorqinlik" value={st.bright ?? null} set={(v) => set("bright", v)} min={20} max={180} suffix="%" optional />
        <SliderField label="Oq-qora" value={st.gray ?? null} set={(v) => set("gray", v)} min={0} max={100} suffix="%" optional />
      </Group>
      {value && (
        <button type="button" className="btn btn--ghost btn--compact" onClick={() => onChange(null)}>
          Uslubni tozalash
        </button>
      )}
    </div>
  );
}

export const ANIMS: [Anim, string][] = [
  ["none", "Yo'q"],
  ["fade", "Paydo bo'lish"],
  ["up", "Pastdan"],
  ["down", "Tepadan"],
  ["left", "Chapdan"],
  ["right", "O'ngdan"],
  ["zoom", "Kattalashib"],
  ["zoomout", "Kichrayib"],
  ["flip", "Ag'darilib"],
  ["rotate", "Burilib"],
  ["blur", "Xiradan aniq"],
];
export const LOOPS: [Loop, string][] = [
  ["none", "Yo'q"],
  ["float", "Suzish"],
  ["pulse", "Puls"],
  ["bounce", "Sakrash"],
  ["wiggle", "Tebranish"],
  ["shake", "Silkinish"],
  ["spin", "Aylanish"],
  ["glow", "Nur to'lqini"],
  ["breathe", "Nafas"],
];

export function AnimField({ value, set }: { value: Anim | undefined; set: (a: Anim) => void }) {
  return (
    <div className="sf-field">
      <span className="sf-label">Paydo bo'lish animatsiyasi</span>
      <select className="input" value={value ?? "none"} onChange={(e) => set(e.target.value as Anim)}>
        {ANIMS.map(([v, l]) => (
          <option key={v} value={v}>
            {l}
          </option>
        ))}
      </select>
    </div>
  );
}

function MotionFields({ node, update }: { node: WANode; update: (p: Partial<WANode>) => void }) {
  return (
    <div className="de-motion">
      <AnimField value={node.anim} set={(a) => update({ anim: a })} />
      {node.anim && node.anim !== "none" ? (
        <SliderField label="Kechikish" value={node.delay ?? 0} set={(v) => update({ delay: v ?? 0 })} min={0} max={2000} step={50} suffix="ms" />
      ) : null}
      <div className="sf-field">
        <span className="sf-label">Doimiy harakat</span>
        <select className="input" value={node.loop ?? "none"} onChange={(e) => update({ loop: e.target.value as Loop })}>
          {LOOPS.map(([v, l]) => (
            <option key={v} value={v}>
              {l}
            </option>
          ))}
        </select>
      </div>
    </div>
  );
}

// ============================================================
// Erkin bo'lim: elementlar daraxti
// ============================================================

export const KINDS: { kind: NodeKind; title: string; icon: string }[] = [
  { kind: "box", title: "Konteyner", icon: "▭" },
  { kind: "text", title: "Matn", icon: "T" },
  { kind: "image", title: "Rasm", icon: "🖼" },
  { kind: "button", title: "Tugma", icon: "🔘" },
  { kind: "icon", title: "Ikonka", icon: "★" },
  { kind: "video", title: "Video", icon: "▶" },
  { kind: "progress", title: "Progress", icon: "▰" },
  { kind: "rating", title: "Reyting", icon: "⭐" },
  { kind: "timer", title: "Taymer", icon: "⏱" },
  { kind: "map", title: "Xarita", icon: "📍" },
  { kind: "spacer", title: "Bo'sh joy", icon: "↕" },
  { kind: "divider", title: "Chiziq", icon: "—" },
];
const KIND_META = Object.fromEntries(KINDS.map((k) => [k.kind, k]));

const LAYOUTS: { layout: BoxLayout; title: string; icon: string; hint: string }[] = [
  { layout: "column", title: "Ustun", icon: "⬇", hint: "Elementlar ustma-ust" },
  { layout: "row", title: "Qator", icon: "➡", hint: "Yonma-yon" },
  { layout: "grid", title: "To'r", icon: "▦", hint: "Kataklar" },
  { layout: "scroll", title: "Karusel", icon: "⇆", hint: "Suriladigan lenta" },
  { layout: "stack", title: "Qatlamlar", icon: "◫", hint: "Ustma-ust (rasm ustida matn)" },
  { layout: "tabs", title: "Yorliqlar", icon: "⊟", hint: "Bo'limlar almashadi" },
  { layout: "accordion", title: "Akkordeon", icon: "☰", hint: "Ochiladigan bo'limlar" },
  { layout: "marquee", title: "Yuguruvchi", icon: "⟿", hint: "Cheksiz lenta" },
];
const LAYOUT_META = Object.fromEntries(LAYOUTS.map((l) => [l.layout, l]));

export function newNode(kind: NodeKind): WANode {
  const base = { id: uid("n"), hidden: false, style: null, wide: null, anim: "none" as Anim };
  switch (kind) {
    case "box":
      return { ...base, kind, layout: "column", gap: 12, align: "stretch", justify: "start", wrap: true, columns: 2, columns_wide: null, action: null, children: [] };
    case "text":
      return { ...base, kind, text: "Yangi matn", tag: "p" };
    case "image":
      return { ...base, kind, media_id: null, fit: "cover", ratio: "auto", action: null };
    case "button":
      return { ...base, kind, text: "Tugma", variant: "primary", icon: null, action: { ...NO_ACTION } };
    case "icon":
      return { ...base, kind, icon: "Star", size: 32, emoji: "", action: null };
    case "spacer":
      return { ...base, kind, size: 16 };
    case "divider":
      return { ...base, kind };
    case "video":
      return { ...base, kind, url: "" };
    case "progress":
      return { ...base, kind, value: 60, label: "Jarayon", show_value: true, bar: null, thickness: 8, shape: "bar" };
    case "rating":
      return { ...base, kind, value: 4.5, size: 20, star: null, show_value: true };
    case "timer":
      return { ...base, kind, until: new Date(Date.now() + 3 * 86400000).toISOString().slice(0, 16), done_text: "Boshlandi!", labels: true };
    case "map":
      return { ...base, kind, query: "Toshkent", zoom: 14, height: 220 };
  }
}

/** Tayyor konteyner: tanlangan joylashuv va namunaviy ichki elementlar bilan */
function newContainer(layout: BoxLayout): BoxNode {
  const box = newNode("box") as BoxNode;
  box.layout = layout;
  const t = (txt: string) => ({ ...(newNode("text") as WANode & { text: string }), text: txt }) as WANode;
  const card = (name: string, txt: string) => ({ ...(newNode("box") as BoxNode), name, style: { bg: "$surface", radius: 16, px: 14, py: 14 }, children: [t(txt)] }) as BoxNode;
  switch (layout) {
    case "row":
      box.align = "center";
      box.children = [t("Chap"), t("O'ng")];
      break;
    case "grid":
      box.children = [card("", "1"), card("", "2"), card("", "3"), card("", "4")];
      break;
    case "scroll":
      box.item_w = 220;
      box.dots = true;
      box.children = [card("", "1-slayd"), card("", "2-slayd"), card("", "3-slayd")];
      break;
    case "stack":
      box.style = { min_height: 180, radius: 20 };
      box.align = "center";
      box.justify = "center";
      box.children = [{ ...(newNode("box") as BoxNode), style: { bg: "#6366f1", bg2: "#ec4899", bg_angle: 135 } }, { ...t("Ustidagi matn"), style: { color: "#ffffff", size: 22, weight: 800 } } as WANode];
      break;
    case "tabs":
      box.children = [card("Birinchi", "Birinchi yorliq mazmuni"), card("Ikkinchi", "Ikkinchi yorliq mazmuni")];
      break;
    case "accordion":
      box.gap = 8;
      box.children = [card("Savol 1?", "Javob matni"), card("Savol 2?", "Javob matni")].map((c) => ({ ...c, style: null }));
      break;
    case "marquee":
      box.gap = 24;
      box.children = [t("✦ Birinchi xabar"), t("✦ Ikkinchi xabar"), t("✦ Uchinchi xabar")];
      break;
    default:
      box.children = [t("Matn")];
  }
  return box;
}

function boxFields(n: BoxNode): FieldSpec[] {
  const f: FieldSpec[] = [];
  const layoutSel: FieldSpec = { kind: "select", key: "layout", label: "Joylashuv", options: LAYOUTS.map((l) => [l.layout, `${l.icon} ${l.title}`]) };
  f.push(layoutSel);
  const gap: FieldSpec = { kind: "slider", key: "gap", label: "Elementlar orasi", min: 0, max: 64, suffix: "px" };
  const align: FieldSpec = { kind: "select", key: "align", label: "Ko'ndalang tekislash", options: [["stretch", "Cho'zish"], ["start", "Boshi"], ["center", "Markaz"], ["end", "Oxiri"]] };
  const justify: FieldSpec = {
    kind: "select",
    key: "justify",
    label: "Bo'ylama tekislash",
    options: [["start", "Boshi"], ["center", "Markaz"], ["end", "Oxiri"], ["between", "Orasida"], ["around", "Atrofida"]],
  };
  switch (n.layout) {
    case "grid":
      f.push({ kind: "slider", key: "columns", label: "Ustunlar", min: 1, max: 6 }, { kind: "slider", key: "columns_wide", label: "Keng oynada ustunlar", min: 1, max: 8, optional: true }, gap, align);
      break;
    case "scroll":
      f.push(
        { kind: "slider", key: "item_w", label: "Element kengligi", min: 60, max: 600, suffix: "px", optional: true },
        gap,
        align,
        { kind: "slider", key: "autoplay", label: "Avtomatik aylanish (soniya, 0 — o'chiq)", min: 0, max: 15 },
        { kind: "toggle", key: "dots", label: "Nuqtalar (sahifa ko'rsatkichi)" },
      );
      break;
    case "stack":
      f.push(
        { kind: "select", key: "align", label: "Gorizontal", options: [["stretch", "Cho'zish"], ["start", "Chap"], ["center", "Markaz"], ["end", "O'ng"]] },
        { kind: "select", key: "justify", label: "Vertikal", options: [["between", "Cho'zish"], ["start", "Tepa"], ["center", "Markaz"], ["end", "Past"]] },
      );
      break;
    case "tabs":
      f.push({ kind: "select", key: "tabs_style", label: "Yorliq ko'rinishi", options: [["pills", "Kapsula"], ["underline", "Tagi chiziq"], ["segmented", "Segment"]] }, gap);
      break;
    case "accordion":
      f.push({ kind: "toggle", key: "open_first", label: "Birinchisi ochiq tursin" }, gap);
      break;
    case "marquee":
      f.push({ kind: "slider", key: "speed", label: "Bir aylanish (soniya)", min: 4, max: 80, suffix: "s" }, gap);
      break;
    default:
      f.push(gap, align, justify, { kind: "toggle", key: "wrap", label: "Sig'masa yangi qatorga o'tsin" });
  }
  f.push({ kind: "action", key: "action", label: "Bosilganda" });
  return f;
}

function nodeFields(n: WANode): FieldSpec[] {
  switch (n.kind) {
    case "box":
      return boxFields(n);
    case "text":
      return [
        { kind: "textarea", key: "text", label: "Matn", max: 4000, rows: 4, hint: "**so'z** — qalin; https://... — havola" },
        { kind: "select", key: "tag", label: "Turi", options: [["h1", "Katta sarlavha"], ["h2", "Sarlavha"], ["h3", "Kichik sarlavha"], ["p", "Matn"], ["small", "Izoh"]] },
      ];
    case "image":
      return [
        { kind: "media", key: "media_id", label: "Rasm" },
        { kind: "select", key: "ratio", label: "Shakl", options: [["auto", "Asl"], ["1:1", "Kvadrat"], ["4:3", "4:3"], ["16:9", "Keng"], ["21:9", "Panorama"], ["3:4", "Tik"], ["9:16", "Hikoya"]] },
        { kind: "select", key: "fit", label: "Joylash", options: [["cover", "To'ldirish"], ["contain", "Sig'dirish"]] },
        { kind: "action", key: "action", label: "Bosilganda" },
      ];
    case "button":
      return [
        { kind: "text", key: "text", label: "Tugma matni", max: 60 },
        { kind: "select", key: "variant", label: "Ko'rinish", options: [["primary", "Asosiy"], ["secondary", "Yumshoq"], ["outline", "Chiziqli"], ["ghost", "Shaffof"], ["link", "Havola"]] },
        { kind: "icon", key: "icon", label: "Ikonka", optional: true },
        { kind: "action", key: "action", label: "Bosilganda" },
      ];
    case "icon":
      return [
        { kind: "icon", key: "icon", label: "Ikonka" },
        { kind: "text", key: "emoji", label: "yoki emoji", max: 8 },
        { kind: "slider", key: "size", label: "O'lcham", min: 10, max: 160, suffix: "px" },
        { kind: "action", key: "action", label: "Bosilganda" },
      ];
    case "spacer":
      return [{ kind: "slider", key: "size", label: "Balandlik", min: 0, max: 240, suffix: "px" }];
    case "divider":
      return [];
    case "video":
      return [{ kind: "text", key: "url", label: "YouTube havolasi", max: 300, placeholder: "https://youtu.be/..." }];
    case "progress":
      return [
        { kind: "slider", key: "value", label: "Qiymat", min: 0, max: 100, suffix: "%" },
        { kind: "text", key: "label", label: "Yozuv", max: 80 },
        { kind: "select", key: "shape", label: "Shakl", options: [["bar", "Chiziq"], ["ring", "Halqa"]] },
        { kind: "slider", key: "thickness", label: "Qalinlik", min: 2, max: 30, suffix: "px" },
        { kind: "toggle", key: "show_value", label: "Foizni ko'rsatish" },
      ];
    case "rating":
      return [
        { kind: "slider", key: "value", label: "Baho", min: 0, max: 5, step: 0.1 } as FieldSpec,
        { kind: "slider", key: "size", label: "Yulduz o'lchami", min: 10, max: 48, suffix: "px" },
        { kind: "toggle", key: "show_value", label: "Raqamni ko'rsatish" },
      ];
    case "timer":
      return [
        { kind: "date", key: "until", label: "Qachongacha" },
        { kind: "text", key: "done_text", label: "Tugagach matn", max: 80 },
        { kind: "toggle", key: "labels", label: "Kun/soat yozuvlari" },
      ];
    case "map":
      return [
        { kind: "text", key: "query", label: "Manzil yoki koordinata", max: 200, placeholder: "Toshkent, Amir Temur 1 yoki 41.31,69.24" },
        { kind: "slider", key: "zoom", label: "Yaqinlik", min: 3, max: 20 },
        { kind: "slider", key: "height", label: "Balandlik", min: 120, max: 600, suffix: "px" },
      ];
  }
}

// --- daraxt amallari (har doim nusxa ustida) ---

type Loc = { parent: BoxNode | null; index: number; node: WANode };

export function locate(root: BoxNode, id: string): Loc | null {
  if (root.id === id) return { parent: null, index: 0, node: root };
  const stack: BoxNode[] = [root];
  while (stack.length) {
    const box = stack.pop()!;
    for (let i = 0; i < box.children.length; i++) {
      const c = box.children[i];
      if (c.id === id) return { parent: box, index: i, node: c };
      if (c.kind === "box") stack.push(c);
    }
  }
  return null;
}

function pathTo(root: BoxNode, id: string): WANode[] {
  const walk = (n: WANode, trail: WANode[]): WANode[] | null => {
    if (n.id === id) return [...trail, n];
    if (n.kind === "box")
      for (const c of n.children) {
        const r = walk(c, [...trail, n]);
        if (r) return r;
      }
    return null;
  };
  return walk(root, []) ?? [root];
}

function isInside(node: WANode, id: string): boolean {
  if (node.id === id) return true;
  return node.kind === "box" && node.children.some((c) => isInside(c, id));
}

function label(n: WANode): string {
  if (n.name?.trim()) return n.name.trim();
  if (n.kind === "text") return n.text.replace(/\*\*/g, "").slice(0, 40) || "Matn";
  if (n.kind === "button") return n.text;
  if (n.kind === "icon") return n.emoji || n.icon;
  if (n.kind === "box") {
    const l = LAYOUT_META[n.layout]?.title ?? "Konteyner";
    return `${n.layout === "grid" ? `To'r ${n.columns}` : l} · ${n.children.length}`;
  }
  if (n.kind === "progress") return `Progress ${n.value}%`;
  if (n.kind === "rating") return `Reyting ${n.value}`;
  return KIND_META[n.kind].title;
}

const kindIcon = (n: WANode) => (n.kind === "box" ? LAYOUT_META[n.layout]?.icon ?? "▭" : KIND_META[n.kind].icon);

/** Element qaysi to'plam yozuvi ichida: eng yaqin takrorlovchi konteyner yoki batafsil sahifa. */
function contextCollection(root: BoxNode, id: string, pageCollection: string | null): string | null {
  const path = pathTo(root, id).slice(0, -1) as BoxNode[];
  for (let i = path.length - 1; i >= 0; i--) if (path[i].repeat?.collection) return path[i].repeat!.collection;
  return pageCollection;
}

type Drop = { id: string; where: "before" | "after" | "inside" };

export function CustomEditor({
  pageCollection = null,
  block,
  onChange,
  selected,
  onSelect,
  fonts,
  ctx,
  clipboard,
  setClipboard,
  theme,
  mediaSrc,
}: {
  pageCollection?: string | null;
  block: CustomBlock;
  onChange: (b: CustomBlock) => void;
  selected: string | null;
  onSelect: (nodeId: string | null) => void;
  fonts: Record<string, string>;
  ctx: Ctx;
  clipboard: WANode | null;
  setClipboard: (n: WANode | null) => void;
  theme: WATheme;
  mediaSrc: (id: number) => string;
}) {
  const [tab, setTab] = useState<"content" | "style" | "hover" | "wide">("content");
  const [adding, setAdding] = useState<"inside" | "after" | null>(null);
  const [gallery, setGallery] = useState<"inside" | "after" | null>(null);
  const [saving, setSaving] = useState<string | null>(null);
  const [dragId, setDragId] = useState<string | null>(null);
  const [drop, setDrop] = useState<Drop | null>(null);
  const qc = useQueryClient();
  const sel = selected ? locate(block.root, selected) : null;
  const current = sel?.node ?? block.root;
  const isRoot = current.id === block.root.id;
  const path = pathTo(block.root, current.id);
  // Takrorlovchi ichidagi elementlar uchun: o'sha to'plam; o'zi takrorlovchi bo'lsa — o'z to'plami
  const dataKey =
    current.kind === "box" && current.repeat?.collection ? current.repeat.collection : contextCollection(block.root, current.id, pageCollection);

  const mutate = (fn: (root: BoxNode) => string | void) => {
    const next = clone(block);
    const focus = fn(next.root);
    onChange(next);
    if (typeof focus === "string") onSelect(focus);
  };

  const insert = (node: WANode, where: "inside" | "after") =>
    mutate((root) => {
      const loc = locate(root, current.id)!;
      if (where === "inside" && loc.node.kind === "box") loc.node.children.push(node);
      else if (loc.parent) loc.parent.children.splice(loc.index + 1, 0, node);
      else root.children.push(node);
      return node.id;
    });

  const move = (d: number) =>
    mutate((root) => {
      const loc = locate(root, current.id)!;
      if (!loc.parent) return;
      const j = loc.index + d;
      if (j < 0 || j >= loc.parent.children.length) return;
      [loc.parent.children[loc.index], loc.parent.children[j]] = [loc.parent.children[j], loc.parent.children[loc.index]];
    });

  const indent = () =>
    mutate((root) => {
      const loc = locate(root, current.id)!;
      if (!loc.parent || loc.index === 0) return;
      const prev = loc.parent.children[loc.index - 1];
      if (prev.kind !== "box") return;
      loc.parent.children.splice(loc.index, 1);
      prev.children.push(loc.node);
    });

  const outdent = () =>
    mutate((root) => {
      const loc = locate(root, current.id)!;
      if (!loc.parent || loc.parent.id === root.id) return;
      const parentLoc = locate(root, loc.parent.id)!;
      if (!parentLoc.parent) return;
      loc.parent.children.splice(loc.index, 1);
      parentLoc.parent.children.splice(parentLoc.index + 1, 0, loc.node);
    });

  const remove = () =>
    mutate((root) => {
      const loc = locate(root, current.id)!;
      if (!loc.parent) return;
      loc.parent.children.splice(loc.index, 1);
      onSelect(loc.parent.id === root.id ? null : loc.parent.id);
    });

  /** Konteynerga o'rash: tanlangan elementni yangi konteyner ichiga oladi */
  const wrap = () =>
    mutate((root) => {
      const loc = locate(root, current.id)!;
      if (!loc.parent) return;
      const box = { ...(newNode("box") as BoxNode), children: [loc.node] };
      loc.parent.children.splice(loc.index, 1, box);
      return box.id;
    });

  const moveTo = (dragged: string, target: Drop) =>
    mutate((root) => {
      if (dragged === target.id || dragged === root.id) return;
      const from = locate(root, dragged);
      if (!from?.parent || isInside(from.node, target.id)) return;
      from.parent.children.splice(from.index, 1);
      const to = locate(root, target.id);
      if (!to) return;
      if (target.where === "inside" && to.node.kind === "box") to.node.children.push(from.node);
      else if (to.parent) to.parent.children.splice(to.index + (target.where === "after" ? 1 : 0), 0, from.node);
      else root.children.push(from.node);
      return from.node.id;
    });

  const saveComponent = async () => {
    const name = (saving ?? "").trim();
    if (!name) return;
    const node = current.kind === "box" ? current : { ...(newNode("box") as BoxNode), children: [current] };
    try {
      await api.saveComponent(name, node);
      qc.invalidateQueries({ queryKey: ["components"] });
      ctx.toast("Komponent saqlandi — kutubxonaning «Mening komponentlarim» bo'limida");
      setSaving(null);
    } catch (e) {
      ctx.toast((e as Error).message, "err");
    }
  };

  const prevIsBox = sel?.parent && sel.index > 0 && sel.parent.children[sel.index - 1]?.kind === "box";
  const canOutdent = sel?.parent && sel.parent.id !== block.root.id;

  const updateNode = (patch: Partial<WANode>) =>
    mutate((root) => {
      const loc = locate(root, current.id)!;
      Object.assign(loc.node, patch);
    });

  const dnd = {
    dragId,
    drop,
    start: (id: string) => setDragId(id),
    over: (d: Drop | null) => setDrop(d),
    end: () => {
      if (dragId && drop) moveTo(dragId, drop);
      setDragId(null);
      setDrop(null);
    },
  };

  return (
    <div className="de">
      <label className="sf-field">
        <span className="sf-label">Bo'lim nomi (faqat sizga)</span>
        <input className="input" maxLength={60} value={block.name} onChange={(e) => onChange({ ...block, name: e.target.value })} />
      </label>

      <div className="de-tree" onDragLeave={(e) => e.currentTarget === e.target && setDrop(null)}>
        <TreeRow node={block.root} depth={0} selected={current.id} onSelect={onSelect} rootId={block.root.id} dnd={dnd} />
      </div>
      <p className="hint de-tree__hint">Elementni ⠿ tutib sudrang: boshqa joyga yoki konteyner ichiga ko'chadi.</p>

      <div className="de-toolbar">
        {current.kind === "box" && (
          <button type="button" className="de-tool de-tool--primary" onClick={() => setAdding(adding === "inside" ? null : "inside")} title="Ichiga qo'shish">
            <Plus size={16} /> Ichiga
          </button>
        )}
        {!isRoot && (
          <button type="button" className="de-tool" onClick={() => setAdding(adding === "after" ? null : "after")} title="Keyin qo'shish">
            <Plus size={16} /> Keyin
          </button>
        )}
        {!isRoot && (
          <>
            <button type="button" className="de-tool" disabled={!sel || sel.index === 0} onClick={() => move(-1)} title="Yuqoriga">
              <ArrowUp size={16} />
            </button>
            <button type="button" className="de-tool" disabled={!sel?.parent || sel.index === sel.parent.children.length - 1} onClick={() => move(1)} title="Pastga">
              <ArrowDown size={16} />
            </button>
            <button type="button" className="de-tool" disabled={!prevIsBox} onClick={indent} title="Oldingi konteyner ichiga">
              <IndentIncrease size={16} />
            </button>
            <button type="button" className="de-tool" disabled={!canOutdent} onClick={outdent} title="Konteynerdan chiqarish">
              <IndentDecrease size={16} />
            </button>
            <button type="button" className="de-tool" onClick={wrap} title="Konteynerga o'rash">
              <Group2 size={16} />
            </button>
            <button type="button" className="de-tool" onClick={() => insert(cloneNode(current), "after")} title="Nusxa (dublikat)">
              <CopyPlus size={16} />
            </button>
          </>
        )}
        <button type="button" className="de-tool" onClick={() => (setClipboard(clone(current)), ctx.toast("Nusxa olindi"))} title="Nusxa olish (Ctrl+C)">
          <Copy size={16} />
        </button>
        <button
          type="button"
          className="de-tool"
          disabled={!clipboard}
          onClick={() => clipboard && insert(cloneNode(clipboard), current.kind === "box" ? "inside" : "after")}
          title="Qo'yish (Ctrl+V)"
        >
          <ClipboardPaste size={16} />
        </button>
        <button type="button" className="de-tool" onClick={() => setSaving(saving === null ? label(current).slice(0, 60) : null)} title="Komponent sifatida saqlash">
          <Star size={16} />
        </button>
        {!isRoot && (
          <>
            <button type="button" className="de-tool" onClick={() => updateNode({ hidden: !current.hidden })} title={current.hidden ? "Ko'rsatish" : "Yashirish"}>
              {current.hidden ? <EyeOff size={16} /> : <Eye size={16} />}
            </button>
            <button type="button" className="de-tool de-tool--danger" onClick={remove} title="O'chirish">
              <Trash2 size={16} />
            </button>
          </>
        )}
      </div>

      {saving !== null && (
        <div className="de-save">
          <span className="sf-label">⭐ Komponent sifatida saqlash — istalgan ilovada qayta ishlatasiz</span>
          <div className="de-save__row">
            <input className="input" maxLength={60} value={saving} autoFocus placeholder="Nomi" onChange={(e) => setSaving(e.target.value)} onKeyDown={(e) => e.key === "Enter" && saveComponent()} />
            <button type="button" className="btn btn--primary btn--compact btn--inline" disabled={!saving.trim()} onClick={saveComponent}>
              Saqlash
            </button>
          </div>
        </div>
      )}

      {adding && (
        <div className="de-add">
          <div className="de-add__head">
            <span className="sf-label">{adding === "inside" ? "Konteyner ichiga qo'shish" : "Shu elementdan keyin qo'shish"}</span>
            <button type="button" className="btn btn--primary btn--compact btn--inline" onClick={() => setGallery(adding)}>
              <Library size={15} /> Kutubxona
            </button>
          </div>
          <div className="de-add__grid">
            {KINDS.filter((k) => k.kind !== "box").map((k) => (
              <button key={k.kind} type="button" onClick={() => (insert(newNode(k.kind), adding), setAdding(null))}>
                <span className="de-add__icon">{k.icon}</span>
                {k.title}
              </button>
            ))}
          </div>
          <span className="sf-label">Konteynerlar</span>
          <div className="de-add__grid">
            {LAYOUTS.map((l) => (
              <button key={l.layout} type="button" title={l.hint} onClick={() => (insert(newContainer(l.layout), adding), setAdding(null))}>
                <span className="de-add__icon">{l.icon}</span>
                {l.title}
              </button>
            ))}
          </div>
        </div>
      )}

      {gallery && (
        <ComponentGallery
          theme={theme}
          mediaSrc={mediaSrc}
          target={gallery === "inside" ? `«${label(current)}» ichiga qo'yiladi` : `«${label(current)}» dan keyin qo'yiladi`}
          onClose={() => setGallery(null)}
          onPick={(root, title) => {
            insert({ ...root, name: root.name || title }, gallery);
            setGallery(null);
            setAdding(null);
          }}
        />
      )}

      <div className="de-inspector">
        {path.length > 1 && (
          <nav className="de-crumbs" aria-label="Yo'l">
            {path.map((n, i) => (
              <span key={n.id}>
                {i > 0 && <ChevronRight size={12} />}
                <button type="button" className={n.id === current.id ? "is-on" : ""} onClick={() => onSelect(n.id === block.root.id ? null : n.id)}>
                  {n.id === block.root.id ? "Bo'lim" : label(n).slice(0, 18)}
                </button>
              </span>
            ))}
          </nav>
        )}
        <div className="de-inspector__title">
          <span className="de-kind">{kindIcon(current)}</span>
          <b>{isRoot ? "Bo'lim (asosiy konteyner)" : current.kind === "box" ? `Konteyner · ${LAYOUT_META[current.layout]?.title}` : KIND_META[current.kind].title}</b>
        </div>
        <div className="segmented segmented--small">
          <button type="button" className={tab === "content" ? "is-selected" : ""} onClick={() => setTab("content")}>
            Kontent
          </button>
          <button type="button" className={tab === "style" ? "is-selected" : ""} onClick={() => setTab("style")}>
            Uslub
          </button>
          <button type="button" className={tab === "hover" ? "is-selected" : ""} onClick={() => setTab("hover")}>
            Hover
          </button>
          <button type="button" className={tab === "wide" ? "is-selected" : ""} onClick={() => setTab("wide")}>
            Keng
          </button>
        </div>
        {tab === "content" && (
          <label className="sf-field">
            <span className="sf-label">{sel?.parent && (sel.parent.layout === "tabs" || sel.parent.layout === "accordion") ? "Sarlavha (yorliq / akkordeon)" : "Qatlam nomi"}</span>
            <input className="input" maxLength={40} value={current.name ?? ""} placeholder={label({ ...current, name: "" } as WANode)} onChange={(e) => updateNode({ name: e.target.value })} />
          </label>
        )}
        {tab === "content" &&
          (nodeFields(current).length ? (
            <SpecForm spec={nodeFields(current)} value={current} onChange={(next) => updateNode(next as Partial<WANode>)} ctx={ctx} />
          ) : (
            <p className="hint">Bu elementning kontent sozlamasi yo'q — «Uslub» bo'limidan rang va masofani o'zgartiring.</p>
          ))}
        {tab === "content" && current.kind === "box" && current.layout !== "tabs" && current.layout !== "accordion" && (
          <div className="de-data">
            <button type="button" className="sf-toggle" onClick={() => updateNode({ repeat: current.repeat ? null : emptyQuery(dataKey ?? "") } as Partial<WANode>)}>
              <span>
                🗂 To'plamdan takrorlash
                <span className="sf-hint">Ichidagi elementlar har bir yozuv uchun chiziladi — istalgan dizayndagi ro'yxat</span>
              </span>
              <span className={`switch ${current.repeat ? "is-on" : ""}`}>
                <i />
              </span>
            </button>
            {current.repeat && <QueryEditor query={current.repeat} onChange={(q) => updateNode({ repeat: q } as Partial<WANode>)} allowSearch={false} />}
          </div>
        )}
        {tab === "content" && current.kind === "image" && dataKey && (
          <ImageBindField collection={dataKey} value={current.bind} onChange={(bind) => updateNode({ bind } as Partial<WANode>)} />
        )}
        {tab === "content" && (current.kind === "text" || current.kind === "button") && dataKey && (
          <FieldChips
            collection={dataKey}
            onPick={(t) => updateNode({ text: `${current.text}${current.text.endsWith(" ") || !current.text ? "" : " "}${t}` } as Partial<WANode>)}
          />
        )}
        {tab === "style" && (
          <>
            <StyleEditor value={current.style} onChange={(s) => updateNode({ style: s })} fonts={fonts} ctx={ctx} />
            <Group title="Harakat (animatsiya)" open={!!(current.anim && current.anim !== "none") || !!(current.loop && current.loop !== "none")}>
              <MotionFields node={current} update={updateNode} />
            </Group>
          </>
        )}
        {tab === "hover" && <StyleEditor value={current.hover} onChange={(s) => updateNode({ hover: s })} fonts={fonts} ctx={ctx} hover />}
        {tab === "wide" && (
          <>
            <p className="hint">Faqat keng oynada (planshet, Telegram Desktop) amal qiladigan qiymatlar. Telefonda «Uslub»dagilari ishlaydi.</p>
            <StyleEditor value={current.wide} onChange={(s) => updateNode({ wide: s })} fonts={fonts} ctx={ctx} />
          </>
        )}
      </div>
    </div>
  );
}

type Dnd = { dragId: string | null; drop: Drop | null; start: (id: string) => void; over: (d: Drop | null) => void; end: () => void };

function TreeRow({
  node,
  depth,
  selected,
  onSelect,
  rootId,
  dnd,
}: {
  node: WANode;
  depth: number;
  selected: string;
  onSelect: (id: string | null) => void;
  rootId: string;
  dnd: Dnd;
}) {
  const isRoot = node.id === rootId;
  const mark = dnd.drop?.id === node.id ? dnd.drop.where : null;
  return (
    <>
      <button
        type="button"
        className={`de-row ${selected === node.id ? "is-selected" : ""} ${node.hidden ? "is-hidden" : ""} ${mark ? `is-drop-${mark}` : ""} ${dnd.dragId === node.id ? "is-dragging" : ""}`}
        style={{ paddingLeft: 10 + depth * 16 }}
        onClick={() => onSelect(isRoot ? null : node.id)}
        draggable={!isRoot}
        onDragStart={(e) => {
          e.dataTransfer.effectAllowed = "move";
          e.dataTransfer.setData("text/plain", node.id);
          dnd.start(node.id);
        }}
        onDragOver={(e) => {
          if (!dnd.dragId || dnd.dragId === node.id) return;
          e.preventDefault();
          const r = e.currentTarget.getBoundingClientRect();
          const y = (e.clientY - r.top) / r.height;
          let where: Drop["where"] = y < 0.3 ? "before" : y > 0.7 ? "after" : node.kind === "box" ? "inside" : y < 0.5 ? "before" : "after";
          if (isRoot) where = "inside";
          if (dnd.drop?.id !== node.id || dnd.drop.where !== where) dnd.over({ id: node.id, where });
        }}
        onDrop={(e) => {
          e.preventDefault();
          dnd.end();
        }}
        onDragEnd={() => dnd.end()}
      >
        {!isRoot && <GripVertical size={13} className="de-row__grip" />}
        <span className="de-kind">{kindIcon(node)}</span>
        <span className="de-row__label">{isRoot ? "Bo'lim" : label(node)}</span>
        {node.hidden && <EyeOff size={13} />}
      </button>
      {node.kind === "box" && node.children.map((c) => <TreeRow key={c.id} node={c} depth={depth + 1} selected={selected} onSelect={onSelect} rootId={rootId} dnd={dnd} />)}
    </>
  );
}
