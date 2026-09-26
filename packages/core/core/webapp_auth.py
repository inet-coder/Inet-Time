"""Telegram Mini App initData tekshiruvi (core.telegram.org/bots/webapps) va foydalanuvchi tokeni."""

import datetime
import hashlib
import hmac
import json
import time
from urllib.parse import parse_qsl

import jwt

from core.settings import settings

INIT_DATA_MAX_AGE_SECONDS = 24 * 3600
USER_TOKEN_TTL_HOURS = 12
_TOKEN_TYPE = "webapp"


class InitDataError(Exception):
    pass


def validate_init_data(init_data: str, bot_token: str, max_age: int = INIT_DATA_MAX_AGE_SECONDS) -> dict:
    """Imzo to'g'ri bo'lsa Telegram foydalanuvchisini (WebAppUser) qaytaradi."""
    fields = dict(parse_qsl(init_data, keep_blank_values=True))
    received_hash = fields.pop("hash", None)
    fields.pop("signature", None)  # hujjat: hash va signature tekshiruv satriga kirmaydi
    if not received_hash:
        raise InitDataError("hash yo'q")

    data_check_string = "\n".join(f"{k}={v}" for k, v in sorted(fields.items()))
    secret_key = hmac.new(b"WebAppData", bot_token.encode(), hashlib.sha256).digest()
    expected = hmac.new(secret_key, data_check_string.encode(), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(expected, received_hash):
        raise InitDataError("imzo noto'g'ri")

    if time.time() - int(fields.get("auth_date", 0)) > max_age:
        raise InitDataError("initData eskirgan")
    if "user" not in fields:
        raise InitDataError("user yo'q")
    return json.loads(fields["user"])


def create_user_token(user_id: int) -> str:
    now = datetime.datetime.now(datetime.timezone.utc)
    payload = {"sub": str(user_id), "typ": _TOKEN_TYPE, "iat": now, "exp": now + datetime.timedelta(hours=USER_TOKEN_TTL_HOURS)}
    return jwt.encode(payload, settings.jwt_secret, algorithm="HS256")


def decode_user_token(token: str) -> int:
    payload = jwt.decode(token, settings.jwt_secret, algorithms=["HS256"])
    if payload.get("typ") != _TOKEN_TYPE:
        # Admin tokeni bilan foydalanuvchi endpointlariga kirib bo'lmasin.
        raise jwt.InvalidTokenError("token turi noto'g'ri")
    return int(payload["sub"])
