"""NEW-API management client. Every call sends both auth headers and never logs response bodies."""

from __future__ import annotations

import logging

import httpx

from app.core.config import settings
from app.services.credential_crypto import MemberTokenError

logger = logging.getLogger(__name__)


class NewApiClient:
    def __init__(self) -> None:
        self.base_url = (settings.NEW_API_ADMIN_BASE_URL or "").rstrip("/")
        self.token = settings.NEW_API_SYSTEM_ACCESS_TOKEN or ""
        self.user_id = str(settings.NEW_API_USER_ID or "")
        self.timeout = float(settings.NEW_API_TIMEOUT_SECONDS or 15)

    def configured(self) -> bool:
        return bool(self.base_url and self.token and self.user_id)

    def require_configured(self) -> None:
        if not self.configured():
            raise MemberTokenError(
                503,
                "errors.member_token.new_api_not_configured",
                "NEW-API 管理端未配置，请检查 backend 的 NEW_API_ADMIN_BASE_URL、NEW_API_SYSTEM_ACCESS_TOKEN 和 NEW_API_USER_ID",
            )

    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self.token}",
            "New-Api-User": self.user_id,
            "Accept": "application/json",
        }

    async def _request(
        self,
        method: str,
        path: str,
        *,
        json: dict | None = None,
        params: dict | None = None,
        failure_key: str,
        failure_message: str,
        not_found_key: str | None = None,
    ) -> object:
        self.require_configured()
        url = f"{self.base_url}{path}"
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.request(
                    method,
                    url,
                    headers=self._headers(),
                    json=json,
                    params=params,
                )
        except httpx.HTTPError as exc:
            logger.warning("NEW-API %s %s transport failed: %s", method, path, type(exc).__name__)
            raise MemberTokenError(502, failure_key, failure_message) from exc
        if response.status_code in (401, 403):
            raise MemberTokenError(
                502,
                "errors.member_token.new_api_auth_failed",
                "NEW-API 鉴权失败，请检查系统访问令牌和 NEW_API_USER_ID",
            )
        if response.status_code == 404 and not_found_key:
            raise MemberTokenError(
                502,
                not_found_key,
                "当前 NEW-API 上找不到该 Token，本地记录保持待关闭",
            )
        try:
            body = response.json()
        except ValueError as exc:
            logger.warning("NEW-API %s %s returned non-JSON status %s", method, path, response.status_code)
            raise MemberTokenError(502, failure_key, failure_message) from exc
        if response.status_code >= 400 or (isinstance(body, dict) and body.get("success") is False):
            logger.warning("NEW-API %s %s failed status %s", method, path, response.status_code)
            raise MemberTokenError(502, failure_key, failure_message)
        if isinstance(body, dict) and "data" in body:
            return body.get("data")
        return body

    async def list_groups(self) -> dict:
        data = await self._request(
            "GET",
            "/api/user/self/groups",
            failure_key="errors.member_token.new_api_groups_failed",
            failure_message="读取 NEW-API 分组失败，请检查 backend 配置和 NEW-API 是否可访问",
        )
        if not isinstance(data, dict):
            raise MemberTokenError(
                502,
                "errors.member_token.new_api_groups_failed",
                "NEW-API 分组响应格式不正确",
            )
        return data

    async def search_exact(self, name: str) -> list[dict]:
        matches: list[dict] = []
        page = 1
        while page <= 20:
            data = await self._request(
                "GET",
                "/api/token/search",
                params={"keyword": name, "p": page, "page_size": 100},
                failure_key="errors.member_token.new_api_search_failed",
                failure_message="按名称搜索 NEW-API Token 失败",
            )
            if not isinstance(data, dict):
                raise MemberTokenError(
                    502,
                    "errors.member_token.new_api_search_failed",
                    "NEW-API Token 搜索响应格式不正确",
                )
            items = data.get("items") or []
            if not isinstance(items, list):
                raise MemberTokenError(
                    502,
                    "errors.member_token.new_api_search_failed",
                    "NEW-API Token 搜索响应格式不正确",
                )
            matches.extend(item for item in items if isinstance(item, dict) and item.get("name") == name)
            total = int(data.get("total") or 0)
            if page * 100 >= total or not items:
                break
            page += 1
        return matches

    async def create_token(self, name: str, group: str) -> None:
        await self._request(
            "POST",
            "/api/token/",
            json={
                "name": name,
                "expired_time": -1,
                "remain_quota": 0,
                "unlimited_quota": True,
                "model_limits_enabled": False,
                "model_limits": "",
                "group": group,
            },
            failure_key="errors.member_token.new_api_create_failed",
            failure_message="创建 NEW-API Token 失败",
        )

    async def fetch_key(self, external_id: str) -> str:
        data = await self._request(
            "POST",
            f"/api/token/{external_id}/key",
            failure_key="errors.member_token.new_api_key_failed",
            failure_message="读取 NEW-API Token Key 失败",
        )
        key = data.get("key") if isinstance(data, dict) else None
        if not isinstance(key, str) or not key:
            raise MemberTokenError(
                502,
                "errors.member_token.new_api_key_failed",
                "NEW-API 未返回 Token Key",
            )
        return key

    async def set_status(self, external_id: str, enabled: bool) -> None:
        await self._request(
            "PUT",
            "/api/token/",
            params={"status_only": "true"},
            json={"id": _external_id(external_id), "status": 1 if enabled else 2},
            failure_key="errors.member_token.new_api_status_failed",
            failure_message="更新 NEW-API Token 状态失败",
        )

    async def update_group(self, external_id: str, group: str) -> None:
        current = await self._request(
            "GET",
            f"/api/token/{external_id}",
            failure_key="errors.member_token.new_api_group_failed",
            failure_message="读取 NEW-API Token 失败，分组未修改",
        )
        if not isinstance(current, dict):
            raise MemberTokenError(
                502,
                "errors.member_token.new_api_group_failed",
                "NEW-API Token 响应格式不正确，分组未修改",
            )
        payload = {key: value for key, value in current.items() if key != "key"}
        payload["id"] = _external_id(external_id)
        payload["group"] = group
        await self._request(
            "PUT",
            "/api/token/",
            json=payload,
            failure_key="errors.member_token.new_api_group_failed",
            failure_message="更新 NEW-API 分组失败，本地分组未修改",
        )

    async def delete_token(self, external_id: str) -> None:
        await self._request(
            "DELETE",
            f"/api/token/{external_id}",
            failure_key="errors.member_token.new_api_delete_failed",
            failure_message="删除 NEW-API Token 失败",
            not_found_key="errors.member_token.new_api_token_missing",
        )


def normalize_groups(raw: dict) -> list[dict]:
    items = []
    for name, info in raw.items():
        if name == "auto":
            continue
        description = ""
        if isinstance(info, dict) and info.get("desc") is not None:
            description = str(info.get("desc"))
        items.append({"value": name, "label": name, "description": description})
    return items


def _external_id(value: str) -> int | str:
    return int(value) if str(value).isdigit() else value
