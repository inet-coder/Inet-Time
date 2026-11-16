"""Web App ma'lumotlar bazasi.

Egasi (konstruktor, Mini App tokeni):  /webapp/bots/{bot_id}/app/collections...
Ilovaning o'zi (ommaviy):              /webapp/apps/{app_id}/data/{key}
    read=public — hamma ko'radi (yashirin maydonlarsiz);
    read=own    — faqat Telegram imzosi (X-Telegram-Init-Data) bilan, har kim faqat o'z yozuvlarini;
    read=none   — ilovada ko'rinmaydi (faqat egasi)."""

import json

from fastapi import APIRouter, Depends, Header, HTTPException, Query
from fastapi.responses import Response
from pydantic import BaseModel, Field
from sqlalchemy import Numeric, cast, delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from core import crypto
from core.appdata import (
    MAX_COLLECTIONS,
    MAX_RECORDS,
    DataError,
    clean_record,
    from_csv,
    image_fields,
    record_view,
    to_csv,
    validate_collection,
)
from core.db.models import AppCollection, AppRecord, MediaFile, User, UserBot, WebApp
from core.webapp_auth import InitDataError, validate_init_data
from deps import get_db
from routers.webapp import current_user
from routers.webapp_apps import _public_app, _require_app

router = APIRouter(prefix="/webapp", tags=["webapp-data"])

MAX_PAGE = 100


def _collection_out(c: AppCollection, count: int = 0) -> dict:
    return {"id": c.id, "key": c.key, "name": c.name, "read": c.read, "create": c.create, "fields": c.fields, "count": count}


async def _owned_collection(db: AsyncSession, app: WebApp, cid: int) -> AppCollection:
    c = await db.get(AppCollection, cid)
    if c is None or c.app_id != app.id:
        raise HTTPException(404, "To'plam topilmadi")
    return c


async def _media_ok(db: AsyncSession, user: User, fields: list[dict], data: dict) -> set[int]:
    ids = {int(data[k]) for k in image_fields(fields) if data.get(k) not in (None, "")}
    if not ids:
        return set()
    return set(await db.scalars(select(MediaFile.id).where(MediaFile.id.in_(ids), MediaFile.user_id == user.id)))


def _query(c: AppCollection, *, q: str | None, sort: str | None, direction: str, filter_field: str | None, filter_value: str | None, own: int | None):
    fields = {f["key"]: f for f in c.fields}
    query = select(AppRecord).where(AppRecord.collection_id == c.id)
    if own is not None:
        query = query.where(AppRecord.created_by_tg == own)
    if q:
        term = q.strip()[:100].replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
        # Faqat matnli maydonlar QIYMATLARI bo'yicha (kalit nomlari va rasm id'lari emas)
        searchable = [k for k, f in fields.items() if f["type"] in ("text", "longtext", "select", "phone", "email", "url", "number", "money", "date")]
        if searchable:
            haystack = func.concat_ws(" ", *[AppRecord.data[k].astext for k in searchable])
            query = query.where(haystack.ilike(f"%{term}%", escape="\\"))
    if filter_field and filter_field in fields and filter_value is not None:
        f = fields[filter_field]
        if f["type"] == "bool":
            query = query.where(AppRecord.data[filter_field].astext == ("true" if filter_value in ("true", "1", "ha") else "false"))
        else:
            query = query.where(AppRecord.data[filter_field].astext == filter_value[:200])
    if sort and sort in fields:
        col = AppRecord.data[sort].astext
        if fields[sort]["type"] in ("number", "money"):
            col = cast(col, Numeric)
        query = query.order_by(col.desc().nulls_last() if direction == "desc" else col.asc().nulls_last(), AppRecord.id.desc())
    else:
        query = query.order_by(AppRecord.id.desc() if direction != "asc" else AppRecord.id.asc())
    return query


# --- Egasi: to'plamlar ---


@router.get("/bots/{bot_id}/app/collections")
async def list_collections(bot_id: int, user: User = Depends(current_user), db: AsyncSession = Depends(get_db)) -> dict:
    _, app = await _require_app(db, user, bot_id)
    rows = (
        await db.execute(
            select(AppCollection, func.count(AppRecord.id))
            .outerjoin(AppRecord, AppRecord.collection_id == AppCollection.id)
            .where(AppCollection.app_id == app.id)
            .group_by(AppCollection.id)
            .order_by(AppCollection.id)
        )
    ).all()
    return {"items": [_collection_out(c, n) for c, n in rows], "limits": {"collections": MAX_COLLECTIONS, "records": MAX_RECORDS}}


