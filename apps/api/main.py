from fastapi import FastAPI

from core.settings import settings

app = FastAPI(title="Userbots API")


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.get("/ready")
async def ready():
    return {"status": "ready", "mock_telegram": settings.mock_telegram}
