import datetime
import random

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import delete, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from core import crypto
from core.db.enums import AutomationStatus, ProfileField, SelectionStrategy, TriggerType
from core.db.models import (
    Automation,
    AutomationAction,
    EncryptedSession,
    ProfileSnapshot,
    Schedule,
    Service,
    TelegramAccount,
)
from core.telegram.field_adapter_factory import get_field_adapter
from core.templates import TemplateContext, render
from deps import get_db
from schemas import (
    ActivateRequest,
    AppliedAction,
    AutomationCreate,
    AutomationOut,
    RunResult,
    StopRequest,
)

router = APIRouter(prefix="/automations", tags=["automations"])

# PHOTO/BIRTHDAY hali FieldAdapter'da implement qilinmagan (BUILD.md: "Kelajakka tayyor").
_UNSUPPORTED_FIELDS = {ProfileField.PHOTO, ProfileField.BIRTHDAY}


async def _get_session_string(db: AsyncSession, account: TelegramAccount) -> str:
    session_row = await db.scalar(
        select(EncryptedSession).where(EncryptedSession.telegram_account_id == account.id)
    )
    if session_row is None or session_row.revoked_at is not None:
        raise HTTPException(409, "Akkaunt sessiyasi mavjud emas yoki bekor qilingan")
    return crypto.decrypt(session_row.ciphertext, session_row.nonce, session_row.key_version)


async def _find_conflicts(
    db: AsyncSession, telegram_account_id: int, fields: set[ProfileField], exclude_automation_id: int | None = None
) -> list[dict]:
    query = (
        select(Automation.id, Automation.priority, AutomationAction.field)
        .join(AutomationAction, AutomationAction.automation_id == Automation.id)
        .where(
            Automation.telegram_account_id == telegram_account_id,
            Automation.status == AutomationStatus.ACTIVE,
            AutomationAction.field.in_(fields),
        )
    )
    if exclude_automation_id is not None:
        query = query.where(Automation.id != exclude_automation_id)
    rows = (await db.execute(query)).all()
    return [{"automation_id": aid, "priority": priority.value, "field": field.value} for aid, priority, field in rows]


@router.post("", response_model=AutomationOut)
async def create_automation(payload: AutomationCreate, db: AsyncSession = Depends(get_db)) -> Automation:
    account = await db.get(TelegramAccount, payload.telegram_account_id)
    if account is None:
        raise HTTPException(404, "Telegram akkaunt topilmadi")

    service = await db.scalar(select(Service).where(Service.code == payload.service_code))
    if service is None:
        raise HTTPException(404, f"Service topilmadi: {payload.service_code}")

    try:
        fields = [ProfileField(a.field) for a in payload.actions]
    except ValueError as exc:
        raise HTTPException(400, f"Noma'lum field: {exc}") from exc
    unsupported = [f.value for f in fields if f in _UNSUPPORTED_FIELDS]
    if unsupported:
        raise HTTPException(400, f"Hali implement qilinmagan field(lar): {', '.join(unsupported)}")

    automation = Automation(
        telegram_account_id=account.id,
        service_id=service.id,
        status=AutomationStatus.DRAFT,
        priority=payload.priority,
        restore_on_stop=payload.restore_on_stop,
        selection_strategy=payload.selection_strategy,
    )
    db.add(automation)
    await db.flush()

    for action_in, field in zip(payload.actions, fields):
        db.add(
            AutomationAction(
                automation_id=automation.id,
                field=field,
                template=action_in.template,
                order_index=action_in.order_index,
            )
        )

    db.add(
        Schedule(
            automation_id=automation.id,
            trigger_type=TriggerType(payload.schedule.trigger_type),
            interval_seconds=payload.schedule.interval_seconds,
            cron_expr=payload.schedule.cron_expr,
            window_start_at=payload.schedule.window_start_at,
            window_end_at=payload.schedule.window_end_at,
            timezone=payload.schedule.timezone,
        )
    )

    await db.commit()
    await db.refresh(automation)
    return automation