class CollectionIn(BaseModel):
    key: str
    name: str
    read: str = "public"
    create: bool = False
    fields: list[dict]


@router.post("/bots/{bot_id}/app/collections")
async def create_collection(bot_id: int, payload: CollectionIn, user: User = Depends(current_user), db: AsyncSession = Depends(get_db)) -> dict:
    _, app = await _require_app(db, user, bot_id)
    try:
        data = validate_collection(payload.model_dump())
    except DataError as exc:
        raise HTTPException(400, str(exc)) from exc
    count = await db.scalar(select(func.count(AppCollection.id)).where(AppCollection.app_id == app.id))
    if count >= MAX_COLLECTIONS:
        raise HTTPException(400, f"Bitta ilovada ko'pi bilan {MAX_COLLECTIONS} ta to'plam")
    if await db.scalar(select(AppCollection.id).where(AppCollection.app_id == app.id, AppCollection.key == data["key"])):
        raise HTTPException(409, f"«{data['key']}» kalitli to'plam bor — boshqa kalit tanlang")
    c = AppCollection(app_id=app.id, **data)
    db.add(c)
    await db.commit()
    return _collection_out(c)


@router.put("/bots/{bot_id}/app/collections/{cid}")
async def update_collection(bot_id: int, cid: int, payload: CollectionIn, user: User = Depends(current_user), db: AsyncSession = Depends(get_db)) -> dict:
    _, app = await _require_app(db, user, bot_id)
    c = await _owned_collection(db, app, cid)
    try:
        data = validate_collection({**payload.model_dump(), "key": c.key})  # kalit o'zgarmaydi (ilova unga bog'langan)
    except DataError as exc:
        raise HTTPException(400, str(exc)) from exc
    c.name, c.read, c.create, c.fields = data["name"], data["read"], data["create"], data["fields"]
    await db.commit()
    count = await db.scalar(select(func.count(AppRecord.id)).where(AppRecord.collection_id == c.id))
    return _collection_out(c, count)


@router.delete("/bots/{bot_id}/app/collections/{cid}")
async def delete_collection(bot_id: int, cid: int, user: User = Depends(current_user), db: AsyncSession = Depends(get_db)) -> dict:
    _, app = await _require_app(db, user, bot_id)
    c = await _owned_collection(db, app, cid)
    await db.delete(c)
    await db.commit()
    return {"ok": True}


# --- Egasi: yozuvlar ---


