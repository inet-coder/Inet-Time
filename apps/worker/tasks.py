import datetime
import random

from sqlalchemy import select, update

from core import crypto
from core.automation_engine import find_conflicts
from core.db.base import async_session
from core.db.enums import AutomationStatus, ProfileField, SelectionStrategy, TelegramAccountStatus, WorkerJobStatus
from core.db.models import (
    Automation,
    AutomationAction,
    EncryptedSession,
    ProfileSnapshot,
    Schedule,
    TelegramAccount,
    WorkerJob,
)
from core.telegram.factory import get_adapter
from core.telegram.field_adapter_factory import get_field_adapter
from core.templates import TemplateContext, render
from core.worker_support.backoff import call_with_backoff
from core.worker_support.lease import AccountBusyError, release_lease, require_lease
from core.worker_support.lock import profile_lock


async def _claim_job(db, job_id: str) -> bool:
    """Idempotency: job faqat PENDING holatda bo'lsa RUNNING'ga o'tadi. Qayta yetkazilsa (arq retry) — o'tkazib yuboriladi."""
    result = await db.execute(
        update(WorkerJob)
        .where(WorkerJob.job_id == job_id, WorkerJob.status == WorkerJobStatus.PENDING)
        .values(status=WorkerJobStatus.RUNNING, started_at=datetime.datetime.now(datetime.timezone.utc))
        .returning(WorkerJob.id)
    )
    claimed = result.first() is not None
    await db.commit()
    return claimed


async def _finish_job(db, job_id: str, status: WorkerJobStatus, payload: dict | None = None, error: str | None = None) -> None:
    job = await db.scalar(select(WorkerJob).where(WorkerJob.job_id == job_id))
    if job is None:
        return
    job.status = status
    if payload is not None:
        job.payload = {**(job.payload or {}), **payload}
    job.error = error
    job.finished_at = datetime.datetime.now(datetime.timezone.utc)
    await db.commit()


async def _get_session_string(db, account: TelegramAccount) -> str:
    session_row = await db.scalar(
        select(EncryptedSession).where(EncryptedSession.telegram_account_id == account.id)
    )
    if session_row is None or session_row.revoked_at is not None:
        raise RuntimeError("Akkaunt sessiyasi mavjud emas yoki bekor qilingan")
    return crypto.decrypt(session_row.ciphertext, session_row.nonce, session_row.key_version)


async def run_automation_once(ctx, automation_id: int, job_id: str) -> None:
    async with async_session() as db:
        if not await _claim_job(db, job_id):
            return

        automation = await db.get(Automation, automation_id)
        if automation is None:
            await _finish_job(db, job_id, WorkerJobStatus.FAILED, error="Automation topilmadi")
            return
        account = await db.get(TelegramAccount, automation.telegram_account_id)

        try:
            if automation.status != AutomationStatus.ACTIVE:
                raise RuntimeError("Faqat ACTIVE automation ishga tushirilishi mumkin")
            await require_lease(ctx["redis"], account.id)

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
            by_field: dict[ProfileField, list[AutomationAction]] = {}
            for a in actions:
                by_field.setdefault(a.field, []).append(a)

            tpl_ctx = TemplateContext(
                first_name=account.first_name, last_name=account.last_name, username=account.username, timezone=tz
            )
            field_adapter = get_field_adapter()
            applied = []
            next_index = automation.last_playlist_index

            async with profile_lock(ctx["redis"], account.id):
                for field, field_actions in by_field.items():
                    conflicts = await find_conflicts(
                        db, automation.telegram_account_id, {field}, exclude_automation_id=automation_id
                    )
                    if conflicts:
                        continue
                    if len(field_actions) == 1 or automation.selection_strategy == SelectionStrategy.NONE:
                        chosen = field_actions[0]
                    elif automation.selection_strategy == SelectionStrategy.RANDOM:
                        chosen = random.choice(field_actions)
                    else:
                        chosen = field_actions[next_index % len(field_actions)]
                        next_index += 1

                    rendered = render(chosen.template, tpl_ctx)
                    await call_with_backoff(field_adapter.apply, session_string, field, rendered)
                    applied.append({"field": field.value, "value": rendered})

            automation.last_playlist_index = next_index
            if schedule is not None:
                schedule.last_run_at = datetime.datetime.now(datetime.timezone.utc)
            await db.commit()
            await _finish_job(db, job_id, WorkerJobStatus.DONE, payload={"applied": applied})
        except AccountBusyError as exc:
            # Vaqtinchalik holat — automation ACTIVE qoladi, keyingi scheduled urinish qayta sinaydi (PHASE 7).
            await _finish_job(db, job_id, WorkerJobStatus.FAILED, error=str(exc))
        except Exception as exc:  # noqa: BLE001 — statusga aniq xato yozib, jobni FAILED belgilaymiz
            automation.status = AutomationStatus.ERROR
            automation.error_message = str(exc)
            await db.commit()
            await _finish_job(db, job_id, WorkerJobStatus.FAILED, error=str(exc))
        finally:
            await release_lease(ctx["redis"], account.id)


