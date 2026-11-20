import asyncio
import datetime
import json
import random
from zoneinfo import ZoneInfo

from sqlalchemy import select, update
from telethon.errors import FloodWaitError

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
from core.session_health import handle_session_dead
from core.telegram.errors import ErrorKind, SessionDeadError, classify
from core.telegram.factory import get_adapter
from core.telegram.field_adapter_factory import get_field_adapter
from core.telegram.presence import online_keeper_key
from core.templates import TemplateContext, render
from core.worker_support.backoff import call_with_backoff
from core.worker_support.lease import AccountBusyError, release_lease, require_lease
from core.worker_support.lock import profile_lock

UNCHANGED_REAPPLY_SECONDS = 600
# Vaqtinchalik xatolar (tarmoq, Telegram serveri, timeout) ketma-ket shuncha marta takrorlansagina xizmat
# ERROR bo'ladi. Avval birinchi xatodayoq to'xtardi — «bazi-bazida o'zi o'chib qolish» sababi shu edi.
MAX_TRANSIENT_FAILURES = 15
FAILURE_COUNTER_TTL = 3 * 3600


def _failures_key(automation_id: int) -> str:
    return f"failures:{automation_id}"


def _flood_key(account_id: int) -> str:
    return f"flood:{account_id}"


async def _set_error(db, automation_id: int, message: str) -> None:
    """Faqat ishlayotgan xizmat ERROR bo'ladi — foydalanuvchi shu payt o'chirgan bo'lsa (CANCELLED) tegilmaydi."""
    await db.execute(
        update(Automation)
        .where(
            Automation.id == automation_id,
            Automation.status.in_((AutomationStatus.ACTIVE, AutomationStatus.STARTING)),
        )
        .values(status=AutomationStatus.ERROR, error_message=message[:1000])
    )
    await db.commit()


async def _handle_failure(ctx, db, job_id: str, automation_id: int, account_id: int, exc: Exception, *, tolerate_transient: bool) -> None:
    """Xatoni turiga qarab ishlaydi: sessiya tugagan / doimiy / vaqtinchalik."""
    await db.rollback()
    kind = classify(exc)
    error = f"{type(exc).__name__}: {exc}"

    if kind == ErrorKind.SESSION_DEAD:
        await handle_session_dead(db, account_id, type(exc).__name__)
        await _finish_job(db, job_id, WorkerJobStatus.FAILED, error=error)
        return

    if isinstance(exc, FloodWaitError):
        # Telegram «kuting» dedi — shu akkauntni muddat tugaguncha bezovta qilmaymiz, xizmat to'xtamaydi.
        await ctx["redis"].set(_flood_key(account_id), "1", ex=int(exc.seconds) + 5)
        await _finish_job(db, job_id, WorkerJobStatus.FAILED, error=error)
        return

    if kind == ErrorKind.TRANSIENT and tolerate_transient:
        key = _failures_key(automation_id)
        failures = await ctx["redis"].incr(key)
        await ctx["redis"].expire(key, FAILURE_COUNTER_TTL)
        if failures < MAX_TRANSIENT_FAILURES:
            await _finish_job(db, job_id, WorkerJobStatus.FAILED, error=f"vaqtinchalik ({failures}/{MAX_TRANSIENT_FAILURES}) {error}")
            return

    await _set_error(db, automation_id, str(exc) or type(exc).__name__)
    await _finish_job(db, job_id, WorkerJobStatus.FAILED, error=error)


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
        raise SessionDeadError("Akkaunt sessiyasi mavjud emas yoki bekor qilingan")
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
        account_id = automation.telegram_account_id
        if automation.status != AutomationStatus.ACTIVE:
            # Navbatda turgan payt foydalanuvchi o'chirgan/almashtirgan — bu xato emas, shunchaki o'tkazamiz.
            await _finish_job(db, job_id, WorkerJobStatus.DONE, payload={"skipped": automation.status.value})
            return
        if await ctx["redis"].exists(_flood_key(account_id)):
            await _finish_job(db, job_id, WorkerJobStatus.FAILED, error="FloodWait: akkaunt dam olmoqda")
            return
        account = await db.get(TelegramAccount, account_id)

        try:
            await require_lease(ctx["redis"], account_id)

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

            async with profile_lock(ctx["redis"], account_id):
                for field, field_actions in by_field.items():
                    conflicts = await find_conflicts(
                        db, account_id, {field}, exclude_automation_id=automation_id
                    )
                    if conflicts:
                        continue
                    if field == ProfileField.ONLINE and await ctx["redis"].exists(online_keeper_key(account_id)):
                        # Listener doimiy ulanishda online'ni ushlab turibdi — alohida ulanib-uzilish shart emas.
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
            await ctx["redis"].delete(_failures_key(automation_id))
            await _finish_job(db, job_id, WorkerJobStatus.DONE, payload={"applied": applied})
        except AccountBusyError as exc:
            # Vaqtinchalik holat — automation ACTIVE qoladi, keyingi scheduled urinish qayta sinaydi (PHASE 7).
            await _finish_job(db, job_id, WorkerJobStatus.FAILED, error=str(exc))
        except Exception as exc:  # noqa: BLE001 — turiga qarab: sessiya / doimiy / vaqtinchalik
            await _handle_failure(ctx, db, job_id, automation_id, account_id, exc, tolerate_transient=True)
        finally:
            await release_lease(ctx["redis"], account_id)


