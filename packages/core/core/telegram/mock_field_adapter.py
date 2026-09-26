from core.db.enums import ProfileField
from core.telegram.field_adapter import FieldAdapter

_DEFAULTS = {
    ProfileField.NAME.value: "Mock User",
    ProfileField.BIO.value: "",
    ProfileField.ONLINE.value: "false",
    ProfileField.EMOJI_STATUS.value: "",
}


class MockFieldAdapter(FieldAdapter):
    """Real MTProto'siz test uchun — session_string bo'yicha xotirada soxta profil."""

    def __init__(self) -> None:
        self._profiles: dict[str, dict[str, str]] = {}

    def _profile(self, session_string: str) -> dict[str, str]:
        return self._profiles.setdefault(session_string, dict(_DEFAULTS))

    async def get_current_value(self, session_string: str, field: ProfileField) -> str | None:
        if field in (ProfileField.PHOTO, ProfileField.BIRTHDAY):
            return None
        return self._profile(session_string).get(field.value)

    async def apply(self, session_string: str, field: ProfileField, value: str) -> None:
        if field in (ProfileField.PHOTO, ProfileField.BIRTHDAY):
            raise NotImplementedError(f"{field.value} uchun apply emas, upload_photo ishlatiladi")
        self._profile(session_string)[field.value] = value

    async def upload_photo(self, session_string: str, data: bytes) -> dict:
        photos = self._profile(session_string).setdefault("photos", [])  # type: ignore[arg-type]
        ref = {"id": len(photos) + 1, "access_hash": 0, "file_reference": "", "size": len(data)}
        photos.append(ref)
        return ref

    async def delete_photo(self, session_string: str, ref: dict) -> None:
        photos = self._profile(session_string).get("photos", [])
        self._profile(session_string)["photos"] = [p for p in photos if p["id"] != ref["id"]]  # type: ignore[assignment]
