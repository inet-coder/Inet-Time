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
  IndentDecrease,
  IndentIncrease,
  Plus,
  Trash2,
  X,
} from "lucide-react";
import { useState, type ReactNode } from "react";
import { cloneNode, SECTIONS } from "../webapp/sections";
import { NO_ACTION, type FieldSpec } from "../webapp/specs";
import { uid, type Anim, type BoxNode, type CustomBlock, type NodeKind, type WANode, type WAPage, type WAStyle } from "../webapp/types";
import { MediaField, SliderField, SpecForm } from "./SpecForm";

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

function ColorRow({ label, value, set }: { label: string; value: string | null | undefined; set: (v: string | null) => void }) {
  return (
    <div className="de-color">
      <span className="sf-label">{label}</span>
      <label className="de-color__swatch" style={{ background: value ?? "transparent" }}>
        <input type="color" value={value ?? "#ffffff"} onChange={(e) => set(e.target.value)} />
        {!value && <span>—</span>}
      </label>
      <input className="input de-color__hex" maxLength={7} value={value ?? ""} placeholder="avto" onChange={(e) => {
        const v = e.target.value.trim();
        if (v === "") set(null);
        else if (/^#[0-9a-fA-F]{6}$/.test(v)) set(v);
      }} />
      {value && (
        <button type="button" className="sf-reset" onClick={() => set(null)} aria-label="Tozalash">
          <X size={12} />
        </button>
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

export function StyleEditor({
  value,
  onChange,
  fonts,
  ctx,
  compact = false,
}: {
  value: WAStyle | null | undefined;
  onChange: (next: WAStyle | null) => void;
  fonts: Record<string, string>;
  ctx: Ctx;
  compact?: boolean;
}) {
  const st: WAStyle = value ?? {};
  const set = <K extends keyof WAStyle>(key: K, v: WAStyle[K] | null) => {
    const next: WAStyle = { ...st, [key]: v };
    // Bo'sh qiymatlar saqlanmaydi — hujjat toza qoladi
    for (const k of Object.keys(next) as (keyof WAStyle)[]) if (next[k] === null || next[k] === undefined) delete next[k];
    onChange(Object.keys(next).length ? next : null);
  };
  const gradient = !!st.bg2;
  return (
    <div className="de-style">
      <Group title="Fon" open={!compact}>
        <ColorRow label="Rang" value={st.bg} set={(v) => set("bg", v)} />
        <button type="button" className="sf-toggle" onClick={() => set("bg2", gradient ? null : st.bg ? "#06b6d4" : "#4f46e5")}>
          <span>Gradient</span>
          <span className={`switch ${gradient ? "is-on" : ""}`}>
            <i />
          </span>
        </button>
        {gradient && (
          <>
            <ColorRow label="Ikkinchi rang" value={st.bg2} set={(v) => set("bg2", v)} />
            <SliderField label="Yo'nalish" value={st.bg_angle ?? 160} set={(v) => set("bg_angle", v ?? 160)} min={0} max={360} suffix="°" />
          </>
        )}
        <MediaField label="Fon rasmi" value={st.bg_image ?? null} set={(v) => set("bg_image", v)} optional ctx={ctx} />
        {st.bg_image ? <SliderField label="Qoraytirish" value={st.overlay ?? 0} set={(v) => set("overlay", v ?? 0)} min={0} max={90} suffix="%" /> : null}
      </Group>
      <Group title="Matn">
        <ColorRow label="Rang" value={st.color} set={(v) => set("color", v)} />
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
        <SliderField label="O'lcham" value={st.size ?? null} set={(v) => set("size", v)} min={10} max={72} suffix="px" optional />
        <Seg label="Qalinlik" value={st.weight ?? null} set={(v) => set("weight", v)} options={[[null, "Avto"], [400, "Oddiy"], [600, "Qalin"], [800, "Juda"]]} />
        <Seg label="Tekislash" value={st.align ?? null} set={(v) => set("align", v)} options={[[null, "Avto"], ["left", "Chap"], ["center", "Markaz"], ["right", "O'ng"]]} />
        <SliderField label="Qator oralig'i" value={st.line ?? null} set={(v) => set("line", v)} min={0.8} max={2.4} step={0.05} optional />
        <SliderField label="Harf oralig'i" value={st.letter ?? null} set={(v) => set("letter", v)} min={-5} max={30} optional />
        <button type="button" className="sf-toggle" onClick={() => set("uppercase", st.uppercase ? null : true)}>
          <span>KATTA HARFLAR</span>
          <span className={`switch ${st.uppercase ? "is-on" : ""}`}>
            <i />
          </span>
        </button>
      </Group>
      <Group title="O'lcham va joy">
        <SliderField label="Ichki masofa (yon)" value={st.px ?? null} set={(v) => set("px", v)} min={0} max={80} suffix="px" optional />
        <SliderField label="Ichki masofa (tepa/past)" value={st.py ?? null} set={(v) => set("py", v)} min={0} max={120} suffix="px" optional />
        <SliderField label="Tepadan bo'shliq" value={st.mt ?? null} set={(v) => set("mt", v)} min={-40} max={120} suffix="px" optional />
        <SliderField label="Pastdan bo'shliq" value={st.mb ?? null} set={(v) => set("mb", v)} min={-40} max={120} suffix="px" optional />
        <Seg label="Kenglik" value={st.width ?? null} set={(v) => set("width", v)} options={[[null, "Avto"], ["full", "To'liq"], ["fit", "Kontentcha"]]} />
        <SliderField label="Maksimal kenglik" value={st.max_width ?? null} set={(v) => set("max_width", v)} min={80} max={1200} step={10} suffix="px" optional />
        <SliderField label="Minimal balandlik" value={st.min_height ?? null} set={(v) => set("min_height", v)} min={0} max={800} step={10} suffix="px" optional />
      </Group>
      <Group title="Burchak, chegara, soya">
        <SliderField label="Burchak" value={st.radius ?? null} set={(v) => set("radius", v)} min={0} max={80} suffix="px" optional />
        <SliderField label="Chegara qalinligi" value={st.border ?? null} set={(v) => set("border", v)} min={0} max={8} suffix="px" optional />
        {st.border ? <ColorRow label="Chegara rangi" value={st.border_color} set={(v) => set("border_color", v)} /> : null}
        <Seg label="Soya" value={st.shadow ?? null} set={(v) => set("shadow", v)} options={[[null, "Yo'q"], ["s", "Yengil"], ["m", "O'rta"], ["l", "Katta"], ["glow", "Nur"]]} />
        <SliderField label="Shaffoflik" value={st.opacity ?? null} set={(v) => set("opacity", v)} min={10} max={100} suffix="%" optional />
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
  ["fade", "Paydo"],
  ["up", "Pastdan"],
  ["left", "Chapdan"],
  ["right", "O'ngdan"],
  ["zoom", "Kattalashib"],
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

// ============================================================
// Erkin bo'lim: elementlar daraxti
// ============================================================

export const KINDS: { kind: NodeKind; title: string; icon: string }[] = [
  { kind: "box", title: "Konteyner", icon: "▭" },
  { kind: "text", title: "Matn", icon: "T" },
  { kind: "image", title: "Rasm", icon: "🖼" },
  { kind: "button", title: "Tugma", icon: "🔘" },
  { kind: "icon", title: "Ikonka", icon: "★" },
  { kind: "spacer", title: "Bo'sh joy", icon: "↕" },
  { kind: "divider", title: "Chiziq", icon: "—" },
];
const KIND_META = Object.fromEntries(KINDS.map((k) => [k.kind, k]));

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
  }
}

const NODE_FIELDS: Record<NodeKind, FieldSpec[]> = {
  box: [
    { kind: "select", key: "layout", label: "Joylashuv", options: [["column", "Ustun ↓"], ["row", "Qator →"], ["grid", "To'r ▦"]] },
    { kind: "slider", key: "columns", label: "Ustunlar (to'r)", min: 1, max: 6 },
    { kind: "slider", key: "columns_wide", label: "Keng oynada ustunlar", min: 1, max: 8, optional: true },
    { kind: "slider", key: "gap", label: "Elementlar orasi", min: 0, max: 64, suffix: "px" },
    { kind: "select", key: "align", label: "Ko'ndalang tekislash", options: [["stretch", "Cho'zish"], ["start", "Boshi"], ["center", "Markaz"], ["end", "Oxiri"]] },
    { kind: "select", key: "justify", label: "Bo'ylama tekislash", options: [["start", "Boshi"], ["center", "Markaz"], ["end", "Oxiri"], ["between", "Orasida"], ["around", "Atrofida"]] },
    { kind: "toggle", key: "wrap", label: "Sig'masa yangi qatorga o'tsin" },
    { kind: "action", key: "action", label: "Bosilganda" },
  ],
  text: [
    { kind: "textarea", key: "text", label: "Matn", max: 4000, rows: 4, hint: "**so'z** — qalin; https://... — havola" },
    { kind: "select", key: "tag", label: "Turi", options: [["h1", "Katta sarlavha"], ["h2", "Sarlavha"], ["h3", "Kichik sarlavha"], ["p", "Matn"], ["small", "Izoh"]] },
  ],
  image: [
    { kind: "media", key: "media_id", label: "Rasm" },
    { kind: "select", key: "ratio", label: "Shakl", options: [["auto", "Asl"], ["1:1", "Kvadrat"], ["4:3", "4:3"], ["16:9", "Keng"], ["21:9", "Panorama"], ["3:4", "Tik"], ["9:16", "Hikoya"]] },
    { kind: "select", key: "fit", label: "Joylash", options: [["cover", "To'ldirish"], ["contain", "Sig'dirish"]] },
    { kind: "action", key: "action", label: "Bosilganda" },
  ],
  button: [
    { kind: "text", key: "text", label: "Tugma matni", max: 60 },
    { kind: "select", key: "variant", label: "Ko'rinish", options: [["primary", "Asosiy"], ["secondary", "Yumshoq"], ["outline", "Chiziqli"], ["ghost", "Shaffof"], ["link", "Havola"]] },
    { kind: "icon", key: "icon", label: "Ikonka", optional: true },
    { kind: "action", key: "action", label: "Bosilganda" },
  ],
  icon: [
    { kind: "icon", key: "icon", label: "Ikonka" },
    { kind: "text", key: "emoji", label: "yoki emoji", max: 8 },
    { kind: "slider", key: "size", label: "O'lcham", min: 10, max: 160, suffix: "px" },
    { kind: "action", key: "action", label: "Bosilganda" },
  ],
  spacer: [{ kind: "slider", key: "size", label: "Balandlik", min: 0, max: 240, suffix: "px" }],
  divider: [],
};

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

function label(n: WANode): string {
  if (n.kind === "text") return n.text.replace(/\*\*/g, "").slice(0, 40) || "Matn";
  if (n.kind === "button") return n.text;
  if (n.kind === "icon") return n.emoji || n.icon;
  if (n.kind === "box") return `${{ column: "Ustun", row: "Qator", grid: `To'r ${n.columns}` }[n.layout]} · ${n.children.length}`;
  return KIND_META[n.kind].title;
}

export function CustomEditor({
  block,
  onChange,
  selected,
  onSelect,
  fonts,
  ctx,
  clipboard,
  setClipboard,
}: {
  block: CustomBlock;
  onChange: (b: CustomBlock) => void;
  selected: string | null;
  onSelect: (nodeId: string | null) => void;
  fonts: Record<string, string>;
  ctx: Ctx;
  clipboard: WANode | null;
  setClipboard: (n: WANode | null) => void;
}) {
  const [tab, setTab] = useState<"content" | "style" | "wide">("content");
  const [adding, setAdding] = useState<"inside" | "after" | null>(null);
  const sel = selected ? locate(block.root, selected) : null;
  const current = sel?.node ?? block.root;
  const isRoot = current.id === block.root.id;

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

  const prevIsBox = sel?.parent && sel.index > 0 && sel.parent.children[sel.index - 1]?.kind === "box";
  const canOutdent = sel?.parent && sel.parent.id !== block.root.id;

  const updateNode = (patch: Partial<WANode>) =>
    mutate((root) => {
      const loc = locate(root, current.id)!;
      Object.assign(loc.node, patch);
    });

  return (
    <div className="de">
      <label className="sf-field">
        <span className="sf-label">Bo'lim nomi (faqat sizga)</span>
        <input className="input" maxLength={60} value={block.name} onChange={(e) => onChange({ ...block, name: e.target.value })} />
      </label>

      <div className="de-tree">
        <TreeRow node={block.root} depth={0} selected={current.id} onSelect={onSelect} rootId={block.root.id} />
      </div>

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

      {adding && (
        <div className="de-add">
          <span className="sf-label">{adding === "inside" ? "Konteyner ichiga qo'shish" : "Shu elementdan keyin qo'shish"}</span>
          <div className="de-add__grid">
            {KINDS.map((k) => (
              <button key={k.kind} type="button" onClick={() => (insert(newNode(k.kind), adding), setAdding(null))}>
                <span className="de-add__icon">{k.icon}</span>
                {k.title}
              </button>
            ))}
          </div>
          <span className="sf-label">Tayyor bo'laklar</span>
          <div className="de-add__grid">
            {SECTIONS.filter((p) => p.key !== "empty").map((p) => (
              <button key={p.key} type="button" onClick={() => (insert(p.make(), adding), setAdding(null))}>
                <span className="de-add__icon">{p.icon}</span>
                {p.title}
              </button>
            ))}
          </div>
        </div>
      )}

      <div className="de-inspector">
        <div className="de-inspector__title">
          <span className="de-kind">{KIND_META[current.kind].icon}</span>
          <b>{isRoot ? "Bo'lim (asosiy konteyner)" : KIND_META[current.kind].title}</b>
        </div>
        <div className="segmented segmented--small">
          <button type="button" className={tab === "content" ? "is-selected" : ""} onClick={() => setTab("content")}>
            Kontent
          </button>
          <button type="button" className={tab === "style" ? "is-selected" : ""} onClick={() => setTab("style")}>
            Uslub
          </button>
          <button type="button" className={tab === "wide" ? "is-selected" : ""} onClick={() => setTab("wide")}>
            Keng oyna
          </button>
        </div>
        {tab === "content" &&
          (NODE_FIELDS[current.kind].length ? (
            <SpecForm spec={NODE_FIELDS[current.kind]} value={current} onChange={(next) => updateNode(next as Partial<WANode>)} ctx={ctx} />
          ) : (
            <p className="hint">Bu elementning kontent sozlamasi yo'q — «Uslub» bo'limidan rang va masofani o'zgartiring.</p>
          ))}
        {tab === "style" && (
          <>
            <StyleEditor value={current.style} onChange={(s) => updateNode({ style: s })} fonts={fonts} ctx={ctx} />
            <AnimField value={current.anim} set={(a) => updateNode({ anim: a })} />
          </>
        )}
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

function TreeRow({
  node,
  depth,
  selected,
  onSelect,
  rootId,
}: {
  node: WANode;
  depth: number;
  selected: string;
  onSelect: (id: string | null) => void;
  rootId: string;
}) {
  return (
    <>
      <button
        type="button"
        className={`de-row ${selected === node.id ? "is-selected" : ""} ${node.hidden ? "is-hidden" : ""}`}
        style={{ paddingLeft: 10 + depth * 16 }}
        onClick={() => onSelect(node.id === rootId ? null : node.id)}
      >
        <span className="de-kind">{KIND_META[node.kind].icon}</span>
        <span className="de-row__label">{node.id === rootId ? "Bo'lim" : label(node)}</span>
        {node.hidden && <EyeOff size={13} />}
      </button>
      {node.kind === "box" && node.children.map((c) => <TreeRow key={c.id} node={c} depth={depth + 1} selected={selected} onSelect={onSelect} rootId={rootId} />)}
    </>
  );
}
