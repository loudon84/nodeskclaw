from __future__ import annotations

import hashlib
import json
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.exceptions import BadRequestError, NotFoundError
from app.models.base import not_deleted
from app.models.hermes_skill.hermes_task import HermesTask, TaskStatus
from app.models.hermes_skill.run_dispatch_outbox import RunDispatchOutbox, RunDispatchStatus
from app.schemas.hermes_skill.runtime_skill_run import (
    StartRuntimeSkillRunRequest,
    generate_request_trace_id,
)
from app.services.expert_gateway.expert_catalog_service import ExpertCatalogService
from app.services.hermes_skill.hermes_queue_policy_service import HermesQueuePolicyService
from app.services.hermes_skill.runtime_skill_run_service import RuntimeSkillRunService
from app.services.hermes_skill.task_service import TaskService

REMOTE_AGENT_TOOL_NAME = "remote_agent"
_ALLOWED_BODY_KEYS = frozenset({
    "client_request_id",
    "agent_ref",
    "prompt",
    "knowledge_refs",
    "session_ref",
})
_TERMINAL_TASK_STATUSES = frozenset({
    TaskStatus.COMPLETED,
    TaskStatus.FAILED,
    TaskStatus.CANCELLED,
    TaskStatus.TIMEOUT,
})
_TASK_PUBLIC_STATUS = {
    TaskStatus.QUEUED: "QUEUED",
    TaskStatus.ACCEPTED: "QUEUED",
    TaskStatus.RUNNING: "RUNNING",
    TaskStatus.WAITING_APPROVAL: "WAITING_APPROVAL",
    TaskStatus.COMPLETED: "COMPLETED",
    TaskStatus.FAILED: "FAILED",
    TaskStatus.CANCELLED: "CANCELLED",
    TaskStatus.TIMEOUT: "FAILED",
}


class RemoteAgentRouteError(Exception):
    def __init__(
        self,
        symbol: str,
        http_status: int,
        code: int,
        message_key: str,
        message: str,
    ):
        super().__init__(message)
        self.symbol = symbol
        self.http_status = http_status
        self.code = code
        self.message_key = message_key
        self.message = message


@dataclass
class ParsedRemoteAgentCreate:
    client_request_id: str
    agent_ref: str
    prompt: str
    knowledge_refs: list[str]
    session_ref: str | None


def request_digest(
    *,
    agent_ref: str,
    prompt: str,
    knowledge_refs: list[str],
    session_ref: str | None,
) -> str:
    body = {
        "agent_ref": agent_ref,
        "prompt": prompt.strip(),
        "knowledge_refs": sorted(knowledge_refs),
        "session_ref": session_ref or "",
    }
    return hashlib.sha256(
        json.dumps(body, sort_keys=True, ensure_ascii=False).encode()
    ).hexdigest()


def decide_before_insert(
    *,
    existing_task: bool,
    digest_matches: bool,
    other_user: bool,
    slug_mismatch: bool,
    session_busy: bool,
) -> str:
    if existing_task and digest_matches:
        return "replay"
    if existing_task and not digest_matches:
        return "conflict"
    if other_user:
        return "forbidden"
    if slug_mismatch:
        return "mismatch"
    if session_busy:
        return "busy"
    return "create"


