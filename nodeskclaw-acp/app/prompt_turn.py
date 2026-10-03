from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any

from app.errors import AdapterError, unsupported_content
from app.event_mapper import (
    IGNORED_EVENTS,
    map_tool_result_status,
    reconcile_final,
    safe_artifact_text,
)
from app.permission_bridge import PermissionBridge
from app.profile import Profile
from app.remote_client import RemoteAgentHttpClient
from app.resource_links import artifact_resource_link, parse_prompt_blocks
from app.session_registry import SessionRegistry, SessionState


class PromptTurnController:
    def __init__(
        self,
        profile: Profile,
        registry: SessionRegistry,
        client: RemoteAgentHttpClient,
        permissions: PermissionBridge,
        *,
        artifact_hints: bool = True,
        notify: Callable[[dict[str, Any]], Awaitable[None]] | None = None,
        request_permission: Callable[[dict[str, Any]], Awaitable[str]] | None = None,
    ):
        self.profile = profile
        self.registry = registry
        self.client = client
        self.permissions = permissions
        self.artifact_hints = artifact_hints
        self.notify = notify
        self.request_permission = request_permission

    def _client_request_id(self, state: SessionState) -> str:
        return f"acp:{state.session_id}:{state.turn_seq}"

    async def run_prompt(self, session_id: str, prompt_id: str, blocks: list[Any]) -> dict[str, Any]:
        text, attachment_refs = parse_prompt_blocks(blocks)
        if not text:
            raise unsupported_content()
        state = self.registry.get(session_id)
        if state.remote_busy:
            status, payload = await self.client.get_session_proof_raw(session_id)
            if status == 200 and str(payload.get("status") or "") == "idle":
                state.remote_busy = False
            else:
                raise AdapterError("ACP_SESSION_BUSY", "当前 Session 已有进行中的 Prompt")
        state = self.registry.begin_turn(session_id)
        state.active_prompt_id = prompt_id
        body = {
            "client_request_id": self._client_request_id(state),
            "agent_ref": self.profile.agent_ref,
            "prompt": text,
            "knowledge_refs": list(self.profile.knowledge_refs),
            "connector_binding_refs": list(self.profile.connector_binding_refs),
            "integration_account_refs": list(self.profile.integration_account_refs),
            "attachment_refs": attachment_refs,
            "session_ref": state.session_id,
        }
        try:
            created = await self.client.create_run(body)
        except AdapterError:
            self.registry.end_turn(session_id)
            raise
        run_id = str(created.get("id") or created.get("run_id") or "")
        if not run_id:
            self.registry.end_turn(session_id)
            raise AdapterError("ACP_REMOTE_CREATE_FAILED", "远程未返回 run_id")
        state.active_run_id = run_id
        stop = "end_turn"
        try:
            async for event in self.client.stream_events(run_id, state.last_sse_event_id):
                if state.cancel_requested:
                    await self.client.cancel_run(run_id)
                    stop = "cancelled"
                    break
                event_id = str(event.get("event_id") or "")
                if event_id and event_id in state.seen_event_ids:
                    continue
                if event_id:
                    state.seen_event_ids.add(event_id)
                    state.last_sse_event_id = event_id
                outcome = await self._handle_event(state, event)
                if outcome:
                    stop = outcome
                    break
        except AdapterError as exc:
            if exc.symbol == "ACP_STREAM_RECONCILIATION_MISMATCH" and state.active_run_id:
                try:
                    await self.client.cancel_run(state.active_run_id)
                except Exception:
                    pass
                exc.run_id = state.active_run_id
            self.registry.end_turn(session_id)
            raise
        self.registry.end_turn(session_id)
        return {"stopReason": stop, "run_id": run_id}

    async def cancel(self, session_id: str) -> None:
        state = self.registry.get(session_id)
        state.cancel_requested = True
        if state.active_run_id:
            try:
                await self.client.cancel_run(state.active_run_id)
            except AdapterError as exc:
                raise AdapterError("ACP_CANCEL_FAILED", exc.message, remote_error_code=exc.remote_error_code)

    async def _emit(self, payload: dict[str, Any]) -> None:
        if self.notify:
            await self.notify(payload)

    async def _handle_event(self, state: SessionState, event: dict[str, Any]) -> str | None:
        event_type = str(event.get("event_type") or "")
        data = event.get("data") if isinstance(event.get("data"), dict) else {}
        if event_type in IGNORED_EVENTS:
            return None
        if event_type == "assistant.delta":
            chunk = str(data.get("delta") or data.get("text") or "")
            if chunk:
                state.accumulated_text += chunk
                state.delta_emitted = True
                await self._emit({"sessionUpdate": "agent_message_chunk", "content": {"type": "text", "text": chunk}})
            return None
        if event_type == "assistant.message":
            final = str(data.get("text") or data.get("message") or "")
            suffix = reconcile_final(state.accumulated_text, final, state.delta_emitted)
            if suffix:
                state.accumulated_text += suffix
                await self._emit({"sessionUpdate": "agent_message_chunk", "content": {"type": "text", "text": suffix}})
            return None
        if event_type == "reasoning.summary":
            summary = str(data.get("summary") or data.get("text") or "")
            if summary:
                await self._emit({"sessionUpdate": "agent_thought_chunk", "content": {"type": "text", "text": summary}})
            return None
        if event_type == "tool.call":
            tool_call_id = str(data.get("tool_call_id") or "")
            await self._emit(
                {
                    "sessionUpdate": "tool_call",
                    "toolCallId": tool_call_id,
                    "title": str(data.get("tool_name") or ""),
                    "status": "in_progress",
                    "rawInput": data.get("arguments") or data.get("summary") or {},
                }
            )
            return None
        if event_type == "tool.result":
            await self._emit(
                {
                    "sessionUpdate": "tool_call_update",
                    "toolCallId": str(data.get("tool_call_id") or ""),
                    "status": map_tool_result_status(str(data.get("outcome") or data.get("status") or "")),
                }
            )
            return None
        if event_type == "approval.requested":
            approval_id = str(data.get("approval_id") or "")
            if not self.request_permission:
                await self.client.cancel_run(state.active_run_id or "")
                return "cancelled"
            option = await self.request_permission(
                {
                    "sessionId": state.session_id,
                    "toolCall": {
                        "toolCallId": str(data.get("tool_call_id") or ""),
                        "title": str(data.get("title") or data.get("tool_name") or ""),
                    },
                    "toolName": str(data.get("tool_name") or ""),
                    "title": str(data.get("title") or data.get("tool_name") or ""),
                    "summary": str(data.get("summary") or data.get("title") or ""),
                    **(
                        {"accountAlias": data["account_alias"]}
                        if data.get("account_alias")
                        else {}
                    ),
                    **(
                        {"ownership": data["ownership"]}
                        if data.get("ownership")
                        else {}
                    ),
                    "options": self.permissions.options(),
                }
            )
            result = await self.permissions.apply(
                session_id=state.session_id,
                run_id=state.active_run_id or "",
                approval_id=approval_id,
                option_id=option,
            )
            if result == "cancelled":
                return "cancelled"
            return None
        if event_type == "clarify.requested":
            question = str(data.get("question") or data.get("text") or "")
            if question:
                await self._emit({"sessionUpdate": "agent_message_chunk", "content": {"type": "text", "text": question}})
            return "end_turn"
        if event_type == "artifact.persisted":
            run_id = state.active_run_id or ""
            await self._emit(
                {
                    "sessionUpdate": "agent_message_chunk",
                    "content": artifact_resource_link(run_id, data),
                }
            )
            if self.artifact_hints:
                await self._emit(
                    {
                        "sessionUpdate": "agent_message_chunk",
                        "content": {"type": "text", "text": safe_artifact_text(data)},
                    }
                )
            return None
        if event_type == "run.completed":
            return "end_turn"
        if event_type == "run.cancelled":
            return "cancelled"
        if event_type in {"run.failed", "run.timed_out"}:
            raise AdapterError(
                "ACP_REMOTE_RUN_FAILED",
                "远程运行失败",
                remote_error_code=str(data.get("error_code") or event_type),
                run_id=state.active_run_id,
            )
        return None
