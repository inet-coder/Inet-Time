// Tayyor «erkin bo'limlar» — tanlangandan keyin har bir elementi o'zgartiriladi.
import { uid, type BoxNode, type WANode, type WAStyle } from "./types";

const NONE = { type: "none" as const, page: null, url: null, phone: null };

const box = (props: Partial<BoxNode>, children: WANode[]): BoxNode => ({
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
  children,
  ...props,
});
const text = (t: string, tag: "h1" | "h2" | "h3" | "p" | "small" = "p", style?: WAStyle): WANode => ({ id: uid("n"), kind: "text", text: t, tag, style: style ?? null });
const button = (t: string, variant: "primary" | "secondary" | "outline" | "ghost" | "link" = "primary", style?: WAStyle, icon: string | null = null): WANode => ({
  id: uid("n"),
  kind: "button",
  text: t,
  variant,
  icon,
  action: { ...NONE },
  style: style ?? null,
});
const icon = (name: string, size = 28, style?: WAStyle): WANode => ({ id: uid("n"), kind: "icon", icon: name, size, emoji: "", style: style ?? null });

export type SectionPreset = { key: string; title: string; desc: string; icon: string; make: () => BoxNode };

export const SECTIONS: SectionPreset[] = [
  {
    key: "empty",
    title: "Bo'sh konteyner",
    desc: "Noldan o'zingiz quring",
    icon: "⬜",
    make: () => box({ style: { py: 16 } }, [text("Matn", "p")]),
  },
  {
    key: "hero",
    title: "Gradient banner",
    desc: "Katta sarlavha, matn va 2 tugma",
    icon: "🌅",
    make: () =>
      box({ align: "center", gap: 14, style: { bg: "#4f46e5", bg2: "#06b6d4", bg_angle: 135, py: 44, px: 22, radius: 24, color: "#ffffff", align: "center" }, anim: "up" }, [
        text("YANGI", "small", { letter: 20, weight: 700, color: "#ffffff", opacity: 80 }),
        text("Biznesingiz uchun eng yaxshi yechim", "h1", { size: 32 }),
        text("Qisqa va aniq taklif: mijoz nima oladi va nega aynan siz.", "p", { opacity: 90 }),
        box({ layout: "row", justify: "center", gap: 10 }, [
          button("Boshlash", "primary", { bg: "#ffffff", color: "#111827" }, "ArrowRight"),
          button("Batafsil", "outline", { color: "#ffffff", border: 1, border_color: "#ffffff" }),
        ]),
      ]),
  },
  {
    key: "features3",
    title: "3 ta afzallik",
    desc: "Ikonka + sarlavha + matn kartalari",
    icon: "✅",
    make: () =>
      box({ layout: "grid", columns: 1, columns_wide: 3, gap: 12 }, [
        ...[
          ["Zap", "Tez", "Buyurtma 1 kunda yetkaziladi"],
          ["ShieldCheck", "Ishonchli", "Kafolat va qaytarish imkoniyati"],
          ["Sparkles", "Sifatli", "Faqat tekshirilgan mahsulotlar"],
        ].map(([ic, t, d]) =>
          box({ gap: 8, style: { bg: "#ffffff", color: "#111418", py: 18, px: 16, radius: 18, shadow: "s" }, anim: "up" }, [
            icon(ic, 26),
            text(t, "h3"),
            text(d, "small"),
          ]),
        ),
      ]),
  },
  {
    key: "cta",
    title: "Taklif kartasi",
    desc: "To'q fonda chaqiruv va tugma",
    icon: "📣",
    make: () =>
      box({ gap: 12, style: { bg: "#0f172a", px: 22, py: 28, radius: 22, color: "#ffffff", shadow: "l" }, anim: "zoom" }, [
        text("Bugun buyurtma bering — 20% chegirma", "h2"),
        text("Taklif faqat shu hafta amal qiladi.", "p", { opacity: 80 }),
        button("Chegirmani olish", "primary", undefined, "Gift"),
      ]),
  },
  {
    key: "testimonial",
    title: "Mijoz sharhi",
    desc: "Iqtibos, yulduzlar va ism",
    icon: "💬",
    make: () =>
      box({ gap: 10, style: { bg: "#ffffff", color: "#111418", px: 18, py: 20, radius: 20, shadow: "m" } }, [
        box({ layout: "row", gap: 2 }, [1, 2, 3, 4, 5].map(() => icon("Star", 18, { color: "#f59e0b" }))),
        text("«Xizmat a'lo darajada! Buyurtma vaqtida keldi, sifati kutganimdan ham yaxshi.»", "p", { size: 16, line: 1.5 }),
        text("— Dilnoza, Toshkent", "small", { weight: 600 }),
      ]),
  },
  {
    key: "price",
    title: "Narx kartasi",
    desc: "Tarif nomi, katta narx, imkoniyatlar",
    icon: "💳",
    make: () =>
      box({ gap: 10, style: { bg: "#ffffff", color: "#111418", px: 20, py: 22, radius: 22, border: 2, border_color: "#2f80ed" } }, [
        text("PREMIUM", "small", { letter: 15, weight: 700, color: "#2f80ed" }),
        text("299 000 so'm", "h1", { size: 34 }),
        ...["Cheksiz foydalanish", "Ustuvor yordam", "Bepul yetkazish"].map((f) =>
          box({ layout: "row", align: "center", gap: 8, wrap: false }, [icon("CircleCheck", 18), text(f, "p")]),
        ),
        button("Tanlash", "primary"),
      ]),
  },
  {
    key: "team",
    title: "Jamoa a'zosi",
    desc: "Rasm, ism va lavozim",
    icon: "👤",
    make: () =>
      box({ align: "center", gap: 6, style: { align: "center", py: 16 } }, [
        { id: uid("n"), kind: "image", media_id: null, fit: "cover", ratio: "1:1", action: null, style: { radius: 80, max_width: 120 } },
        text("Ism Familiya", "h3"),
        text("Bosh mutaxassis", "small"),
      ]),
  },
  {
    key: "stats",
    title: "Raqamlar qatori",
    desc: "3 ta katta raqam",
    icon: "🔢",
    make: () =>
      box({ layout: "grid", columns: 3, gap: 8 }, [
        ...[
          ["10+", "yil"],
          ["5 000", "mijoz"],
          ["4.9", "reyting"],
        ].map(([v, l]) =>
          box({ align: "center", gap: 2, style: { bg: "#ffffff", color: "#111418", py: 14, radius: 16, align: "center" } }, [
            text(v, "h2", { color: "#2f80ed" }),
            text(l, "small"),
          ]),
        ),
      ]),
  },
  {
    key: "footer",
    title: "Footer",
    desc: "Kichik matn va havolalar",
    icon: "🔻",
    make: () =>
      box({ align: "center", gap: 8, style: { py: 22, align: "center", opacity: 80 } }, [
        box({ layout: "row", justify: "center", gap: 16 }, [button("Biz haqimizda", "link"), button("Aloqa", "link"), button("Shartlar", "link")]),
        text("© 2026 Kompaniya nomi. Barcha huquqlar himoyalangan.", "small"),
      ]),
  },
];

/** Daraxtni yangi id'lar bilan nusxalash (nusxa olish/qo'yish uchun). */
export function cloneNode<T extends WANode>(node: T): T {
  const copy = JSON.parse(JSON.stringify(node)) as T;
  const walk = (n: WANode) => {
    n.id = uid("n");
    if (n.kind === "box") n.children.forEach(walk);
  };
  walk(copy);
  return copy;
}
