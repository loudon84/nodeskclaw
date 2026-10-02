from __future__ import annotations

from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm.attributes import flag_modified

from app.models.hermes_skill.hermes_task import HermesTask
from app.services.external_action.composio_client import ComposioCallError, ComposioClient

SESSION_METADATA_KEY = "provider_execution_session_ref"


class ExternalActionBroker:
    def __init__(self, db: AsyncSession, client: ComposioClient | None = None):
        self.db = db
        self.client = client or ComposioClient()

    async def execute(
        self,
        *,
        task: HermesTask,
        provider_user_id: str,
        connected_account_id: str,
        toolkit_slug: str,
        provider_tool_key: str,
        arguments: dict[str, Any],
    ) -> dict[str, Any]:
        metadata = dict(task.routing_metadata or {})
        session_id = str(metadata.get(SESSION_METADATA_KEY) or "")
        if not session_id:
            try:
                session_id = await self.client.create_session(
                    provider_user_id=provider_user_id,
                    connected_account_id=connected_account_id,
                    toolkit_slug=toolkit_slug,
                )
            except ComposioCallError:
                return {"outcome": "tool_error"}
            metadata[SESSION_METADATA_KEY] = session_id
            task.routing_metadata = metadata
            flag_modified(task, "routing_metadata")
            await self.db.commit()
        try:
            payload = await self.client.execute(
                session_id=session_id,
                provider_tool_key=provider_tool_key,
                arguments=arguments,
            )
        except ComposioCallError as exc:
            return {"outcome": exc.kind}
        return {"outcome": "ok", "result": {"isError": False, "content": [{"type": "text", "text": str(payload.get("data") or payload)}]}}

    async def close(self, task: HermesTask) -> None:
        metadata = dict(task.routing_metadata or {})
        session_id = str(metadata.get(SESSION_METADATA_KEY) or "")
        if not session_id:
            return
        try:
            await self.client.close_session(session_id)
        except ComposioCallError:
            pass
        metadata.pop(SESSION_METADATA_KEY, None)
        task.routing_metadata = metadata
        flag_modified(task, "routing_metadata")
        await self.db.commit()
