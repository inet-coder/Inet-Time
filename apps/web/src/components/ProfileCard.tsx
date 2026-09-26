import { AtSign, Info, Star } from "lucide-react";
import { emojiUrl, mediaUrl } from "../api";
import type { ProfileView } from "../profile";
import { tg } from "../tg";

function initials(name: string): string {
  const letters = name.replace(/[^\p{L}\s]/gu, "").trim().split(/\s+/).map((w) => w[0]);
  return (letters.slice(0, 2).join("") || "?").toUpperCase();
}

function Badge({ profile }: { profile: ProfileView }) {
  // Telegram'dagi kabi: emoji status bo'lsa u, bo'lmasa Premium yulduzchasi.
  if (profile.emoji) return <img className="profile__emoji" src={emojiUrl(profile.emoji)} alt="" />;
  if (profile.premium) return <Star className="profile__star" size={18} fill="currentColor" strokeWidth={0} />;
  return null;
}

export function ProfileCard({ profile, compact = false }: { profile: ProfileView; compact?: boolean }) {
  const tgPhoto = tg?.initDataUnsafe.user?.photo_url;
  const avatar = profile.photo ? mediaUrl(profile.photo) : tgPhoto;
  const status = (
    <div className={`profile__status ${profile.online ? "is-online" : ""}`}>{profile.online ? "online" : "yaqinda online edi"}</div>
  );
  const avatarEl = (
    <div className="profile__avatar">
      {avatar ? <img src={avatar} alt="" /> : <span>{initials(profile.name)}</span>}
      {profile.online && <i className="profile__dot" />}
    </div>
  );

  if (compact) {
    return (
      <div className="profile profile--compact">
        {avatarEl}
        <div className="profile__main">
          <div className="profile__name">
            <span>{profile.name || "Ism"}</span>
            <Badge profile={profile} />
          </div>
          {status}
        </div>
        {profile.bio && <div className="profile__bio-compact">{profile.bio}</div>}
      </div>
    );
  }

  return (
    <div className="profile">
      <div className="profile__cover" />
      {avatarEl}
      <div className="profile__name">
        <span>{profile.name || "Ism"}</span>
        <Badge profile={profile} />
      </div>
      {status}
      <div className="profile__info">
        {profile.username && (
          <div className="profile__row">
            <AtSign size={18} className="profile__row-icon" />
            <div>
              <div className="profile__value">@{profile.username}</div>
              <div className="profile__label">Username</div>
            </div>
          </div>
        )}
        <div className="profile__row">
          <Info size={18} className="profile__row-icon" />
          <div>
            <div className={`profile__value ${profile.bio ? "" : "is-empty"}`}>{profile.bio || "Bio ko'rsatilmagan"}</div>
            <div className="profile__label">Bio</div>
          </div>
        </div>
      </div>
    </div>
  );
}