@router.get("", response_model=list[AutomationOut])
async def list_automations(telegram_account_id: int, db: AsyncSession = Depends(get_db)) -> list[Automation]:
    result = await db.scalars(
        select(Automation).where(Automation.telegram_account_id == telegram_account_id)
    )
    return list(result)


@router.post("/{automation_id}/activate", response_model=AutomationOut)
async def activate_automation(
    automation_id: int, payload: ActivateRequest, db: AsyncSession = Depends(get_db)
) -> Automation:
    automation = await db.get(Automation, automation_id)
    if automation is None:
        raise HTTPException(404, "Automation topilmadi")
    if automation.status not in (AutomationStatus.DRAFT, AutomationStatus.PAUSED, AutomationStatus.ERROR):
        raise HTTPException(400, "Faqat DRAFT/PAUSED/ERROR holatidan faollashtirish mumkin")

    actions = list(
        await db.scalars(select(AutomationAction).where(AutomationAction.automation_id == automation_id))
    )
    fields = {a.field for a in actions}

    conflicts = await _find_conflicts(db, automation.telegram_account_id, fields, exclude_automation_id=automation_id)
    skip_fields: set[ProfileField] = set()

    if conflicts:
        if payload.resolution is None:
            raise HTTPException(409, {"message": "Field conflict", "conflicts": conflicts})
        if payload.resolution == "cancel":
            automation.status = AutomationStatus.CANCELLED
            await db.commit()
            await db.refresh(automation)
            return automation
        if payload.resolution == "replace":
            conflicting_ids = {c["automation_id"] for c in conflicts}
            await db.execute(
                update(Automation).where(Automation.id.in_(conflicting_ids)).values(status=AutomationStatus.PAUSED)
            )
        elif payload.resolution == "merge":
            skip_fields = {ProfileField(c["field"]) for c in conflicts}
            # Bu automation bu fieldlarga umuman egalik qilmaydi — keyinroq boshqa
            # automation to'xtasa ham snapshotsiz "yetim" qo'llanib qolmasligi uchun butunlay olib tashlanadi.
            await db.execute(
                delete(AutomationAction).where(
                    AutomationAction.automation_id == automation_id, AutomationAction.field.in_(skip_fields)
                )
            )
            actions = [a for a in actions if a.field not in skip_fields]
        else:
            raise HTTPException(400, "resolution: replace | merge | cancel bo'lishi kerak")

    account = await db.get(TelegramAccount, automation.telegram_account_id)
    session_string = await _get_session_string(db, account)
    field_adapter = get_field_adapter()
    now = datetime.datetime.now(datetime.timezone.utc)

    for action in actions:
        if action.field in skip_fields:
            continue
        has_snapshot = await db.scalar(
            select(ProfileSnapshot).where(
                ProfileSnapshot.telegram_account_id == account.id,
                ProfileSnapshot.field == action.field,
                ProfileSnapshot.restored == False,  # noqa: E712
            )
        )
        if has_snapshot is None:
            current_value = await field_adapter.get_current_value(session_string, action.field)
            db.add(
                ProfileSnapshot(
                    telegram_account_id=account.id,
                    automation_id=automation.id,
                    field=action.field,
                    value=current_value,
                    captured_at=now,
                )
            )

    automation.status = AutomationStatus.ACTIVE
    automation.started_at = now
    await db.commit()
    await db.refresh(automation)
    return automation


