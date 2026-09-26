import datetime
import json
import random
from zoneinfo import ZoneInfo

from sqlalchemy import select, update

from core import crypto
from core.automation_engine import find_conflicts
from core.db.base import async_session
from core.db.enums import AutomationStatus, ProfileField, SelectionStrategy, TelegramAccountStatus, WorkerJobStatus
from core.db.models import (
    Automation,
    AutomationAction,
    EncryptedSession,
    MediaFile,
    ProfileSnapshot,
    Schedule,
    TelegramAccount,
    WorkerJob,
)
from core.preview import slot_index
from core.telegram.factory import get_adapter
from core.telegram.field_adapter_factory import get_field_adapter
from core.templates import TemplateContext, render
from core.worker_support.backoff import call_with_backoff
from core.worker_support.lease import AccountBusyError, release_lease, require_lease
from core.worker_support.lock import profile_lock

UNCHANGED_REAPPLY_SECONDS = 600


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


def _choose_by_time(actions: list[AutomationAction], tz: str) -> AutomationAction:
    """Jadval: hozirgi mahalliy vaqtdan oldingi eng oxirgi slot; birinchi slotdan oldin — kechagi oxirgisi."""
    timed = [a for a in actions if a.at_time]
    if not timed:
        return actions[0]
    now = datetime.datetime.now(ZoneInfo(tz)).strftime("%H:%M")
    return timed[slot_index([a.at_time for a in timed], now)]


def _photo_ref_key(automation_id: int) -> str:
    return f"photo_ref:{automation_id}"


async def _apply_photo(ctx, db, session_string: str, automation_id: int, media_id: int) -> None:
    """Yangi rasmni qo'yadi va oldin biz qo'ygan rasmni o'chiradi — profilda bizdan faqat bitta rasm qoladi."""
    media = await db.get(MediaFile, media_id)
    if media is None:
        raise RuntimeError("Rasm topilmadi")
    field_adapter = get_field_adapter()
    new_ref = await call_with_backoff(field_adapter.upload_photo, session_string, media.data)
    old = await ctx["redis"].get(_photo_ref_key(automation_id))
    await ctx["redis"].set(_photo_ref_key(automation_id), json.dumps(new_ref))
    if old:
        try:
            await call_with_backoff(field_adapter.delete_photo, session_string, json.loads(old))
        except Exception:  # noqa: BLE001 — eski rasmni o'chira olmasak ham yangisi qo'yilgan
            pass


