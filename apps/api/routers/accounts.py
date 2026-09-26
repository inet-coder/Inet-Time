import datetime
import logging

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core import crypto
from core.db.enums import TelegramAccountStatus
from core.db.models import EncryptedSession, TelegramAccount, User
from core.entitlements import EntitlementError, check_can_add_account
from core.settings import settings
from core.telegram.enums import LoginStatus
from core.telegram.factory import get_adapter
from core.telegram.mock_adapter import MockAdapter
from core.telegram.types import LoginState
from deps import get_db
from jobs import enqueue
from schemas import (
    AccountOut,
    CodeSubmit,
    JobQueuedOut,
    LoginStatusOut,
    MockSimulateScan,
    PasswordSubmit,
    PhoneLoginStart,
    QrLoginStart,
)

router = APIRouter(prefix="/accounts", tags=["accounts"])
logger = logging.getLogger(__name__)

# login_id -> qaysi user nomidan login boshlangani. Faqat shu api processi xotirasida;
# PHASE 6'da worker/lease tizimiga ko'chganda Redisga o'tadi.
_pending_user_by_login: dict[str, int] = {}
_completed: dict[str, LoginStatusOut] = {}


async def _require_user(user_id: int, db: AsyncSession) -> User:
    user = await db.get(User, user_id)
    if user is None:
        raise HTTPException(404, "Foydalanuvchi topilmadi")
    return user


async def _persist_success(db: AsyncSession, user_id: int, state: LoginState) -> TelegramAccount:
    existing = await db.scalar(
        select(TelegramAccount).where(TelegramAccount.telegram_user_id == state.telegram_user_id)
    )
    is_new_for_user = (
        existing is None or existing.user_id != user_id or existing.status == TelegramAccountStatus.REVOKED
    )
    if is_new_for_user:
        try:
            await check_can_add_account(db, user_id)
        except EntitlementError as exc:
            # Telegram tomonida sessiya allaqachon yaratilgan — saqlamaymiz, "osilib" qolmasligi uchun chiqamiz.
            try:
                await get_adapter().revoke(state.session_string)
            except Exception:  # noqa: BLE001
                pass
            raise HTTPException(402, str(exc)) from exc

    now = datetime.datetime.now(datetime.timezone.utc)
    if existing is None:
        account = TelegramAccount(
            user_id=user_id,
            telegram_user_id=state.telegram_user_id,
            username=state.username,
            first_name=state.first_name,
            last_name=state.last_name,
            is_premium=state.is_premium,
            status=TelegramAccountStatus.CONNECTED,
            last_connected_at=now,
        )
        db.add(account)
        await db.flush()
    else:
        if existing.user_id != user_id and existing.status not in (
            TelegramAccountStatus.REVOKED,
            TelegramAccountStatus.ERROR,
        ):
            raise HTTPException(409, "Bu Telegram akkaunt allaqachon boshqa foydalanuvchiga ulangan")
        account = existing
        account.user_id = user_id
        account.username = state.username
        account.first_name = state.first_name
        account.last_name = state.last_name
        account.is_premium = state.is_premium
        account.status = TelegramAccountStatus.CONNECTED
        account.last_connected_at = now

    ciphertext, nonce, key_version = crypto.encrypt(state.session_string)
    session_row = await db.scalar(
        select(EncryptedSession).where(EncryptedSession.telegram_account_id == account.id)
    )
    if session_row is None:
        db.add(
            EncryptedSession(
                telegram_account_id=account.id, ciphertext=ciphertext, nonce=nonce, key_version=key_version
            )
        )
    else:
        session_row.ciphertext = ciphertext
        session_row.nonce = nonce
        session_row.key_version = key_version
        session_row.revoked_at = None

    await db.commit()
    await db.refresh(account)
    return account


async def _handle_state(login_id: str, state: LoginState, db: AsyncSession) -> LoginStatusOut:
    if login_id in _completed:
        return _completed[login_id]

    if state.status == LoginStatus.SUCCESS:
        user_id = _pending_user_by_login.pop(login_id, None)
        if user_id is None:
            raise HTTPException(500, "login_id uchun boshlang'ich foydalanuvchi topilmadi")
        try:
            account = await _persist_success(db, user_id, state)
        except HTTPException as exc:
            # Keyingi status so'rovlari ham shu xatoni ko'rsin (500 emas).
            await get_adapter().cleanup(login_id)
            status = "LIMIT_REACHED" if exc.status_code == 402 else LoginStatus.ERROR.value
            resp = LoginStatusOut(login_id=login_id, status=status, error=str(exc.detail))
            _completed[login_id] = resp
            return resp
        await get_adapter().cleanup(login_id)
        resp = LoginStatusOut(
            login_id=login_id,
            status=state.status.value,
            account_id=account.id,
            telegram_user_id=account.telegram_user_id,
            username=account.username,
        )
        _completed[login_id] = resp
        return resp

    if state.status == LoginStatus.EXPIRED:
        # ERROR (masalan noto'g'ri kod) tozalanmaydi — foydalanuvchi shu login_id bilan qayta urinishi mumkin.
        _pending_user_by_login.pop(login_id, None)
        await get_adapter().cleanup(login_id)

    return LoginStatusOut(
        login_id=login_id, status=state.status.value, qr_url=state.qr_url, error=state.error
    )


