"""Faollik holati («oxirgi marta ko'rilgan») va Telegram profilidagi tug'ilgan kun.

«Yaqinda onlayn edi» — Telegram'ning o'z maxfiylik sozlamasi (StatusTimestamp): aniq vaqtni kimlar ko'rishi.
Eslatma (Telegram qoidasi): vaqtingizni yashirsangiz, siz ham boshqalarnikini ko'rmaysiz (Premium'dan tashqari)."""

from telethon import TelegramClient, functions, types
from telethon.sessions import StringSession

from core.settings import settings

# rejim -> Telegram qoidasi
PRIVACY_RULES = {
    "everybody": types.InputPrivacyValueAllowAll,
    "contacts": types.InputPrivacyValueAllowContacts,
    "nobody": types.InputPrivacyValueDisallowAll,
}


def _client(session_string: str) -> TelegramClient:
    return TelegramClient(
        StringSession(session_string),
        settings.telegram_api_id,
        settings.telegram_api_hash,
        receive_updates=False,  # listener'dan yangilanishlarni tortib olmasin
    )


def _rules_to_mode(rules) -> str:
    kinds = {type(r) for r in rules}
    if types.PrivacyValueAllowAll in kinds:
        return "everybody"
    if types.PrivacyValueAllowContacts in kinds:
        return "contacts"
    return "nobody"


async def get_last_seen(session_string: str) -> str:
    """everybody | contacts | nobody"""
    client = _client(session_string)
    await client.connect()
    try:
        result = await client(functions.account.GetPrivacyRequest(key=types.InputPrivacyKeyStatusTimestamp()))
        return _rules_to_mode(result.rules)
    finally:
        await client.disconnect()


async def set_last_seen(session_string: str, mode: str) -> None:
    """Istisnolar (alohida odamlar ro'yxati) o'chadi — bitta umumiy qoida qoladi."""
    client = _client(session_string)
    await client.connect()
    try:
        await client(
            functions.account.SetPrivacyRequest(key=types.InputPrivacyKeyStatusTimestamp(), rules=[PRIVACY_RULES[mode]()])
        )
    finally:
        await client.disconnect()


async def get_telegram_birthday(session_string: str) -> str | None:
    """Telegram profilidagi tug'ilgan kun: "YYYY-MM-DD" yoki "MM-DD"; yo'q bo'lsa None."""
    client = _client(session_string)
    await client.connect()
    try:
        full = await client(functions.users.GetFullUserRequest("me"))
        birthday = getattr(full.full_user, "birthday", None)
        if birthday is None:
            return None
        month_day = f"{birthday.month:02d}-{birthday.day:02d}"
        return f"{birthday.year:04d}-{month_day}" if birthday.year else month_day
    finally:
        await client.disconnect()
