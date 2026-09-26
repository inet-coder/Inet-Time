from fastapi import FastAPI

from core.settings import settings
from routers import accounts, automations, users

app = FastAPI(title="Userbots API")
app.include_router(users.router)
app.include_router(accounts.router)
app.include_router(automations.router)


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.get("/ready")
async def ready():
    return {"status": "ready", "mock_telegram": settings.mock_telegram}
