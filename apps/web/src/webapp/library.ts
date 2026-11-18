// Komponentlar kutubxonasi: tayyor, lekin to'liq tahrirlanadigan erkin bo'laklar.
// Har biri oddiy elementlar daraxti (konteyner, matn, tugma...) — qo'yilgandan keyin istalgan qismini
// o'zgartirish, o'chirish yoki boshqa joyga ko'chirish mumkin. Ranglar asosan mavzu ranglari ($primary,
// $surface...) — ilova mavzusi yoki tun rejimi o'zgarsa, komponent ham moslashadi.
// Kelajakda AI ham aynan shu kutubxonadan «so'z boyligi» sifatida foydalanadi.
import { uid, type BoxNode, type ButtonNode, type WAAction, type WANode, type WAStyle } from "./types";

const NONE: WAAction = { type: "none", page: null, url: null, phone: null };
type Extra = Partial<Omit<WANode, "kind" | "id">> & Record<string, unknown>;

export function box(props: Partial<BoxNode>, children: WANode[]): BoxNode {
  return {
    id: uid("n"),
    kind: "box",
    layout: "column",
    gap: 12,
    align: "stretch",
    justify: "start",
    wrap: true,
    columns: 2,
    columns_wide: null,
    action: null,
    ...props,
    children,
  };
}
const row = (children: WANode[], props: Partial<BoxNode> = {}) => box({ layout: "row", align: "center", wrap: false, ...props }, children);
const grid = (cols: number, children: WANode[], props: Partial<BoxNode> = {}) => box({ layout: "grid", columns: cols, ...props }, children);

export function text(t: string, tag: "h1" | "h2" | "h3" | "p" | "small" = "p", style?: WAStyle, extra: Extra = {}): WANode {
  return { id: uid("n"), kind: "text", text: t, tag, style: style ?? null, ...extra } as WANode;
}
export function button(
  t: string,
  variant: ButtonNode["variant"] = "primary",
  style?: WAStyle,
  icon: string | null = null,
  extra: Extra = {},
): WANode {
  return { id: uid("n"), kind: "button", text: t, variant, icon, action: { ...NONE }, style: style ?? null, ...extra } as WANode;
}
export function icon(name: string, size = 28, style?: WAStyle, extra: Extra = {}): WANode {
  return { id: uid("n"), kind: "icon", icon: name, size, emoji: "", action: null, style: style ?? null, ...extra } as WANode;
}
const emoji = (e: string, size = 32, style?: WAStyle, extra: Extra = {}): WANode =>
  ({ id: uid("n"), kind: "icon", icon: "Star", size, emoji: e, action: null, style: style ?? null, ...extra }) as WANode;
const image = (ratio: "1:1" | "4:3" | "16:9" | "3:4" | "auto" = "4:3", style?: WAStyle): WANode =>
  ({ id: uid("n"), kind: "image", media_id: null, fit: "cover", ratio, action: null, style: style ?? null }) as WANode;
const spacer = (size = 16): WANode => ({ id: uid("n"), kind: "spacer", size }) as WANode;
const divider = (style?: WAStyle): WANode => ({ id: uid("n"), kind: "divider", style: style ?? null }) as WANode;
const progress = (value: number, label = "", extra: Extra = {}): WANode =>
  ({ id: uid("n"), kind: "progress", value, label, show_value: true, bar: null, thickness: 8, shape: "bar", ...extra }) as WANode;
const rating = (value = 4.8, extra: Extra = {}): WANode =>
  ({ id: uid("n"), kind: "rating", value, size: 16, star: null, show_value: false, ...extra }) as WANode;
const timer = (days = 3, extra: Extra = {}): WANode =>
  ({
    id: uid("n"),
    kind: "timer",
    until: new Date(Date.now() + days * 86400000).toISOString().slice(0, 19),
    done_text: "Aksiya tugadi",
    labels: true,
    ...extra,
  }) as WANode;
const mapNode = (query: string, height = 200): WANode => ({ id: uid("n"), kind: "map", query, zoom: 15, height }) as WANode;
const video = (url = ""): WANode => ({ id: uid("n"), kind: "video", url }) as WANode;

// Tez-tez ishlatiladigan uslublar
const CARD: WAStyle = { bg: "$surface", radius: 20, px: 16, py: 16, shadow: "s" };
const SOFT: WAStyle = { bg: "$primary", bg_alpha: 10, radius: 16, px: 14, py: 14 };
const CHIP: WAStyle = { bg: "$primary", bg_alpha: 12, color: "$primary", radius: 999, px: 10, py: 4, size: 12, weight: 700, width: "fit" };
const MUTED: WAStyle = { color: "$hint" };
const media = (from: string, to: string, extra: WAStyle = {}): WAStyle => ({ bg: from, bg2: to, bg_angle: 135, radius: 16, aspect: "4:3", ...extra });

export type LibraryItem = {
  key: string;
  title: string;
  desc: string;
  cat: string;
  tags?: string;
  make: () => BoxNode;
};

export const CATEGORIES: { key: string; title: string; icon: string }[] = [
  { key: "hero", title: "Bannerlar", icon: "🌅" },
  { key: "nav", title: "Navigatsiya", icon: "🧭" },
  { key: "cards", title: "Kartalar", icon: "🃏" },
  { key: "carousel", title: "Karusel", icon: "🎠" },
  { key: "features", title: "Afzalliklar", icon: "✅" },
  { key: "shop", title: "Do'kon", icon: "🛍" },
  { key: "pricing", title: "Narxlar", icon: "💎" },
  { key: "social", title: "Sharhlar", icon: "💬" },
  { key: "stats", title: "Raqamlar", icon: "📊" },
  { key: "content", title: "Kontent", icon: "📄" },
  { key: "cta", title: "Chaqiruv", icon: "📣" },
  { key: "team", title: "Jamoa va profil", icon: "👥" },
  { key: "media", title: "Media va xarita", icon: "🎬" },
  { key: "footer", title: "Pastki qism", icon: "⬇️" },
  { key: "atoms", title: "Elementlar", icon: "🧩" },
];

const blob = (color: string, size: number, pos: WAStyle, loop: "float" | "breathe" = "float"): WANode =>
  box({ loop, style: { pos: "absolute", w: size, h: size, radius: 999, bg: color, blur: 40, opacity: 70, ...pos } }, []);

