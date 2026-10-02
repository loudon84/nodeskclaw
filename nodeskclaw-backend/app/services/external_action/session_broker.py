from __future__ import annotations

from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm.attributes import flag_modified

from app.models.hermes_skill.hermes_task import HermesTask
from app.services.external_action.composio_client import ComposioCallError, ComposioClient
from app.services.external_action.provider_port import ComposioExternalActionProvider, ExternalActionProviderPort
from app.services.external_action.scope import scope_digest

SESSION_METADATA_KEY = "provider_execution_session_ref"
SCOPE_DIGEST_KEY = "provider_execution_scope_digest"
CLOSE_WARNING_KEY = "provider_execution_session_close"


class ExternalActionBroker:
    def __init__(
        self,
        db: AsyncSession,
        client: ComposioClient | None = None,
        provider: ExternalActionProviderPort | None = None,
    ):
        self.db = db
        self.client = client or ComposioClient()
        self.provider = provider or ComposioExternalActionProvider(self.client)

    async def execute(
        self,
        *,
        task: HermesTask,
        provider_user_id: str,
        connected_account_id: str,
        toolkit_slug: str,
        provider_tool_key: str,
        arguments: dict[str, Any],
        scope: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        metadata = dict(task.routing_metadata or {})
        session_id = str(metadata.get(SESSION_METADATA_KEY) or "")
        stored_digest = str(metadata.get(SCOPE_DIGEST_KEY) or "")
        required = scope_digest(scope) if scope is not None else ""
        if session_id and scope is not None and not stored_digest:
            return {"outcome": "fail_run"}
        if session_id and required and stored_digest and stored_digest != required:
            await self._drop_session(task, metadata, session_id, warning=False)
            metadata = dict(task.routing_metadata or {})
            session_id = ""
        if not session_id:
            if scope is not None and not list(scope.get("tool_allowlist") or []):
                return {"outcome": "fail_run"}
            try:
                if scope is not None:
                    pins = list(scope.get("account_pins") or [])
                    session_id = await self.provider.create_session(
                        provider_user_id=str(scope.get("provider_user_id") or provider_user_id),
                        connected_account_ids=[str(pin.get("connected_account_id") or "") for pin in pins if pin.get("connected_account_id")],
                        toolkit_slugs=list(scope.get("toolkit_allowlist") or []),
                        tool_allowlist=list(scope.get("tool_allowlist") or []),
                    )
                else:
                    session_id = await self.provider.create_session(
                        provider_user_id=provider_user_id,
                        connected_account_id=connected_account_id,
                        toolkit_slug=toolkit_slug,
                    )
            except ComposioCallError:
                return {"outcome": "tool_error"}
            metadata[SESSION_METADATA_KEY] = session_id
            if required:
                metadata[SCOPE_DIGEST_KEY] = required
            task.routing_metadata = metadata
            flag_modified(task, "routing_metadata")
            await self.db.commit()
        try:
            payload = await self.provider.execute(
                session_id=session_id,
                provider_tool_key=provider_tool_key,
                arguments=arguments,
            )
        except ComposioCallError as exc:
            return {"outcome": exc.kind}
        request_id = payload.get("request_id") if isinstance(payload.get("request_id"), str) else None
        return {
            "outcome": "ok",
            "request_id": request_id,
            "result": {"isError": False, "content": [{"type": "text", "text": str(payload.get("data") or payload)}]},
        }

    async def close(self, task: HermesTask) -> None:
        metadata = dict(task.routing_metadata or {})
        session_id = str(metadata.get(SESSION_METADATA_KEY) or "")
        if not session_id:
            return
        warning = False
        try:
            await self.provider.close_session(session_id)
        except ComposioCallError:
            warning = True
        self._clear_session(metadata, warning=warning)
        task.routing_metadata = metadata
        flag_modified(task, "routing_metadata")
        await self.db.commit()

    async def _drop_session(self, task: HermesTask, metadata: dict[str, Any], session_id: str, *, warning: bool) -> None:
        try:
            await self.provider.close_session(session_id)
        except ComposioCallError:
            warning = True
        self._clear_session(metadata, warning=warning)
        task.routing_metadata = metadata
        flag_modified(task, "routing_metadata")
        await self.db.commit()

    def _clear_session(self, metadata: dict[str, Any], *, warning: bool) -> None:
        metadata.pop(SESSION_METADATA_KEY, None)
        if warning:
            metadata[CLOSE_WARNING_KEY] = "CLOSED_WITH_WARNING"
