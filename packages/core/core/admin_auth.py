import datetime

import bcrypt
import jwt
import pyotp

from core.settings import settings

ACCESS_TOKEN_TTL_MINUTES = 60
JWT_ALGORITHM = "HS256"


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("ascii")


def verify_password(password: str, password_hash: str) -> bool:
    if not password_hash:
        return False
    return bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("ascii"))


def create_access_token(admin_id: int) -> str:
    now = datetime.datetime.now(datetime.timezone.utc)
    payload = {
        "sub": str(admin_id),
        "typ": "admin",
        "iat": now,
        "exp": now + datetime.timedelta(minutes=ACCESS_TOKEN_TTL_MINUTES),
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm=JWT_ALGORITHM)


def decode_access_token(token: str) -> int:
    """Admin ID qaytaradi. Noto'g'ri/muddati o'tgan yoki admin bo'lmagan token uchun jwt.PyJWTError ko'taradi."""
    payload = jwt.decode(token, settings.jwt_secret, algorithms=[JWT_ALGORITHM])
    if payload.get("typ") != "admin":
        # Mini App foydalanuvchi tokeni bilan admin endpointlariga kirib bo'lmasin (ID'lar kesishishi mumkin).
        raise jwt.InvalidTokenError("admin tokeni emas")
    return int(payload["sub"])


def generate_totp_secret() -> str:
    return pyotp.random_base32()


def totp_provisioning_uri(secret: str, username: str) -> str:
    return pyotp.TOTP(secret).provisioning_uri(name=username, issuer_name="Userbots Admin")


def verify_totp_code(secret: str, code: str) -> bool:
    return pyotp.TOTP(secret).verify(code, valid_window=1)
