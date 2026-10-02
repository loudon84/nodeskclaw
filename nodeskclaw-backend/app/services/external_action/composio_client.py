from __future__ import annotations

from typing import Any

import httpx

from app.core.config import settings
from app.core.exceptions import BadRequestError


class ComposioCallError(Exception):
    def __init__(self, kind: str, message: str):
        super().__init__(message)
        self.kind = kind


class ComposioClient:
    def __init__(self, *, api_key: str | None = None, base_url: str | None = None, transport: httpx.AsyncBaseTransport | None = None):
        self.api_key = api_key if api_key is not None else settings.COMPOSIO_API_KEY
        self.base_url = (base_url if base_url is not None else settings.COMPOSIO_BASE_URL).rstrip("/")
        self._transport = transport

    def _require_key(self) -> str:
        if not self.api_key:
            raise BadRequestError(
                "管理员尚未配置外部账号连接",
                "errors.integration.composio_unconfigured",
            )
        return self.api_key

    async def create_connect_link(self, *, provider_user_id: str, toolkit_slug: str) -> str:
        auth_config_id = await self._default_auth_config(toolkit_slug)
        payload = await self._request(
            "POST",
            "/api/v3/connected_accounts/link",
            json={"user_id": provider_user_id, "auth_config_id": auth_config_id},
        )
        url = payload.get("redirect_url") or payload.get("redirectUrl") or payload.get("url")
        if not isinstance(url, str) or not url.strip():
            raise ComposioCallError("tool_error", "connect link missing")
        return url.strip()

    async def find_connected_account(self, *, provider_user_id: str, toolkit_slug: str) -> str | None:
        payload = await self._request(
            "GET",
            "/api/v3/connected_accounts",
            params={
                "user_ids": provider_user_id,
                "toolkit_slugs": toolkit_slug,
                "statuses": "ACTIVE",
            },
        )
        items = payload.get("items") or payload.get("connected_accounts") or []
        if isinstance(payload, dict) and not items and isinstance(payload.get("id"), str):
            items = [payload]
        for item in items if isinstance(items, list) else []:
            if not isinstance(item, dict):
                continue
            status = str(item.get("status") or "ACTIVE").upper()
            if status not in {"ACTIVE", "CONNECTED"}:
                continue
            account_id = item.get("id") or item.get("connected_account_id")
            if isinstance(account_id, str) and account_id.strip():
                return account_id.strip()
        return None

    async def list_active_account_ids(self, *, provider_user_id: str, toolkit_slug: str) -> list[str]:
        payload = await self._request(
            "GET",
            "/api/v3/connected_accounts",
            params={
                "user_ids": provider_user_id,
                "toolkit_slugs": toolkit_slug,
                "statuses": "ACTIVE",
            },
        )
        items = payload.get("items") or payload.get("connected_accounts") or []
        if isinstance(payload, dict) and not items and isinstance(payload.get("id"), str):
            items = [payload]
        found: list[str] = []
        for item in items if isinstance(items, list) else []:
            if not isinstance(item, dict):
                continue
            status = str(item.get("status") or "ACTIVE").upper()
            if status not in {"ACTIVE", "CONNECTED"}:
                continue
            account_id = item.get("id") or item.get("connected_account_id")
            if isinstance(account_id, str) and account_id.strip() and account_id.strip() not in found:
                found.append(account_id.strip())
        return found

    async def revoke_connected_account(self, connected_account_id: str) -> None:
        if not connected_account_id:
            return
        await self._request("DELETE", f"/api/v3/connected_accounts/{connected_account_id}")

    async def create_session(
        self,
        *,
        provider_user_id: str,
        connected_account_id: str = "",
        toolkit_slug: str = "",
        connected_account_ids: list[str] | None = None,
        toolkit_slugs: list[str] | None = None,
        tool_allowlist: list[str] | None = None,
    ) -> str:
        accounts = list(connected_account_ids or [])
        if not accounts and connected_account_id:
            accounts = [connected_account_id]
        toolkits = list(toolkit_slugs or [])
        if not toolkits and toolkit_slug:
            toolkits = [toolkit_slug]
        body: dict[str, Any] = {
            "user_id": provider_user_id,
            "toolkits": {"enable": toolkits},
            "connected_accounts": {"enable": accounts},
        }
        if tool_allowlist:
            body["tools"] = {"enable": list(tool_allowlist)}
        payload = await self._request(
            "POST",
            "/api/v3/tool_router/session",
            json=body,
        )
        session_id = payload.get("session_id") or payload.get("id")
        if not isinstance(session_id, str) or not session_id.strip():
            raise ComposioCallError("tool_error", "session id missing")
        return session_id.strip()

    async def execute(self, *, session_id: str, provider_tool_key: str, arguments: dict[str, Any]) -> dict[str, Any]:
        payload = await self._request(
            "POST",
            f"/api/v3/tool_router/session/{session_id}/execute",
            json={"tool_slug": provider_tool_key, "arguments": arguments},
        )
        return payload

    async def close_session(self, session_id: str) -> None:
        if not session_id:
            return
        await self._request("DELETE", f"/api/v3/tool_router/session/{session_id}")

    async def _default_auth_config(self, toolkit_slug: str) -> str:
        payload = await self._request(
            "GET",
            "/api/v3/auth_configs",
            params={"toolkit_slug": toolkit_slug},
        )
        items = payload.get("items") or payload.get("auth_configs") or []
        if isinstance(items, list):
            for item in items:
                if isinstance(item, dict) and isinstance(item.get("id"), str) and item["id"].strip():
                    return item["id"].strip()
        raise ComposioCallError("tool_error", "auth config missing")

    async def _request(self, method: str, path: str, *, json: dict | None = None, params: dict | None = None) -> dict[str, Any]:
        key = self._require_key()
        try:
            async with httpx.AsyncClient(timeout=httpx.Timeout(30.0, connect=5.0), transport=self._transport) as client:
                response = await client.request(
                    method,
                    f"{self.base_url}{path}",
                    json=json,
                    params=params,
                    headers={"x-api-key": key},
                )
                response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            raise ComposioCallError("tool_error", "provider rejected the request") from exc
        except (httpx.TimeoutException, httpx.NetworkError, OSError) as exc:
            raise ComposioCallError("outcome_unknown", "provider outcome unknown") from exc
        data = response.json()
        return data if isinstance(data, dict) else {}
