import { emojiUrl, mediaUrl, type State } from "../api";
import { upcoming } from "../profile";
import { whenText } from "../util";

const FIELD_LABELS: Record<string, string> = { name: "Ism", bio: "Bio", emoji_status: "Emoji", photo: "Rasm", online: "Holat" };

function Value({ field, value }: { field: string; value: string }) {
  if (field === "photo") return <img className="thumb" src={mediaUrl(value)} alt="" />;
  if (field === "emoji_status") return <img className="thumb thumb--emoji" src={emojiUrl(value)} alt="" />;
  if (value === "🎲") return <span className="hint">tasodifiy tanlanadi</span>;
  return <span className="timeline__text">{value}</span>;
}

export function Timeline({ state }: { state: State }) {
  const catalog = Object.fromEntries(state.catalog.map((c) => [c.code, c]));
  const items = upcoming(state);

  if (items.length === 0) {
    return <p className="hint center">Yaqin orada o'zgarish rejalashtirilmagan.</p>;
  }
  return (
    <ul className="timeline">
      {items.map((s) => (
        <li key={s.id}>
          <div className="timeline__when">{whenText(s.preview.next_at, state.timezone)}</div>
          <div className="timeline__what">
            <span className="timeline__label">
              {catalog[s.service_code]?.icon} {FIELD_LABELS[s.field] ?? s.field}
            </span>
            <Value field={s.field} value={s.preview.next!} />
          </div>
        </li>
      ))}
    </ul>
  );
}
