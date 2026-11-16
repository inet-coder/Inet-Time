// Har bir blok turi konstruktorda qanday tahrirlanishi — bitta umumiy forma (SpecForm) shu tavsiflardan quriladi.
import { uid, type BlockType, type FormField, type WAAction, type WABlock } from "./types";

export type Opt = [string | number, string];

export type FieldSpec =
  | { kind: "text"; key: string; label: string; max: number; placeholder?: string; hint?: string }
  | { kind: "textarea"; key: string; label: string; max: number; rows?: number; placeholder?: string; hint?: string }
  | { kind: "number"; key: string; label: string; min?: number; max?: number; optional?: boolean; hint?: string }
  | { kind: "select"; key: string; label: string; options: Opt[] }
  | { kind: "toggle"; key: string; label: string; hint?: string }
  | { kind: "emoji"; key: string; label: string }
  | { kind: "media"; key: string; label: string; optional?: boolean }
  | { kind: "medias"; key: string; label: string; max: number }
  | { kind: "action"; key: string; label: string }
  | { kind: "btn"; key: string; label: string }
  | { kind: "date"; key: string; label: string }
  | { kind: "lines"; key: string; label: string; max: number; hint?: string }
  | { kind: "list"; key: string; label: string; max: number; item: FieldSpec[]; title: (item: any) => string; make: () => any };

export const NO_ACTION: WAAction = { type: "none", page: null, url: null, phone: null };

export const ACTION_TYPES: Opt[] = [
  ["none", "Hech narsa"],
  ["page", "Sahifaga o'tish"],
  ["url", "Havola"],
  ["bot", "Botga qaytish"],
  ["phone", "Qo'ng'iroq"],
  ["share", "Ulashish"],
  ["cart", "Savatchani ochish"],
];

export const FIELD_TYPES: Opt[] = [
  ["text", "Matn"],
  ["textarea", "Katta matn"],
  ["phone", "Telefon"],
  ["email", "Email"],
  ["number", "Son"],
  ["select", "Ro'yxatdan tanlash"],
  ["radio", "Variantlar (tugma)"],
  ["checkbox", "Belgilash (ha/yo'q)"],
  ["date", "Sana"],
];

export const FORM_FIELD_SPEC: FieldSpec[] = [
  { kind: "text", key: "label", label: "Savol / nomi", max: 100 },
  { kind: "select", key: "type", label: "Turi", options: FIELD_TYPES },
  { kind: "text", key: "placeholder", label: "Ichidagi izoh", max: 100 },
  { kind: "toggle", key: "required", label: "Majburiy" },
  { kind: "lines", key: "options", label: "Variantlar (har biri yangi qatorda)", max: 20, hint: "«Ro'yxatdan tanlash» va «Variantlar» turlari uchun" },
];

export const newField = (): FormField => ({ id: uid("f"), type: "text", label: "Yangi savol", placeholder: "", required: false, options: [] });

const ALIGN: Opt[] = [
  ["left", "Chapda"],
  ["center", "O'rtada"],
];

export type BlockSpec = {
  title: string;
  icon: string;
  desc: string;
  category: "Asosiy" | "Media" | "Savdo" | "Ma'lumot" | "Forma";
  make: () => Omit<WABlock, "id">;
  fields: FieldSpec[];
  summary: (b: any) => string;
};