async def _require_account_slot(user_id: int, db: AsyncSession) -> None:
    """Foydalanuvchi QR skanerlashdan OLDIN limit haqida bilsin (asosiy tekshiruv _persist_success'da)."""
    try:
        await check_can_add_account(db, user_id)
    except EntitlementError as exc:
        raise HTTPException(402, str(exc)) from exc


@router.post("/qr-login/start", response_model=LoginStatusOut)
async def qr_login_start(payload: QrLoginStart, db: AsyncSession = Depends(get_db)) -> LoginStatusOut:
    await _require_user(payload.user_id, db)
    await _require_account_slot(payload.user_id, db)
    state = await get_adapter().start_qr_login()
    _pending_user_by_login[state.login_id] = payload.user_id
    return LoginStatusOut(login_id=state.login_id, status=state.status.value, qr_url=state.qr_url)


@router.get("/qr-login/{login_id}/status", response_model=LoginStatusOut)
async def qr_login_status(login_id: str, db: AsyncSession = Depends(get_db)) -> LoginStatusOut:
    state = await get_adapter().get_login_state(login_id)
    return await _handle_state(login_id, state, db)


@router.post("/phone-login/start", response_model=LoginStatusOut)
async def phone_login_start(payload: PhoneLoginStart, db: AsyncSession = Depends(get_db)) -> LoginStatusOut:
    await _require_user(payload.user_id, db)
    await _require_account_slot(payload.user_id, db)
    try:
        state = await get_adapter().start_phone_login(payload.phone)
    except Exception as exc:  # noqa: BLE001 — Telegram xatosi (noto'g'ri raqam, FloodWait) foydalanuvchiga texnik ko'rinmasin
        logger.warning("phone login start failed: %s", type(exc).__name__)
        raise HTTPException(400, "Bu raqamga kod yuborib bo'lmadi. Raqamni tekshirib, qaytadan urinib ko'ring.") from exc
    _pending_user_by_login[state.login_id] = payload.user_id
    return LoginStatusOut(login_id=state.login_id, status=state.status.value)


@router.post("/phone-login/{login_id}/code", response_model=LoginStatusOut)
async def phone_login_code(login_id: str, payload: CodeSubmit, db: AsyncSession = Depends(get_db)) -> LoginStatusOut:
    state = await get_adapter().submit_code(login_id, payload.code)
    return await _handle_state(login_id, state, db)


@router.post("/login/{login_id}/password", response_model=LoginStatusOut)
async def submit_password(login_id: str, payload: PasswordSubmit, db: AsyncSession = Depends(get_db)) -> LoginStatusOut:
    state = await get_adapter().submit_password(login_id, payload.password)
    return await _handle_state(login_id, state, db)


@router.post("/mock/{login_id}/simulate-scan", response_model=LoginStatusOut)
async def mock_simulate_scan(
    login_id: str, payload: MockSimulateScan, db: AsyncSession = Depends(get_db)
) -> LoginStatusOut:
    if not settings.mock_telegram:
        raise HTTPException(404, "Faqat MOCK_TELEGRAM=true rejimida mavjud")
    adapter = get_adapter()
    assert isinstance(adapter, MockAdapter)
    state = await adapter.simulate_scan(
        login_id,
        need_password=payload.need_password,
        telegram_user_id=payload.telegram_user_id,
        username=payload.username,
        first_name=payload.first_name,
        last_name=payload.last_name,
        is_premium=payload.is_premium,
    )
    return await _handle_state(login_id, state, db)


@router.get("", response_model=list[AccountOut])
async def list_accounts(user_id: int, db: AsyncSession = Depends(get_db)) -> list[TelegramAccount]:
    result = await db.scalars(select(TelegramAccount).where(TelegramAccount.user_id == user_id))
    return list(result)


@router.post("/{account_id}/revoke", response_model=JobQueuedOut)
async def revoke_account(account_id: int, db: AsyncSession = Depends(get_db)) -> JobQueuedOut:
    """Session decrypt + Telegram log_out workerga navbatga qo'yiladi (PHASE 6) — API session shifrini ochmaydi."""
    account = await db.get(TelegramAccount, account_id)
    if account is None:
        raise HTTPException(404, "Akkaunt topilmadi")

    job_id = await enqueue(
        db,
        task_name="revoke_account_job",
        telegram_account_id=account.id,
        automation_id=None,
        task_kwargs={"account_id": account.id},
    )
    return JobQueuedOut(job_id=job_id)
