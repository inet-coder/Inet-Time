"""Mini App manzili: .env'dagi WEBAPP_URL yoki (lokal sinovda) cloudflared quick tunnel'dan."""

import httpx

from core.settings import settings


async def discover_webapp_url() -> str | None:
    if settings.webapp_url:
        return settings.webapp_url
    try:
        async with httpx.AsyncClient(timeout=5) as client:
            hostname = (await client.get(settings.tunnel_metrics_url)).json().get("hostname")
    except (httpx.HTTPError, ValueError):
        return None
    return f"https://{hostname}" if hostname else None