async def activate_automation_job(ctx, automation_id: int, job_id: str) -> None:
    async with async_session() as db:
        if not await _claim_job(db, job_id):
            return

        automation = await db.get(Automation, automation_id)
        if automation is None:
            await _finish_job(db, job_id, WorkerJobStatus.FAILED, error="Automation topilmadi")
            return
        account_id = automation.telegram_account_id
        account = await db.get(TelegramAccount, account_id)

        try:
            await require_lease(ctx["redis"], account_id)

            actions = list(
                await db.scalars(select(AutomationAction).where(AutomationAction.automation_id == automation_id))
            )
            now = datetime.datetime.now(datetime.timezone.utc)
            session_string: str | None = None
            field_adapter = get_field_adapter()

            for action in actions:
                has_snapshot = await db.scalar(
                    select(ProfileSnapshot).where(
                        ProfileSnapshot.telegram_account_id == account_id,
                        ProfileSnapshot.field == action.field,
                        ProfileSnapshot.restored == False,  # noqa: E712
                    )
                )
                if has_snapshot is None:
                    if action.field == ProfileField.ONLINE:
                        current_value = None  # online holati tiklanmaydi — Telegram'ga ulanish shart emas
                    else:
                        if session_string is None:
                            session_string = await _get_session_string(db, account)
                        current_value = await call_with_backoff(field_adapter.get_current_value, session_string, action.field)
                    db.add(
                        ProfileSnapshot(
                            telegram_account_id=account_id,
                            automation_id=automation_id,
                            field=action.field,
                            value=current_value,
                            captured_at=now,
                        )
                    )

            automation.status = AutomationStatus.ACTIVE
            automation.error_message = None
            automation.started_at = now
            await db.commit()
            await ctx["redis"].delete(_failures_key(automation_id))
            await _finish_job(db, job_id, WorkerJobStatus.DONE)
        except AccountBusyError as exc:
            await _finish_job(db, job_id, WorkerJobStatus.FAILED, error=str(exc))
        except Exception as exc:  # noqa: BLE001
            await _handle_failure(ctx, db, job_id, automation_id, account_id, exc, tolerate_transient=False)
        finally:
            await release_lease(ctx["redis"], account_id)