export const LIBRARY: LibraryItem[] = [
  // ------------------------------------------------------------ Bannerlar
  {
    key: "hero-gradient",
    cat: "hero",
    title: "Gradient banner",
    desc: "Katta sarlavha, matn va 2 tugma",
    make: () =>
      box({ align: "center", gap: 14, anim: "up", style: { bg: "#4f46e5", bg2: "#06b6d4", bg_angle: 135, py: 44, px: 22, radius: 28, color: "#ffffff", align: "center" } }, [
        text("YANGI", "small", { ...CHIP, bg: "#ffffff", bg_alpha: 20, color: "#ffffff" }),
        text("Biznesingiz uchun eng yaxshi yechim", "h1", { size: 32 }),
        text("Qisqa va aniq taklif: mijoz nima oladi va nega aynan siz.", "p", { opacity: 90 }),
        row([button("Boshlash", "primary", { bg: "#ffffff", color: "#111827" }, "ArrowRight"), button("Batafsil", "outline", { color: "#ffffff", border: 1, border_color: "#ffffff" })], {
          justify: "center",
          gap: 10,
          wrap: true,
        }),
      ]),
  },
  {
    key: "hero-glass",
    cat: "hero",
    title: "Shisha banner",
    desc: "Suzuvchi rangli dog'lar ustida shaffof karta",
    tags: "glass blur",
    make: () =>
      box({ style: { bg: "#0f172a", radius: 28, py: 36, px: 18, overflow: "hidden", min_height: 300 }, justify: "center" }, [
        blob("#7c3aed", 180, { top: -40, left: -40 }),
        blob("#06b6d4", 160, { bottom: -50, right: -30 }),
        blob("#f43f5e", 110, { top: 90, right: 40 }, "breathe"),
        box({ gap: 10, anim: "zoom", style: { bg: "#ffffff", bg_alpha: 10, backdrop: 18, radius: 24, px: 20, py: 24, border: 1, border_color: "#ffffff", color: "#ffffff", z: 1 } }, [
          text("✦ Premium", "small", { color: "#e0e7ff", weight: 700, letter: 10 }),
          text("Kelajak dizayni bugun", "h1", { size: 30 }),
          text("Shaffof «shisha» effekti, yumshoq ranglar va harakat.", "p", { opacity: 85 }),
          button("Boshlash", "primary", { bg: "#ffffff", color: "#0f172a", radius: 999 }, "Sparkles"),
        ]),
      ]),
  },
  {
    key: "hero-split",
    cat: "hero",
    title: "Ikki ustunli banner",
    desc: "Chapda matn, o'ngda rasm (keng oynada yonma-yon)",
    make: () =>
      grid(1, [
        box({ gap: 12, justify: "center" }, [
          text("2025-yil yangiligi", "small", CHIP),
          text("Sizning mahsulotingiz — **bir qarashda**", "h1"),
          text("Qisqacha tavsif: muammo, yechim va natija bir jumlada.", "p", MUTED),
          row([button("Buyurtma berish", "primary", undefined, "ShoppingBag"), button("Katalog", "ghost")], { gap: 8, wrap: true }),
        ]),
        box({ justify: "center", align: "center", style: media("#fde68a", "#f97316", { aspect: "1:1", radius: 28 }) }, [emoji("📦", 72, undefined, { loop: "float" })]),
      ], { columns_wide: 2, gap: 20, align: "center" }),
  },
  {
    key: "hero-type",
    cat: "hero",
    title: "Katta tipografiya",
    desc: "Minimal: faqat yirik gradient sarlavha",
    make: () =>
      box({ gap: 10, style: { py: 30 } }, [
        text("Kreativ agentlik", "small", { ...MUTED, uppercase: true, letter: 18, weight: 700 }),
        text("Biz g'oyalarni brendga aylantiramiz", "h1", { size: 44, weight: 800, line: 1.02, letter: -3, text_grad: "$primary", text_grad2: "#ec4899", bg_angle: 90 }, { anim: "blur" }),
        text("Strategiya · Dizayn · Marketing", "p", MUTED),
      ]),
  },
  {
    key: "hero-app",
    cat: "hero",
    title: "Ilova taqdimoti",
    desc: "Reyting, belgi va telefon maketi",
    make: () =>
      box({ align: "center", gap: 14, style: { bg: "$primary", bg_alpha: 8, radius: 28, py: 32, px: 18, align: "center" } }, [
        row([rating(4.9), text("10 000+ foydalanuvchi", "small")], { gap: 8, justify: "center" }),
        text("Hammasi bitta ilovada", "h1", { size: 30 }),
        text("Buyurtma, to'lov va yetkazib berish — bir necha bosishda.", "p", MUTED),
        button("Hoziroq sinab ko'ring", "primary", { radius: 999, px: 22 }, "ArrowRight", { loop: "pulse" }),
        box({ align: "center", justify: "center", style: { w: 170, h: 250, radius: 34, bg: "$surface", border: 6, border_color: "#111111", shadow: "xl", mt: 10 }, anim: "up" }, [
          emoji("📱", 56),
          text("Sizning ekraningiz", "small"),
        ]),
      ]),
  },
  {
    key: "hero-neon",
    cat: "hero",
    title: "Neon tun",
    desc: "Qora fon, porlovchi sarlavha va tugma",
    make: () =>
      box({ align: "center", gap: 14, style: { bg: "#05010f", bg2: "#1e0b3a", bg_type: "radial", radius: 28, py: 44, px: 20, align: "center", color: "#ffffff" } }, [
        text("LIVE · 21:00", "small", { color: "#f0abfc", weight: 700, letter: 20 }),
        text("Neon kecha", "h1", { size: 46, weight: 800, text_grad: "#f0abfc", text_grad2: "#22d3ee", bg_angle: 90 }),
        text("Eng yaxshi DJ'lar, yorqin chiroqlar va unutilmas kayfiyat.", "p", { opacity: 80 }),
        button("Chipta olish", "primary", { bg: "#d946ef", color: "#ffffff", radius: 999, shadow: "glow", shadow_color: "#d946ef" }, "Ticket", { loop: "glow" }),
      ]),
  },
  {
    key: "hero-photo",
    cat: "hero",
    title: "Fon rasmli banner",
    desc: "Rasm ustida matn (Uslub → Fon rasmi)",
    make: () =>
      box({ justify: "end", gap: 8, style: { min_height: 320, radius: 26, px: 20, py: 22, bg: "#334155", bg2: "#0f172a", overlay: 35, color: "#ffffff" } }, [
        text("Sayohat · Samarqand", "small", { color: "#ffffff", opacity: 85 }),
        text("Afsonaviy shaharga 3 kunlik tur", "h1", { size: 28 }),
        row([button("Joy band qilish", "primary", { bg: "#ffffff", color: "#0f172a" }), text("1 200 000 so'm", "p", { weight: 700 })], { gap: 12, wrap: true }),
      ]),
  },
  {
    key: "announce",
    cat: "hero",
    title: "Yuguruvchi e'lon",
    desc: "Cheksiz harakatlanuvchi lenta",
    tags: "marquee",
    make: () =>
      box({ layout: "marquee", gap: 28, speed: 18, style: { bg: "$primary", color: "$on_primary", py: 10, radius: 14, weight: 700 } }, [
        text("🔥 Bugun barcha mahsulotlarga −20%", "p", { nowrap: true }),
        text("🚚 Yetkazib berish bepul", "p", { nowrap: true }),
        text("🎁 Har bir buyurtmaga sovg'a", "p", { nowrap: true }),
      ]),
  },

  // ------------------------------------------------------------ Navigatsiya
  {
    key: "header",
    cat: "nav",
    title: "Yuqori panel",
    desc: "Logotip, nom va ikonka tugmalar",
    make: () =>
      row([
        box({ align: "center", justify: "center", style: { w: 40, h: 40, radius: 12, bg: "$primary", color: "$on_primary" } }, [icon("Zap", 20, { color: "$on_primary" })]),
        box({ gap: 0, style: { grow: true } }, [text("Brend nomi", "h3"), text("Onlayn do'kon", "small")]),
        box({ align: "center", justify: "center", style: { w: 40, h: 40, radius: 999, bg: "$text", bg_alpha: 6 } }, [icon("Search", 19, { color: "$text" })]),
        box({ align: "center", justify: "center", style: { w: 40, h: 40, radius: 999, bg: "$text", bg_alpha: 6 } }, [icon("Bell", 19, { color: "$text" })]),
      ], { gap: 10, style: { py: 4 } }),
  },
  {
    key: "tabbar",
    cat: "nav",
    title: "Pastki menyu",
    desc: "Ekran pastiga yopishgan 4 ta bo'lim",
    tags: "fixed bottom nav",
    make: () =>
      row(
        [
          ["House", "Asosiy", true],
          ["Search", "Qidiruv", false],
          ["ShoppingBag", "Savat", false],
          ["User", "Profil", false],
        ].map(([ic, l, on]) =>
          box({ align: "center", gap: 2, style: { grow: true, color: on ? "$primary" : "$hint" } }, [icon(ic as string, 22, { color: on ? "$primary" : "$hint" }), text(l as string, "small", { size: 11, weight: 600, color: on ? "$primary" : "$hint" })]),
        ),
        { justify: "around", style: { pos: "sticky", bottom: 8, z: 20, bg: "$surface", bg_alpha: 88, backdrop: 16, radius: 22, py: 10, px: 6, shadow: "l", border: 1, border_color: "$line" } },
      ),
  },
  {
    key: "chips",
    cat: "nav",
    title: "Kategoriya chiplari",
    desc: "Gorizontal suriladigan filtrlar",
    make: () =>
      box({ layout: "scroll", gap: 8, item_w: 110 }, [
        button("Hammasi", "primary", { radius: 999, py: 8 }),
        ...["Yangi", "Mashhur", "Chegirma", "Sovg'a", "Premium"].map((l) => button(l, "secondary", { radius: 999, py: 8 })),
      ]),
  },
  {
    key: "tabs",
    cat: "nav",
    title: "Yorliqlar (tabs)",
    desc: "Bosilganda bo'limlar almashadi",
    make: () =>
      box({ layout: "tabs", tabs_style: "pills" }, [
        box({ name: "Tavsif", style: { ...CARD } }, [text("Mahsulot haqida batafsil ma'lumot shu yerda.", "p")]),
        box({ name: "Tarkibi", style: { ...CARD } }, [text("• Paxta 95%\n• Elastan 5%", "p")]),
        box({ name: "Yetkazish", style: { ...CARD } }, [text("Toshkent bo'ylab 1 kunda, viloyatlarga 2–3 kunda.", "p")]),
      ]),
  },
  {
    key: "tabs-seg",
    cat: "nav",
    title: "Segment yorliqlar",
    desc: "iOS uslubidagi almashtirgich",
    make: () =>
      box({ layout: "tabs", tabs_style: "segmented" }, [
        box({ name: "Oylik", gap: 4, style: { ...CARD, align: "center" } }, [text("99 000 so'm", "h2"), text("har oy", "small")]),
        box({ name: "Yillik", gap: 4, style: { ...CARD, align: "center" } }, [text("990 000 so'm", "h2"), text("2 oy bepul", "small", { color: "#16a34a" })]),
      ]),
  },
  {
    key: "menu-list",
    cat: "nav",
    title: "Menyu ro'yxati",
    desc: "Ikonka, nom va strelka — sozlamalar uslubida",
    make: () =>
      box({ gap: 0, style: { bg: "$surface", radius: 18, overflow: "hidden" } }, [
        ...[
          ["Package", "Buyurtmalarim", "#2563eb"],
          ["Heart", "Sevimlilar", "#e11d48"],
          ["MapPin", "Manzillar", "#16a34a"],
          ["Settings", "Sozlamalar", "#64748b"],
        ].flatMap(([ic, l, c], i) => [
          ...(i ? [divider({ mt: 0, mb: 0 })] : []),
          row([
            box({ align: "center", justify: "center", style: { w: 34, h: 34, radius: 10, bg: c } }, [icon(ic, 18, { color: "#ffffff" })]),
            text(l, "p", { grow: true, weight: 600 }),
            icon("ChevronRight", 18, { color: "$hint" }),
          ], { gap: 12, style: { px: 14, py: 12 }, hover: { bg: "$text", bg_alpha: 4 } }),
        ]),
      ]),
  },

  // ------------------------------------------------------------ Kartalar
  {
    key: "card-product",
    cat: "cards",
    title: "Mahsulot kartasi",
    desc: "Rasm, belgi, nom, narx va tugma",
    make: () =>
      box({ gap: 10, style: { ...CARD, px: 12, py: 12, max_width: 300 }, hover: { ty: -4, shadow: "l" } }, [
        box({ layout: "stack", style: media("#e0e7ff", "#c7d2fe", { aspect: "1:1" }) }, [
          box({ align: "center", justify: "center" }, [emoji("👟", 64)]),
          box({ align: "start", style: { px: 8, py: 8 } }, [text("−30%", "small", { ...CHIP, bg: "#ef4444", bg_alpha: 100, color: "#ffffff" })]),
        ]),
        text("Krossovka Air Lite", "h3"),
        row([text("349 000 so'm", "p", { weight: 800, color: "$primary" }), text("499 000", "small", { decoration: "line-through" })], { gap: 8 }),
        button("Savatga", "primary", { radius: 12 }, "ShoppingCart"),
      ]),
  },
  {
    key: "card-overlay",
    cat: "cards",
    title: "Rasm ustida matn",
    desc: "Qatlamli karta (stack)",
    tags: "stack overlay",
    make: () =>
      box({ layout: "stack", style: { radius: 24, overflow: "hidden", aspect: "4:3" }, hover: { scale: 102 } }, [
        box({ style: { bg: "#0ea5e9", bg2: "#6366f1", bg_angle: 135 } }, []),
        box({ justify: "end", gap: 4, style: { px: 18, py: 18, bg: "#000000", bg_alpha: 30, color: "#ffffff" } }, [
          text("Kolleksiya", "small", { color: "#ffffff", opacity: 80 }),
          text("Yozgi to'plam 2025", "h2"),
          button("Ko'rish", "link", { color: "#ffffff" }, "ArrowRight"),
        ]),
      ]),
  },
  {
    key: "card-service",
    cat: "cards",
    title: "Xizmat kartasi",
    desc: "Ikonka doira, sarlavha, matn, havola",
    make: () =>
      box({ gap: 10, style: { ...CARD, py: 20 }, hover: { border: 1, border_color: "$primary" } }, [
        box({ align: "center", justify: "center", style: { w: 52, h: 52, radius: 16, bg: "$primary", bg_alpha: 12 } }, [icon("Rocket", 26)]),
        text("Veb-sayt yaratish", "h3"),
        text("Zamonaviy, tez va mobilga moslashgan sayt 7 kunda.", "p", MUTED),
        button("Batafsil", "link", undefined, "ArrowRight"),
      ]),
  },
  {
    key: "card-glass",
    cat: "cards",
    title: "Shisha karta",
    desc: "Gradient fonda shaffof karta",
    make: () =>
      box({ style: { bg: "#ec4899", bg2: "#8b5cf6", bg_angle: 120, radius: 26, px: 18, py: 26 } }, [
        box({ gap: 6, style: { bg: "#ffffff", bg_alpha: 16, backdrop: 14, radius: 20, px: 18, py: 18, color: "#ffffff", border: 1, border_color: "#ffffff" } }, [
          row([icon("CreditCard", 22, { color: "#ffffff" }), text("VISA", "small", { color: "#ffffff", weight: 800, letter: 10 })], { justify: "between" }),
          spacer(18),
          text("**** **** **** 4242", "h3", { letter: 12 }),
          row([text("Sardor A.", "small", { color: "#ffffff" }), text("12/28", "small", { color: "#ffffff" })], { justify: "between" }),
        ]),
      ]),
  },
  {
    key: "card-brutal",
    cat: "cards",
    title: "Neo-brutal karta",
    desc: "Qalin chegara va qattiq soya",
    make: () =>
      box({ gap: 10, style: { bg: "#fde047", color: "#111111", radius: 14, px: 18, py: 18, border: 3, border_color: "#111111", shadow: "hard", shadow_color: "#111111" }, hover: { tx: -2, ty: -2 } }, [
        text("YANGI KURS", "small", { color: "#111111", weight: 800, letter: 10 }),
        text("Dizayn asoslari 30 kunda", "h2", { weight: 800 }),
        button("Yozilish →", "primary", { bg: "#111111", color: "#ffffff", radius: 10 }),
      ]),
  },
  {
    key: "card-coupon",
    cat: "cards",
    title: "Kupon",
    desc: "Uzilgan chiziqli chegirma kartasi",
    make: () =>
      row([
        box({ align: "center", justify: "center", gap: 0, style: { px: 16, py: 16, bg: "$primary", color: "$on_primary", radius: 16 } }, [text("−25%", "h2", { color: "$on_primary" })]),
        box({ gap: 2, style: { grow: true } }, [text("Birinchi buyurtmaga", "h3"), text("Promokod: SALOM25", "small", { weight: 700, color: "$primary" })]),
        button("Olish", "secondary", { radius: 999 }),
      ], { gap: 12, style: { bg: "$surface", radius: 20, px: 10, py: 10, border: 2, border_style: "dashed", border_color: "$primary" } }),
  },
  {
    key: "card-horizontal",
    cat: "cards",
    title: "Gorizontal karta",
    desc: "Chapda rasm, o'ngda ma'lumot",
    make: () =>
      row([
        box({ align: "center", justify: "center", style: { w: 88, h: 88, radius: 16, bg: "#fef3c7", bg2: "#fcd34d" } }, [emoji("🍔", 40)]),
        box({ gap: 4, style: { grow: true } }, [text("Klassik burger", "h3"), text("Mol go'shti, pishloq, maxsus sous", "small", { clamp: 2 }), text("45 000 so'm", "p", { weight: 800, color: "$primary" })]),
        box({ align: "center", justify: "center", style: { w: 36, h: 36, radius: 999, bg: "$primary" } }, [icon("Plus", 18, { color: "$on_primary" })]),
      ], { gap: 12, style: { ...CARD, px: 10, py: 10 } }),
  },
  {
    key: "alert",
    cat: "cards",
    title: "Xabar qutilari",
    desc: "Ma'lumot, muvaffaqiyat va ogohlantirish",
    make: () =>
      box({ gap: 8 }, [
        ...[
          ["Info", "#2563eb", "Yangi funksiya: endi to'lov Click orqali ham."],
          ["CircleCheck", "#16a34a", "Buyurtmangiz qabul qilindi."],
          ["AlertCircle", "#d97706", "Ish vaqti: 9:00 dan 21:00 gacha."],
        ].map(([ic, c, t]) =>
          row([icon(ic, 20, { color: c }), text(t, "p", { size: 14, grow: true })], { gap: 10, align: "start", style: { bg: c, bg_alpha: 10, radius: 14, px: 14, py: 12, border: 1, border_color: c } }),
        ),
      ]),
  },

  // ------------------------------------------------------------ Karusel
  {
    key: "promo-slider",
    cat: "carousel",
    title: "Aksiya slayderi",
    desc: "Avtomatik aylanadi, nuqtalar bilan",
    tags: "carousel slider autoplay",
    make: () =>
      box({ layout: "scroll", gap: 10, autoplay: 4, dots: true, item_w: 340 }, [
        ...[
          ["#f97316", "#ef4444", "🔥", "Qaynoq chegirmalar", "−50% gacha"],
          ["#0ea5e9", "#6366f1", "🎁", "Har buyurtmaga sovg'a", "Faqat shu hafta"],
          ["#10b981", "#059669", "🚚", "Bepul yetkazish", "200 000 so'mdan"],
        ].map(([a, b, e, t, s]) =>
          row([box({ gap: 4, style: { grow: true } }, [text(s, "small", { color: "#ffffff", opacity: 85 }), text(t, "h2", { color: "#ffffff" })]), emoji(e, 54)], {
            gap: 10,
            style: { bg: a, bg2: b, bg_angle: 120, radius: 22, px: 18, py: 22, min_height: 130 },
          }),
        ),
      ]),
  },
  {
    key: "stories",
    cat: "carousel",
    title: "Hikoyalar doirasi",
    desc: "Instagram uslubidagi doiralar",
    make: () =>
      box({ layout: "scroll", gap: 12, item_w: 72 }, [
        ...["🍕", "🍣", "🍔", "🥗", "🍰", "☕"].map((e, i) =>
          box({ align: "center", gap: 6 }, [
            box({ align: "center", justify: "center", style: { w: 66, h: 66, radius: 999, bg: "#f59e0b", bg2: "#ec4899", bg_angle: 45, px: 3, py: 3 } }, [
              box({ align: "center", justify: "center", style: { w: 60, h: 60, radius: 999, bg: "$surface", border: 2, border_color: "$bg" } }, [emoji(e, 28)]),
            ]),
            text(["Pitsa", "Sushi", "Burger", "Salat", "Desert", "Qahva"][i], "small", { size: 11, align: "center" }),
          ]),
        ),
      ]),
  },
  {
    key: "cards-scroll",
    cat: "carousel",
    title: "Kartalar lentasi",
    desc: "Suriladigan mahsulot kartalari",
    make: () =>
      box({ layout: "scroll", gap: 12, item_w: 160 }, [
        ...[
          ["🎧", "Quloqchin", "290 000"],
          ["⌚", "Soat", "450 000"],
          ["📷", "Kamera", "2 100 000"],
          ["🎮", "Joystik", "380 000"],
        ].map(([e, t, p]) =>
          box({ gap: 6, style: { ...CARD, px: 10, py: 10 } }, [
            box({ align: "center", justify: "center", style: media("$primary", "$primary", { bg_alpha: 10, aspect: "1:1", radius: 14 }) }, [emoji(e, 44)]),
            text(t, "h3", { size: 15 }),
            text(`${p} so'm`, "small", { color: "$primary", weight: 700 }),
          ]),
        ),
      ]),
  },
  {
    key: "reviews-scroll",
    cat: "carousel",
    title: "Sharhlar karuseli",
    desc: "Suriladigan mijoz fikrlari",
    make: () =>
      box({ layout: "scroll", gap: 12, item_w: 280, dots: true }, [
        ...[
          ["Aziza", "Juda tez yetkazib berishdi, sifat a'lo!"],
          ["Bekzod", "Narxi hamyonbop, yana buyurtma beraman."],
          ["Malika", "Xizmat ko'rsatish yuqori darajada."],
        ].map(([n, t]) =>
          box({ gap: 10, style: { ...CARD, py: 18 } }, [rating(5), text(`«${t}»`, "p", { italic: true }), text(`— ${n}`, "small", { weight: 700 })]),
        ),
      ]),
  },

  // ------------------------------------------------------------ Afzalliklar
  {
    key: "features3",
    cat: "features",
    title: "3 ta afzallik",
    desc: "Ikonka + sarlavha + matn kartalari",
    make: () =>
      grid(1, [
        ...[
          ["Zap", "Tez", "Buyurtma 1 kunda yetkaziladi"],
          ["ShieldCheck", "Ishonchli", "Kafolat va qaytarish imkoniyati"],
          ["Sparkles", "Sifatli", "Faqat tekshirilgan mahsulotlar"],
        ].map(([ic, t, d], i) => box({ gap: 8, anim: "up", delay: i * 120, style: { ...CARD, py: 18 } }, [icon(ic, 26), text(t, "h3"), text(d, "small")])),
      ], { columns_wide: 3 }),
  },
  {
    key: "bento",
    cat: "features",
    title: "Bento to'r",
    desc: "Turli o'lchamdagi kartalar mozaikasi",
    tags: "bento grid",
    make: () =>
      grid(2, [
        box({ gap: 6, justify: "end", style: { span: 2, bg: "#111827", color: "#ffffff", radius: 22, px: 18, py: 20, min_height: 150 } }, [
          icon("Sparkles", 26, { color: "#facc15" }),
          text("Hammasi bir joyda", "h2"),
          text("Bitta ilovada barcha xizmatlar", "small", { color: "#ffffff", opacity: 75 }),
        ]),
        box({ gap: 6, style: { bg: "#dbeafe", color: "#1e3a8a", radius: 22, px: 16, py: 16, row_span: 2 }, justify: "between" }, [icon("Rocket", 30, { color: "#1d4ed8" }, { loop: "float" }), text("Tez ishga tushirish", "h3")]),
        box({ gap: 4, style: { bg: "#fce7f3", color: "#831843", radius: 22, px: 16, py: 16 } }, [text("24/7", "h2"), text("qo'llab-quvvatlash", "small", { color: "#831843" })]),
        box({ gap: 4, style: { bg: "#dcfce7", color: "#14532d", radius: 22, px: 16, py: 16 } }, [text("99%", "h2"), text("mamnun mijozlar", "small", { color: "#14532d" })]),
      ], { columns_wide: 3, gap: 10 }),
  },
  {
    key: "checklist",
    cat: "features",
    title: "Belgilangan ro'yxat",
    desc: "✓ belgili afzalliklar",
    make: () =>
      box({ gap: 10 }, [
        text("Nimalar kiradi", "h2"),
        ...["Bepul konsultatsiya", "Shartnoma va kafolat", "Tezkor yetkazib berish", "24/7 yordam"].map((t) =>
          row([box({ align: "center", justify: "center", style: { w: 24, h: 24, radius: 999, bg: "#16a34a" } }, [icon("Check", 14, { color: "#ffffff" })]), text(t, "p")], { gap: 10 }),
        ),
      ]),
  },
  {
    key: "steps",
    cat: "features",
    title: "Qadamlar",
    desc: "Raqamlangan bosqichlar (timeline)",
    make: () =>
      box({ gap: 0 }, [
        ...[
          ["Ariza qoldiring", "Formani to'ldiring yoki botga yozing"],
          ["Bog'lanamiz", "15 daqiqa ichida menejer qo'ng'iroq qiladi"],
          ["Natija", "Kelishilgan muddatda tayyor ish"],
        ].map(([t, d], i, all) =>
          row([
            box({ align: "center", gap: 0, style: { self_align: "stretch" } }, [
              box({ align: "center", justify: "center", style: { w: 34, h: 34, radius: 999, bg: "$primary", color: "$on_primary", weight: 800 } }, [text(String(i + 1), "p", { color: "$on_primary", weight: 800 })]),
              ...(i < all.length - 1 ? [box({ style: { w: 2, grow: true, bg: "$primary", bg_alpha: 25, min_height: 24 } }, [])] : []),
            ]),
            box({ gap: 2, style: { mb: 18 } }, [text(t, "h3"), text(d, "small")]),
          ], { gap: 14, align: "start" }),
        ),
      ]),
  },
  {
    key: "icon-grid",
    cat: "features",
    title: "Ikonkalar to'ri",
    desc: "4 ustunli kichik xizmatlar",
    make: () =>
      grid(4, [
        ...[
          ["Wallet", "To'lov"],
          ["Truck", "Yetkazish"],
          ["Gift", "Bonus"],
          ["Headphones", "Yordam"],
          ["Ticket", "Kupon"],
          ["Star", "Top"],
          ["MapPin", "Filial"],
          ["Phone", "Aloqa"],
        ].map(([ic, l]) =>
          box({ align: "center", gap: 6 }, [box({ align: "center", justify: "center", style: { w: 54, h: 54, radius: 18, bg: "$surface", shadow: "s" }, hover: { ty: -3 } }, [icon(ic, 24)]), text(l, "small", { size: 12, align: "center" })]),
        ),
      ], { gap: 12, columns_wide: 8 }),
  },

  // ------------------------------------------------------------ Do'kon
  {
    key: "product-grid",
    cat: "shop",
    title: "Mahsulotlar to'ri",
    desc: "2 ustunli kartalar",
    make: () =>
      grid(2, [
        ...[
          ["☕", "Kapuchino", "25 000", "#fef3c7"],
          ["🧁", "Keks", "18 000", "#fce7f3"],
          ["🥐", "Kruassan", "22 000", "#ffedd5"],
          ["🍵", "Ko'k choy", "12 000", "#dcfce7"],
        ].map(([e, t, p, c]) =>
          box({ gap: 8, style: { ...CARD, px: 10, py: 10 }, hover: { ty: -3, shadow: "m" } }, [
            box({ align: "center", justify: "center", style: { bg: c, aspect: "1:1", radius: 14 } }, [emoji(e, 48)]),
            text(t, "h3", { size: 15 }),
            row([text(`${p} so'm`, "small", { weight: 800, color: "$text" }), box({ align: "center", justify: "center", style: { w: 30, h: 30, radius: 999, bg: "$primary" } }, [icon("Plus", 16, { color: "$on_primary" })])], { justify: "between" }),
          ]),
        ),
      ], { columns_wide: 4, gap: 10 }),
  },
  {
    key: "sale-timer",
    cat: "shop",
    title: "Aksiya taymeri",
    desc: "Teskari sanoq bilan chegirma banneri",
    make: () =>
      box({ gap: 12, style: { bg: "#ef4444", bg2: "#f97316", bg_angle: 120, radius: 24, px: 18, py: 22, color: "#ffffff", align: "center" } }, [
        text("⚡ Flash sale", "small", { color: "#ffffff", weight: 800, letter: 10, uppercase: true }),
        text("Barchasiga −40%", "h1", { size: 30 }),
        timer(2, { style: { color: "#ffffff" } }),
        button("Xarid qilish", "primary", { bg: "#ffffff", color: "#b91c1c", radius: 999 }, "ShoppingBag"),
      ]),
  },
  {
    key: "product-detail",
    cat: "shop",
    title: "Mahsulot sahifasi",
    desc: "Katta rasm, reyting, variantlar, tugma",
    make: () =>
      box({ gap: 12 }, [
        box({ align: "center", justify: "center", style: media("#e0f2fe", "#bae6fd", { aspect: "1:1", radius: 26 }) }, [emoji("🎧", 110, undefined, { loop: "float" })]),
        row([text("Simsiz quloqchin Pro", "h2", { grow: true }), icon("Heart", 22, { color: "#e11d48" })], { gap: 8 }),
        row([rating(4.7, { show_value: true }), text("· 128 sharh", "small")], { gap: 6 }),
        row([text("590 000 so'm", "h2", { color: "$primary" }), text("790 000", "p", { decoration: "line-through", color: "$hint" })], { gap: 10, align: "end" }),
        row([...["Qora", "Oq", "Ko'k"].map((c, i) => button(c, i ? "outline" : "primary", { radius: 999, py: 6, px: 14 }))], { gap: 8, wrap: true }),
        text("Shovqinni yutish, 30 soat ishlash va tez quvvatlash.", "p", MUTED),
        button("Savatga qo'shish", "primary", { radius: 16, py: 14 }, "ShoppingCart"),
      ]),
  },
  {
    key: "cart-row",
    cat: "shop",
    title: "Buyurtma qatori",
    desc: "Rasm, nom, miqdor va narx",
    make: () =>
      box({ gap: 10, style: { ...CARD } }, [
        ...[
          ["🍕", "Pepperoni pitsa", "2 × 65 000"],
          ["🥤", "Limonad", "1 × 15 000"],
        ].map(([e, t, q]) =>
          row([box({ align: "center", justify: "center", style: { w: 48, h: 48, radius: 12, bg: "$bg" } }, [emoji(e, 26)]), box({ gap: 0, style: { grow: true } }, [text(t, "p", { weight: 600 }), text(q, "small")])], { gap: 12 }),
        ),
        divider(),
        row([text("Jami", "p", { weight: 700 }), text("145 000 so'm", "h3", { color: "$primary" })], { justify: "between" }),
      ]),
  },

  // ------------------------------------------------------------ Narxlar
  {
    key: "pricing3",
    cat: "pricing",
    title: "3 ta tarif",
    desc: "O'rtadagisi ajratilgan",
    make: () =>
      grid(1, [
        ...[
          ["Start", "0", ["1 loyiha", "Asosiy imkoniyatlar"], false],
          ["Pro", "99 000", ["10 loyiha", "Barcha imkoniyatlar", "Ustuvor yordam"], true],
          ["Biznes", "299 000", ["Cheksiz", "Jamoa", "Shaxsiy menejer"], false],
        ].map(([n, p, list, hi]) =>
          box(
            {
              gap: 10,
              style: hi
                ? { bg: "$primary", color: "$on_primary", radius: 24, px: 18, py: 22, shadow: "glow" }
                : { ...CARD, py: 22, border: 1, border_color: "$line" },
            },
            [
              row([text(n as string, "h3", hi ? { color: "$on_primary" } : undefined), ...(hi ? [text("Mashhur", "small", { ...CHIP, bg: "#ffffff", bg_alpha: 25, color: "$on_primary" })] : [])], { justify: "between" }),
              row([text(p === "0" ? "Bepul" : `${p}`, "h1", { size: 30, ...(hi ? { color: "$on_primary" } : {}) }), ...(p === "0" ? [] : [text("so'm/oy", "small", hi ? { color: "$on_primary" } : undefined)])], { gap: 6, align: "end" }),
              ...(list as string[]).map((l) => row([icon("Check", 16, { color: hi ? "$on_primary" : "#16a34a" }), text(l, "p", { size: 14, ...(hi ? { color: "$on_primary" } : {}) })], { gap: 8 })),
              button(hi ? "Tanlash" : "Boshlash", hi ? "primary" : "outline", hi ? { bg: "#ffffff", color: "#111111" } : undefined),
            ],
          ),
        ),
      ], { columns_wide: 3, gap: 12, align: "center" }),
  },
  {
    key: "price-big",
    cat: "pricing",
    title: "Bitta tarif",
    desc: "Katta narx va imkoniyatlar ro'yxati",
    make: () =>
      box({ gap: 12, style: { ...CARD, py: 26, align: "center", border: 2, border_color: "$primary" } }, [
        text("Cheksiz obuna", "small", CHIP),
        text("149 000 so'm", "h1", { size: 38, weight: 800 }),
        text("oyiga · istalgan vaqt bekor qilish", "small"),
        divider(),
        ...["Barcha kurslar", "Sertifikat", "Mentor bilan chat"].map((t) => text(`✓ ${t}`, "p")),
        button("Obuna bo'lish", "primary", { radius: 999, width: "full" }),
      ]),
  },
  {
    key: "compare",
    cat: "pricing",
    title: "Taqqoslash jadvali",
    desc: "Imkoniyatlar bo'yicha 2 tarif",
    make: () =>
      box({ gap: 0, style: { bg: "$surface", radius: 18, overflow: "hidden", border: 1, border_color: "$line" } }, [
        grid(3, [text("Imkoniyat", "small", { weight: 700 }), text("Oddiy", "small", { weight: 700, align: "center" }), text("Pro", "small", { weight: 700, align: "center", color: "$primary" })], {
          style: { px: 14, py: 12, bg: "$text", bg_alpha: 4 },
        }),
        ...[
          ["Loyihalar", "3", "∞"],
          ["Shablonlar", "✓", "✓"],
          ["AI yordamchi", "—", "✓"],
          ["Statistika", "—", "✓"],
        ].map(([a, b, c]) =>
          grid(3, [text(a, "p", { size: 14 }), text(b, "p", { size: 14, align: "center" }), text(c, "p", { size: 14, align: "center", weight: 700, color: "$primary" })], {
            style: { px: 14, py: 11 },
          }),
        ),
      ]),
  },

  // ------------------------------------------------------------ Sharhlar
  {
    key: "testimonial",
    cat: "social",
    title: "Mijoz fikri",
    desc: "Avatar, ism, reyting va iqtibos",
    make: () =>
      box({ gap: 12, style: { ...CARD, py: 20 } }, [
        icon("MessageCircle", 28, { color: "$primary", opacity: 40 }),
        text("«Ilova orqali buyurtma berish juda qulay. Kuryer o'z vaqtida keldi, hammasi zo'r!»", "p", { size: 16, line: 1.5 }),
        row([
          box({ align: "center", justify: "center", style: { w: 44, h: 44, radius: 999, bg: "#f59e0b", bg2: "#ef4444", color: "#ffffff" } }, [text("DK", "p", { color: "#ffffff", weight: 800 })]),
          box({ gap: 0, style: { grow: true } }, [text("Dilnoza Karimova", "p", { weight: 700 }), text("Doimiy mijoz", "small")]),
          rating(5),
        ], { gap: 12 }),
      ]),
  },
  {
    key: "rating-summary",
    cat: "social",
    title: "Reyting xulosasi",
    desc: "Umumiy baho va yulduzlar taqsimoti",
    make: () =>
      row([
        box({ align: "center", gap: 4, style: { w: 110 } }, [text("4.8", "h1", { size: 42, weight: 800 }), rating(4.8), text("1 204 baho", "small")]),
        box({ gap: 6, style: { grow: true } }, [
          ...[
            [5, 82],
            [4, 12],
            [3, 4],
            [2, 1],
            [1, 1],
          ].map(([s, v]) => row([text(String(s), "small", { w: 12 }), progress(v, "", { show_value: false, thickness: 6, bar: "#f5b301", style: { grow: true } })], { gap: 8 })),
        ]),
      ], { gap: 16, style: { ...CARD } }),
  },
  {
    key: "logos",
    cat: "social",
    title: "Hamkorlar lentasi",
    desc: "Yuguruvchi logotiplar",
    make: () =>
      box({ gap: 10 }, [
        text("Bizga ishonishadi", "small", { align: "center", uppercase: true, letter: 12, weight: 700, color: "$hint" }),
        box({ layout: "marquee", gap: 34, speed: 25 }, [...["Uzum", "Payme", "Click", "Humo", "Beeline", "Artel"].map((n) => text(n, "h2", { opacity: 45, weight: 800, nowrap: true }))]),
      ]),
  },
  {
    key: "avatars",
    cat: "social",
    title: "Avatarlar guruhi",
    desc: "Ustma-ust doiralar va matn",
    make: () =>
      row([
        row(
          ["#f97316", "#0ea5e9", "#22c55e", "#a855f7"].map((c, i) =>
            box({ align: "center", justify: "center", style: { w: 38, h: 38, radius: 999, bg: c, border: 3, border_color: "$bg", tx: -i * 12 } }, [text(["A", "B", "M", "S"][i], "small", { color: "#ffffff", weight: 800 })]),
          ),
          { gap: 0 },
        ),
        text("**2 500+** kishi qo'shildi", "p", { size: 14, tx: -30 }),
      ], { gap: 10 }),
  },

  // ------------------------------------------------------------ Raqamlar
  {
    key: "stats4",
    cat: "stats",
    title: "Katta raqamlar",
    desc: "4 ta ko'rsatkich",
    make: () =>
      grid(2, [
        ...[
          ["10K+", "Mijozlar"],
          ["4.9", "Reyting"],
          ["24/7", "Yordam"],
          ["5 yil", "Tajriba"],
        ].map(([n, l], i) => box({ gap: 2, anim: "zoom", delay: i * 90, style: { ...CARD, align: "center" } }, [text(n, "h1", { size: 30, color: "$primary", weight: 800 }), text(l, "small")])),
      ], { columns_wide: 4, gap: 10 }),
  },
  {
    key: "skills",
    cat: "stats",
    title: "Ko'nikmalar shkalasi",
    desc: "Progress chiziqlari",
    make: () => box({ gap: 14, style: { ...CARD } }, [text("Ko'nikmalar", "h3"), progress(95, "Dizayn"), progress(80, "Frontend", { bar: "#8b5cf6" }), progress(65, "Marketing", { bar: "#f97316" })]),
  },
  {
    key: "rings",
    cat: "stats",
    title: "Doiraviy ko'rsatkichlar",
    desc: "3 ta halqa progress",
    make: () =>
      grid(3, [
        progress(76, "Vazifalar", { shape: "ring", thickness: 10 }),
        progress(52, "Byudjet", { shape: "ring", thickness: 10, bar: "#f59e0b" }),
        progress(90, "Mijozlar", { shape: "ring", thickness: 10, bar: "#10b981" }),
      ], { gap: 10, style: { ...CARD } }),
  },
  {
    key: "kpi",
    cat: "stats",
    title: "KPI kartalari",
    desc: "Ikonka, qiymat va o'sish",
    make: () =>
      grid(2, [
        ...[
          ["TrendingUp", "Savdo", "12.4 mln", "+18%", "#16a34a"],
          ["Users", "Mijozlar", "1 284", "+6%", "#2563eb"],
        ].map(([ic, l, v, d, c]) =>
          box({ gap: 6, style: { ...CARD } }, [row([icon(ic, 20, { color: c }), text(l, "small", { grow: true }), text(d, "small", { color: c, weight: 800 })], { gap: 6 }), text(v, "h2")]),
        ),
      ], { gap: 10 }),
  },

  // ------------------------------------------------------------ Kontent
  {
    key: "faq",
    cat: "content",
    title: "Savol-javob (akkordeon)",
    desc: "Bosilganda ochiladigan bo'limlar",
    tags: "accordion faq",
    make: () =>
      box({ gap: 10 }, [
        text("Ko'p beriladigan savollar", "h2"),
        box({ layout: "accordion", gap: 8 }, [
          box({ name: "Yetkazib berish qancha vaqt oladi?" }, [text("Toshkent bo'ylab 1 kun, viloyatlarga 2–3 kun.", "p", MUTED)]),
          box({ name: "To'lov qanday amalga oshiriladi?" }, [text("Naqd, karta yoki Click/Payme orqali.", "p", MUTED)]),
          box({ name: "Mahsulotni qaytarsa bo'ladimi?" }, [text("Ha, 14 kun ichida qaytarish mumkin.", "p", MUTED)]),
        ]),
      ]),
  },
  {
    key: "quote",
    cat: "content",
    title: "Iqtibos",
    desc: "Katta, chap chiziqli iqtibos",
    make: () =>
      box({ gap: 8, style: { px: 18, py: 6, border: 0, bg: "$primary", bg_alpha: 6, radius: 4 } }, [
        box({ style: { pos: "absolute", left: 0, top: 0, bottom: 0, w: 4, bg: "$primary" } }, []),
        text("«Sifat — hech kim ko'rmayotganda ham to'g'ri ish qilish.»", "h3", { italic: true, line: 1.4 }),
        text("— Genri Ford", "small"),
      ]),
  },
  {
    key: "article",
    cat: "content",
    title: "Maqola boshi",
    desc: "Teg, sarlavha, muallif va sana",
    make: () =>
      box({ gap: 10 }, [
        text("Yangiliklar", "small", CHIP),
        text("Telegram Mini App'lar biznesni qanday o'zgartirmoqda", "h1", { size: 28 }),
        row([box({ align: "center", justify: "center", style: { w: 32, h: 32, radius: 999, bg: "$primary" } }, [text("I", "small", { color: "$on_primary", weight: 800 })]), text("Inet jamoasi · 5 daqiqa o'qish", "small")], { gap: 8 }),
        box({ align: "center", justify: "center", style: media("#c7d2fe", "#fbcfe8", { aspect: "16:9", radius: 20 }) }, [emoji("📰", 56)]),
        text("Kirish qismi: maqolaning asosiy g'oyasi 2–3 jumlada.", "p", { line: 1.6 }),
      ]),
  },
  {
    key: "timeline",
    cat: "content",
    title: "Vaqt chizig'i",
    desc: "Yillar bo'yicha tarix",
    make: () =>
      box({ gap: 14, style: { px: 4 } }, [
        ...[
          ["2019", "Kompaniya tashkil topdi"],
          ["2021", "Birinchi 1000 mijoz"],
          ["2024", "Yangi filiallar ochildi"],
        ].map(([y, t], i) =>
          row([text(y, "h3", { w: 56, color: "$primary" }), box({ style: { w: 10, h: 10, radius: 999, bg: "$primary", shadow: "glow" } }, []), text(t, "p", { grow: true })], { gap: 12, anim: "left", delay: i * 120 }),
        ),
      ]),
  },
  {
    key: "divider-label",
    cat: "content",
    title: "Yozuvli ajratgich",
    desc: "O'rtasida matnli chiziq",
    make: () => row([divider({ grow: true }), text("yoki", "small", { uppercase: true, letter: 10 }), divider({ grow: true })], { gap: 12 }),
  },
  {
    key: "section-title",
    cat: "content",
    title: "Bo'lim sarlavhasi",
    desc: "Kichik yorliq, sarlavha va «Hammasi»",
    make: () =>
      row([box({ gap: 2, style: { grow: true } }, [text("Tavsiya etamiz", "small", { color: "$primary", weight: 700 }), text("Mashhur mahsulotlar", "h2")]), button("Hammasi", "link", undefined, "ArrowRight")], { gap: 8, align: "end" }),
  },

  // ------------------------------------------------------------ Chaqiruv
  {
    key: "cta-card",
    cat: "cta",
    title: "Taklif kartasi",
    desc: "Ikonka, matn va tugma",
    make: () =>
      box({ gap: 12, style: { bg: "$primary", color: "$on_primary", radius: 24, px: 20, py: 24 } }, [
        icon("Gift", 34, { color: "$on_primary" }, { loop: "wiggle" }),
        text("Birinchi buyurtmaga −15%", "h2", { color: "$on_primary" }),
        text("Promokod: SALOM. Faqat shu hafta.", "p", { color: "$on_primary", opacity: 85 }),
        button("Buyurtma berish", "primary", { bg: "#ffffff", color: "#111111", width: "fit" }, "ArrowRight"),
      ]),
  },
  {
    key: "cta-sticky",
    cat: "cta",
    title: "Pastki tugma paneli",
    desc: "Ekran pastida turadigan narx va tugma",
    tags: "sticky",
    make: () =>
      row([box({ gap: 0, style: { grow: true } }, [text("Jami", "small"), text("145 000 so'm", "h3")]), button("Rasmiylashtirish", "primary", { radius: 14 }, "ArrowRight")], {
        gap: 12,
        style: { pos: "sticky", bottom: 10, z: 20, bg: "$surface", bg_alpha: 92, backdrop: 14, radius: 20, px: 14, py: 10, shadow: "l" },
      }),
  },
  {
    key: "fab",
    cat: "cta",
    title: "Suzuvchi tugma",
    desc: "Burchakdagi doira (masalan, chat)",
    make: () =>
      box({ align: "end" }, [
        box({ align: "center", justify: "center", loop: "bounce", style: { pos: "fixed", bottom: 22, right: 18, z: 30, w: 58, h: 58, radius: 999, bg: "$primary", shadow: "glow" } }, [icon("MessageCircle", 26, { color: "$on_primary" })]),
      ]),
  },
  {
    key: "contact-cta",
    cat: "cta",
    title: "Bog'lanish bloki",
    desc: "Qo'ng'iroq va Telegram tugmalari",
    make: () =>
      box({ gap: 12, style: { ...CARD, py: 22, align: "center" } }, [
        text("Savolingiz bormi?", "h2"),
        text("Mutaxassisimiz 5 daqiqada javob beradi.", "p", MUTED),
        grid(2, [button("Qo'ng'iroq", "secondary", undefined, "Phone"), button("Telegram", "primary", undefined, "Send")], { gap: 8 }),
      ]),
  },

  // ------------------------------------------------------------ Jamoa va profil
  {
    key: "profile-header",
    cat: "team",
    title: "Profil sarlavhasi",
    desc: "Muqova, avatar va statistika",
    make: () =>
      box({ gap: 0, style: { bg: "$surface", radius: 24, overflow: "hidden" } }, [
        box({ style: { h: 110, bg: "#6366f1", bg2: "#ec4899", bg_angle: 120 } }, []),
        box({ align: "center", gap: 6, style: { px: 16, py: 16, mt: -56, align: "center" } }, [
          box({ align: "center", justify: "center", style: { w: 88, h: 88, radius: 999, bg: "#f59e0b", border: 4, border_color: "$surface", shadow: "m" } }, [text("SA", "h2", { color: "#ffffff" })]),
          text("Sardor Aliyev", "h2"),
          text("Fotograf · Toshkent", "small"),
          grid(3, [
            ...[
              ["128", "Ish"],
              ["4.9", "Reyting"],
              ["2K", "Obunachi"],
            ].map(([n, l]) => box({ gap: 0, style: { align: "center" } }, [text(n, "h3"), text(l, "small")])),
          ], { gap: 8, style: { mt: 8, w_pct: 100 } }),
          row([button("Yozish", "primary", { grow: true }, "Send"), button("Obuna", "outline", { grow: true })], { gap: 8, style: { w_pct: 100, mt: 6 } }),
        ]),
      ]),
  },
  {
    key: "team-grid",
    cat: "team",
    title: "Jamoa",
    desc: "Doira avatar, ism va lavozim",
    make: () =>
      grid(2, [
        ...[
          ["AK", "Anvar K.", "Direktor", "#0ea5e9"],
          ["MN", "Madina N.", "Dizayner", "#ec4899"],
          ["JR", "Javlon R.", "Dasturchi", "#22c55e"],
          ["SO", "Sevara O.", "Marketing", "#f59e0b"],
        ].map(([i, n, r, c]) =>
          box({ align: "center", gap: 6, style: { ...CARD, align: "center" }, hover: { ty: -4 } }, [
            box({ align: "center", justify: "center", style: { w: 72, h: 72, radius: 999, bg: c } }, [text(i, "h3", { color: "#ffffff" })]),
            text(n, "h3", { size: 15 }),
            text(r, "small"),
          ]),
        ),
      ], { columns_wide: 4, gap: 10 }),
  },
  {
    key: "contact-card",
    cat: "team",
    title: "Kontakt kartasi",
    desc: "Telefon, manzil, ish vaqti",
    make: () =>
      box({ gap: 12, style: { ...CARD } }, [
        text("Biz bilan bog'laning", "h3"),
        ...[
          ["Phone", "+998 90 123 45 67"],
          ["MapPin", "Toshkent, Amir Temur ko'chasi 1"],
          ["Clock", "Har kuni 9:00 — 21:00"],
        ].map(([ic, t]) => row([box({ align: "center", justify: "center", style: { w: 36, h: 36, radius: 12, ...SOFT, px: 0, py: 0 } }, [icon(ic, 18)]), text(t, "p", { size: 14, grow: true })], { gap: 12 })),
      ]),
  },

  // ------------------------------------------------------------ Media
  {
    key: "video-card",
    cat: "media",
    title: "Video karta",
    desc: "YouTube video va sarlavha",
    make: () => box({ gap: 10 }, [video(""), text("Biz haqimizda 2 daqiqada", "h3"), text("Video havolasini element sozlamasida kiriting.", "small")]),
  },
  {
    key: "gallery",
    cat: "media",
    title: "Rasmlar to'ri",
    desc: "3 ustunli galereya (rasmlarni tanlang)",
    make: () => grid(3, [image("1:1", { radius: 14 }), image("1:1", { radius: 14 }), image("1:1", { radius: 14 }), image("1:1", { radius: 14 }), image("1:1", { radius: 14 }), image("1:1", { radius: 14 })], { gap: 6 }),
  },
  {
    key: "map-card",
    cat: "media",
    title: "Xarita va manzil",
    desc: "Google xarita, manzil va tugma",
    make: () =>
      box({ gap: 0, style: { bg: "$surface", radius: 22, overflow: "hidden" } }, [
        mapNode("Tashkent, Amir Temur square", 200),
        row([icon("MapPin", 22), box({ gap: 0, style: { grow: true } }, [text("Bosh ofis", "p", { weight: 700 }), text("Amir Temur xiyoboni, Toshkent", "small")]), button("Yo'l", "secondary", { radius: 999, py: 6 })], {
          gap: 10,
          style: { px: 14, py: 12 },
        }),
      ]),
  },
  {
    key: "image-text",
    cat: "media",
    title: "Rasm + matn",
    desc: "Yonma-yon rasm va tavsif",
    make: () =>
      grid(1, [image("4:3", { radius: 20 }), box({ gap: 8, justify: "center" }, [text("Bizning ustaxona", "h2"), text("Har bir buyum qo'lda, sevgi bilan tayyorlanadi.", "p", MUTED), button("Batafsil", "outline", { width: "fit" })])], {
        columns_wide: 2,
        gap: 16,
        align: "center",
      }),
  },

  // ------------------------------------------------------------ Pastki qism
  {
    key: "footer",
    cat: "footer",
    title: "Pastki qism",
    desc: "Logotip, havolalar va ijtimoiy tarmoqlar",
    make: () =>
      box({ gap: 14, style: { bg: "#0f172a", color: "#ffffff", radius: 24, px: 20, py: 24 } }, [
        row([icon("Zap", 22, { color: "#facc15" }), text("Brend", "h3", { color: "#ffffff" })], { gap: 8 }),
        text("Sifatli xizmat — har kuni, har joyda.", "small", { color: "#ffffff", opacity: 70 }),
        grid(2, [...["Biz haqimizda", "Yetkazish", "To'lov", "Aloqa"].map((l) => text(l, "p", { size: 14, color: "#ffffff", opacity: 85 }))], { gap: 8 }),
        divider({ border_color: "#ffffff", opacity: 20 }),
        row([...["Send", "Camera", "Globe", "Phone"].map((ic) => box({ align: "center", justify: "center", style: { w: 38, h: 38, radius: 999, bg: "#ffffff", bg_alpha: 10 }, hover: { bg: "#ffffff", bg_alpha: 20 } }, [icon(ic, 18, { color: "#ffffff" })]))], { gap: 8 }),
        text("© 2025 Brend. Barcha huquqlar himoyalangan.", "small", { color: "#ffffff", opacity: 50 }),
      ]),
  },
  {
    key: "footer-mini",
    cat: "footer",
    title: "Kichik pastki qism",
    desc: "Bir qatorda nom va havolalar",
    make: () => box({ gap: 6, style: { align: "center", py: 16 } }, [text("Brend © 2025", "small", { weight: 700 }), text("Maxfiylik · Shartlar · Aloqa", "small")]),
  },

  // ------------------------------------------------------------ Elementlar
  {
    key: "eyebrow-title",
    cat: "atoms",
    title: "Sarlavha + yorliq",
    desc: "Kichik rangli yorliq ustida sarlavha",
    make: () => box({ gap: 6 }, [text("Xizmatlar", "small", CHIP), text("Biz nima qilamiz", "h2"), text("Qisqa tushuntirish matni.", "p", MUTED)]),
  },
  {
    key: "gradient-title",
    cat: "atoms",
    title: "Gradient sarlavha",
    desc: "Rangli o'tishli katta matn",
    make: () => box({}, [text("Ajoyib natijalar", "h1", { size: 36, weight: 800, text_grad: "$primary", text_grad2: "#f43f5e", bg_angle: 90 })]),
  },
  {
    key: "buttons",
    cat: "atoms",
    title: "Tugmalar to'plami",
    desc: "Asosiy, chiziqli, kapsula, nurli",
    make: () =>
      row([
        button("Asosiy", "primary"),
        button("Chiziqli", "outline"),
        button("Kapsula", "secondary", { radius: 999 }),
        button("Nurli", "primary", { radius: 999, shadow: "glow" }, "Sparkles", { loop: "pulse" }),
      ], { gap: 8, wrap: true }),
  },
  {
    key: "badges",
    cat: "atoms",
    title: "Belgilar (badge)",
    desc: "Rangli kichik yorliqlar",
    make: () =>
      row([
        text("Yangi", "small", CHIP),
        text("Sotuvda", "small", { ...CHIP, bg: "#16a34a", color: "#16a34a" }),
        text("Xit", "small", { ...CHIP, bg: "#ef4444", bg_alpha: 100, color: "#ffffff" }),
        text("Premium", "small", { ...CHIP, bg: "#f59e0b", bg2: "#ef4444", bg_alpha: 100, color: "#ffffff" }),
      ], { gap: 6, wrap: true }),
  },
  {
    key: "icon-circle",
    cat: "atoms",
    title: "Ikonka doirasi",
    desc: "Rangli fonda ikonka",
    make: () => row([...["Heart", "Star", "Zap", "Crown"].map((ic, i) => box({ align: "center", justify: "center", style: { w: 52, h: 52, radius: 999, bg: ["#fee2e2", "#fef3c7", "#dbeafe", "#ede9fe"][i] } }, [icon(ic, 24, { color: ["#dc2626", "#d97706", "#2563eb", "#7c3aed"][i] })]))], { gap: 10 }),
  },
  {
    key: "rating-el",
    cat: "atoms",
    title: "Reyting",
    desc: "Yulduzlar va baho",
    make: () => row([rating(4.5, { size: 20, show_value: true })]),
  },
  {
    key: "progress-el",
    cat: "atoms",
    title: "Progress",
    desc: "To'ldirilganlik chizig'i",
    make: () => box({}, [progress(70, "Yig'ildi: 7 000 000 / 10 000 000", { thickness: 10 })]),
  },
  {
    key: "timer-el",
    cat: "atoms",
    title: "Taymer",
    desc: "Teskari sanoq",
    make: () => box({}, [timer(5)]),
  },
  {
    key: "divider-el",
    cat: "atoms",
    title: "Bo'sh joy va chiziq",
    desc: "Bo'limlarni ajratish",
    make: () => box({ gap: 0 }, [spacer(12), divider(), spacer(12)]),
  },
  {
    key: "empty",
    cat: "atoms",
    title: "Bo'sh konteyner",
    desc: "Noldan o'zingiz quring",
    make: () => box({ style: { py: 16 } }, [text("Matn", "p")]),
  },
];

/** Tugunlar daraxtidan nusxa (yangi id bilan) */
export function cloneNode<T extends WANode>(node: T): T {
  const copy = JSON.parse(JSON.stringify(node)) as T;
  const walk = (n: WANode) => {
    n.id = uid("n");
    if (n.kind === "box") n.children.forEach(walk);
  };
  walk(copy);
  return copy;
}

export function searchLibrary(q: string, cat: string | null): LibraryItem[] {
  const s = q.trim().toLowerCase();
  return LIBRARY.filter((i) => (!cat || i.cat === cat) && (!s || `${i.title} ${i.desc} ${i.tags ?? ""}`.toLowerCase().includes(s)));
}
