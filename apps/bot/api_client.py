import base64

import httpx

from core.settings import settings


class ApiError(Exception):
    """API foydalanuvchiga ko'rsatsa bo'ladigan xato qaytardi (402 limit, 409 conflict va h.k.)."""

    def __init__(self, status_code: int, detail) -> None:
        self.status_code = status_code
        self.detail = detail
        super().__init__(str(detail))

    @property
    def message(self) -> str:
        if isinstance(self.detail, dict):
            return str(self.detail.get("message", self.detail))
        return str(self.detail)


class ApiClient:
    def __init__(self) -> None:
        self._client = httpx.AsyncClient(base_url=settings.api_base_url, timeout=15)
        self._admin_token: str | None = None

    async def close(self) -> None:
        await self._client.aclose()

    async def _call(self, method: str, path: str, **kwargs):
        resp = await self._client.request(method, path, **kwargs)
        if resp.status_code in (400, 402, 404, 409):
            raise ApiError(resp.status_code, resp.json().get("detail"))
        resp.raise_for_status()
        return resp.json()

    # --- foydalanuvchi ---

    async def get_or_create_user(self, tg_user, referral_code: str | None = None) -> dict:
        return await self._call(
            "POST",
            "/users/get-or-create",
            json={
                "telegram_user_id": tg_user.id,
                "username": tg_user.username,
                "first_name": tg_user.first_name,
                "last_name": tg_user.last_name,
                "language_code": tg_user.language_code,
                "referral_code": referral_code,
            },
        )

    async def get_user(self, user_id: int) -> dict:
        return await self._call("GET", f"/users/{user_id}")

    async def get_overview(self, user_id: int) -> dict:
        return await self._call("GET", f"/users/{user_id}/overview")

    # --- akkaunt ulash ---

    async def qr_login_start(self, user_id: int) -> dict:
        return await self._call("POST", "/accounts/qr-login/start", json={"user_id": user_id})

    async def qr_login_status(self, login_id: str) -> dict:
        return await self._call("GET", f"/accounts/qr-login/{login_id}/status")

    async def phone_login_start(self, user_id: int, phone: str) -> dict:
        return await self._call("POST", "/accounts/phone-login/start", json={"user_id": user_id, "phone": phone})

    async def phone_login_code(self, login_id: str, code: str) -> dict:
        return await self._call("POST", f"/accounts/phone-login/{login_id}/code", json={"code": code})

    async def submit_password(self, login_id: str, password: str) -> dict:
        return await self._call("POST", f"/accounts/login/{login_id}/password", json={"password": password})

    async def revoke_account(self, account_id: int) -> dict:
        return await self._call("POST", f"/accounts/{account_id}/revoke")

    # --- xizmatlar ---

    async def enable_service(
        self,
        account_id: int,
        service_code: str,
        actions: list[dict],
        interval_seconds: int,
        selection_strategy: str = "NONE",
    ) -> dict:
        """Yaratadi va faollashtiradi. Shu fieldni band qilgan boshqa xizmat avtomatik almashtiriladi.
        actions: [{"field", "template", "order_index"?, "at_time"?}]"""
        automation = await self._call(
            "POST",
            "/automations",
            json={
                "telegram_account_id": account_id,
                "service_code": service_code,
                "selection_strategy": selection_strategy,
                "actions": [{"order_index": i, **a} for i, a in enumerate(actions)],
                "schedule": {
                    "trigger_type": "INTERVAL",
                    "interval_seconds": interval_seconds,
                    "timezone": settings.default_timezone,
                },
            },
        )
        return await self._call("POST", f"/automations/{automation['id']}/activate", json={"resolution": "replace"})

    async def upload_media(self, user_id: int, data: bytes) -> int:
        result = await self._call(
            "POST", "/media", json={"user_id": user_id, "data_b64": base64.b64encode(data).decode("ascii")}
        )
        return result["id"]

    async def stop_service(self, automation_id: int, restore: bool = True) -> dict:
        return await self._call("POST", f"/automations/{automation_id}/stop", json={"restore": restore})

    # --- billing ---

    async def list_plans(self) -> list[dict]:
        return await self._call("GET", "/plans")

    async def buy_plan(self, user_id: int, plan_code: str) -> dict:
        return await self._call("POST", "/subscriptions/buy", json={"user_id": user_id, "plan_code": plan_code})

    async def create_topup(self, user_id: int, amount: float) -> dict:
        return await self._call("POST", "/payments/topup", json={"user_id": user_id, "amount": amount})

    # --- admin (bot service-account orqali) ---

    async def _admin_login(self) -> str:
        resp = await self._client.post("/admin/login", json={"username": "admin", "password": settings.admin_secret})
        resp.raise_for_status()
        return resp.json()["access_token"]

    async def _admin_call(self, method: str, path: str, **kwargs):
        if self._admin_token is None:
            self._admin_token = await self._admin_login()
        resp = await self._client.request(method, path, headers={"Authorization": f"Bearer {self._admin_token}"}, **kwargs)
        if resp.status_code == 401:
            self._admin_token = await self._admin_login()
            resp = await self._client.request(
                method, path, headers={"Authorization": f"Bearer {self._admin_token}"}, **kwargs
            )
        if resp.status_code in (400, 402, 404, 409):
            raise ApiError(resp.status_code, resp.json().get("detail"))
        resp.raise_for_status()
        return resp.json()

    async def admin_list_payments(self, status: str | None = None) -> list[dict]:
        return await self._admin_call("GET", "/payments", params={"status": status} if status else {})

    async def admin_confirm_payment(self, payment_id: int) -> dict:
        return await self._admin_call("POST", f"/payments/{payment_id}/confirm")

    async def admin_reject_payment(self, payment_id: int) -> dict:
        return await self._admin_call("POST", f"/payments/{payment_id}/reject", json={})

    async def admin_list_users(self) -> list[dict]:
        return await self._admin_call("GET", "/admin/users")

    async def admin_ban_user(self, user_id: int) -> dict:
        return await self._admin_call("POST", f"/admin/users/{user_id}/ban")

    async def admin_unban_user(self, user_id: int) -> dict:
        return await self._admin_call("POST", f"/admin/users/{user_id}/unban")


api_client = ApiClient()
