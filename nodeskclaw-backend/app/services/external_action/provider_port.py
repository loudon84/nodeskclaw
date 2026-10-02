from __future__ import annotations

from typing import Any

from app.services.external_action.composio_client import ComposioClient


class ExternalActionProviderPort:
    idempotency_support = False
    supports_execution_inspection = False

    async def create_session(self, **kwargs: Any) -> str:
        raise NotImplementedError

    async def execute(self, **kwargs: Any) -> dict[str, Any]:
        raise NotImplementedError

    async def close_session(self, session_id: str) -> None:
        raise NotImplementedError


class ComposioExternalActionProvider(ExternalActionProviderPort):
    idempotency_support = False
    supports_execution_inspection = False

    def __init__(self, client: ComposioClient | None = None):
        self.client = client or ComposioClient()

    async def create_session(self, **kwargs: Any) -> str:
        return await self.client.create_session(**kwargs)

    async def execute(self, **kwargs: Any) -> dict[str, Any]:
        return await self.client.execute(
            session_id=kwargs["session_id"],
            provider_tool_key=kwargs["provider_tool_key"],
            arguments=kwargs.get("arguments") or {},
        )

    async def close_session(self, session_id: str) -> None:
        await self.client.close_session(session_id)
