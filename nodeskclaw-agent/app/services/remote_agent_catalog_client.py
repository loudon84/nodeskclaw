from __future__ import annotations

from typing import Any

import httpx

from app.config import settings


class RemoteAgentCatalogClient:
    def __init__(self, *, base_url: str | None = None, token: str | None = None) -> None:
        self.base_url = (base_url or settings.SKILL_AGENT_CENTRAL_BASE_URL).rstrip("/")
        self.token = token if token is not None else settings.SKILL_AGENT_INTERNAL_TOKEN

    async def list_tools(
        self,
        *,
        org_id: str,
        binding_ids: list[str],
        account_ids: list[str] | None = None,
        expert_id: str | None = None,
        user_id: str | None = None,
    ) -> list[dict[str, Any]]:
        body = await self._post(
            "/api/v1/internal/v1/skill-agent/remote-agent/tools",
            {
                "org_id": org_id,
                "binding_ids": binding_ids,
                "account_ids": list(account_ids or []),
                "expert_id": expert_id or "",
                "user_id": user_id or "",
            },
        )
        tools = body.get("tools") if isinstance(body, dict) else None
        return list(tools or [])

    async def resolve_route(self, *, org_id: str, binding_ids: list[str], tool_name: str) -> dict[str, Any] | None:
        try:
            return await self._post(
                "/api/v1/internal/v1/skill-agent/remote-agent/connector-route",
                {"org_id": org_id, "binding_ids": binding_ids, "tool_name": tool_name},
            )
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code == 404:
                return None
            raise

    async def execute_external(self, *, run_id: str, tool_name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        return await self._post(
            "/api/v1/internal/v1/skill-agent/remote-agent/external-execute",
            {"run_id": run_id, "tool_name": tool_name, "arguments": arguments},
        )

    async def close_external_session(self, run_id: str) -> None:
        await self._post(
            "/api/v1/internal/v1/skill-agent/remote-agent/external-close",
            {"run_id": run_id},
        )

    async def _post(self, path: str, payload: dict[str, Any]) -> dict[str, Any]:
        async with httpx.AsyncClient(timeout=httpx.Timeout(30.0, connect=5.0)) as client:
            response = await client.post(
                f"{self.base_url}{path}",
                json=payload,
                headers={"X-Skill-Agent-Token": self.token},
            )
            response.raise_for_status()
            data = response.json()
        return data if isinstance(data, dict) else {}
