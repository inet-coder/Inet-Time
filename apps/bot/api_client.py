import httpx

from core.settings import settings


class ApiClient:
    def __init__(self) -> None:
        self._client = httpx.AsyncClient(base_url=settings.api_base_url, timeout=10)

    async def close(self) -> None:
        await self._client.aclose()

    async def get_or_create_user(
        self,
        telegram_user_id: int,
        username: str | None,
        first_name: str | None,
        last_name: str | None,
        language_code: str | None,
        referral_code: str | None,
    ) -> dict:
        resp = await self._client.post(
            "/users/get-or-create",
            json={
                "telegram_user_id": telegram_user_id,
                "username": username,
                "first_name": first_name,
                "last_name": last_name,
                "language_code": language_code,
                "referral_code": referral_code,
            },
        )
        resp.raise_for_status()
        return resp.json()

    async def list_accounts(self, user_id: int) -> list[dict]:
        resp = await self._client.get("/accounts", params={"user_id": user_id})
        resp.raise_for_status()
        return resp.json()

    async def qr_login_start(self, user_id: int) -> dict:
        resp = await self._client.post("/accounts/qr-login/start", json={"user_id": user_id})
        resp.raise_for_status()
        return resp.json()

    async def qr_login_status(self, login_id: str) -> dict:
        resp = await self._client.get(f"/accounts/qr-login/{login_id}/status")
        resp.raise_for_status()
        return resp.json()

    async def phone_login_start(self, user_id: int, phone: str) -> dict:
        resp = await self._client.post("/accounts/phone-login/start", json={"user_id": user_id, "phone": phone})
        resp.raise_for_status()
        return resp.json()

    async def phone_login_code(self, login_id: str, code: str) -> dict:
        resp = await self._client.post(f"/accounts/phone-login/{login_id}/code", json={"code": code})
        resp.raise_for_status()
        return resp.json()

    async def submit_password(self, login_id: str, password: str) -> dict:
        resp = await self._client.post(f"/accounts/login/{login_id}/password", json={"password": password})
        resp.raise_for_status()
        return resp.json()

    async def revoke_account(self, account_id: int) -> dict:
        resp = await self._client.post(f"/accounts/{account_id}/revoke")
        resp.raise_for_status()
        return resp.json()


api_client = ApiClient()