@router.get("/bots/{bot_id}/app/collections/{cid}/records")
async def list_records(
    bot_id: int,
    cid: int,
    q: str | None = None,
    sort: str | None = None,
    dir: str = "desc",
    offset: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=MAX_PAGE),
    user: User = Depends(current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    _, app = await _require_app(db, user, bot_id)
    c = await _owned_collection(db, app, cid)
    query = _query(c, q=q, sort=sort, direction=dir, filter_field=None, filter_value=None, own=None)
    total = await db.scalar(select(func.count()).select_from(query.order_by(None).subquery()))
    rows = list(await db.scalars(query.offset(offset).limit(limit)))
    return {
        "items": [
            {**record_view(c.fields, r.id, r.data, show_private=True), "_by": r.created_by_tg, "_at": r.created_at.isoformat() if r.created_at else None}
            for r in rows
        ],
        "total": total,
    }


class RecordIn(BaseModel):
    data: dict


async def _check_room(db: AsyncSession, c: AppCollection, extra: int = 1) -> None:
    count = await db.scalar(select(func.count(AppRecord.id)).where(AppRecord.collection_id == c.id))
    if count + extra > MAX_RECORDS:
        raise HTTPException(400, f"To'plamda ko'pi bilan {MAX_RECORDS} ta yozuv")


@router.post("/bots/{bot_id}/app/collections/{cid}/records")
async def create_record(bot_id: int, cid: int, payload: RecordIn, user: User = Depends(current_user), db: AsyncSession = Depends(get_db)) -> dict:
    _, app = await _require_app(db, user, bot_id)
    c = await _owned_collection(db, app, cid)
    await _check_room(db, c)
    try:
        data = clean_record(c.fields, payload.data, owned_media=await _media_ok(db, user, c.fields, payload.data))
    except DataError as exc:
        raise HTTPException(400, str(exc)) from exc
    r = AppRecord(collection_id=c.id, data=data)
    db.add(r)
    await db.commit()
    return record_view(c.fields, r.id, r.data, show_private=True)


@router.put("/bots/{bot_id}/app/collections/{cid}/records/{rid}")
async def update_record(bot_id: int, cid: int, rid: int, payload: RecordIn, user: User = Depends(current_user), db: AsyncSession = Depends(get_db)) -> dict:
    _, app = await _require_app(db, user, bot_id)
    c = await _owned_collection(db, app, cid)
    r = await db.get(AppRecord, rid)
    if r is None or r.collection_id != c.id:
        raise HTTPException(404, "Yozuv topilmadi")
    try:
        r.data = clean_record(c.fields, payload.data, owned_media=await _media_ok(db, user, c.fields, payload.data))
    except DataError as exc:
        raise HTTPException(400, str(exc)) from exc
    await db.commit()
    return record_view(c.fields, r.id, r.data, show_private=True)


class IdsIn(BaseModel):
    ids: list[int] = Field(max_length=500)


@router.post("/bots/{bot_id}/app/collections/{cid}/records/delete")
async def delete_records(bot_id: int, cid: int, payload: IdsIn, user: User = Depends(current_user), db: AsyncSession = Depends(get_db)) -> dict:
    _, app = await _require_app(db, user, bot_id)
    c = await _owned_collection(db, app, cid)
    result = await db.execute(delete(AppRecord).where(AppRecord.collection_id == c.id, AppRecord.id.in_(payload.ids)))
    await db.commit()
    return {"deleted": result.rowcount}


@router.get("/bots/{bot_id}/app/collections/{cid}/export.csv")
async def export_csv(bot_id: int, cid: int, user: User = Depends(current_user), db: AsyncSession = Depends(get_db)) -> Response:
    _, app = await _require_app(db, user, bot_id)
    c = await _owned_collection(db, app, cid)
    rows = list(await db.scalars(select(AppRecord).where(AppRecord.collection_id == c.id).order_by(AppRecord.id)))
    body = to_csv(c.fields, [(r.id, r.data) for r in rows])
    return Response(body, media_type="text/csv; charset=utf-8", headers={"Content-Disposition": f'attachment; filename="{c.key}.csv"'})


class ImportIn(BaseModel):
    csv: str = Field(max_length=2_000_000)


@router.post("/bots/{bot_id}/app/collections/{cid}/import")
async def import_csv(bot_id: int, cid: int, payload: ImportIn, user: User = Depends(current_user), db: AsyncSession = Depends(get_db)) -> dict:
    _, app = await _require_app(db, user, bot_id)
    c = await _owned_collection(db, app, cid)
    count = await db.scalar(select(func.count(AppRecord.id)).where(AppRecord.collection_id == c.id))
    room = MAX_RECORDS - count
    if room <= 0:
        raise HTTPException(400, f"To'plamda ko'pi bilan {MAX_RECORDS} ta yozuv")
    try:
        rows = from_csv(c.fields, payload.csv, room)
    except DataError as exc:
        raise HTTPException(400, str(exc)) from exc
    db.add_all([AppRecord(collection_id=c.id, data=d) for d in rows])
    await db.commit()
    return {"imported": len(rows)}


@router.get("/bots/{bot_id}/app/data/{key}")
async def preview_data(
    bot_id: int,
    key: str,
    q: str | None = None,
    sort: str | None = None,
    dir: str = "desc",
    limit: int = Query(20, ge=1, le=MAX_PAGE),
    filter_field: str | None = None,
    filter_value: str | None = None,
    record: int | None = None,
    user: User = Depends(current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Konstruktordagi jonli ko'rinish uchun: egasi hamma yozuvlarni ko'radi."""
    _, app = await _require_app(db, user, bot_id)
    c = await db.scalar(select(AppCollection).where(AppCollection.app_id == app.id, AppCollection.key == key))
    if c is None:
        return {"items": [], "missing": True}
    if record is not None:
        r = await db.get(AppRecord, record)
        return {"items": [record_view(c.fields, r.id, r.data, show_private=True)] if r and r.collection_id == c.id else []}
    query = _query(c, q=q, sort=sort, direction=dir, filter_field=filter_field, filter_value=filter_value, own=None)
    rows = list(await db.scalars(query.limit(limit)))
    return {"items": [record_view(c.fields, r.id, r.data, show_private=True) for r in rows]}


# --- Ilovaning o'zi ---


def _tg_user(bot: UserBot, init_data: str | None) -> dict | None:
    if not init_data:
        return None
    try:
        return validate_init_data(init_data, crypto.decrypt_packed(bot.token_encrypted))
    except InitDataError:
        return None


@router.get("/apps/{app_id}/data/{key}")
async def public_data(
    app_id: int,
    key: str,
    q: str | None = None,
    sort: str | None = None,
    dir: str = "desc",
    limit: int = Query(20, ge=1, le=MAX_PAGE),
    offset: int = Query(0, ge=0),
    filter_field: str | None = None,
    filter_value: str | None = None,
    record: int | None = None,
    x_telegram_init_data: str | None = Header(None),
    db: AsyncSession = Depends(get_db),
) -> Response:
    app, bot = await _public_app(db, app_id)
    c = await db.scalar(select(AppCollection).where(AppCollection.app_id == app.id, AppCollection.key == key))
    if c is None or c.read == "none":
        raise HTTPException(404, "Ma'lumot topilmadi")
    own = None
    if c.read == "own":
        tg = _tg_user(bot, x_telegram_init_data)
        if tg is None:
            raise HTTPException(401, "Ilovani Telegram ichida, bot orqali oching")
        own = int(tg["id"])
    show_private = c.read == "own"
    if record is not None:
        r = await db.get(AppRecord, record)
        if r is None or r.collection_id != c.id or (own is not None and r.created_by_tg != own):
            raise HTTPException(404, "Yozuv topilmadi")
        items = [record_view(c.fields, r.id, r.data, show_private=show_private)]
    else:
        query = _query(c, q=q, sort=sort, direction=dir, filter_field=filter_field, filter_value=filter_value, own=own)
        rows = list(await db.scalars(query.offset(offset).limit(limit)))
        items = [record_view(c.fields, r.id, r.data, show_private=show_private) for r in rows]
    # Shaxsiy ma'lumot keshlanmasin; ommaviy ro'yxat qisqa muddat keshlanadi
    cache = "private, no-store" if own is not None else "public, max-age=15"
    return Response(json.dumps({"items": items}, ensure_ascii=False), media_type="application/json", headers={"Cache-Control": cache})


@router.get("/apps/{app_id}/records-media/{media_id}")
async def record_media(app_id: int, media_id: int, db: AsyncSession = Depends(get_db)) -> Response:
    """Ommaviy to'plam yozuvlaridagi rasmlar."""
    app, _ = await _public_app(db, app_id)
    collections = list(await db.scalars(select(AppCollection).where(AppCollection.app_id == app.id, AppCollection.read == "public")))
    for c in collections:
        for key in image_fields(c.fields):
            hit = await db.scalar(
                select(AppRecord.id).where(AppRecord.collection_id == c.id, AppRecord.data[key].astext == str(media_id)).limit(1)
            )
            if hit:
                media = await db.get(MediaFile, media_id)
                if media is None:
                    break
                return Response(media.data, media_type=media.mime, headers={"Cache-Control": "public, max-age=604800"})
    raise HTTPException(404, "Rasm topilmadi")


async def save_form_record(db: AsyncSession, app: WebApp, key: str, values: dict, tg_user_id: int) -> int | None:
    """Forma «to'plamga saqlash» sozlangan bo'lsa — yozuv yaratadi. Xato bo'lsa DataError."""
    c = await db.scalar(select(AppCollection).where(AppCollection.app_id == app.id, AppCollection.key == key))
    if c is None:
        return None
    count = await db.scalar(select(func.count(AppRecord.id)).where(AppRecord.collection_id == c.id))
    if count >= MAX_RECORDS:
        raise DataError("Qabul qilish vaqtincha to'xtatilgan (to'plam to'lgan)")
    data = clean_record(c.fields, values, from_user=True)
    r = AppRecord(collection_id=c.id, data=data, created_by_tg=tg_user_id)
    db.add(r)
    await db.flush()
    return r.id
