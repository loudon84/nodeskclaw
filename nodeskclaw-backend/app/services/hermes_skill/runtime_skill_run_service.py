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
from app.core.exceptions import BadRequestError, ConflictError, ForbiddenError, NotFoundError
from app.models.base import not_deleted
from app.models.connector.binding import SkillConnectorBinding
from app.models.connector.definition import ConnectorDefinition
from app.models.connector.instance import ConnectorInstance, ConnectorPlacement
from app.models.hermes_skill.hermes_agent_instance import HermesAgentInstance
from app.models.hermes_skill.hermes_task import TaskStatus
from app.models.hermes_skill.run_dispatch_outbox import RunDispatchOutbox, RunDispatchStatus
from app.models.hermes_skill.skill import HermesSkill
from app.schemas.hermes_skill.runtime_skill_run import (
    RuntimeSkillRunResult,
    StartRuntimeSkillRunRequest,
)
from app.schemas.skill_run.constants import SKILL_RUN_CONTRACT_VERSION_V121
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

_FORBIDDEN_CLIENT_INJECTION_KEYS = frozenset(
    {
        "content",
        "body",
        "bytes",
        "file_path",
        "internal_path",
        "download_url",
        "presigned_url",
        "text",
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
                stored_args = existing.arguments if isinstance(existing.arguments, dict) else {}
                requested_args = request.arguments if isinstance(request.arguments, dict) else {}
                if json.dumps(stored_args, sort_keys=True, default=str) != json.dumps(
                    requested_args, sort_keys=True, default=str
                ):
                    raise ConflictError(
                        "幂等键与请求参数冲突",
                        "errors.run.idempotency_conflict",
                    )
                return await self._build_result_for_existing_task(request, existing)

        run_id = str(uuid.uuid4())

        release_meta = await self._resolve_release_meta(request)
        execution_context = await self._build_authorized_execution_context(request, release_meta)

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
            await self._enqueue_agent_run_outbox(
                request,
                route_snapshot,
                task.id,
                release_meta=release_meta,
                execution_context=execution_context,
            )

        await self.db.flush()

        return await self._finalize_run(request, task, output_policy)

    async def _enqueue_agent_run_outbox(
        self,
        request: StartRuntimeSkillRunRequest,
        route_snapshot: dict[str, Any],
        run_id: str,
        *,
        release_meta: dict[str, Any] | None = None,
        execution_context: dict[str, Any] | None = None,
    ) -> RunDispatchOutbox:
        release_meta = release_meta or await self._resolve_release_meta(request)
        enriched_route = await self._enrich_route_snapshot(request, route_snapshot)
        connector_bindings = list((release_meta.get("placement") or {}).get("connector_bindings") or [])
        if connector_bindings:
            enriched_route["connector_bindings"] = connector_bindings
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
            "run_session_id": request.session_id,
            "execution_context": execution_context or {},
            "context_version": (execution_context or {}).get("context_version"),
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
                "session_id": request.session_id,
                "workspace_id": request.workspace_id,
                "attachment_refs": list(request.attachment_refs or []),
                "connector_binding_refs": list(connector_snapshot.get("connector_binding_refs") or []),
                "knowledge_refs": list(connector_snapshot.get("knowledge_refs") or []),
                "placement": {
                    "role": connector_snapshot.get("placement", "central"),
                    "engine": "connector",
                    "edge_node_id": connector_snapshot.get("edge_node_id"),
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
            "session_id": request.session_id,
            "workspace_id": request.workspace_id,
            "attachment_refs": list(request.attachment_refs or []),
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
            select(
                SkillConnectorBinding.id.label("binding_id"),
                ConnectorInstance.id.label("connector_instance_id"),
                ConnectorDefinition.kind.label("connector_kind"),
                ConnectorInstance.config.label("connector_config"),
                ConnectorInstance.secret_ref_id.label("connector_secret_ref_id"),
                ConnectorInstance.placement.label("placement"),
                ConnectorInstance.edge_node_id.label("edge_node_id"),
            )
            .join(SkillConnectorBinding, SkillConnectorBinding.connector_instance_id == ConnectorInstance.id)
            .join(ConnectorDefinition, ConnectorDefinition.id == ConnectorInstance.definition_id)
            .where(
                not_deleted(SkillConnectorBinding),
                not_deleted(ConnectorInstance),
                not_deleted(ConnectorDefinition),
                SkillConnectorBinding.org_id == org_id,
                SkillConnectorBinding.id.in_(binding_ids),
                ConnectorInstance.org_id == org_id,
                ConnectorInstance.is_active.is_(True),
            )
        )
        bindings = [dict(row) for row in result.mappings().all()]
        for binding in bindings:
            binding["network_policy"] = dict((binding.get("connector_config") or {}).get("network_policy") or {})
        found_binding_ids = {str(binding["binding_id"]) for binding in bindings}
        missing_binding_ids = {str(binding_id) for binding_id in binding_ids} - found_binding_ids
        if missing_binding_ids:
            raise BadRequestError(
                "Connector 绑定不存在、不可用或不属于当前组织",
                "errors.connector.binding_unavailable",
            )
        placements = {binding["placement"] for binding in bindings}
        has_edge = ConnectorPlacement.EDGE.value in placements
        has_central = ConnectorPlacement.CENTRAL.value in placements or not placements
        if has_edge and has_central:
            return {"role": "hybrid", "engine": "hybrid", "connector_bindings": bindings}
        if has_edge:
            return {"role": "edge", "engine": "connector", "connector_bindings": bindings}
        return {"role": "central", "engine": "hermes", "connector_bindings": bindings}

    async def _enrich_route_snapshot(
        self,
        request: StartRuntimeSkillRunRequest,
        route_snapshot: dict[str, Any],
    ) -> dict[str, Any]:
        enriched = dict(route_snapshot)
        if request.catalog_kind == "connector":
            return enriched
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
            contract_version=(
                SKILL_RUN_CONTRACT_VERSION_V121
                if request.task_source != "expert_mcp" and settings.SKILL_AGENT_ENABLED
                else None
            ),
        )

        return RuntimeSkillRunResult(
            task=task,
            sse_token=event_token,
            structured_content=structured_content,
        )

    async def _resolve_member_id(self, org_id: str, user_id: str) -> str:
        from app.models.org_membership import OrgMembership

        result = await self.db.execute(
            select(OrgMembership.id).where(
                not_deleted(OrgMembership),
                OrgMembership.org_id == org_id,
                OrgMembership.user_id == user_id,
            )
        )
        member_id = result.scalar_one_or_none()
        if not member_id:
            raise ForbiddenError(
                "组织成员不存在",
                "errors.auth.membership_not_found",
            )
        return str(member_id)

    def _reject_client_context_injection(self, client_context: dict[str, Any]) -> None:
        for key, value in client_context.items():
            lowered = key.lower()
            if lowered in _FORBIDDEN_CLIENT_INJECTION_KEYS:
                raise BadRequestError(
                    "客户端上下文包含禁止字段",
                    "errors.run.context_injection_denied",
                )
            if lowered in {"knowledge_refs", "attachment_refs"} and isinstance(value, list):
                extra = set(value)
                continue
            if isinstance(value, str) and (
                value.startswith("/") or value.startswith("http://") or value.startswith("https://")
            ):
                raise BadRequestError(
                    "客户端上下文包含禁止路径或 URL",
                    "errors.run.context_injection_denied",
                )

    async def _fetch_knowledge_proofs(
        self,
        org_id: str,
        member_id: str,
        knowledge_set_ids: list[str],
    ) -> dict[str, dict[str, Any]]:
        if not knowledge_set_ids:
            return {}
        if not settings.KNOWLEDGE_SERVICE_BASE_URL or not settings.KNOWLEDGE_SERVICE_TOKEN:
            raise ForbiddenError(
                "Knowledge 服务未配置",
                "errors.knowledge.service_unavailable",
            )
        url = f"{settings.KNOWLEDGE_SERVICE_BASE_URL.rstrip('/')}/api/v2/skill-run/auth-proofs"
        headers = {
            "Authorization": f"Bearer {settings.KNOWLEDGE_SERVICE_TOKEN}",
            "Content-Type": "application/json",
        }
        payload = {
            "org_id": org_id,
            "member_id": member_id,
            "knowledge_set_ids": knowledge_set_ids,
        }
        try:
            async with httpx.AsyncClient(
                timeout=httpx.Timeout(settings.KNOWLEDGE_AUTH_PROOF_TIMEOUT_SECONDS, connect=2.0)
            ) as client:
                response = await client.post(url, headers=headers, json=payload)
        except httpx.HTTPError as exc:
            raise ForbiddenError(
                "Knowledge 授权证明不可达",
                "errors.knowledge.proof_unreachable",
            ) from exc
        if response.status_code != 200:
            raise ForbiddenError(
                "Knowledge 授权证明失败",
                "errors.knowledge.proof_denied",
            )
        data = response.json().get("data") or {}
        proofs = {
            item["set_id"]: item
            for item in (data.get("proofs") or [])
            if isinstance(item, dict) and item.get("set_id")
        }
        return proofs

    async def _assert_workspace_proof(
        self,
        workspace_id: str,
        org_id: str,
        user_id: str,
    ) -> dict[str, Any]:
        from app.models.user import User
        from app.services import workspace_member_service as wm_service

        user = await self.db.get(User, user_id)
        if user is None:
            raise ForbiddenError("用户不存在", "errors.auth.user_not_found")
        await wm_service.check_workspace_access(workspace_id, user, "send_chat", self.db)
        auth_version = hashlib.sha256(f"{workspace_id}:{org_id}:{user_id}".encode()).hexdigest()[:16]
        return {
            "type": "workspace",
            "stable_id": workspace_id,
            "auth_version": auth_version,
            "expires_at": None,
        }

    async def _assert_attachment_proofs(
        self,
        workspace_id: str,
        org_id: str,
        user_id: str,
        attachment_refs: list[str],
    ) -> list[dict[str, Any]]:
        from app.models.user import User
        from app.services import file_reference_service
        from app.services import workspace_member_service as wm_service

        user = await self.db.get(User, user_id)
        if user is None:
            raise ForbiddenError("用户不存在", "errors.auth.user_not_found")
        await wm_service.check_workspace_access(workspace_id, user, "send_chat", self.db)

        parsed_refs: list[dict[str, str]] = []
        for ref in attachment_refs:
            if ":" in ref:
                source, file_id = ref.split(":", 1)
                parsed_refs.append({"source": source, "file_id": file_id})
            else:
                parsed_refs.append({"source": file_reference_service.SOURCE_CHAT_ATTACHMENT, "file_id": ref})

        resolved = await file_reference_service.resolve_message_file_references(
            self.db,
            workspace_id,
            file_references=parsed_refs,
        )
        if len(resolved) != len(parsed_refs):
            raise ForbiddenError(
                "附件引用未授权或不可用",
                "errors.run.attachment_proof_denied",
            )
        descriptors: list[dict[str, Any]] = []
        for item in resolved:
            stable_id = f"{item.get('source')}:{item.get('file_id')}"
            auth_version = hashlib.sha256(
                json.dumps(item, sort_keys=True, default=str).encode()
            ).hexdigest()[:16]
            descriptors.append(
                {
                    "type": "attachment",
                    "stable_id": stable_id,
                    "auth_version": auth_version,
                    "expires_at": None,
                }
            )
        return descriptors

    async def _build_authorized_execution_context(
        self,
        request: StartRuntimeSkillRunRequest,
        release_meta: dict[str, Any],
    ) -> dict[str, Any]:
        client_context = dict(request.client_context or {})
        self._reject_client_context_injection(client_context)

        knowledge_refs = list(release_meta.get("knowledge_refs") or [])
        client_knowledge = client_context.get("knowledge_refs")
        if isinstance(client_knowledge, list) and set(client_knowledge) - set(knowledge_refs):
            raise ForbiddenError(
                "客户端不能扩大 Release 知识引用",
                "errors.run.context_ref_expansion_denied",
            )

        descriptors: list[dict[str, Any]] = []
        if knowledge_refs:
            member_id = await self._resolve_member_id(request.org_id, request.user_id)
            proofs = await self._fetch_knowledge_proofs(request.org_id, member_id, knowledge_refs)
            for ref in knowledge_refs:
                proof = proofs.get(ref)
                if not proof or not proof.get("allowed"):
                    raise ForbiddenError(
                        "Knowledge 引用未授权",
                        "errors.run.knowledge_proof_denied",
                    )
                descriptors.append(
                    {
                        "type": "knowledge",
                        "stable_id": ref,
                        "auth_version": proof.get("auth_version") or "",
                        "expires_at": None,
                    }
                )

        if request.workspace_id:
            descriptors.append(
                await self._assert_workspace_proof(
                    request.workspace_id,
                    request.org_id,
                    request.user_id,
                )
            )

        if request.attachment_refs:
            if not request.workspace_id:
                raise BadRequestError(
                    "附件引用需要 workspace_id",
                    "errors.run.attachment_workspace_required",
                )
            descriptors.extend(
                await self._assert_attachment_proofs(
                    request.workspace_id,
                    request.org_id,
                    request.user_id,
                    list(request.attachment_refs),
                )
            )

        if request.session_id:
            descriptors.append(
                {
                    "type": "session",
                    "stable_id": request.session_id,
                    "auth_version": hashlib.sha256(request.session_id.encode()).hexdigest()[:16],
                    "expires_at": None,
                }
            )

        context_version = int(
            hashlib.sha256(json.dumps(descriptors, sort_keys=True, default=str).encode()).hexdigest()[:8],
            16,
        )
        return {"context_version": context_version, "descriptors": descriptors}

    async def revalidate_execution_context(
        self,
        *,
        org_id: str,
        user_id: str,
        execution_context: dict[str, Any],
        context_version: int,
    ) -> None:
        if int(execution_context.get("context_version") or 0) != int(context_version):
            raise ForbiddenError(
                "上下文版本不一致",
                "errors.run.context_version_mismatch",
            )
        descriptors = list(execution_context.get("descriptors") or [])
        knowledge_refs = [d["stable_id"] for d in descriptors if d.get("type") == "knowledge"]
        if knowledge_refs:
            member_id = await self._resolve_member_id(org_id, user_id)
            proofs = await self._fetch_knowledge_proofs(org_id, member_id, knowledge_refs)
            for ref in knowledge_refs:
                proof = proofs.get(ref)
                if not proof or not proof.get("allowed"):
                    raise ForbiddenError(
                        "Knowledge 引用已撤权",
                        "errors.run.knowledge_proof_denied",
                    )
                for descriptor in descriptors:
                    if descriptor.get("type") == "knowledge" and descriptor.get("stable_id") == ref:
                        if descriptor.get("auth_version") != proof.get("auth_version"):
                            raise ForbiddenError(
                                "Knowledge 授权版本不一致",
                                "errors.run.context_version_mismatch",
                            )

        workspace_ids = [d["stable_id"] for d in descriptors if d.get("type") == "workspace"]
        for workspace_id in workspace_ids:
            await self._assert_workspace_proof(workspace_id, org_id, user_id)

        attachment_refs = [d["stable_id"] for d in descriptors if d.get("type") == "attachment"]
        if attachment_refs:
            workspace_id = workspace_ids[0] if workspace_ids else None
            if not workspace_id:
                raise ForbiddenError(
                    "附件上下文缺少 workspace",
                    "errors.run.attachment_workspace_required",
                )
            await self._assert_attachment_proofs(workspace_id, org_id, user_id, attachment_refs)

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
