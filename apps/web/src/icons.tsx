import {
  Bot,
  Cake,
  CalendarClock,
  CircleDashed,
  Clock,
  Eye,
  FileText,
  Images,
  PenLine,
  Radio,
  Repeat,
  SmilePlus,
  Sparkles,
  type LucideIcon,
} from "lucide-react";

// Har bir xizmatning o'z ikonkasi va gradient rangi (iOS sozlamalaridagi kabi plitka).
export const SERVICE_ICONS: Record<string, { Icon: LucideIcon; from: string; to: string }> = {
  clock_name: { Icon: Clock, from: "#4f8cff", to: "#2b5cf0" },
  auto_bio: { Icon: FileText, from: "#a47bff", to: "#6c3cf0" },
  auto_name: { Icon: PenLine, from: "#ff7aa8", to: "#e0336f" },
  online: { Icon: Radio, from: "#3ddc84", to: "#16a35a" },
  playlist: { Icon: Repeat, from: "#ffab4a", to: "#f06b1d" },
  schedule: { Icon: CalendarClock, from: "#35d0d6", to: "#118aa8" },
  emoji: { Icon: SmilePlus, from: "#ffd84d", to: "#f0a01d" },
  photo: { Icon: Images, from: "#ff6b6b", to: "#c9304a" },
  ai_reply: { Icon: Bot, from: "#1fd1b6", to: "#0b7f9e" },
  stories: { Icon: CircleDashed, from: "#ff8a4c", to: "#e1306c" },
  birthday: { Icon: Cake, from: "#ff9ad5", to: "#d9408f" },
  presence: { Icon: Eye, from: "#7aa7ff", to: "#4a5bd6" },
};

const FALLBACK = { Icon: Sparkles, from: "#8a93a6", to: "#5b6478" };

export function ServiceIcon({ code, size = 40 }: { code: string; size?: number }) {
  const { Icon, from, to } = SERVICE_ICONS[code] ?? FALLBACK;
  return (
    <span
      className="tile"
      style={{ width: size, height: size, borderRadius: size * 0.28, background: `linear-gradient(145deg, ${from}, ${to})` }}
    >
      <Icon size={size * 0.52} strokeWidth={2.2} color="#fff" />
    </span>
  );
}
