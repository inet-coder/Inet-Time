"""Foydalanuvchi botlari uchun minimal Telegram Bot API klienti (httpx).

Token URL ichida bo'ladi — shuning uchun httpx'ning INFO loglari o'chiriladi (token logga tushmasin)
va xatolarda URL emas, faqat Telegram'ning izohi ko'rsatiladi."""

import json
import logging

import httpx

logging.getLogger("httpx").setLevel(logging.WARNING)

API = "https://api.telegram.org"


class BotApiError(Exception):
    def __init__(self, code: int, description: str, retry_after: int | None = None) -> None:
        super().__init__(f"{code}: {description}")
        self.code = code
        self.description = description
        self.retry_after = retry_after

    @property
    def token_revoked(self) -> bool:
        # Token BotFather'da o'zgartirilgan / bot o'chirilgan.
        return self.code == 401 or (self.code == 404 and "Not Found" in self.description)

    @property
    def user_blocked(self) -> bool:
        return self.code == 403


async def call(client: httpx.AsyncClient, token: str, method: str, data: dict | None = None, files: dict | None = None, timeout: float | None = None):
    payload = None
    if data is not None:
        # multipart'da murakkab maydonlar (reply_markup) JSON satr bo'lishi kerak
        payload = {k: (json.dumps(v, ensure_ascii=False) if isinstance(v, (dict, list)) else v) for k, v in data.items() if v is not None}
    try:
        if files:
            resp = await client.post(f"{API}/bot{token}/{method}", data=payload, files=files, timeout=timeout)
        else:
            resp = await client.post(f"{API}/bot{token}/{method}", json={k: v for k, v in (data or {}).items() if v is not None}, timeout=timeout)
    except httpx.HTTPError as exc:
        raise BotApiError(0, f"tarmoq xatosi: {type(exc).__name__}") from None
    try:
        body = resp.json()
    except ValueError:
        raise BotApiError(resp.status_code, "Telegram javobi noto'g'ri") from None
    if not body.get("ok"):
        params = body.get("parameters") or {}
        raise BotApiError(body.get("error_code", resp.status_code), body.get("description", ""), params.get("retry_after"))
    return body["result"]


async def get_me(token: str) -> dict:
    async with httpx.AsyncClient(timeout=15) as client:
        return await call(client, token, "getMe")


def looks_like_token(token: str) -> bool:
    head, _, tail = token.partition(":")
    return head.isdigit() and len(tail) >= 30 and all(c.isalnum() or c in "-_" for c in tail)