@router.post("/{automation_id}/run-once", response_model=RunResult)
async def run_once(automation_id: int, db: AsyncSession = Depends(get_db)) -> RunResult:
    """Scheduler/worker hali qurilmagan (PHASE 6/7) — bu endpoint dvigatelni qo'lda/testda ishga tushiradi."""
    automation = await db.get(Automation, automation_id)
    if automation is None:
        raise HTTPException(404, "Automation topilmadi")
    if automation.status != AutomationStatus.ACTIVE:
        raise HTTPException(400, "Faqat ACTIVE automation ishga tushirilishi mumkin")

    account = await db.get(TelegramAccount, automation.telegram_account_id)
    session_string = await _get_session_string(db, account)
    schedule = await db.scalar(select(Schedule).where(Schedule.automation_id == automation_id))
    tz = schedule.timezone if schedule else "UTC"

    actions = list(
        await db.scalars(
            select(AutomationAction)
            .where(AutomationAction.automation_id == automation_id)
            .order_by(AutomationAction.order_index)
        )
    )

    # Bir fieldga bir nechta action bo'lsa (Playlist), selection_strategy bo'yicha bittasini tanlaymiz.
    by_field: dict[ProfileField, list[AutomationAction]] = {}
    for action in actions:
        by_field.setdefault(action.field, []).append(action)

    ctx = TemplateContext(first_name=account.first_name, last_name=account.last_name, username=account.username, timezone=tz)
    field_adapter = get_field_adapter()
    applied: list[AppliedAction] = []
    next_index = automation.last_playlist_index

    for field, field_actions in by_field.items():
        # Boshqa ACTIVE automation shu fieldga egalik qilsa (merge holati) — bu yerda o'tkazib yuboramiz.
        owner_conflicts = await _find_conflicts(db, automation.telegram_account_id, {field}, exclude_automation_id=automation_id)
        if owner_conflicts:
            continue

        if len(field_actions) == 1 or automation.selection_strategy == SelectionStrategy.NONE:
            chosen = field_actions[0]
        elif automation.selection_strategy == SelectionStrategy.RANDOM:
            chosen = random.choice(field_actions)
        else:  # SEQUENTIAL
            chosen = field_actions[next_index % len(field_actions)]
            next_index += 1

        rendered = render(chosen.template, ctx)
        try:
            await field_adapter.apply(session_string, field, rendered)
        except Exception as exc:  # noqa: BLE001 — statusga aniq xato yozib qo'yamiz
            automation.status = AutomationStatus.ERROR
            automation.error_message = str(exc)
            await db.commit()
            raise HTTPException(502, f"Field yangilashda xatolik: {exc}") from exc
        applied.append(AppliedAction(field=field.value, value=rendered))

    automation.last_playlist_index = next_index
    if schedule is not None:
        schedule.last_run_at = datetime.datetime.now(datetime.timezone.utc)
    await db.commit()
    return RunResult(applied=applied)


@router.post("/{automation_id}/stop", response_model=AutomationOut)
async def stop_automation(automation_id: int, payload: StopRequest, db: AsyncSession = Depends(get_db)) -> Automation:
    automation = await db.get(Automation, automation_id)
    if automation is None:
        raise HTTPException(404, "Automation topilmadi")
    if automation.status != AutomationStatus.ACTIVE:
        raise HTTPException(400, "Faqat ACTIVE automation to'xtatilishi mumkin")

    restore = payload.restore if payload.restore is not None else automation.restore_on_stop

    if restore:
        own_fields = set(
            await db.scalars(
                select(AutomationAction.field).where(AutomationAction.automation_id == automation_id)
            )
        )
        account = await db.get(TelegramAccount, automation.telegram_account_id)
        session_string = await _get_session_string(db, account)
        field_adapter = get_field_adapter()
        # Snapshot automation_id emas, (akkaunt, field) bo'yicha qidiriladi: "replace" orqali
        # fieldni egallab olgan automation to'xtaganda ham asl (birinchi) qiymat tiklanishi kerak.
        snapshots = list(
            await db.scalars(
                select(ProfileSnapshot).where(
                    ProfileSnapshot.telegram_account_id == account.id,
                    ProfileSnapshot.field.in_(own_fields),
                    ProfileSnapshot.restored == False,  # noqa: E712
                )
            )
        )
        for snap in snapshots:
            if snap.value is not None:
                await field_adapter.apply(session_string, snap.field, snap.value)
            snap.restored = True

    automation.status = AutomationStatus.CANCELLED
    await db.commit()
    await db.refresh(automation)
    return automation
