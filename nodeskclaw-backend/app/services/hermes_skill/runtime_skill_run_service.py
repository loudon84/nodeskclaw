from __future__ import annotations

import hashlib
import json
import logging
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.exceptions import BadRequestError
from app.models.base import not_deleted
from app.models.connector.binding import SkillConnectorBinding
from app.models.connector.instance import ConnectorInstance, ConnectorPlacement
from app.models.hermes_skill.hermes_agent_instance import HermesAgentInstance
from app.models.hermes_skill.hermes_task import TaskStatus
from app.models.hermes_skill.run_dispatch_outbox import RunDispatchOutbox, RunDispatchStatus
from app.models.hermes_skill.skill import HermesSkill
from app.schemas.hermes_skill.runtime_skill_run import (
    RuntimeSkillRunResult,
    StartRuntimeSkillRunRequest,
)
from app.services.hermes_external.hermes_docker_binding_service import HermesDockerBindingService
from app.services.hermes_external.hermes_env_parser import parse_env_file
from app.services.hermes_skill.skill_release_service import (
    SkillReleaseService,
    compute_skill_content_digest,
    snapshot_hash,
)
from app.services.hermes_skill.task_event_token_service import TaskEventTokenService
from app.services.hermes_skill.task_service import TaskService

logger = logging.getLogger(__name__)

RUNTIME_SKILL_ROUTE_TYPE = "hermes_api_server"
ASYNC_EVENT_MODE = "async_event"

_SECRET_ROUTE_KEYS = frozenset(
    {
        "gateway_url",
        "gateway_token",
        "api_token",
        "api_server_key",
        "hermes_base_url",
        "env_file",
    }
)


