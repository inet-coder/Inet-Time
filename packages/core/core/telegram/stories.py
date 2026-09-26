"""Stories: akkaunt ko'ra oladigan hikoyalarni ro'yxatlash va yuklab olish (Telethon).

- Faqat shu akkaunt Telegram'da o'zi ham ko'ra oladigan hikoyalar (maxfiylik sozlamalarini server tekshiradi).
- Egasi saqlashni taqiqlagan (noforwards) hikoyalar yuklanmaydi.
- Ko'rilgan hikoyalar «ko'rilgan» deb belgilanadi — egasi ko'rganlar ro'yxatida sizni ko'radi, xuddi ilovadagidek."""

from dataclasses import dataclass

from telethon import TelegramClient, functions, types
from telethon.errors import RPCError, UsernameInvalidError, UsernameNotOccupiedError
from telethon.sessions import StringSession

from core.settings import settings

MAX_STORY_BYTES = 45 * 1024 * 1024  # Bot API 50 MB chegarasi


class StoryError(Exception):
    """Foydalanuvchiga ko'rsatsa bo'ladigan xato."""


@dataclass
class StoryInfo:
    id: int
    date: int
    expire_date: int
    kind: str  # photo | video | other
    protected: bool
    caption: str
    thumb: bytes | None = None


@dataclass
class Peer:
    id: int
    name: str
    username: str | None


def _client(session_string: str) -> TelegramClient:
    return TelegramClient(
            StringSession(session_string),
            settings.telegram_api_id,
            settings.telegram_api_hash,
            # Qisqa ulanish yangilanishlarni (updates) olmasin — aks holda ular listener'ga yetib bormaydi
            # (bitta sessiya ikki ulanishda bo'lsa, Telegram ularni faqat bittasiga yuboradi).
            receive_updates=False,
        )


def _kind(media) -> str:
    if isinstance(media, types.MessageMediaPhoto):
        return "photo"
    if isinstance(media, types.MessageMediaDocument):
        mime = getattr(media.document, "mime_type", "") or ""
        return "video" if mime.startswith("video") else "other"
    return "other"


def _thumb_size(media):
    """Ro'yxat uchun kichik (≈320px) rasm."""
    if isinstance(media, types.MessageMediaPhoto) and media.photo:
        sizes = [s for s in media.photo.sizes if isinstance(s, (types.PhotoSize, types.PhotoSizeProgressive))]
        for wanted in ("m", "x", "s"):
            for size in sizes:
                if size.type == wanted:
                    return size
        return sizes[-1] if sizes else None
    if isinstance(media, types.MessageMediaDocument) and media.document and media.document.thumbs:
        return media.document.thumbs[-1]
    return None


async def _resolve(client: TelegramClient, username: str):
    username = username.strip().lstrip("@")
    if not username:
        raise StoryError("Username kiriting")
    try:
        entity = await client.get_entity(username)
    except (UsernameInvalidError, UsernameNotOccupiedError, ValueError) as exc:
        raise StoryError(f"@{username} topilmadi") from exc
    if not isinstance(entity, (types.User, types.Channel)):
        raise StoryError("Bu foydalanuvchi yoki kanal emas")
    return entity


async def _stories(client: TelegramClient, entity) -> list:
    result = await client(functions.stories.GetPeerStoriesRequest(peer=entity))
    items = list(result.stories.stories)
    # Ro'yxatda ba'zilari "o'tkazib yuborilgan" (media'siz) keladi — ularni ID bo'yicha to'liq so'raymiz.
    skipped = [s.id for s in items if isinstance(s, types.StoryItemSkipped)]
    if skipped:
        full = await client(functions.stories.GetStoriesByIDRequest(peer=entity, id=skipped))
        by_id = {s.id: s for s in full.stories}
        items = [by_id.get(s.id, s) for s in items]
    return [s for s in items if isinstance(s, types.StoryItem)]


def _peer(entity) -> Peer:
    if isinstance(entity, types.User):
        name = " ".join(x for x in (entity.first_name, entity.last_name) if x) or "—"
    else:
        name = entity.title
    return Peer(id=entity.id, name=name, username=getattr(entity, "username", None))


async def list_stories(session_string: str, username: str, with_thumbs: bool = True) -> tuple[Peer, list[StoryInfo]]:
    client = _client(session_string)
    await client.connect()
    try:
        entity = await _resolve(client, username)
        stories = await _stories(client, entity)
        infos = []
        for story in stories:
            protected = bool(story.noforwards)
            info = StoryInfo(
                id=story.id,
                date=int(story.date.timestamp()),
                expire_date=int(story.expire_date.timestamp()),
                kind=_kind(story.media),
                protected=protected,
                caption=(story.caption or "")[:200],
            )
            if with_thumbs and not protected:
                size = _thumb_size(story.media)
                if size is not None:
                    try:
                        info.thumb = await client.download_media(story.media, file=bytes, thumb=size)
                    except RPCError:
                        info.thumb = None
            infos.append(info)
        if stories:
            await client(functions.stories.ReadStoriesRequest(peer=entity, max_id=max(s.id for s in stories)))
        return _peer(entity), infos
    finally:
        await client.disconnect()


async def download_stories(session_string: str, username: str, story_ids: list[int] | None) -> tuple[Peer, list[tuple[StoryInfo, bytes]]]:
    """Himoyalanmagan hikoyalarni yuklab oladi. story_ids=None — hammasi."""
    client = _client(session_string)
    await client.connect()
    try:
        entity = await _resolve(client, username)
        stories = await _stories(client, entity)
        if story_ids:
            wanted = set(story_ids)
            stories = [s for s in stories if s.id in wanted]
        files = []
        for story in stories:
            if story.noforwards:
                continue
            kind = _kind(story.media)
            if kind == "other":
                continue
            document = getattr(story.media, "document", None)
            if document is not None and (document.size or 0) > MAX_STORY_BYTES:
                continue
            data = await client.download_media(story.media, file=bytes)
            if data:
                info = StoryInfo(
                    id=story.id, date=int(story.date.timestamp()), expire_date=int(story.expire_date.timestamp()),
                    kind=kind, protected=False, caption=(story.caption or "")[:900],
                )
                files.append((info, data))
        if stories:
            await client(functions.stories.ReadStoriesRequest(peer=entity, max_id=max(s.id for s in stories)))
        return _peer(entity), files
    finally:
        await client.disconnect()
