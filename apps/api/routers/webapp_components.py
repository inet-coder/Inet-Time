"""Foydalanuvchining o'z komponentlari: konstruktorda saqlangan erkin bo'laklar.

Bir marta yig'ilgan dizaynni (karta, banner, menyu...) istalgan ilovada qayta ishlatish uchun."""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from core.db.models import MediaFile, User, WebComponent
from core.webapp_builder import MAX_COMPONENTS, WebAppError, referenced_media, validate_component
from deps import get_db
from routers.webapp import current_user

router = APIRouter(prefix="/webapp/components", tags=["webapp-components"])


def _out(c: WebComponent) -> dict:
    return {"id": c.id, "name": c.name, "node": c.node, "created_at": c.created_at.isoformat() if c.created_at else None}


@router.get("")
async def list_components(user: User = Depends(current_user), db: AsyncSession = Depends(get_db)) -> dict:
    rows = await db.scalars(select(WebComponent).where(WebComponent.user_id == user.id).order_by(WebComponent.id.desc()))
    return {"items": [_out(c) for c in rows], "limit": MAX_COMPONENTS}


class ComponentIn(BaseModel):
    name: str = Field(min_length=1, max_length=60)
    node: dict


async def _clean(db: AsyncSession, user: User, node: dict) -> dict:
    ids = referenced_media({"pages": [{"blocks": [{"type": "custom", "root": node}]}]})
    owned = set(await db.scalars(select(MediaFile.id).where(MediaFile.id.in_(ids), MediaFile.user_id == user.id))) if ids else set()
    try:
        return validate_component(node, owned)
    except WebAppError as exc:
        raise HTTPException(400, str(exc)) from exc


@router.post("")
async def create_component(payload: ComponentIn, user: User = Depends(current_user), db: AsyncSession = Depends(get_db)) -> dict:
    count = await db.scalar(select(func.count()).select_from(WebComponent).where(WebComponent.user_id == user.id))
    if (count or 0) >= MAX_COMPONENTS:
        raise HTTPException(400, f"Ko'pi bilan {MAX_COMPONENTS} ta komponent saqlash mumkin")
    comp = WebComponent(user_id=user.id, name=payload.name.strip(), node=await _clean(db, user, payload.node))
    db.add(comp)
    await db.commit()
    await db.refresh(comp)
    return _out(comp)


class RenameIn(BaseModel):
    name: str = Field(min_length=1, max_length=60)


@router.put("/{component_id}")
async def rename_component(component_id: int, payload: RenameIn, user: User = Depends(current_user), db: AsyncSession = Depends(get_db)) -> dict:
    comp = await db.get(WebComponent, component_id)
    if comp is None or comp.user_id != user.id:
        raise HTTPException(404, "Komponent topilmadi")
    comp.name = payload.name.strip()
    await db.commit()
    return _out(comp)


@router.delete("/{component_id}")
async def delete_component(component_id: int, user: User = Depends(current_user), db: AsyncSession = Depends(get_db)) -> dict:
    comp = await db.get(WebComponent, component_id)
    if comp is None or comp.user_id != user.id:
        raise HTTPException(404, "Komponent topilmadi")
    await db.delete(comp)
    await db.commit()
    return {"ok": True}