async def _cleanup_photo(ctx, session_string: str, automation_id: int, restore: bool) -> None:
    """Xizmat to'xtaganda: restore bo'lsa biz qo'ygan rasm o'chiriladi va asl rasm yana ko'rinadi."""
    old = await ctx["redis"].get(_photo_ref_key(automation_id))
    if old and restore:
        try:
            await call_with_backoff(get_field_adapter().delete_photo, session_string, json.loads(old))
        except Exception:  # noqa: BLE001
            pass
    await ctx["redis"].delete(_photo_ref_key(automation_id), f"last_applied:{automation_id}:{ProfileField.PHOTO.value}")


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
                first_name=account.first_name, last_name=account.last_name, username=account.username, timezone=tz,
                birthday=account.birthday,
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
                    elif automation.selection_strategy == SelectionStrategy.BY_TIME:
                        chosen = _choose_by_time(field_actions, tz)
                    else:
                        chosen = field_actions[next_index % len(field_actions)]
                        next_index += 1

                    rendered = render(chosen.template, tpl_ctx)
                    # O'zgarmagan qiymatni har daqiqada qayta yubormaymiz (FloodWait xavfi); ONLINE esa
                    # doim yangilanishi kerak. TTL tufayli qo'lda o'zgartirilgan profil ham vaqti-vaqti bilan tiklanadi;
                    # rasm esa faqat boshqasiga almashganda qayta yuklanadi.
                    cache_key = f"last_applied:{automation_id}:{field.value}"
                    if field != ProfileField.ONLINE:
                        last = await ctx["redis"].get(cache_key)
                        if last is not None and (last.decode() if isinstance(last, bytes) else last) == rendered:
                            continue
                    if field == ProfileField.PHOTO:
                        await _apply_photo(ctx, db, session_string, automation_id, int(rendered))
                        await ctx["redis"].set(cache_key, rendered)
                    else:
                        await call_with_backoff(field_adapter.apply, session_string, field, rendered)
                        await ctx["redis"].set(cache_key, rendered, ex=UNCHANGED_REAPPLY_SECONDS)
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

            own_fields = set(
                await db.scalars(select(AutomationAction.field).where(AutomationAction.automation_id == automation_id))
            )
            session_string = await _get_session_string(db, account) if restore else ""
            if ProfileField.PHOTO in own_fields:
                await _cleanup_photo(ctx, session_string, automation_id, restore)

            if restore:
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
                # Log out'dan OLDIN: profil asl holiga qaytariladi (keyin sessiya yaroqsiz bo'ladi).
                snapshots = list(
                    await db.scalars(
                        select(ProfileSnapshot).where(
                            ProfileSnapshot.telegram_account_id == account.id,
                            ProfileSnapshot.restored == False,  # noqa: E712
                        )
                    )
                )
                field_adapter = get_field_adapter()
                async with profile_lock(ctx["redis"], account.id):
                    for snap in snapshots:
                        if snap.value is not None:
                            try:
                                await call_with_backoff(field_adapter.apply, session_string, snap.field, snap.value)
                            except Exception:  # noqa: BLE001 — restore best-effort, uzish baribir bajariladi
                                pass
                        snap.restored = True
                    account_automation_ids = list(
                        await db.scalars(select(Automation.id).where(Automation.telegram_account_id == account.id))
                    )
                    for automation_id in account_automation_ids:
                        await _cleanup_photo(ctx, session_string, automation_id, restore=True)
                await call_with_backoff(get_adapter().revoke, session_string)
                session_row.revoked_at = datetime.datetime.now(datetime.timezone.utc)

            await db.execute(
                update(Automation)
                .where(
                    Automation.telegram_account_id == account.id,
                    Automation.status.not_in((AutomationStatus.CANCELLED, AutomationStatus.COMPLETED)),
                )
                .values(status=AutomationStatus.CANCELLED)
            )
            account.status = TelegramAccountStatus.REVOKED
            await db.commit()
            await _finish_job(db, job_id, WorkerJobStatus.DONE)
        except Exception as exc:  # noqa: BLE001
            await _finish_job(db, job_id, WorkerJobStatus.FAILED, error=str(exc))
        finally:
            await release_lease(ctx["redis"], account.id)


async def send_stories_job(ctx, account_id: int, username: str, chat_id: int, job_id: str, story_ids: list[int] | None = None) -> None:
    """Hikoyalarni akkaunt nomidan yuklab olib, foydalanuvchiga bot chatiga yuboradi."""
    # Import shu yerda: stories moduli faqat shu vazifaga kerak.
    import datetime as _dt

    from core.notify import send_media, send_telegram
    from core.settings import settings
    from core.telegram.stories import StoryError, download_stories

    async with async_session() as db:
        if not await _claim_job(db, job_id):
            return
        account = await db.get(TelegramAccount, account_id)
        if account is None:
            await _finish_job(db, job_id, WorkerJobStatus.FAILED, error="Akkaunt topilmadi")
            return
        try:
            session_string = await _get_session_string(db, account)
            peer, files = await download_stories(session_string, username, story_ids)
        except StoryError as exc:
            await send_telegram(chat_id, f"👀 {exc}")
            await _finish_job(db, job_id, WorkerJobStatus.FAILED, error=str(exc))
            return
        except Exception as exc:  # noqa: BLE001 — foydalanuvchiga qisqa xabar, to'liq xato — job'da
            await send_telegram(chat_id, "⚠️ Hikoyalarni olib bo'lmadi. Keyinroq urinib ko'ring.")
            await _finish_job(db, job_id, WorkerJobStatus.FAILED, error=str(exc))
            return

        who = f"@{peer.username}" if peer.username else peer.name
        if not files:
            await send_telegram(chat_id, f"👀 {who}: yuklab olinadigan hikoya yo'q (yo'q yoki himoyalangan).")
            await _finish_job(db, job_id, WorkerJobStatus.DONE, payload={"sent": 0})
            return
        sent = 0
        for info, data in files:
            when = _dt.datetime.fromtimestamp(info.date, ZoneInfo(settings.default_timezone)).strftime("%d.%m %H:%M")
            caption = f"👀 {who} · {when}" + (f"\n{info.caption}" if info.caption else "")
            if await send_media(chat_id, info.kind, data, caption):
                sent += 1
        await _finish_job(db, job_id, WorkerJobStatus.DONE, payload={"sent": sent, "total": len(files)})

