// Kodsiz Web App hujjati — server tomonidagi sxema: packages/core/core/webapp_builder.py

export type ActionType = "none" | "page" | "url" | "bot" | "phone" | "share" | "cart";
export type WAAction = { type: ActionType; page?: string | null; url?: string | null; phone?: string | null };
export type WABtn = { text: string; action: WAAction };

type Base = { id: string; hidden?: boolean };

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
export type FormBlock = Base & { type: "form"; title: string; fields: FormField[]; submit_text: string; success_text: string };
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
export type DividerBlock = Base & { type: "divider"; style: "line" | "space"; size: "s" | "m" | "l" };

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
  | DividerBlock;

export type BlockType = WABlock["type"];

export type WAPage = { id: string; title: string; emoji: string; in_nav: boolean; blocks: WABlock[] };

export type WATheme = {
  preset: string;
  adaptive: boolean;
  primary: string;
  background: string;
  surface: string;
  text: string;
  radius: number;
  font: "system" | "rounded" | "serif" | "mono";
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