async def stop_automation_job(ctx, automation_id: int, job_id: str, restore: bool) -> None:
    """Xizmatni o'chirish HAR DOIM o'tishi kerak: profilni tiklash — best-effort.
    Avval sessiya tugagan bo'lsa yoki tarmoq uzilsa xizmat o'chmay, «xatolik»da qolib ketardi."""
    async with async_session() as db:
        if not await _claim_job(db, job_id):
            return

        automation = await db.get(Automation, automation_id)
        if automation is None:
            await _finish_job(db, job_id, WorkerJobStatus.FAILED, error="Automation topilmadi")
            return
        account_id = automation.telegram_account_id
        account = await db.get(TelegramAccount, account_id)

        try:
            await require_lease(ctx["redis"], account_id)
        except AccountBusyError as exc:
            await _finish_job(db, job_id, WorkerJobStatus.FAILED, error=str(exc))
            return

        restore_errors: list[str] = []
        session_dead_reason: str | None = None
        try:
            own_fields = set(
                await db.scalars(select(AutomationAction.field).where(AutomationAction.automation_id == automation_id))
            )
            session_string = ""
            if restore:
                try:
                    session_string = await _get_session_string(db, account)
                except SessionDeadError:
                    restore = False  # tiklab bo'lmaydi; snapshotlar keyingi ulanish uchun saqlanadi
            if ProfileField.PHOTO in own_fields:
                await _cleanup_photo(ctx, session_string, automation_id, restore)

            if restore:
                field_adapter = get_field_adapter()
                snapshots = list(
                    await db.scalars(
                        select(ProfileSnapshot).where(
                            ProfileSnapshot.telegram_account_id == account_id,
                            ProfileSnapshot.field.in_(own_fields),
                            ProfileSnapshot.restored == False,  # noqa: E712
                        )
                    )
                )
                async with profile_lock(ctx["redis"], account_id):
                    for snap in snapshots:
                        if snap.value is not None:
                            try:
                                await call_with_backoff(field_adapter.apply, session_string, snap.field, snap.value)
                            except Exception as exc:  # noqa: BLE001 — tiklanmagan snapshot saqlanib qoladi
                                restore_errors.append(f"{snap.field.value}: {type(exc).__name__}: {exc}")
                                if classify(exc) == ErrorKind.SESSION_DEAD:
                                    session_dead_reason = type(exc).__name__
                                    break
                                continue
                        snap.restored = True
        except Exception as exc:  # noqa: BLE001
            restore_errors.append(f"{type(exc).__name__}: {exc}")

        try:
            automation.status = AutomationStatus.CANCELLED
            await db.commit()
        except Exception:  # noqa: BLE001 — tranzaksiya buzilgan bo'lsa ham xizmat o'chishi shart
            await db.rollback()
            await db.execute(update(Automation).where(Automation.id == automation_id).values(status=AutomationStatus.CANCELLED))
            await db.commit()
        await ctx["redis"].delete(_failures_key(automation_id))
        await release_lease(ctx["redis"], account_id)

        if session_dead_reason:
            await handle_session_dead(db, account_id, session_dead_reason)
        if restore_errors:
            await _finish_job(db, job_id, WorkerJobStatus.DONE, payload={"restore_errors": restore_errors}, error="; ".join(restore_errors)[:2000])
        else:
            await _finish_job(db, job_id, WorkerJobStatus.DONE)


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
                try:
                    await call_with_backoff(get_adapter().revoke, session_string)
                except Exception as exc:  # noqa: BLE001
                    # Telegram'da sessiya allaqachon tugatilgan — chiqish shart emas, akkaunt baribir o'chiriladi.
                    if classify(exc) != ErrorKind.SESSION_DEAD:
                        raise
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



async def broadcast_job(ctx, broadcast_id: int) -> None:
    """Ommaviy xabar: auditoriyaga ketma-ket yuboradi, har 25 tadan keyin hisobni yangilaydi va bekor qilinganini tekshiradi."""
    import httpx

    from core.broadcasts import SEND_DELAY, SendResult, personalize, recipients, reply_markup, send_one
    from core.db.models import Broadcast
    from core.webapp_url import discover_webapp_url

    async with async_session() as db:
        broadcast = await db.get(Broadcast, broadcast_id)
        if broadcast is None or broadcast.status != "sending":
            return
        users = await recipients(db, broadcast.segment or {})
        broadcast.total = len(users)
        broadcast.started_at = datetime.datetime.now(datetime.timezone.utc)
        await db.commit()
        photo: bytes | str | None = None
        if broadcast.media_id:
            media = await db.get(MediaFile, broadcast.media_id)
            photo = media.data if media else None
        markup = reply_markup(broadcast.buttons or [], await discover_webapp_url())
        text = broadcast.text

    counts = {SendResult.OK: 0, SendResult.BLOCKED: 0, SendResult.FAILED: 0}
    async with httpx.AsyncClient(timeout=30) as client:
        for index, (chat_id, first_name) in enumerate(users, 1):
            result, file_id, _ = await send_one(client, chat_id, personalize(text, first_name), markup, photo)
            counts[result] += 1
            if file_id and isinstance(photo, bytes):
                photo = file_id  # rasm bir marta yuklanadi, keyin file_id bilan
            await asyncio.sleep(SEND_DELAY)
            if index % 25 == 0 or index == len(users):
                async with async_session() as db:
                    broadcast = await db.get(Broadcast, broadcast_id)
                    broadcast.sent, broadcast.blocked, broadcast.failed = counts[SendResult.OK], counts[SendResult.BLOCKED], counts[SendResult.FAILED]
                    cancelled = broadcast.status == "cancelled"
                    await db.commit()
                if cancelled:
                    break

    async with async_session() as db:
        broadcast = await db.get(Broadcast, broadcast_id)
        broadcast.sent, broadcast.blocked, broadcast.failed = counts[SendResult.OK], counts[SendResult.BLOCKED], counts[SendResult.FAILED]
        if broadcast.status == "sending":
            broadcast.status = "done"
        broadcast.finished_at = datetime.datetime.now(datetime.timezone.utc)
        await db.commit()


