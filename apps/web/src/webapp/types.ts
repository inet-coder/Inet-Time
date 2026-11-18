// Kodsiz Web App hujjati — server tomonidagi sxema: packages/core/core/webapp_builder.py

export type ActionType = "none" | "page" | "url" | "bot" | "phone" | "share" | "cart" | "detail";
export type WAAction = { type: ActionType; page?: string | null; url?: string | null; phone?: string | null };
export type WABtn = { text: string; action: WAAction };

export type Anim = "none" | "fade" | "up" | "down" | "zoom" | "zoomout" | "left" | "right" | "flip" | "blur" | "rotate";
export type Loop = "none" | "float" | "pulse" | "spin" | "shake" | "bounce" | "glow" | "wiggle" | "breathe";

/** Uslub — har qanday blok yoki element uchun. Hammasi ixtiyoriy. */
export type WAStyle = {
  px?: number | null;
  py?: number | null;
  mt?: number | null;
  mb?: number | null;
  width?: "auto" | "full" | "fit" | null;
  max_width?: number | null;
  min_height?: number | null;
  bg?: string | null;
  bg2?: string | null;
  bg_angle?: number;
  bg_image?: number | null;
  overlay?: number;
  color?: string | null;
  border?: number | null;
  border_color?: string | null;
  radius?: number | null;
  shadow?: "none" | "s" | "m" | "l" | "xl" | "glow" | "inner" | "hard" | null;
  opacity?: number | null;
  font?: string | null;
  size?: number | null;
  weight?: number | null;
  align?: "left" | "center" | "right" | null;
  line?: number | null;
  letter?: number | null;
  uppercase?: boolean;
  italic?: boolean;
  decoration?: "underline" | "line-through" | null;
  clamp?: number | null;
  nowrap?: boolean;
  text_grad?: string | null;
  text_grad2?: string | null;
  w?: number | null;
  w_pct?: number | null;
  h?: number | null;
  aspect?: "1:1" | "4:3" | "3:2" | "16:9" | "21:9" | "3:4" | "2:3" | "9:16" | null;
  grow?: boolean;
  self_align?: "start" | "center" | "end" | "stretch" | null;
  overflow?: "hidden" | "visible" | "scroll" | null;
  pos?: "relative" | "absolute" | "sticky" | "fixed" | null;
  top?: number | null;
  right?: number | null;
  bottom?: number | null;
  left?: number | null;
  z?: number | null;
  rotate?: number | null;
  scale?: number | null;
  tx?: number | null;
  ty?: number | null;
  skew?: number | null;
  bg_type?: "linear" | "radial" | "conic" | null;
  bg_alpha?: number | null;
  bg_size?: "cover" | "contain" | "tile" | null;
  blur?: number | null;
  backdrop?: number | null;
  bright?: number | null;
  gray?: number | null;
  border_style?: "solid" | "dashed" | "dotted" | "double" | null;
  shadow_color?: string | null;
  gap?: number | null;
  span?: number | null;
  row_span?: number | null;
};

export type WAQuery = {
  collection: string;
  limit: number;
  sort_field: string | null;
  sort_dir: "asc" | "desc";
  filter_field: string | null;
  filter_value: string | null;
  search: boolean;
  empty_text: string;
};

type NodeBase = {
  id: string;
  name?: string;
  hidden?: boolean;
  style?: WAStyle | null;
  wide?: WAStyle | null;
  hover?: WAStyle | null;
  anim?: Anim;
  delay?: number;
  loop?: Loop;
};
export type BoxLayout = "column" | "row" | "grid" | "scroll" | "stack" | "tabs" | "accordion" | "marquee";
export type BoxNode = NodeBase & {
  kind: "box";
  layout: BoxLayout;
  gap: number;
  item_w?: number | null;
  autoplay?: number;
  dots?: boolean;
  tabs_style?: "pills" | "underline" | "segmented";
  open_first?: boolean;
  speed?: number;
  align: "start" | "center" | "end" | "stretch";
  justify: "start" | "center" | "end" | "between" | "around";
  wrap: boolean;
  columns: number;
  columns_wide?: number | null;
  action?: WAAction | null;
  repeat?: WAQuery | null;
  children: WANode[];
};
export type TextNode = NodeBase & { kind: "text"; text: string; tag: "h1" | "h2" | "h3" | "p" | "small" };
export type ImageNode = NodeBase & {
  kind: "image";
  media_id: number | null;
  fit: "cover" | "contain";
  ratio: "auto" | "1:1" | "4:3" | "16:9" | "3:4" | "21:9" | "9:16";
  bind?: string | null;
  action?: WAAction | null;
};
export type ButtonNode = NodeBase & {
  kind: "button";
  text: string;
  variant: "primary" | "secondary" | "outline" | "ghost" | "link";
  icon?: string | null;
  action: WAAction;
};
export type IconNode = NodeBase & { kind: "icon"; icon: string; size: number; emoji: string; action?: WAAction | null };
export type SpacerNode = NodeBase & { kind: "spacer"; size: number };
export type DividerNode = NodeBase & { kind: "divider" };
export type VideoNode = NodeBase & { kind: "video"; url: string };
export type ProgressNode = NodeBase & {
  kind: "progress";
  value: number;
  label: string;
  show_value: boolean;
  bar?: string | null;
  thickness: number;
  shape: "bar" | "ring";
};
export type RatingNode = NodeBase & { kind: "rating"; value: number; size: number; star?: string | null; show_value: boolean };
export type TimerNode = NodeBase & { kind: "timer"; until: string; done_text: string; labels: boolean };
export type MapNode = NodeBase & { kind: "map"; query: string; zoom: number; height: number };
export type WANode =
  | BoxNode
  | TextNode
  | ImageNode
  | ButtonNode
  | IconNode
  | SpacerNode
  | DividerNode
  | VideoNode
  | ProgressNode
  | RatingNode
  | TimerNode
  | MapNode;
