import hmac
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from sqlalchemy import select

from core.admin_auth import hash_password, verify_password
from core.db.base import async_session
from core.db.models import AdminUser
from core.settings import settings
from routers import accounts, admin, admin_auth, automations, jobs, payments, users, webapp, webapp_admin, webapp_admin_tools, webapp_ai, webapp_profile

if settings.is_production and (missing := settings.missing_production_secrets()):
    raise RuntimeError(f"Production uchun .env'da yetishmaydi: {', '.join(missing)}")

logger = logging.getLogger("api")


async def sync_service_admin_password() -> None:
    """Bot ishlatadigan "admin" hisobining paroli doim ADMIN_SECRET bilan bir xil bo'lsin.

    Yangi bazada migratsiya vaqtinchalik (zaif) parol qo'yadi — server birinchi ishga tushganda almashtiriladi."""
    if not settings.admin_secret:
        return
    async with async_session() as db:
        admin = await db.scalar(select(AdminUser).where(AdminUser.username == "admin"))
        if admin is not None and not verify_password(settings.admin_secret, admin.password_hash):
            admin.password_hash = hash_password(settings.admin_secret)
            await db.commit()
            logger.info("admin paroli ADMIN_SECRET bilan yangilandi")


@asynccontextmanager
async def lifespan(_: FastAPI):
    await sync_service_admin_password()
    yield


# Production'da API sxemasi (/docs) tashqariga ko'rsatilmaydi.
docs = {} if not settings.is_production else {"docs_url": None, "redoc_url": None, "openapi_url": None}
app = FastAPI(title="Userbots API", lifespan=lifespan, **docs)

# Tashqaridan (Mini App orqali) faqat shular ochiq; qolgan hamma narsa — bot uchun ichki API.
PUBLIC_PREFIXES = ("/webapp/", "/health", "/ready")


@app.middleware("http")
async def internal_only(request: Request, call_next):
    if not request.url.path.startswith(PUBLIC_PREFIXES):
        token = settings.internal_api_token
        if token:
            given = request.headers.get("x-internal-token", "")
            if not hmac.compare_digest(given.encode(), token.encode()):
                return JSONResponse({"detail": "Forbidden"}, status_code=403)
        elif settings.is_production:
            return JSONResponse({"detail": "Forbidden"}, status_code=403)
    return await call_next(request)


app.include_router(users.router)
app.include_router(accounts.router)
app.include_router(automations.router)
app.include_router(automations.services_router)
app.include_router(automations.media_router)
app.include_router(jobs.router)
app.include_router(payments.router)
app.include_router(payments.plans_router)
app.include_router(payments.subscriptions_router)
app.include_router(admin_auth.router)
app.include_router(admin.router)
app.include_router(webapp.router)
app.include_router(webapp_admin.router)
app.include_router(webapp_admin_tools.router)
app.include_router(webapp_admin_tools.user_router)
app.include_router(webapp_admin_tools.internal_router)
app.include_router(webapp_ai.router)
app.include_router(webapp_ai.internal_router)
app.include_router(webapp_profile.router)
app.include_router(webapp_profile.internal_router)


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.get("/ready")
async def ready():
    return {"status": "ready", "mock_telegram": settings.mock_telegram}