async def user_bot_broadcast_job(ctx, broadcast_id: int) -> None:
    """Foydalanuvchi botining obunachilariga xabar: ~20 xabar/soniya, 429 bo'lsa retry_after kutiladi,
    botni bloklaganlar belgilanadi (keyingi safar ularga yuborilmaydi)."""
    import httpx

    from core.botapi import BotApiError, call
    from core.db.models import BotBroadcast, BotSubscriber, UserBot

    async with async_session() as db:
        item = await db.get(BotBroadcast, broadcast_id)
        if item is None or item.status != "sending":
            return
        bot = await db.get(UserBot, item.bot_id)
        if bot is None:
            return
        token = crypto.decrypt_packed(bot.token_encrypted)
        from core.segments import conditions

        chat_ids = list(await db.scalars(select(BotSubscriber.tg_user_id).where(*conditions(item.segment or "all", bot.id))))
        photo = None
        if item.media_id:
            media = await db.get(MediaFile, item.media_id)
            photo = (media.data, media.mime) if media else None
        text = item.text
        copy_from = (item.from_chat_id, item.message_id) if item.from_chat_id and item.message_id else None
        # Egasi o'zi ham obunachi bo'lishi mumkin — o'ziga nusxa yuborilmaydi.
        if copy_from:
            chat_ids = [c for c in chat_ids if c != copy_from[0]]
        item.total = len(chat_ids)
        await db.commit()

    sent = failed = 0
    revoked = False
    blocked: list[int] = []
    file_id: str | None = None
    async with httpx.AsyncClient(timeout=30) as client:
        for index, chat_id in enumerate(chat_ids, 1):
            for _attempt in range(3):
                try:
                    if copy_from is not None:
                        await call(client, token, "copyMessage", {"chat_id": chat_id, "from_chat_id": copy_from[0], "message_id": copy_from[1]})
                    elif photo is not None:
                        if file_id is None:
                            data, mime = photo
                            result = await call(client, token, "sendPhoto", {"chat_id": chat_id, "caption": text}, files={"photo": ("photo.jpg", data, mime)})
                            file_id = result["photo"][-1]["file_id"]
                        else:
                            await call(client, token, "sendPhoto", {"chat_id": chat_id, "photo": file_id, "caption": text})
                    else:
                        await call(client, token, "sendMessage", {"chat_id": chat_id, "text": text})
                    sent += 1
                except BotApiError as exc:
                    if exc.retry_after is not None:
                        await asyncio.sleep(exc.retry_after + 1)
                        continue
                    if exc.token_revoked:
                        failed += len(chat_ids) - index + 1
                        revoked = True  # token bekor — qolganlarga yuborib bo'lmaydi
                    elif exc.user_blocked:
                        blocked.append(chat_id)
                        failed += 1
                    else:
                        failed += 1
                break
            if revoked:
                break
            await asyncio.sleep(0.05)
            if index % 50 == 0:
                async with async_session() as db:
                    item = await db.get(BotBroadcast, broadcast_id)
                    item.sent, item.failed = sent, failed
                    await db.commit()

    async with async_session() as db:
        if blocked:
            await db.execute(
                update(BotSubscriber)
                .where(BotSubscriber.bot_id == bot.id, BotSubscriber.tg_user_id.in_(blocked))
                .values(blocked=True)
            )
        item = await db.get(BotBroadcast, broadcast_id)
        item.sent, item.failed = sent, failed
        item.status = "done"
        item.finished_at = datetime.datetime.now(datetime.timezone.utc)
        await db.commit()

    if copy_from is not None and not revoked:
        # Bot ichidan boshlangan tarqatish — natijani egasiga o'sha botning o'zida aytamiz.
        try:
            async with httpx.AsyncClient(timeout=30) as client:
                await call(
                    client,
                    token,
                    "sendMessage",
                    {"chat_id": copy_from[0], "text": f"✅ Xabar tarqatildi\n\n📬 Yetkazildi: {sent}\n⚠️ Yetmadi: {failed}\n👥 Jami: {len(chat_ids)}"},
                )
        except BotApiError:
            pass