export const BLOCK_SPECS: Record<BlockType, BlockSpec> = {
  hero: {
    title: "Banner",
    icon: "🌟",
    desc: "Katta sarlavha, rasm va tugma",
    category: "Asosiy",
    make: () => ({ type: "hero", title: "Sarlavha", subtitle: "Qisqa tavsif", media_id: null, emoji: "✨", align: "center", button: null }),
    fields: [
      { kind: "text", key: "title", label: "Sarlavha", max: 120 },
      { kind: "textarea", key: "subtitle", label: "Tavsif", max: 400, rows: 2 },
      { kind: "media", key: "media_id", label: "Rasm", optional: true },
      { kind: "emoji", key: "emoji", label: "Emoji (rasm bo'lmasa)" },
      { kind: "select", key: "align", label: "Joylashuv", options: ALIGN },
      { kind: "btn", key: "button", label: "Tugma" },
    ],
    summary: (b) => b.title,
  },
  heading: {
    title: "Sarlavha",
    icon: "🔠",
    desc: "Bo'lim sarlavhasi",
    category: "Asosiy",
    make: () => ({ type: "heading", text: "Bo'lim nomi", size: 2, align: "left" }),
    fields: [
      { kind: "text", key: "text", label: "Matn", max: 160 },
      { kind: "select", key: "size", label: "O'lcham", options: [[1, "Katta"], [2, "O'rta"], [3, "Kichik"]] },
      { kind: "select", key: "align", label: "Joylashuv", options: ALIGN },
    ],
    summary: (b) => b.text,
  },
  text: {
    title: "Matn",
    icon: "📝",
    desc: "Paragraf, **qalin** va havolalar",
    category: "Asosiy",
    make: () => ({ type: "text", text: "Matningizni yozing. **Qalin** qilish uchun ikki yulduzcha ishlating.", align: "left", muted: false }),
    fields: [
      { kind: "textarea", key: "text", label: "Matn", max: 4000, rows: 6, hint: "**so'z** — qalin; https://... — havola" },
      { kind: "select", key: "align", label: "Joylashuv", options: ALIGN },
      { kind: "toggle", key: "muted", label: "Xira rang (izoh uchun)" },
    ],
    summary: (b) => b.text,
  },
  button: {
    title: "Tugma",
    icon: "🔘",
    desc: "Sahifa, havola, qo'ng'iroq...",
    category: "Asosiy",
    make: () => ({ type: "button", text: "Batafsil", style: "primary", action: { ...NO_ACTION } }),
    fields: [
      { kind: "text", key: "text", label: "Tugma matni", max: 40 },
      { kind: "select", key: "style", label: "Ko'rinish", options: [["primary", "Asosiy"], ["secondary", "Yumshoq"], ["outline", "Chiziqli"]] },
      { kind: "action", key: "action", label: "Bosilganda" },
    ],
    summary: (b) => b.text,
  },
  divider: {
    title: "Ajratgich",
    icon: "➖",
    desc: "Chiziq yoki bo'sh joy",
    category: "Asosiy",
    make: () => ({ type: "divider", style: "line", size: "m" }),
    fields: [
      { kind: "select", key: "style", label: "Turi", options: [["line", "Chiziq"], ["space", "Bo'sh joy"]] },
      { kind: "select", key: "size", label: "O'lcham", options: [["s", "Kichik"], ["m", "O'rta"], ["l", "Katta"]] },
    ],
    summary: (b) => (b.style === "line" ? "Chiziq" : "Bo'sh joy"),
  },
  image: {
    title: "Rasm",
    icon: "🖼️",
    desc: "Bitta rasm, izoh bilan",
    category: "Media",
    make: () => ({ type: "image", media_id: null, ratio: "auto", caption: "", action: { ...NO_ACTION } }),
    fields: [
      { kind: "media", key: "media_id", label: "Rasm" },
      { kind: "select", key: "ratio", label: "Shakl", options: [["auto", "Asl"], ["1:1", "Kvadrat"], ["4:3", "4:3"], ["16:9", "Keng"], ["3:4", "Tik"]] },
      { kind: "text", key: "caption", label: "Izoh", max: 200 },
      { kind: "action", key: "action", label: "Bosilganda" },
    ],
    summary: (b) => b.caption || (b.media_id ? "Rasm" : "⚠️ Rasm yuklanmagan"),
  },
  gallery: {
    title: "Galereya",
    icon: "🎞️",
    desc: "Bir nechta rasm to'ri",
    category: "Media",
    make: () => ({ type: "gallery", media_ids: [], columns: 2 }),
    fields: [
      { kind: "medias", key: "media_ids", label: "Rasmlar", max: 24 },
      { kind: "select", key: "columns", label: "Ustunlar", options: [[2, "2 ta"], [3, "3 ta"]] },
    ],
    summary: (b) => (b.media_ids.length ? `${b.media_ids.length} ta rasm` : "⚠️ Rasm yo'q"),
  },
  video: {
    title: "Video",
    icon: "🎬",
    desc: "YouTube videosi",
    category: "Media",
    make: () => ({ type: "video", url: "https://youtu.be/", caption: "" }),
    fields: [
      { kind: "text", key: "url", label: "YouTube havolasi", max: 300, placeholder: "https://youtu.be/..." },
      { kind: "text", key: "caption", label: "Izoh", max: 200 },
    ],
    summary: (b) => b.url,
  },
  products: {
    title: "Mahsulotlar",
    icon: "🛍️",
    desc: "Katalog va savatcha",
    category: "Savdo",
    make: () => ({
      type: "products",
      title: "Mahsulotlar",
      columns: 2,
      items: [{ id: uid("p"), title: "Mahsulot", price: 100000, old_price: null, media_id: null, emoji: "📦", text: "", badge: "" }],
    }),
    fields: [
      { kind: "text", key: "title", label: "Bo'lim nomi", max: 80 },
      { kind: "select", key: "columns", label: "Ko'rinish", options: [[2, "Kartochkalar (2 ustun)"], [1, "Ro'yxat"]] },
      {
        kind: "list",
        key: "items",
        label: "Mahsulotlar",
        max: 100,
        title: (p) => `${p.emoji || "📦"} ${p.title} — ${Number(p.price).toLocaleString("ru-RU")}`,
        make: () => ({ id: uid("p"), title: "Yangi mahsulot", price: 0, old_price: null, media_id: null, emoji: "📦", text: "", badge: "" }),
        item: [
          { kind: "text", key: "title", label: "Nomi", max: 100 },
          { kind: "number", key: "price", label: "Narxi", min: 0, max: 1e12 },
          { kind: "number", key: "old_price", label: "Eski narxi (chegirma uchun)", min: 0, max: 1e12, optional: true },
          { kind: "media", key: "media_id", label: "Rasm", optional: true },
          { kind: "emoji", key: "emoji", label: "Emoji (rasm bo'lmasa)" },
          { kind: "textarea", key: "text", label: "Tavsif", max: 500, rows: 2 },
          { kind: "text", key: "badge", label: "Belgi (masalan: Yangi, -20%)", max: 20 },
        ],
      },
    ],
    summary: (b) => `${b.title || "Mahsulotlar"} · ${b.items.length} ta`,
  },
  pricing: {
    title: "Tariflar",
    icon: "💳",
    desc: "Narx rejalari solishtirish",
    category: "Savdo",
    make: () => ({
      type: "pricing",
      items: [
        { name: "Standart", price: "100 000 so'm", period: "oy", features: ["Imkoniyat 1", "Imkoniyat 2"], highlight: false, button: null },
        { name: "Premium", price: "200 000 so'm", period: "oy", features: ["Hammasi", "Ustuvor yordam"], highlight: true, button: null },
      ],
    }),
    fields: [
      {
        kind: "list",
        key: "items",
        label: "Tariflar",
        max: 6,
        title: (p) => `${p.highlight ? "⭐ " : ""}${p.name} — ${p.price}`,
        make: () => ({ name: "Tarif", price: "", period: "", features: [], highlight: false, button: null }),
        item: [
          { kind: "text", key: "name", label: "Nomi", max: 60 },
          { kind: "text", key: "price", label: "Narxi (matn)", max: 40, placeholder: "150 000 so'm" },
          { kind: "text", key: "period", label: "Davri", max: 30, placeholder: "oy" },
          { kind: "lines", key: "features", label: "Imkoniyatlar (har biri yangi qatorda)", max: 12 },
          { kind: "toggle", key: "highlight", label: "Ajratib ko'rsatish" },
          { kind: "btn", key: "button", label: "Tugma" },
        ],
      },
    ],
    summary: (b) => b.items.map((p: any) => p.name).join(" · "),
  },
  features: {
    title: "Afzalliklar",
    icon: "✅",
    desc: "Emoji + sarlavha + matn kartochkalari",
    category: "Ma'lumot",
    make: () => ({
      type: "features",
      columns: 2,
      items: [
        { emoji: "🚚", title: "Tez yetkazish", text: "1 kunda" },
        { emoji: "💳", title: "Qulay to'lov", text: "Click, Payme" },
      ],
    }),
    fields: [
      { kind: "select", key: "columns", label: "Ustunlar", options: [[2, "2 ta"], [1, "1 ta"]] },
      {
        kind: "list",
        key: "items",
        label: "Kartochkalar",
        max: 24,
        title: (f) => `${f.emoji} ${f.title}`,
        make: () => ({ emoji: "⭐", title: "Sarlavha", text: "" }),
        item: [
          { kind: "emoji", key: "emoji", label: "Emoji" },
          { kind: "text", key: "title", label: "Sarlavha", max: 80 },
          { kind: "textarea", key: "text", label: "Matn", max: 300, rows: 2 },
        ],
      },
    ],
    summary: (b) => b.items.map((f: any) => f.title).join(" · "),
  },
  links: {
    title: "Ro'yxat",
    icon: "📋",
    desc: "Menyu, havolalar, dastur",
    category: "Ma'lumot",
    make: () => ({ type: "links", items: [{ emoji: "📄", title: "Bo'lim", subtitle: "", action: { ...NO_ACTION } }] }),
    fields: [
      {
        kind: "list",
        key: "items",
        label: "Qatorlar",
        max: 30,
        title: (i) => `${i.emoji} ${i.title}`,
        make: () => ({ emoji: "📄", title: "Yangi qator", subtitle: "", action: { ...NO_ACTION } }),
        item: [
          { kind: "emoji", key: "emoji", label: "Emoji" },
          { kind: "text", key: "title", label: "Sarlavha", max: 80 },
          { kind: "text", key: "subtitle", label: "Izoh", max: 120 },
          { kind: "action", key: "action", label: "Bosilganda" },
        ],
      },
    ],
    summary: (b) => b.items.map((i: any) => i.title).join(" · "),
  },
  stats: {
    title: "Raqamlar",
    icon: "🔢",
    desc: "10+ yil, 2000 mijoz...",
    category: "Ma'lumot",
    make: () => ({ type: "stats", items: [{ value: "10+", label: "yil" }, { value: "2000+", label: "mijoz" }] }),
    fields: [
      {
        kind: "list",
        key: "items",
        label: "Raqamlar",
        max: 6,
        title: (s) => `${s.value} ${s.label}`,
        make: () => ({ value: "100", label: "" }),
        item: [
          { kind: "text", key: "value", label: "Qiymat", max: 20 },
          { kind: "text", key: "label", label: "Izoh", max: 60 },
        ],
      },
    ],
    summary: (b) => b.items.map((s: any) => s.value).join(" · "),
  },
  faq: {
    title: "Savol-javob",
    icon: "❓",
    desc: "Ochiladigan savollar",
    category: "Ma'lumot",
    make: () => ({ type: "faq", items: [{ q: "Savol?", a: "Javob." }] }),
    fields: [
      {
        kind: "list",
        key: "items",
        label: "Savollar",
        max: 40,
        title: (i) => i.q,
        make: () => ({ q: "Yangi savol?", a: "Javob." }),
        item: [
          { kind: "text", key: "q", label: "Savol", max: 200 },
          { kind: "textarea", key: "a", label: "Javob", max: 1500, rows: 3 },
        ],
      },
    ],
    summary: (b) => `${b.items.length} ta savol`,
  },
  contacts: {
    title: "Kontaktlar",
    icon: "📞",
    desc: "Telefon, Telegram, manzil",
    category: "Ma'lumot",
    make: () => ({ type: "contacts", phone: "+998 90 000 00 00", telegram: null, instagram: null, website: null, address: "", map_url: null }),
    fields: [
      { kind: "text", key: "phone", label: "Telefon", max: 20, placeholder: "+998 90 123 45 67" },
      { kind: "text", key: "telegram", label: "Telegram", max: 33, placeholder: "@username" },
      { kind: "text", key: "instagram", label: "Instagram", max: 33, placeholder: "@username" },
      { kind: "text", key: "website", label: "Veb-sayt", max: 300, placeholder: "https://..." },
      { kind: "text", key: "address", label: "Manzil", max: 200 },
      { kind: "text", key: "map_url", label: "Xarita havolasi", max: 500, placeholder: "https://maps.google.com/..." },
    ],
    summary: (b) => [b.phone, b.telegram && `@${b.telegram}`, b.address].filter(Boolean).join(" · "),
  },
  countdown: {
    title: "Ortga sanash",
    icon: "⏳",
    desc: "Tadbir yoki aksiyagacha",
    category: "Ma'lumot",
    make: () => ({ type: "countdown", title: "Aksiya tugashiga", date: new Date(Date.now() + 7 * 86400000).toISOString(), done_text: "Boshlandi! 🎉" }),
    fields: [
      { kind: "text", key: "title", label: "Sarlavha", max: 120 },
      { kind: "date", key: "date", label: "Sana va vaqt" },
      { kind: "text", key: "done_text", label: "Vaqt tugaganda", max: 200 },
    ],
    summary: (b) => `${b.title} · ${new Date(b.date).toLocaleString("ru-RU")}`,
  },
  form: {
    title: "Forma",
    icon: "🧾",
    desc: "Ariza, yozilish, so'rovnoma",
    category: "Forma",
    make: () => ({
      type: "form",
      title: "Ariza qoldiring",
      fields: [
        { id: uid("f"), type: "text", label: "Ismingiz", placeholder: "", required: true, options: [] },
        { id: uid("f"), type: "phone", label: "Telefon", placeholder: "+998 90 123 45 67", required: true, options: [] },
      ],
      submit_text: "Yuborish",
      success_text: "✅ Yuborildi! Tez orada bog'lanamiz.",
    }),
    fields: [
      { kind: "text", key: "title", label: "Sarlavha", max: 120 },
      { kind: "list", key: "fields", label: "Savollar", max: 20, title: (f) => `${f.required ? "* " : ""}${f.label}`, make: newField, item: FORM_FIELD_SPEC },
      { kind: "text", key: "submit_text", label: "Tugma matni", max: 40 },
      { kind: "textarea", key: "success_text", label: "Yuborilgandan keyin", max: 300, rows: 2 },
    ],
    summary: (b) => `${b.title || "Forma"} · ${b.fields.length} ta savol`,
  },
};

export const CATEGORIES: BlockSpec["category"][] = ["Asosiy", "Media", "Savdo", "Ma'lumot", "Forma"];

export function newBlock(type: BlockType): WABlock {
  return { id: uid("b"), hidden: false, ...BLOCK_SPECS[type].make() } as WABlock;
}

/** Nusxa: yangi id'lar bilan (mahsulot id'lari ilova bo'ylab takrorlanmasligi kerak). */
export function cloneBlock(block: WABlock): WABlock {
  const copy = JSON.parse(JSON.stringify(block)) as WABlock;
  copy.id = uid("b");
  if (copy.type === "products") copy.items = copy.items.map((p) => ({ ...p, id: uid("p") }));
  return copy;
}
