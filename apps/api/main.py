from fastapi import FastAPI

from core.settings import settings
from routers import accounts, admin, admin_auth, automations, jobs, payments, users

app = FastAPI(title="Userbots API")
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


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.get("/ready")
async def ready():
    return {"status": "ready", "mock_telegram": settings.mock_telegram}
