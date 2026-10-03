from __future__ import annotations

from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ForbiddenError, NotFoundError
from app.schemas.hermes_skill.runtime_skill_run import StartRuntimeSkillRunRequest
from app.services.expert_gateway.expert_catalog_service import ExpertCatalogService
from app.services.hermes_skill.public_attachment_service import prove_org_user_attachment
from app.services.hermes_skill.runtime_skill_run_service import RuntimeSkillRunService
from app.services.remote_acp.errors import EXPERT_NOT_FOUND, EXPERT_UNAVAILABLE, RUNTIME_UNAVAILABLE


async def build_run_context(
    db: AsyncSession,
    *,
    org_id: str,
    user_id: str,
    agent_ref: str,
    session_id: str,
    attachment_refs: list[str] | None = None,
    knowledge_refs: list[str] | None = None,
) -> dict[str, Any]:
    catalog = ExpertCatalogService(db)
    expert = await catalog.get_by_slug(org_id, agent_ref)
    if expert is None or not expert.published or not expert.enabled:
        raise EXPERT_NOT_FOUND
    try:
        ready = await catalog.runtime_ready(org_id, expert)
    except NotFoundError as exc:
        raise RUNTIME_UNAVAILABLE from exc
    if not ready:
        raise EXPERT_UNAVAILABLE
    profile = await catalog.resolve_agent_profile(org_id, expert)
    runtime = RuntimeSkillRunService(db)
    request = StartRuntimeSkillRunRequest(
        org_id=org_id,
        user_id=user_id,
        tool_name="remote_agent",
        runtime_skill_id="",
        agent_profile=profile,
        hermes_agent_instance_id=expert.hermes_agent_id,
        agent_id=None,
        arguments={},
        client_context={},
        output_policy={},
        task_source="remote_acp",
        skill_id="",
        session_id=session_id,
        attachment_refs=list(attachment_refs or []),
    )
    route_snapshot = await runtime._enrich_route_snapshot(
        request,
        {"expert_slug": agent_ref, "agent_ref": agent_ref},
    )
    try:
        execution = await runtime._build_authorized_execution_context(
            request,
            {"knowledge_refs": list(knowledge_refs or [])},
        )
    except ForbiddenError as exc:
        raise
    for ref in list(attachment_refs or []):
        await prove_org_user_attachment(db, org_id=org_id, user_id=user_id, attachment_ref=ref)
    return {
        "route_snapshot": route_snapshot,
        "execution_context": execution,
        "context_version": int(execution.get("context_version") or 1),
        "knowledge_refs": list(knowledge_refs or []),
    }
