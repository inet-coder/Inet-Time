import { CalendarCheck2, Shuffle } from "lucide-react";
import { emojiUrl, mediaUrl, type State } from "../api";
import { ServiceIcon } from "../icons";
import { upcoming } from "../profile";
import { whenText } from "../util";

const FIELD_LABELS: Record<string, string> = { name: "Ism", bio: "Bio", emoji_status: "Emoji status", photo: "Profil rasmi", online: "Holat" };

function Value({ field, value }: { field: string; value: string }) {
  if (field === "photo") return <img className="thumb" src={mediaUrl(value)} alt="" />;
  if (field === "emoji_status") return <img className="thumb thumb--emoji" src={emojiUrl(value)} alt="" />;
  if (value === "🎲")
    return (
      <span className="timeline__random">
        <Shuffle size={14} /> tasodifiy tanlanadi
      </span>
    );
  return <span className="timeline__text">{value}</span>;
}

export function Timeline({ state }: { state: State }) {
  const items = upcoming(state);

  if (items.length === 0) {
    return (
      <div className="placeholder">
        <CalendarCheck2 size={22} />
        <span>Yaqin orada o'zgarish rejalashtirilmagan</span>
      </div>
    );
  }
  return (
    <ul className="timeline">
      {items.map((s) => (
        <li key={s.id}>
          <ServiceIcon code={s.service_code} size={32} />
          <div className="timeline__what">
            <div className="timeline__head">
              <span className="timeline__label">{FIELD_LABELS[s.field] ?? s.field}</span>
              <span className="timeline__when">{whenText(s.preview.next_at, state.timezone)}</span>
            </div>
            <Value field={s.field} value={s.preview.next!} />
          </div>
        </li>
      ))}
    </ul>
  );
}