def parse_create_body(payload: Any) -> ParsedRemoteAgentCreate:
    if not isinstance(payload, dict):
        raise _context_rejected()
    unknown = set(payload) - _ALLOWED_BODY_KEYS - {"connector_binding_refs"}
    if unknown:
        raise _context_rejected()
    if "connector_binding_refs" in payload:
        refs = payload.get("connector_binding_refs")
        if refs not in (None, [], ""):
            raise RemoteAgentRouteError(
                "REMOTE_AGENT_BINDING_UNSUPPORTED",
                409,
                40901,
                "errors.remote_agent.binding_unsupported",
                "当前版本不支持连接器绑定",
            )
    client_request_id = payload.get("client_request_id")
    if not isinstance(client_request_id, str) or not client_request_id.strip() or len(client_request_id.strip()) > 128:
        raise RemoteAgentRouteError(
            "REMOTE_AGENT_REQUEST_ID_INVALID",
            400,
            40003,
            "errors.remote_agent.request_id_invalid",
            "client_request_id 必须是 1 到 128 个字符",
        )
    prompt = payload.get("prompt")
    if not isinstance(prompt, str) or not prompt.strip():
        raise RemoteAgentRouteError(
            "REMOTE_AGENT_PROMPT_REQUIRED",
            400,
            40001,
            "errors.remote_agent.prompt_required",
            "prompt 不能为空",
        )
    agent_ref = payload.get("agent_ref")
    if not isinstance(agent_ref, str) or not agent_ref.strip():
        raise RemoteAgentRouteError(
            "REMOTE_AGENT_TARGET_NOT_FOUND",
            404,
            40401,
            "errors.remote_agent.target_not_found",
            "专家不存在或未发布",
        )
    raw_refs = payload.get("knowledge_refs") or []
    if not isinstance(raw_refs, list) or any(not isinstance(item, str) or not item.strip() for item in raw_refs):
        raise _context_rejected()
    session_ref = payload.get("session_ref")
    if session_ref is not None:
        if not isinstance(session_ref, str) or not _is_uuid(session_ref):
            raise RemoteAgentRouteError(
                "REMOTE_AGENT_SESSION_REF_INVALID",
                400,
                40002,
                "errors.remote_agent.session_ref_invalid",
                "session_ref 必须是不超过 36 个字符的 UUID",
            )
        session_ref = session_ref.strip()
    return ParsedRemoteAgentCreate(
        client_request_id=client_request_id.strip(),
        agent_ref=agent_ref.strip(),
        prompt=prompt.strip(),
        knowledge_refs=[item.strip() for item in raw_refs],
        session_ref=session_ref,
    )


def public_task_status(task: HermesTask) -> str:
    status = task.status
    if isinstance(status, str):
        try:
            status = TaskStatus(status)
        except ValueError:
            return "FAILED"
    return _TASK_PUBLIC_STATUS.get(status, "FAILED")


def public_run_body(task: HermesTask, *, include_updated_at: bool) -> dict[str, Any]:
    metadata = task.routing_metadata or {}
    body: dict[str, Any] = {
        "run_id": task.id,
        "status": public_task_status(task),
        "agent_ref": task.catalog_slug or metadata.get("agent_ref"),
        "created_at": _rfc3339(task.created_at),
    }
    session_ref = metadata.get("session_ref") or None
    if session_ref:
        body["session_ref"] = session_ref
    if include_updated_at:
        body["updated_at"] = _rfc3339(task.updated_at)
    return body


