from telethon import TelegramClient, functions, types
from telethon.sessions import StringSession

from core.db.enums import ProfileField
from core.settings import settings
from core.telegram.field_adapter import FieldAdapter

_UNSUPPORTED = (ProfileField.PHOTO, ProfileField.BIRTHDAY)


class TelethonFieldAdapter(FieldAdapter):
    """Rasmiy Telethon hujjatidan tasdiqlangan chaqiriqlar:
    account.UpdateProfileRequest, account.UpdateStatusRequest,
    account.UpdateEmojiStatusRequest, users.GetFullUserRequest."""

    def _client(self, session_string: str) -> TelegramClient:
        return TelegramClient(StringSession(session_string), settings.telegram_api_id, settings.telegram_api_hash)

    async def get_current_value(self, session_string: str, field: ProfileField) -> str | None:
        if field in _UNSUPPORTED:
            return None
        client = self._client(session_string)
        await client.connect()
        try:
            if field == ProfileField.NAME:
                me = await client.get_me()
                return f"{me.first_name or ''} {me.last_name or ''}".strip()
            if field == ProfileField.BIO:
                full = await client(functions.users.GetFullUserRequest("me"))
                return full.full_user.about
            if field == ProfileField.ONLINE:
                return None  # online holati saqlanmaydi — restore = avtomatikani to'xtatish
            if field == ProfileField.EMOJI_STATUS:
                me = await client.get_me()
                status = getattr(me, "emoji_status", None)
                return str(status.document_id) if status is not None and hasattr(status, "document_id") else ""
            raise ValueError(f"Qo'llab-quvvatlanmaydigan field: {field}")
        finally:
            await client.disconnect()

    async def apply(self, session_string: str, field: ProfileField, value: str) -> None:
        if field in _UNSUPPORTED:
            raise NotImplementedError(f"{field.value} field hali implement qilinmagan (Kelajakka tayyor)")
        client = self._client(session_string)
        await client.connect()
        try:
            if field == ProfileField.NAME:
                first, _, last = value.partition(" ")
                await client(functions.account.UpdateProfileRequest(first_name=first, last_name=last or None))
            elif field == ProfileField.BIO:
                await client(functions.account.UpdateProfileRequest(about=value))
            elif field == ProfileField.ONLINE:
                await client(functions.account.UpdateStatusRequest(offline=(value != "true")))
            elif field == ProfileField.EMOJI_STATUS:
                me = await client.get_me()
                if not getattr(me, "premium", False):
                    raise RuntimeError("Emoji status faqat Telegram Premium akkauntlar uchun")
                if value in ("", "0", "none"):
                    status = types.EmojiStatusEmpty()
                else:
                    status = types.EmojiStatus(document_id=int(value))
                await client(functions.account.UpdateEmojiStatusRequest(emoji_status=status))
            else:
                raise ValueError(f"Qo'llab-quvvatlanmaydigan field: {field}")
        finally:
            await client.disconnect()
