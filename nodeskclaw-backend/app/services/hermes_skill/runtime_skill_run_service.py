from __future__ import annotations

import logging
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.exceptions import BadRequestError
from app.schemas.hermes_skill.runtime_skill_run import (
    RuntimeSkillRunResult,
    StartRuntimeSkillRunRequest,
)
from app.services.hermes_skill.task_event_token_service import TaskEventTokenService
from app.services.hermes_skill.task_service import TaskService

logger = logging.getLogger(__name__)

RUNTIME_SKILL_ROUTE_TYPE = "hermes_api_server"
ASYNC_EVENT_MODE = "async_event"


class RuntimeSkillRunService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def start(self, request: StartRuntimeSkillRunRequest) -> RuntimeSkillRunResult:
        route_snapshot = self._build_route_snapshot(request)
        execution_contract = self._build_execution_contract(request.execution_mode)
        routing_metadata: dict[str, Any] = {
            "route_snapshot": route_snapshot,
            "output_policy": dict(request.output_policy),
            "execution_contract": execution_contract,
            "task_source": request.task_source,
        }
        if request.installation_id:
            routing_metadata["installation_id"] = request.installation_id
        if request.routing_metadata_extras:
            routing_metadata.update(request.routing_metadata_extras)

        logger.info(
            "runtime_skill_run.start trace_id=%s tool=%s entrypoint=%s task_source=%s "
            "route_type=%s runtime_invocation=%s catalog_slug=%s",
            request.request_trace_id or "",
            request.tool_name,
            request.entrypoint,
            request.task_source,
            route_snapshot.get("route_type"),
            execution_contract.get("runtime_invocation"),
            request.catalog_slug or "",
        )

        try:
            task = await TaskService(self.db).create_task(
                org_id=request.org_id,
                skill_id=request.skill_id,
                tool_name=request.tool_name,
                agent_id=request.agent_id,
                profile_id=request.agent_profile,
                workspace_id=request.workspace_id,
                installation_id=request.installation_id,
                user_id=request.user_id or None,
                arguments=request.arguments,
                client_context=request.client_context,
                routing_metadata=routing_metadata,
            )
        except BadRequestError:
            raise
        except Exception as exc:
            raise BadRequestError(str(exc), "errors.hermes.cannot_enqueue") from exc

        timeout = int(route_snapshot.get("timeout_seconds") or settings.HERMES_TASK_DEFAULT_TIMEOUT_SECONDS)
        task.timeout_seconds = timeout
        task.output_policy = dict(request.output_policy)
        output_policy = dict(request.output_policy)
        suggested = output_policy.get("suggested_workspace_path")
        if suggested:
            output_policy["suggested_workspace_path"] = f"{suggested}/{task.id}"
            task.output_policy = output_policy
            routing_metadata["output_policy"] = output_policy
            task.routing_metadata = routing_metadata

        task.request_trace_id = request.request_trace_id
        task.request_snapshot = request.request_snapshot
        task.route_diagnostics = request.route_diagnostics
        await self.db.flush()

        logger.info(
            "runtime_skill_run.task_created trace_id=%s task_id=%s task_no=%s tool=%s "
            "entrypoint=%s task_source=%s route_type=%s",
            request.request_trace_id or "",
            task.id,
            task.task_no,
            request.tool_name,
            request.entrypoint,
            request.task_source,
            route_snapshot.get("route_type"),
        )

        ttl = request.sse_token_ttl_seconds
        if ttl is None:
            ttl = (
                settings.EXPERT_EVENT_TOKEN_TTL_SECONDS
                if request.task_source == "expert_mcp"
                else settings.MCP_TASK_SSE_TOKEN_TTL_SECONDS
            )

        try:
            token_data = await TaskEventTokenService(self.db).create_token(
                task.id,
                request.user_id,
                request.org_id,
                ttl_seconds=ttl,
            )
        except Exception as exc:
            raise BadRequestError(str(exc), "errors.expert.event_token_create_failed") from exc

        event_sse_url = token_data["event_url"]
        event_token = event_sse_url.split("token=", 1)[-1] if "token=" in event_sse_url else ""

        logger.info(
            "runtime_skill_run.token_created trace_id=%s task_id=%s task_no=%s tool=%s entrypoint=%s",
            request.request_trace_id or "",
            task.id,
            task.task_no,
            request.tool_name,
            request.entrypoint,
        )

        structured_content = self.build_structured_content(
            task=task,
            request=request,
            event_sse_url=event_sse_url,
            output_policy=output_policy,
        )

        return RuntimeSkillRunResult(
            task=task,
            sse_token=event_token,
            structured_content=structured_content,
        )

    @staticmethod
    def _build_route_snapshot(request: StartRuntimeSkillRunRequest) -> dict[str, Any]:
        snapshot: dict[str, Any] = {
            "route_type": RUNTIME_SKILL_ROUTE_TYPE,
            "force_instance": True,
            "hermes_agent_instance_id": request.hermes_agent_instance_id,
            "agent_profile": request.agent_profile,
            "runtime_skill_id": request.runtime_skill_id,
            "hermes_instance_name": request.agent_profile,
            "timeout_seconds": request.timeout_seconds or settings.HERMES_TASK_DEFAULT_TIMEOUT_SECONDS,
        }
        if request.upstream_tool_name:
            snapshot["upstream_tool_name"] = request.upstream_tool_name
        if request.catalog_kind:
            snapshot["catalog_kind"] = request.catalog_kind
        if request.catalog_slug:
            snapshot["catalog_slug"] = request.catalog_slug
        snapshot.update(request.extra_route_snapshot)
        return snapshot

    @staticmethod
    def _build_execution_contract(execution_mode: str) -> dict[str, Any]:
        return {
            "mode": execution_mode,
            "timeline_provider": "nodeskclaw_task_events",
            "runtime_invocation": "chat_completions",
            "desktop_route_override_allowed": False,
        }

    @staticmethod
    def build_structured_content(
        *,
        task: Any,
        request: StartRuntimeSkillRunRequest,
        event_sse_url: str,
        output_policy: dict[str, Any],
    ) -> dict[str, Any]:
        status = task.status.value if hasattr(task.status, "value") else str(task.status)
        if status in ("queued", "accepted"):
            status = "running"

        artifact_mode = output_policy.get("artifact_mode", "pull_only")
        content: dict[str, Any] = {
            "task_id": task.id,
            "task_no": task.task_no,
            "status": status,
            "execution_mode": request.execution_mode,
            "tool_name": request.tool_name,
            "event_stream": event_sse_url,
            "event_url": task.event_url,
            "event_token_url": f"/api/v1/hermes/tasks/{task.id}/events-token",
            "artifact_url": task.artifact_url,
            "result_url": f"/api/v1/hermes/tasks/{task.id}/result",
            "artifact_mode": artifact_mode,
            "server_artifacts": task.server_artifacts or [],
            "wait_strategy": {
                "type": "sse",
                "fallback": "poll",
                "poll_url": f"/api/v1/hermes/tasks/{task.id}",
                "poll_tool": "nodeskclaw_task_wait",
                "result_url": f"/api/v1/hermes/tasks/{task.id}/result",
            },
            "message": "任务已启动，请等待事件流通知完成",
            "committed": True,
            "entrypoint": request.entrypoint,
            "task_source": request.task_source,
            "agent_profile": request.agent_profile,
            "runtime_skill_id": request.runtime_skill_id,
        }
        if request.catalog_kind:
            content["catalog_kind"] = request.catalog_kind
        if request.catalog_slug:
            content["catalog_slug"] = request.catalog_slug
        if request.skill_name:
            content["skill_name"] = request.skill_name
        if request.invocation_id:
            content["invocation_id"] = request.invocation_id
        return content
