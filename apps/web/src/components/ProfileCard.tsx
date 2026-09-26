import { emojiUrl, mediaUrl } from "../api";
import type { ProfileView } from "../profile";
import { tg } from "../tg";

function initials(name: string): string {
  const letters = name.replace(/[^\p{L}\s]/gu, "").trim().split(/\s+/).map((w) => w[0]);
  return (letters.slice(0, 2).join("") || "?").toUpperCase();
}

export function ProfileCard({ profile, compact = false }: { profile: ProfileView; compact?: boolean }) {
  const tgPhoto = tg?.initDataUnsafe.user?.photo_url;
  const avatar = profile.photo ? mediaUrl(profile.photo) : tgPhoto;

  return (
    <div className={`profile ${compact ? "profile--compact" : ""}`}>
      <div className="profile__avatar">
        {avatar ? <img src={avatar} alt="" /> : <span>{initials(profile.name)}</span>}
        {profile.online && <i className="profile__dot" />}
      </div>
      <div className="profile__name">
        <span>{profile.name || "Ism"}</span>
        {profile.emoji && <img className="profile__emoji" src={emojiUrl(profile.emoji)} alt="" />}
      </div>
      <div className={`profile__status ${profile.online ? "is-online" : ""}`}>
        {profile.online ? "online" : "yaqinda online edi"}
      </div>
      {!compact && (
        <div className="profile__info">
          {profile.username && (
            <div className="profile__row">
              <div className="profile__value">@{profile.username}</div>
              <div className="profile__label">Username</div>
            </div>
          )}
          <div className="profile__row">
            <div className={`profile__value ${profile.bio ? "" : "is-empty"}`}>{profile.bio || "Bio ko'rsatilmagan"}</div>
            <div className="profile__label">Bio</div>
          </div>
        </div>
      )}
      {compact && profile.bio && <div className="profile__bio-compact">{profile.bio}</div>}
    </div>
  );
}
