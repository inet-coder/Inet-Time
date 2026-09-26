from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from admin_deps import get_current_admin
from core import crypto
from core.admin_auth import (
    create_access_token,
    generate_totp_secret,
    totp_provisioning_uri,
    verify_password,
    verify_totp_code,
)
from core.audit import record_audit
from core.db.enums import ActorType
from core.db.models import AdminRole, AdminUser
from deps import get_db
from schemas import Admin2faSetupOut, Admin2faVerify, AdminLogin, AdminMeOut, AdminTokenOut

router = APIRouter(prefix="/admin", tags=["admin-auth"])


def _decrypt_totp_secret(admin: AdminUser) -> str:
    return crypto.decrypt_packed(admin.totp_secret_encrypted)


@router.post("/login", response_model=AdminTokenOut)
async def admin_login(payload: AdminLogin, db: AsyncSession = Depends(get_db)) -> AdminTokenOut:
    admin = await db.scalar(select(AdminUser).where(AdminUser.username == payload.username))
    if admin is None or not admin.is_active or not verify_password(payload.password, admin.password_hash):
        raise HTTPException(401, "Login yoki parol noto'g'ri")

    if admin.is_2fa_enabled:
        if not payload.totp_code or not verify_totp_code(_decrypt_totp_secret(admin), payload.totp_code):
            raise HTTPException(401, "2FA kodi noto'g'ri yoki kiritilmagan")

    await record_audit(db, actor_type=ActorType.ADMIN, actor_id=admin.id, action="login")
    await db.commit()
    return AdminTokenOut(access_token=create_access_token(admin.id))


@router.get("/me", response_model=AdminMeOut)
async def admin_me(admin: AdminUser = Depends(get_current_admin), db: AsyncSession = Depends(get_db)) -> AdminMeOut:
    role = await db.get(AdminRole, admin.role_id)
    return AdminMeOut(id=admin.id, username=admin.username, role_name=role.name, is_2fa_enabled=admin.is_2fa_enabled)


@router.post("/2fa/setup", response_model=Admin2faSetupOut)
async def setup_2fa(admin: AdminUser = Depends(get_current_admin), db: AsyncSession = Depends(get_db)) -> Admin2faSetupOut:
    secret = generate_totp_secret()
    admin.totp_secret_encrypted = crypto.encrypt_packed(secret)
    await db.commit()
    return Admin2faSetupOut(secret=secret, provisioning_uri=totp_provisioning_uri(secret, admin.username))


@router.post("/2fa/verify", response_model=AdminMeOut)
async def verify_2fa(
    payload: Admin2faVerify, admin: AdminUser = Depends(get_current_admin), db: AsyncSession = Depends(get_db)
) -> AdminMeOut:
    if not admin.totp_secret_encrypted:
        raise HTTPException(400, "Avval /admin/2fa/setup chaqiring")
    if not verify_totp_code(_decrypt_totp_secret(admin), payload.code):
        raise HTTPException(400, "Kod noto'g'ri")

    admin.is_2fa_enabled = True
    role = await db.get(AdminRole, admin.role_id)
    await record_audit(db, actor_type=ActorType.ADMIN, actor_id=admin.id, action="2fa_enabled")
    await db.commit()
    return AdminMeOut(id=admin.id, username=admin.username, role_name=role.name, is_2fa_enabled=True)
