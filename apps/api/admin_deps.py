import jwt
from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from core.admin_auth import decode_access_token
from core.db.models import AdminRole, AdminUser
from core.permissions import has_permission
from deps import get_db

_bearer = HTTPBearer(auto_error=True)


async def get_current_admin(
    credentials: HTTPAuthorizationCredentials = Depends(_bearer),
    db: AsyncSession = Depends(get_db),
) -> AdminUser:
    try:
        admin_id = decode_access_token(credentials.credentials)
    except jwt.PyJWTError as exc:
        raise HTTPException(401, "Token yaroqsiz yoki muddati o'tgan") from exc

    admin = await db.get(AdminUser, admin_id)
    if admin is None or not admin.is_active:
        raise HTTPException(401, "Admin topilmadi yoki faol emas")
    return admin


def require_permission(permission_key: str):
    async def _checker(admin: AdminUser = Depends(get_current_admin), db: AsyncSession = Depends(get_db)) -> AdminUser:
        role = await db.get(AdminRole, admin.role_id)
        if role is None or not has_permission(role, permission_key):
            raise HTTPException(403, "Bu amal uchun ruxsat yo'q")
        return admin

    return _checker
