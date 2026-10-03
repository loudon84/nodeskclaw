from __future__ import annotations

from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm.attributes import flag_modified

from app.models.hermes_skill.hermes_task import HermesTask
from app.services.external_action.composio_client import ComposioCallError, ComposioClient
from app.services.external_action.provider_port import ComposioExternalActionProvider, ExternalActionProviderPort
from app.services.external_action.scope import scope_digest

SESSION_METADATA_KEY = "provider_execution_session_ref"
SESSION_SET_METADATA_KEY = "provider_execution_session_set"
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
        session_set = self._session_set(metadata)
        principal = str((scope or {}).get("provider_user_id") or provider_user_id)
        entry = session_set.get(principal) if isinstance(session_set.get(principal), dict) else {}
        session_id = str(entry.get("session_ref") or "")
        stored_digest = str(entry.get("scope_digest") or "")
        if not session_id:
            session_id = str(metadata.get(SESSION_METADATA_KEY) or "")
            stored_digest = str(metadata.get(SCOPE_DIGEST_KEY) or "")
            if session_id and str(metadata.get("provider_user_id") or principal) != principal:
                session_id = ""
                stored_digest = ""
        required = scope_digest(scope) if scope is not None else ""
        if session_id and scope is not None and not stored_digest:
            return {"outcome": "fail_run"}
        if session_id and required and stored_digest and stored_digest != required:
            await self._drop_principal_session(task, metadata, principal, session_id, warning=False)
            metadata = dict(task.routing_metadata or {})
            session_set = self._session_set(metadata)
            session_id = ""
        if not session_id:
            if scope is not None and not list(scope.get("tool_allowlist") or []):
                return {"outcome": "fail_run"}
            try:
                if scope is not None:
                    pins = [
                        pin
                        for pin in list(scope.get("account_pins") or [])
                        if str(pin.get("provider_user_id") or principal) == principal
                    ]
                    if not pins:
                        pins = list(scope.get("account_pins") or [])
                    session_id = await self.provider.create_session(
                        provider_user_id=principal,
                        connected_account_ids=[
                            str(pin.get("connected_account_id") or "")
                            for pin in pins
                            if pin.get("connected_account_id")
                        ],
                        toolkit_slugs=sorted({str(pin.get("toolkit_slug") or "") for pin in pins if pin.get("toolkit_slug")})
                        or list(scope.get("toolkit_allowlist") or []),
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
            session_set[principal] = {
                "session_ref": session_id,
                "provider_user_id": principal,
                "scope_digest": required,
            }
            metadata[SESSION_SET_METADATA_KEY] = session_set
            metadata[SESSION_METADATA_KEY] = session_id
            if required:
                metadata[SCOPE_DIGEST_KEY] = required
            metadata["provider_user_id"] = principal
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
        session_set = self._session_set(metadata)
        warning = False
        principals = list(session_set.keys())
        if not principals:
            legacy = str(metadata.get(SESSION_METADATA_KEY) or "")
            if legacy:
                principals = ["__legacy__"]
                session_set["__legacy__"] = {"session_ref": legacy}
        for principal in principals:
            entry = session_set.get(principal) if isinstance(session_set.get(principal), dict) else {}
            session_id = str(entry.get("session_ref") or "")
            if not session_id:
                continue
            try:
                await self.provider.close_session(session_id)
            except ComposioCallError:
                warning = True
        self._clear_session_set(metadata, warning=warning)
        task.routing_metadata = metadata
        flag_modified(task, "routing_metadata")
        await self.db.commit()

    async def _drop_principal_session(
        self,
        task: HermesTask,
        metadata: dict[str, Any],
        principal: str,
        session_id: str,
        *,
        warning: bool,
    ) -> None:
        try:
            await self.provider.close_session(session_id)
        except ComposioCallError:
            warning = True
        session_set = self._session_set(metadata)
        session_set.pop(principal, None)
        metadata[SESSION_SET_METADATA_KEY] = session_set
        if str(metadata.get(SESSION_METADATA_KEY) or "") == session_id:
            metadata.pop(SESSION_METADATA_KEY, None)
            metadata.pop(SCOPE_DIGEST_KEY, None)
        if warning:
            metadata[CLOSE_WARNING_KEY] = "CLOSED_WITH_WARNING"
        task.routing_metadata = metadata
        flag_modified(task, "routing_metadata")
        await self.db.commit()

    def _session_set(self, metadata: dict[str, Any]) -> dict[str, Any]:
        raw = metadata.get(SESSION_SET_METADATA_KEY)
        if isinstance(raw, dict):
            return dict(raw)
        return {}

    def _clear_session_set(self, metadata: dict[str, Any], *, warning: bool) -> None:
        metadata.pop(SESSION_SET_METADATA_KEY, None)
        metadata.pop(SESSION_METADATA_KEY, None)
        metadata.pop(SCOPE_DIGEST_KEY, None)
        metadata.pop("provider_user_id", None)
        if warning:
            metadata[CLOSE_WARNING_KEY] = "CLOSED_WITH_WARNING"