async def activate_automation_job(ctx, automation_id: int, job_id: str) -> None:
    async with async_session() as db:
        if not await _claim_job(db, job_id):
            return

        automation = await db.get(Automation, automation_id)
        if automation is None:
            await _finish_job(db, job_id, WorkerJobStatus.FAILED, error="Automation topilmadi")
            return
        account = await db.get(TelegramAccount, automation.telegram_account_id)

        try:
            await require_lease(ctx["redis"], account.id)

            session_string = await _get_session_string(db, account)
            field_adapter = get_field_adapter()
            actions = list(
                await db.scalars(select(AutomationAction).where(AutomationAction.automation_id == automation_id))
            )
            now = datetime.datetime.now(datetime.timezone.utc)

            for action in actions:
                has_snapshot = await db.scalar(
                    select(ProfileSnapshot).where(
                        ProfileSnapshot.telegram_account_id == account.id,
                        ProfileSnapshot.field == action.field,
                        ProfileSnapshot.restored == False,  # noqa: E712
                    )
                )
                if has_snapshot is None:
                    current_value = await call_with_backoff(field_adapter.get_current_value, session_string, action.field)
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
            await _finish_job(db, job_id, WorkerJobStatus.DONE)
        except AccountBusyError as exc:
            await _finish_job(db, job_id, WorkerJobStatus.FAILED, error=str(exc))
        except Exception as exc:  # noqa: BLE001
            automation.status = AutomationStatus.ERROR
            automation.error_message = str(exc)
            await db.commit()
            await _finish_job(db, job_id, WorkerJobStatus.FAILED, error=str(exc))
        finally:
            await release_lease(ctx["redis"], account.id)


async def stop_automation_job(ctx, automation_id: int, job_id: str, restore: bool) -> None:
    async with async_session() as db:
        if not await _claim_job(db, job_id):
            return

        automation = await db.get(Automation, automation_id)
        if automation is None:
            await _finish_job(db, job_id, WorkerJobStatus.FAILED, error="Automation topilmadi")
            return
        account = await db.get(TelegramAccount, automation.telegram_account_id)

        try:
            await require_lease(ctx["redis"], account.id)

            if restore:
                own_fields = set(
                    await db.scalars(
                        select(AutomationAction.field).where(AutomationAction.automation_id == automation_id)
                    )
                )
                session_string = await _get_session_string(db, account)
                field_adapter = get_field_adapter()
                snapshots = list(
                    await db.scalars(
                        select(ProfileSnapshot).where(
                            ProfileSnapshot.telegram_account_id == account.id,
                            ProfileSnapshot.field.in_(own_fields),
                            ProfileSnapshot.restored == False,  # noqa: E712
                        )
                    )
                )
                async with profile_lock(ctx["redis"], account.id):
                    for snap in snapshots:
                        if snap.value is not None:
                            await call_with_backoff(field_adapter.apply, session_string, snap.field, snap.value)
                        snap.restored = True

            automation.status = AutomationStatus.CANCELLED
            await db.commit()
            await _finish_job(db, job_id, WorkerJobStatus.DONE)
        except AccountBusyError as exc:
            await _finish_job(db, job_id, WorkerJobStatus.FAILED, error=str(exc))
        except Exception as exc:  # noqa: BLE001
            automation.status = AutomationStatus.ERROR
            automation.error_message = str(exc)
            await db.commit()
            await _finish_job(db, job_id, WorkerJobStatus.FAILED, error=str(exc))
        finally:
            await release_lease(ctx["redis"], account.id)


async def revoke_account_job(ctx, account_id: int, job_id: str) -> None:
    async with async_session() as db:
        if not await _claim_job(db, job_id):
            return

        account = await db.get(TelegramAccount, account_id)
        if account is None:
            await _finish_job(db, job_id, WorkerJobStatus.FAILED, error="Akkaunt topilmadi")
            return

        try:
            await require_lease(ctx["redis"], account.id)

            session_row = await db.scalar(
                select(EncryptedSession).where(EncryptedSession.telegram_account_id == account_id)
            )
            if session_row is not None and session_row.revoked_at is None:
                session_string = crypto.decrypt(session_row.ciphertext, session_row.nonce, session_row.key_version)
                await call_with_backoff(get_adapter().revoke, session_string)
                session_row.revoked_at = datetime.datetime.now(datetime.timezone.utc)

            account.status = TelegramAccountStatus.REVOKED
            await db.commit()
            await _finish_job(db, job_id, WorkerJobStatus.DONE)
        except Exception as exc:  # noqa: BLE001
            await _finish_job(db, job_id, WorkerJobStatus.FAILED, error=str(exc))
        finally:
            await release_lease(ctx["redis"], account.id)