class RemoteAgentProviderService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create(self, *, org_id: str, user_id: str, payload: Any) -> tuple[HermesTask, bool]:
        parsed = parse_create_body(payload)
        digest = request_digest(
            agent_ref=parsed.agent_ref,
            prompt=parsed.prompt,
            knowledge_refs=parsed.knowledge_refs,
            session_ref=parsed.session_ref,
        )
        catalog = ExpertCatalogService(self.db)
        expert = await catalog.get_by_slug(org_id, parsed.agent_ref)
        if expert is None or not expert.published or not expert.enabled:
            raise RemoteAgentRouteError(
                "REMOTE_AGENT_TARGET_NOT_FOUND",
                404,
                40401,
                "errors.remote_agent.target_not_found",
                "专家不存在或未发布",
            )
        try:
            if not await catalog.runtime_ready(org_id, expert):
                raise RemoteAgentRouteError(
                    "REMOTE_AGENT_RUNTIME_UNAVAILABLE",
                    409,
                    40902,
                    "errors.remote_agent.runtime_unavailable",
                    "专家运行时未就绪",
                )
            agent_profile = await catalog.resolve_agent_profile(org_id, expert)
        except NotFoundError as exc:
            raise RemoteAgentRouteError(
                "REMOTE_AGENT_RUNTIME_UNAVAILABLE",
                409,
                40902,
                "errors.remote_agent.runtime_unavailable",
                "专家运行时未就绪",
            ) from exc

        skill_runs = RuntimeSkillRunService(self.db)
        run_request = StartRuntimeSkillRunRequest(
            org_id=org_id,
            user_id=user_id,
            tool_name=REMOTE_AGENT_TOOL_NAME,
            runtime_skill_id="",
            agent_profile=agent_profile,
            hermes_agent_instance_id=expert.hermes_agent_id,
            agent_id=None,
            arguments={"prompt": parsed.prompt},
            client_context={},
            output_policy={},
            task_source="remote_agent",
            skill_id="",
            catalog_slug=expert.expert_slug,
            idempotency_key=parsed.client_request_id,
            session_id=parsed.session_ref,
        )
        execution_context = await skill_runs._build_authorized_execution_context(
            run_request,
            {"knowledge_refs": parsed.knowledge_refs},
        )
        tasks = TaskService(self.db)
        existing = await tasks.find_idempotent_task(
            org_id,
            user_id,
            REMOTE_AGENT_TOOL_NAME,
            parsed.client_request_id,
        )
        other_user = False
        slug_mismatch = False
        session_busy = False
        if parsed.session_ref:
            other_user, slug_mismatch, session_busy = await self._session_flags(
                org_id,
                user_id,
                parsed.session_ref,
                expert.expert_slug,
            )
        decision = decide_before_insert(
            existing_task=existing is not None,
            digest_matches=bool(
                existing
                and (existing.routing_metadata or {}).get("request_digest") == digest
            ),
            other_user=other_user,
            slug_mismatch=slug_mismatch,
            session_busy=session_busy,
        )
        if decision == "replay":
            return existing, True
        if decision == "conflict":
            raise RemoteAgentRouteError(
                "RUN_IDEMPOTENCY_CONFLICT",
                409,
                40903,
                "errors.run.idempotency_conflict",
                "相同 client_request_id 的请求内容不一致",
            )
        if decision == "forbidden":
            raise RemoteAgentRouteError(
                "REMOTE_AGENT_SESSION_FORBIDDEN",
                403,
                40301,
                "errors.remote_agent.session_forbidden",
                "会话不属于当前调用方",
            )
        if decision == "mismatch":
            raise RemoteAgentRouteError(
                "REMOTE_AGENT_SESSION_AGENT_MISMATCH",
                409,
                40905,
                "errors.remote_agent.session_agent_mismatch",
                "会话已绑定其他专家",
            )
        if decision == "busy":
            raise RemoteAgentRouteError(
                "REMOTE_AGENT_SESSION_BUSY",
                409,
                40904,
                "errors.remote_agent.session_busy",
                "会话已有未结束的运行",
            )

        can_enqueue, message_key = await HermesQueuePolicyService(self.db).can_enqueue(
            org_id,
            user_id,
            None,
            None,
        )
        if not can_enqueue:
            raise BadRequestError("任务无法入队", message_key or "errors.hermes.cannot_enqueue")

        route_snapshot = await skill_runs._enrich_route_snapshot(
            run_request,
            {
                "expert_slug": expert.expert_slug,
                "delegation_topology": "single_agent",
                "hermes_agent_instance_id": expert.hermes_agent_id,
            },
        )
        route_snapshot["expert_slug"] = expert.expert_slug
        route_snapshot.pop("runtime_skill_id", None)
        trace_id = generate_request_trace_id()
        task = HermesTask(
            id=str(uuid.uuid4()),
            org_id=org_id,
            task_no=f"TASK-{org_id[:4]}-{uuid.uuid4().hex[:8]}",
            skill_id=None,
            tool_name=REMOTE_AGENT_TOOL_NAME,
            agent_id=None,
            profile_id=agent_profile,
            user_id=user_id,
            status=TaskStatus.QUEUED,
            arguments={"prompt": parsed.prompt},
            arguments_hash=digest,
            timeout_seconds=settings.HERMES_TASK_DEFAULT_TIMEOUT_SECONDS,
            priority=settings.HERMES_QUEUE_DEFAULT_PRIORITY,
            max_retry=settings.HERMES_TASK_DEFAULT_MAX_RETRY,
            queue_entered_at=datetime.now(timezone.utc),
            idempotency_key=parsed.client_request_id,
            catalog_slug=expert.expert_slug,
            request_trace_id=trace_id,
            routing_metadata={
                "agent_ref": expert.expert_slug,
                "session_ref": parsed.session_ref or "",
                "request_digest": digest,
            },
            request_snapshot={
                "agent_ref": expert.expert_slug,
                "prompt": parsed.prompt,
                "knowledge_refs": parsed.knowledge_refs,
                "session_ref": parsed.session_ref,
                "request_digest": digest,
            },
        )
        self.db.add(task)
        await self.db.flush()
        task.event_url = f"/api/v1/remote-agent/runs/{task.id}/events"
        task.artifact_url = f"/api/v1/remote-agent/runs/{task.id}/artifacts"
        context_version = execution_context.get("context_version")
        body = {
            "run_id": task.id,
            "org_id": org_id,
            "user_id": user_id,
            "tool_name": REMOTE_AGENT_TOOL_NAME,
            "skill_id": None,
            "connector_binding_refs": [],
            "knowledge_refs": parsed.knowledge_refs,
            "placement": {"role": "central", "engine": "hermes"},
            "delegation_topology": "single_agent",
            "arguments": {"prompt": parsed.prompt},
            "route_snapshot": route_snapshot,
            "idempotency_key": parsed.client_request_id,
            "run_session_id": parsed.session_ref,
            "execution_context": execution_context,
            "context_version": context_version,
            "request_trace_id": trace_id,
            "dispatch_id": f"disp_{task.id}",
        }
        self.db.add(
            RunDispatchOutbox(
                run_id=task.id,
                dispatch_id=body["dispatch_id"],
                org_id=org_id,
                user_id=user_id,
                tool_name=REMOTE_AGENT_TOOL_NAME,
                status=RunDispatchStatus.PENDING.value,
                payload=body,
                command_digest=digest,
            )
        )
        await self.db.commit()
        await self.db.refresh(task)
        return task, False

    async def _session_flags(
        self,
        org_id: str,
        user_id: str,
        session_ref: str,
        expert_slug: str,
    ) -> tuple[bool, bool, bool]:
        result = await self.db.execute(
            select(HermesTask).where(
                not_deleted(HermesTask),
                HermesTask.org_id == org_id,
                HermesTask.tool_name == REMOTE_AGENT_TOOL_NAME,
                HermesTask.routing_metadata["session_ref"].astext == session_ref,
            )
        )
        other_user = False
        slug_mismatch = False
        session_busy = False
        for task in result.scalars().all():
            if task.user_id and task.user_id != user_id:
                other_user = True
                continue
            pinned = task.catalog_slug or (task.routing_metadata or {}).get("agent_ref")
            if pinned and pinned != expert_slug:
                slug_mismatch = True
            if task.status not in _TERMINAL_TASK_STATUSES:
                session_busy = True
        return other_user, slug_mismatch, session_busy


def _context_rejected() -> RemoteAgentRouteError:
    return RemoteAgentRouteError(
        "REMOTE_AGENT_CONTEXT_REJECTED",
        400,
        40004,
        "errors.remote_agent.context_rejected",
        "请求包含当前版本不接受的上下文字段",
    )


def _is_uuid(value: str) -> bool:
    text = value.strip()
    if not text or len(text) > 36:
        return False
    try:
        parsed = uuid.UUID(text)
    except ValueError:
        return False
    return str(parsed) == text.lower() or parsed.hex == text.lower()


def _rfc3339(value: datetime | None) -> str | None:
    if value is None:
        return None
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.isoformat().replace("+00:00", "Z")