def strip_internal_route_secrets(payload: Any) -> Any:
    if isinstance(payload, dict):
        cleaned: dict[str, Any] = {}
        for key, value in payload.items():
            if key in _SECRET_ROUTE_KEYS:
                continue
            if key in ("runtime_policy", "route_snapshot", "snapshot"):
                cleaned[key] = strip_internal_route_secrets(value)
            else:
                cleaned[key] = strip_internal_route_secrets(value)
        return cleaned
    if isinstance(payload, list):
        return [strip_internal_route_secrets(item) for item in payload]
    return payload


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
            "execution_owner": "agent" if settings.SKILL_AGENT_ENABLED else "backend",
        }
        if request.installation_id:
            routing_metadata["installation_id"] = request.installation_id
        if request.routing_metadata_extras:
            routing_metadata.update(request.routing_metadata_extras)

        logger.info(
            "runtime_skill_run.start trace_id=%s tool=%s entrypoint=%s task_source=%s "
            "route_type=%s runtime_invocation=%s catalog_slug=%s execution_owner=%s",
            request.request_trace_id or "",
            request.tool_name,
            request.entrypoint,
            request.task_source,
            route_snapshot.get("route_type"),
            execution_contract.get("runtime_invocation"),
            request.catalog_slug or "",
            routing_metadata.get("execution_owner"),
        )

        task_service = TaskService(self.db)
        if request.idempotency_key:
            existing = await task_service.find_idempotent_task(
                request.org_id,
                request.user_id,
                request.tool_name,
                request.idempotency_key,
            )
            if existing is not None:
                return await self._build_result_for_existing_task(request, existing)

        run_id = str(uuid.uuid4())

        try:
            task = await task_service.create_task(
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
                output_policy=dict(request.output_policy),
                idempotency_key=request.idempotency_key,
                catalog_slug=request.catalog_slug,
                request_snapshot=request.request_snapshot,
                request_trace_id=request.request_trace_id,
                route_diagnostics=request.route_diagnostics,
                task_id=run_id,
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
        if suggested and not suggested.endswith(f"/{task.id}"):
            output_policy["suggested_workspace_path"] = f"{suggested}/{task.id}"
            task.output_policy = output_policy
            routing_metadata["output_policy"] = output_policy
            task.routing_metadata = routing_metadata

        task.request_trace_id = request.request_trace_id
        if request.request_snapshot is not None:
            task.request_snapshot = request.request_snapshot
        if request.route_diagnostics is not None:
            task.route_diagnostics = request.route_diagnostics
        if settings.SKILL_AGENT_ENABLED and bool((request.client_context or {}).get("requires_approval")):
            task.status = TaskStatus.WAITING_APPROVAL

        if settings.SKILL_AGENT_ENABLED:
            await self._enqueue_agent_run_outbox(request, route_snapshot, task.id)

        await self.db.flush()

        return await self._finalize_run(request, task, output_policy)

    async def _enqueue_agent_run_outbox(
        self,
        request: StartRuntimeSkillRunRequest,
        route_snapshot: dict[str, Any],
        run_id: str,
    ) -> RunDispatchOutbox:
        release_meta = await self._resolve_release_meta(request)
        enriched_route = await self._enrich_route_snapshot(request, route_snapshot)
        requires_approval = bool((request.client_context or {}).get("requires_approval"))
        body = {
            "run_id": run_id,
            "tool_name": request.tool_name,
            "skill_id": request.skill_id,
            "skill_version": release_meta.get("skill_version"),
            "skill_release_id": release_meta.get("skill_release_id"),
            "skill_release_digest": release_meta.get("skill_release_digest"),
            "snapshot_hash": release_meta.get("snapshot_hash"),
            "connector_binding_refs": list(release_meta.get("connector_binding_refs") or []),
            "knowledge_refs": list(release_meta.get("knowledge_refs") or []),
            "placement": dict(release_meta.get("placement") or {"role": "central"}),
            "arguments": request.arguments or {},
            "requires_approval": requires_approval,
            "route_snapshot": enriched_route,
            "output_policy": dict(request.output_policy),
            "client_context": dict(request.client_context or {}),
            "request_trace_id": request.request_trace_id,
            "idempotency_key": request.idempotency_key,
        }
        cmd_body = {
            "tool_name": request.tool_name,
            "skill_id": request.skill_id,
            "skill_version": release_meta.get("skill_version"),
            "skill_release_id": release_meta.get("skill_release_id"),
            "snapshot_hash": release_meta.get("snapshot_hash"),
            "arguments": request.arguments or {},
            "placement": release_meta.get("placement") or {},
        }
        command_digest = hashlib.sha256(json.dumps(cmd_body, sort_keys=True, default=str).encode()).hexdigest()
        dispatch_id = f"disp_{run_id}"
        body["dispatch_id"] = dispatch_id

        outbox = RunDispatchOutbox(
            run_id=run_id,
            dispatch_id=dispatch_id,
            org_id=request.org_id,
            user_id=request.user_id or "",
            tool_name=request.tool_name,
            status=RunDispatchStatus.PENDING.value,
            payload=body,
            command_digest=command_digest,
            retry_count=0,
            max_retries=5,
        )
        self.db.add(outbox)
        return outbox

    async def _resolve_release_meta(self, request: StartRuntimeSkillRunRequest) -> dict[str, Any]:
        if request.catalog_kind == "connector":
            connector_snapshot = dict(request.extra_route_snapshot or {})
            route_for_hash = {
                "route_type": connector_snapshot.get("route_type", "connector"),
                "connector_kind": connector_snapshot.get("connector_kind"),
                "connector_tool_name": connector_snapshot.get("connector_tool_name") or request.tool_name,
                "placement": connector_snapshot.get("placement", "central"),
            }
            digest_source = {
                "tool_name": request.tool_name,
                "route": connector_snapshot,
                "output_policy": request.output_policy,
            }
            digest = hashlib.sha256(
                json.dumps(digest_source, sort_keys=True, ensure_ascii=False, default=str).encode("utf-8")
            ).hexdigest()
            return {
                "skill_release_id": None,
                "skill_version": "connector-v1",
                "skill_release_digest": digest,
                "session_id": request.session_id if hasattr(request, "session_id") else None,
                "workspace_id": getattr(request, "workspace_id", None),
                "attachment_refs": list(getattr(request, "attachment_refs", []) or []),
                "connector_binding_refs": list(connector_snapshot.get("connector_binding_refs") or []),
                "knowledge_refs": list(connector_snapshot.get("knowledge_refs") or []),
                "placement": {
                    "role": connector_snapshot.get("placement", "central"),
                    "engine": "connector",
                },
                "snapshot_hash": snapshot_hash(
                    skill_release_id=request.tool_name,
                    digest=digest,
                    route_snapshot=route_for_hash,
                ),
            }
        service = SkillReleaseService(self.db)
        published = await service.get_published(request.org_id, request.skill_id)
        if published:
            digest = published.digest
            version = published.version
            release_id = published.id
            requirements = dict(published.requirements or {})
        else:
            skill = await self.db.execute(
                select(HermesSkill).where(
                    not_deleted(HermesSkill),
                    HermesSkill.org_id == request.org_id,
                    HermesSkill.skill_id == request.skill_id,
                )
            )
            skill_row = skill.scalar_one_or_none()
            if not skill_row:
                raise BadRequestError("Skill 不存在", "errors.skill.not_found")
            digest = compute_skill_content_digest(skill_row)
            version = skill_row.version
            release_id = None
            requirements = {}
            if request.task_source != "expert_mcp":
                raise BadRequestError(
                    "Skill 尚未发布 Release，员工无法调用",
                    "errors.skill.release_required",
                )
        route_for_hash = {
            "route_type": RUNTIME_SKILL_ROUTE_TYPE,
            "runtime_skill_id": request.runtime_skill_id,
            "agent_profile": request.agent_profile,
        }
        return {
            "skill_release_id": release_id,
            "skill_version": version,
            "skill_release_digest": digest,
            "session_id": getattr(request, "session_id", None),
            "workspace_id": getattr(request, "workspace_id", None),
            "attachment_refs": list(getattr(request, "attachment_refs", []) or []),
            "connector_binding_refs": list(requirements.get("connector_binding_ids") or []),
            "knowledge_refs": list(requirements.get("knowledge_refs") or []),
            "placement": await self._resolve_placement(org_id=request.org_id, requirements=requirements),
            "snapshot_hash": snapshot_hash(
                skill_release_id=release_id or request.skill_id,
                digest=digest,
                route_snapshot=route_for_hash,
            ),
        }

    async def _resolve_placement(self, *, org_id: str, requirements: dict[str, Any]) -> dict[str, Any]:
        binding_ids = list(requirements.get("connector_binding_ids") or [])
        if not binding_ids:
            return {"role": "central", "engine": "hermes"}

        result = await self.db.execute(
            select(ConnectorInstance.placement)
            .join(SkillConnectorBinding, SkillConnectorBinding.connector_instance_id == ConnectorInstance.id)
            .where(
                not_deleted(SkillConnectorBinding),
                not_deleted(ConnectorInstance),
                SkillConnectorBinding.org_id == org_id,
                SkillConnectorBinding.id.in_(binding_ids),
            )
        )
        placements = {row[0] for row in result.all()}
        has_edge = ConnectorPlacement.EDGE.value in placements
        has_central = ConnectorPlacement.CENTRAL.value in placements or not placements
        if has_edge and has_central:
            return {"role": "hybrid", "engine": "hybrid"}
        if has_edge:
            return {"role": "edge", "engine": "connector"}
        return {"role": "central", "engine": "hermes"}

    async def _enrich_route_snapshot(
        self,
        request: StartRuntimeSkillRunRequest,
        route_snapshot: dict[str, Any],
    ) -> dict[str, Any]:
        enriched = dict(route_snapshot)
        instance_id = request.hermes_agent_instance_id or enriched.get("hermes_agent_instance_id")
        record: HermesAgentInstance | None = None
        if instance_id:
            result = await self.db.execute(
                select(HermesAgentInstance).where(
                    not_deleted(HermesAgentInstance),
                    HermesAgentInstance.id == str(instance_id),
                    HermesAgentInstance.org_id == request.org_id,
                )
            )
            record = result.scalar_one_or_none()
        if not record and request.agent_profile:
            record = await HermesDockerBindingService(self.db).get_by_profile(
                request.org_id, request.agent_profile
            )
        if record:
            if record.gateway_url:
                enriched["gateway_url"] = str(record.gateway_url).rstrip("/")
            if record.env_file:
                try:
                    env = parse_env_file(Path(record.env_file), require_gateway_port=False)
                    model_name = (env.api_server_model_name or request.agent_profile or "").strip()
                    if model_name:
                        enriched["model"] = model_name
                except Exception:
                    logger.debug("Failed to parse env_file for route snapshot", exc_info=True)
            if record.id:
                enriched["credential_lease_ref"] = {
                    "instance_id": record.id,
                    "agent_profile": request.agent_profile,
                    "scope": "hermes:invoke",
                }
            if request.runtime_skill_id:
                enriched["runtime_skill_id"] = request.runtime_skill_id
            if request.agent_profile:
                enriched["agent_profile"] = request.agent_profile
        return enriched

    async def _build_result_for_existing_task(
        self,
        request: StartRuntimeSkillRunRequest,
        task: Any,
    ) -> RuntimeSkillRunResult:
        output_policy = dict(task.output_policy or request.output_policy or {})
        return await self._finalize_run(request, task, output_policy)

    async def _finalize_run(
        self,
        request: StartRuntimeSkillRunRequest,
        task: Any,
        output_policy: dict[str, Any],
    ) -> RuntimeSkillRunResult:
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
        contract_version: str | None = None,
    ) -> dict[str, Any]:
        status = task.status.value if hasattr(task.status, "value") else str(task.status)
        if status in ("queued", "accepted"):
            status = "running"
        if status == "waiting_approval":
            status = "WAITING_APPROVAL"

        artifact_mode = output_policy.get("artifact_mode", "pull_only")
        employee_contract = request.task_source != "expert_mcp" and settings.SKILL_AGENT_ENABLED

        if employee_contract:
            run_event_stream = f"/api/v1/runs/{task.id}/events"
            if "token=" in event_sse_url:
                run_event_stream = f"{run_event_stream}?{event_sse_url.split('?', 1)[-1]}"
            content: dict[str, Any] = {
                "run_id": task.id,
                "status": status.upper() if status in ("running", "queued") else status,
                "execution_mode": request.execution_mode,
                "tool_name": request.tool_name,
                "event_stream": run_event_stream,
                "result_url": f"/api/v1/runs/{task.id}/result",
                "artifact_url": f"/api/v1/runs/{task.id}/artifacts",
                "artifact_mode": artifact_mode,
                "server_artifacts": task.server_artifacts or [],
                "message": (
                    "Run waiting approval"
                    if status == "WAITING_APPROVAL"
                    else "Run accepted"
                ),
                "committed": True,
                "entrypoint": request.entrypoint,
                "task_source": request.task_source,
            }
            if contract_version:
                content["contract_version"] = contract_version
            if request.catalog_kind:
                content["catalog_kind"] = request.catalog_kind
            if request.catalog_slug:
                content["catalog_slug"] = request.catalog_slug
            if request.skill_name:
                content["skill_name"] = request.skill_name
            if request.invocation_id:
                content["invocation_id"] = request.invocation_id
            if request.request_trace_id:
                content["request_trace_id"] = request.request_trace_id
            return content

        content = {
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
        if contract_version:
            content["contract_version"] = contract_version
        if request.catalog_kind:
            content["catalog_kind"] = request.catalog_kind
        if request.catalog_slug:
            content["catalog_slug"] = request.catalog_slug
        if request.skill_name:
            content["skill_name"] = request.skill_name
        if request.invocation_id:
            content["invocation_id"] = request.invocation_id
        if request.request_trace_id:
            content["request_trace_id"] = request.request_trace_id
        return content
