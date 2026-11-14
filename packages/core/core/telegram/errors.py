"""Telegram/worker xatolarini turlarga ajratish.

Avval HAR QANDAY xato (tarmoq uzilishi, Telegram serveri 500, lock band) xizmatni butunlay ERROR qilib
qo'yardi — shuning uchun xizmatlar «bazi-bazida» o'zi to'xtab qolardi. Endi:

- SESSION_DEAD — sessiya Telegram'da tugatilgan (Qurilmalar ro'yxatidan chiqarilgan, akkaunt o'chirilgan):
  qayta urinish befoyda, akkauntni qayta ulash kerak;
- PERMANENT — so'rovning o'zi noto'g'ri (masalan bio juda uzun, Premium kerak): qayta urinish befoyda;
- TRANSIENT — vaqtinchalik (tarmoq, timeout, Telegram serveri, FloodWait, lock): keyingi urinishda o'tib ketadi."""

import asyncio
import enum

from telethon.errors import (
    AuthKeyDuplicatedError,
    BadRequestError,
    ForbiddenError,
    SessionPasswordNeededError,
    UnauthorizedError,
)

try:  # redis hamma servisda o'rnatilmagan (masalan api) — bo'lmasa shunchaki tekshirilmaydi
    from redis.exceptions import RedisError as _RedisError
except ImportError:  # pragma: no cover
    _RedisError = None


class ErrorKind(str, enum.Enum):
    SESSION_DEAD = "session_dead"
    PERMANENT = "permanent"
    TRANSIENT = "transient"


class SessionDeadError(RuntimeError):
    """Bazada sessiya yo'q / bekor qilingan yoki Telegram uni tan olmayapti."""


class PermanentError(RuntimeError):
    """Qayta urinib bo'lmaydigan xato (masalan, Premium talab qilinadi)."""


def classify(exc: BaseException) -> ErrorKind:
    if isinstance(exc, SessionDeadError):
        return ErrorKind.SESSION_DEAD
    # 401: AUTH_KEY_UNREGISTERED, SESSION_REVOKED, SESSION_EXPIRED, USER_DEACTIVATED(_BAN) ...
    # SESSION_PASSWORD_NEEDED ham 401, lekin u faqat login paytida chiqadi — sessiya o'lgani emas.
    if isinstance(exc, UnauthorizedError) and not isinstance(exc, SessionPasswordNeededError):
        return ErrorKind.SESSION_DEAD
    # Bitta kalit bir vaqtda turli IP'lardan ishlatilsa Telegram uni bekor qiladi.
    if isinstance(exc, AuthKeyDuplicatedError):
        return ErrorKind.SESSION_DEAD
    # redis LockError ValueError'dan meros oladi — lekin u vaqtinchalik (lock band/muddati o'tgan).
    if _RedisError is not None and isinstance(exc, _RedisError):
        return ErrorKind.TRANSIENT
    if isinstance(exc, (PermanentError, BadRequestError, ForbiddenError, ValueError, NotImplementedError)):
        return ErrorKind.PERMANENT
    # OSError/ConnectionError, asyncio.TimeoutError, ServerError (5xx), FloodWait, redis LockError va h.k.
    return ErrorKind.TRANSIENT


def is_retryable(exc: BaseException) -> bool:
    return classify(exc) == ErrorKind.TRANSIENT and not isinstance(exc, asyncio.CancelledError)