export type NodeKind = WANode["kind"];

type Base = { id: string; hidden?: boolean; style?: WAStyle | null; anim?: Anim };

export type HeroBlock = Base & {
  type: "hero";
  title: string;
  subtitle: string;
  media_id: number | null;
  emoji: string;
  align: "center" | "left";
  button: WABtn | null;
};
export type HeadingBlock = Base & { type: "heading"; text: string; size: 1 | 2 | 3; align: "left" | "center" };
export type TextBlock = Base & { type: "text"; text: string; align: "left" | "center"; muted: boolean };
export type ImageBlock = Base & {
  type: "image";
  media_id: number | null;
  ratio: "auto" | "1:1" | "4:3" | "16:9" | "3:4";
  caption: string;
  action: WAAction;
};
export type GalleryBlock = Base & { type: "gallery"; media_ids: number[]; columns: 2 | 3 };
export type ButtonBlock = Base & { type: "button"; text: string; style: "primary" | "secondary" | "outline"; action: WAAction };
export type FeatureItem = { emoji: string; title: string; text: string };
export type FeaturesBlock = Base & { type: "features"; columns: 1 | 2; items: FeatureItem[] };
export type LinkItem = { emoji: string; title: string; subtitle: string; action: WAAction };
export type LinksBlock = Base & { type: "links"; items: LinkItem[] };
export type Product = {
  id: string;
  title: string;
  price: number;
  old_price: number | null;
  media_id: number | null;
  emoji: string;
  text: string;
  badge: string;
};
export type ProductsBlock = Base & { type: "products"; title: string; columns: 1 | 2; items: Product[] };
export type FieldType = "text" | "textarea" | "phone" | "email" | "number" | "select" | "radio" | "checkbox" | "date";
export type FormField = { id: string; type: FieldType; label: string; placeholder: string; required: boolean; options: string[] };
export type FormBlock = Base & {
  type: "form";
  title: string;
  fields: FormField[];
  submit_text: string;
  success_text: string;
  save_to?: string | null;
};
export type ContactsBlock = Base & {
  type: "contacts";
  phone: string | null;
  telegram: string | null;
  instagram: string | null;
  website: string | null;
  address: string;
  map_url: string | null;
};
export type FaqBlock = Base & { type: "faq"; items: { q: string; a: string }[] };
export type PricingPlan = { name: string; price: string; period: string; features: string[]; highlight: boolean; button: WABtn | null };
export type PricingBlock = Base & { type: "pricing"; items: PricingPlan[] };
export type StatsBlock = Base & { type: "stats"; items: { value: string; label: string }[] };
export type CountdownBlock = Base & { type: "countdown"; title: string; date: string; done_text: string };
export type VideoBlock = Base & { type: "video"; url: string; caption: string };
export type DividerBlock = Omit<Base, "style"> & { type: "divider"; style: "line" | "space"; size: "s" | "m" | "l" };
export type CustomBlock = Base & { type: "custom"; name: string; root: BoxNode };
export type CollectionBlock = Base & {
  type: "collection";
  title: string;
  query: WAQuery;
  layout: "cards" | "list" | "grid";
  columns: number;
  title_field: string | null;
  subtitle_field: string | null;
  image_field: string | null;
  price_field: string | null;
  badge_field: string | null;
  detail_page: string | null;
};

export type WABlock =
  | HeroBlock
  | HeadingBlock
  | TextBlock
  | ImageBlock
  | GalleryBlock
  | ButtonBlock
  | FeaturesBlock
  | LinksBlock
  | ProductsBlock
  | FormBlock
  | ContactsBlock
  | FaqBlock
  | PricingBlock
  | StatsBlock
  | CountdownBlock
  | VideoBlock
  | DividerBlock
  | CustomBlock
  | CollectionBlock;

export type BlockType = WABlock["type"];

export type WAPage = { id: string; title: string; emoji: string; in_nav: boolean; collection?: string | null; blocks: WABlock[] };

export type WATheme = {
  preset: string;
  adaptive: boolean;
  primary: string;
  background: string;
  surface: string;
  text: string;
  radius: number;
  font: string;
};

export type WASettings = { title: string; currency: string; checkout_fields: FormField[]; checkout_success: string };

export type AppDoc = { version: number; theme: WATheme; settings: WASettings; start: string; pages: WAPage[] };

export type SubmitPayload =
  | { kind: "form"; block_id: string; values: Record<string, string | boolean> }
  | { kind: "order"; items: { id: string; qty: number }[]; values: Record<string, string | boolean> };

export function uid(prefix: string): string {
  return prefix + Math.random().toString(36).slice(2, 8);
}

export function youtubeId(url: string): string | null {
  const m = url.match(/(?:youtube\.com\/(?:watch\?v=|embed\/|shorts\/)|youtu\.be\/)([A-Za-z0-9_-]{11})/);
  return m ? m[1] : null;
}

export function formatMoney(amount: number, currency: string): string {
  return `${Math.round(amount).toLocaleString("ru-RU").replace(/,/g, " ")}${currency ? ` ${currency}` : ""}`;
}
