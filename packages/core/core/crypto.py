import base64
import os

from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from core.settings import settings

CURRENT_KEY_VERSION = 1


def _get_key(key_version: int) -> bytes:
    if key_version != CURRENT_KEY_VERSION:
        raise ValueError(f"Noma'lum key_version: {key_version}")
    raw = settings.session_encryption_key
    if not raw:
        raise RuntimeError("SESSION_ENCRYPTION_KEY o'rnatilmagan")
    key = base64.b64decode(raw)
    if len(key) != 32:
        raise RuntimeError("SESSION_ENCRYPTION_KEY base64'da 32 baytli AES-256 kalit bo'lishi kerak")
    return key


def encrypt(plaintext: str) -> tuple[bytes, bytes, int]:
    """Ciphertext, nonce, key_version qaytaradi. AES-256-GCM, har chaqiriqda yangi nonce."""
    key = _get_key(CURRENT_KEY_VERSION)
    nonce = os.urandom(12)
    ciphertext = AESGCM(key).encrypt(nonce, plaintext.encode("utf-8"), None)
    return ciphertext, nonce, CURRENT_KEY_VERSION


def decrypt(ciphertext: bytes, nonce: bytes, key_version: int) -> str:
    key = _get_key(key_version)
    return AESGCM(key).decrypt(nonce, ciphertext, None).decode("utf-8")


def generate_key() -> str:
    """Yangi SESSION_ENCRYPTION_KEY qiymati (base64, 32 bayt) — .env uchun."""
    return base64.b64encode(os.urandom(32)).decode("ascii")
