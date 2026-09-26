import secrets

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.db.models import Referral, User
from deps import get_db
from schemas import UserCreate, UserGetOrCreate, UserOut

router = APIRouter(prefix="/users", tags=["users"])


@router.post("", response_model=UserOut)
async def create_user(payload: UserCreate, db: AsyncSession = Depends(get_db)) -> User:
    user = User(
        telegram_user_id=payload.telegram_user_id,
        username=payload.username,
        first_name=payload.first_name,
        referral_code=secrets.token_urlsafe(6),
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user


@router.post("/get-or-create", response_model=UserOut)
async def get_or_create_user(payload: UserGetOrCreate, db: AsyncSession = Depends(get_db)) -> User:
    """Bot /start bosqichida chaqiriladi — idempotent, referral_code bo'lsa referral yozuvini yaratadi."""
    user = await db.scalar(select(User).where(User.telegram_user_id == payload.telegram_user_id))
    if user is not None:
        return user

    referrer = None
    if payload.referral_code:
        referrer = await db.scalar(select(User).where(User.referral_code == payload.referral_code))

    user = User(
        telegram_user_id=payload.telegram_user_id,
        username=payload.username,
        first_name=payload.first_name,
        last_name=payload.last_name,
        language_code=payload.language_code,
        referral_code=secrets.token_urlsafe(6),
        referred_by_user_id=referrer.id if referrer else None,
    )
    db.add(user)
    await db.flush()

    if referrer is not None:
        db.add(Referral(referrer_user_id=referrer.id, referred_user_id=user.id, code=payload.referral_code))

    await db.commit()
    await db.refresh(user)
    return user


@router.get("/{user_id}", response_model=UserOut)
async def get_user(user_id: int, db: AsyncSession = Depends(get_db)) -> User:
    user = await db.get(User, user_id)
    if user is None:
        raise HTTPException(404, "Foydalanuvchi topilmadi")
    return user
