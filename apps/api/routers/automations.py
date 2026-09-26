from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import delete, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from core.automation_engine import find_conflicts
from core.db.enums import AutomationStatus, ProfileField, TriggerType
from core.db.models import Automation, AutomationAction, Schedule, Service, TelegramAccount
from deps import get_db
from jobs import enqueue
from schemas import ActivateRequest, AutomationCreate, AutomationOut, JobQueuedOut, StopRequest

router = APIRouter(prefix="/automations", tags=["automations"])

# PHOTO/BIRTHDAY hali FieldAdapter'da implement qilinmagan (BUILD.md: "Kelajakka tayyor").
_UNSUPPORTED_FIELDS = {ProfileField.PHOTO, ProfileField.BIRTHDAY}


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
    result = await db.scalars(select(Automation).where(Automation.telegram_account_id == telegram_account_id))
    return list(result)


@router.post("/{automation_id}/activate")
async def activate_automation(automation_id: int, payload: ActivateRequest, db: AsyncSession = Depends(get_db)) -> dict:
    """Conflict tekshiruvi va resolution (DB-only, tez) shu yerda; snapshot capture + ACTIVE'ga
    o'tish workerga navbatga qo'yiladi — session shifrini API hech qachon ochmaydi (PHASE 6)."""
    automation = await db.get(Automation, automation_id)
    if automation is None:
        raise HTTPException(404, "Automation topilmadi")
    if automation.status not in (AutomationStatus.DRAFT, AutomationStatus.PAUSED, AutomationStatus.ERROR):
        raise HTTPException(400, "Faqat DRAFT/PAUSED/ERROR holatidan faollashtirish mumkin")

    actions = list(
        await db.scalars(select(AutomationAction).where(AutomationAction.automation_id == automation_id))
    )
    if not actions:
        raise HTTPException(400, "Automationda hech qanday action yo'q")
    fields = {a.field for a in actions}

    conflicts = await find_conflicts(db, automation.telegram_account_id, fields, exclude_automation_id=automation_id)

    if conflicts:
        if payload.resolution is None:
            raise HTTPException(409, {"message": "Field conflict", "conflicts": conflicts})
        if payload.resolution == "cancel":
            automation.status = AutomationStatus.CANCELLED
            await db.commit()
            return {"status": "CANCELLED"}
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
        else:
            raise HTTPException(400, "resolution: replace | merge | cancel bo'lishi kerak")

    remaining = await db.scalar(
        select(AutomationAction).where(AutomationAction.automation_id == automation_id)
    )
    if remaining is None:
        raise HTTPException(409, "Merge'dan keyin hech qanday field qolmadi")

    automation.status = AutomationStatus.STARTING
    await db.commit()

    job_id = await enqueue(
        db,
        task_name="activate_automation_job",
        telegram_account_id=automation.telegram_account_id,
        automation_id=automation.id,
        task_kwargs={"automation_id": automation.id},
    )
    return {"job_id": job_id, "status": "PENDING"}


@router.post("/{automation_id}/run-once", response_model=JobQueuedOut)
async def run_once(automation_id: int, db: AsyncSession = Depends(get_db)) -> JobQueuedOut:
    automation = await db.get(Automation, automation_id)
    if automation is None:
        raise HTTPException(404, "Automation topilmadi")
    if automation.status != AutomationStatus.ACTIVE:
        raise HTTPException(400, "Faqat ACTIVE automation ishga tushirilishi mumkin")

    job_id = await enqueue(
        db,
        task_name="run_automation_once",
        telegram_account_id=automation.telegram_account_id,
        automation_id=automation.id,
        task_kwargs={"automation_id": automation.id},
    )
    return JobQueuedOut(job_id=job_id)


@router.post("/{automation_id}/stop", response_model=JobQueuedOut)
async def stop_automation(automation_id: int, payload: StopRequest, db: AsyncSession = Depends(get_db)) -> JobQueuedOut:
    automation = await db.get(Automation, automation_id)
    if automation is None:
        raise HTTPException(404, "Automation topilmadi")
    if automation.status != AutomationStatus.ACTIVE:
        raise HTTPException(400, "Faqat ACTIVE automation to'xtatilishi mumkin")

    restore = payload.restore if payload.restore is not None else automation.restore_on_stop

    job_id = await enqueue(
        db,
        task_name="stop_automation_job",
        telegram_account_id=automation.telegram_account_id,
        automation_id=automation.id,
        task_kwargs={"automation_id": automation.id, "restore": restore},
    )
    return JobQueuedOut(job_id=job_id)
