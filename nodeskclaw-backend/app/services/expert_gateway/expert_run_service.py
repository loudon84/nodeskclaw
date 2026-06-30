from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.exceptions import BadRequestError
from app.models.expert import Expert
from app.models.expert_invocation_log import ExpertInvocationLog
from app.models.expert_skill import ExpertSkill
from app.models.expert_team import ExpertTeam
from app.models.expert_team_skill import ExpertTeamSkill
from app.models.hermes_skill.hermes_agent_instance import HermesAgentInstance
from app.services.expert_gateway.errors import (
    EXPERT_EVENT_TOKEN_CREATE_FAILED,
    EXPERT_TASK_CREATE_FAILED,
    mcp_success,
)
from app.services.expert_gateway.expert_catalog_service import ExpertCatalogService
from app.services.expert_gateway.expert_invocation_log_service import ExpertInvocationLogService
from app.services.hermes_skill.task_event_token_service import TaskEventTokenService
from app.services.hermes_skill.task_service import TaskService

_STREAM_EVENTS = [
    "task.started",
    "task.progress",
    "task.artifact.ready",
    "task.completed",
    "task.failed",
    "task.timeline",
]


@dataclass
class StartExpertRunResult:
    task: Any
    log: ExpertInvocationLog
    event_token: str
    event_sse_url: str
    structured_content: dict[str, Any]


def _client_meta(headers: dict[str, str] | None) -> dict[str, str | None]:
    headers = headers or {}
    return {
        "client_source": headers.get("x-client"),
        "client_version": headers.get("x-proxy-version"),
        "client_device_id": headers.get("x-device-id"),
    }


def _desktop_context(arguments: dict[str, Any]) -> dict[str, Any]:
    context = arguments.get("context")
    if not isinstance(context, dict):
        return {}
    return {
        "conversation_id": context.get("conversationId") or context.get("conversation_id"),
        "workspace_id": context.get("workspaceId") or context.get("workspace_id"),
    }


class ExpertRunService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.catalog = ExpertCatalogService(db)
        self.logs = ExpertInvocationLogService(db)
        self.tasks = TaskService(db)

    async def _resolve_execution_agent(
        self,
        org_id: str,
        hermes_agent_id: str | None,
    ) -> HermesAgentInstance:
        if not hermes_agent_id:
            raise BadRequestError(
                "Expert 绑定的 Hermes Agent 尚未关联 AI 员工实例",
                "errors.expert.agent_instance_not_bound",
            )
        agent = await self.catalog._get_agent(org_id, hermes_agent_id)
        if not agent.instance_id:
            raise BadRequestError(
                "Expert 绑定的 Hermes Agent 尚未关联 AI 员工实例",
                "errors.expert.agent_instance_not_bound",
            )
        return agent

    async def start_expert_skill_run(
        self,
        org_id: str,
        user_id: str,
        expert: Expert,
        skill: ExpertSkill,
        arguments: dict[str, Any],
        *,
        catalog_slug: str,
        headers: dict[str, str] | None = None,
        log: ExpertInvocationLog,
        jsonrpc_id: Any,
    ) -> dict:
        agent = await self._resolve_execution_agent(org_id, expert.hermes_agent_id)
        agent_profile = agent.profile_name
        route_snapshot = self._build_expert_route_snapshot(
            expert=expert,
            skill=skill,
            agent_profile=agent_profile,
            catalog_slug=catalog_slug,
        )
        client_context = self._build_client_context(
            headers=headers,
            catalog_kind="expert",
            catalog_slug=catalog_slug,
            expert_id=expert.id,
            skill_id=skill.id,
            arguments=arguments,
        )
        output_policy = {
            "artifact_mode": "pull_only",
            "suggested_workspace_path": f"experts/{expert.expert_slug}",
        }
        run_result = await self._create_task_run(
            org_id=org_id,
            user_id=user_id,
            skill=skill,
            agent_id=agent.instance_id,
            agent_profile=agent_profile,
            arguments=arguments,
            client_context=client_context,
            route_snapshot=route_snapshot,
            output_policy=output_policy,
            log=log,
        )
        return self._build_mcp_accepted_result(
            jsonrpc_id=jsonrpc_id,
            run_result=run_result,
            kind="expert",
            slug=catalog_slug,
            skill_name=skill.skill_name,
        )

    async def start_team_skill_run(
        self,
        org_id: str,
        user_id: str,
        team: ExpertTeam,
        skill: ExpertTeamSkill,
        arguments: dict[str, Any],
        *,
        catalog_slug: str,
        orchestration_mode: str,
        headers: dict[str, str] | None = None,
        log: ExpertInvocationLog,
        jsonrpc_id: Any,
    ) -> dict:
        agent = await self._resolve_execution_agent(org_id, team.hermes_agent_id)
        agent_profile = agent.profile_name
        route_snapshot = self._build_team_route_snapshot(
            team=team,
            skill=skill,
            agent_profile=agent_profile,
            catalog_slug=catalog_slug,
            orchestration_mode=orchestration_mode,
        )
        client_context = self._build_client_context(
            headers=headers,
            catalog_kind="expert_team",
            catalog_slug=catalog_slug,
            expert_team_id=team.id,
            skill_id=skill.id,
            arguments=arguments,
        )
        output_policy = {
            "artifact_mode": "pull_only",
            "suggested_workspace_path": f"experts/{team.team_slug}",
        }
        run_result = await self._create_task_run(
            org_id=org_id,
            user_id=user_id,
            skill=skill,
            agent_id=agent.instance_id,
            agent_profile=agent_profile,
            arguments=arguments,
            client_context=client_context,
            route_snapshot=route_snapshot,
            output_policy=output_policy,
            log=log,
        )
        return self._build_mcp_accepted_result(
            jsonrpc_id=jsonrpc_id,
            run_result=run_result,
            kind="expert_team",
            slug=catalog_slug,
            skill_name=skill.skill_name,
        )

    async def _create_task_run(
        self,
        *,
        org_id: str,
        user_id: str,
        skill: ExpertSkill | ExpertTeamSkill,
        agent_id: str | None,
        agent_profile: str,
        arguments: dict[str, Any],
        client_context: dict[str, Any],
        route_snapshot: dict[str, Any],
        output_policy: dict[str, Any],
        log: ExpertInvocationLog,
    ) -> StartExpertRunResult:
        routing_metadata = {
            "route_snapshot": route_snapshot,
            "output_policy": output_policy,
        }
        try:
            task = await self.tasks.create_task(
                org_id=org_id,
                skill_id=skill.skill_name,
                tool_name=skill.upstream_tool_name,
                agent_id=agent_id,
                profile_id=agent_profile,
                workspace_id=None,
                installation_id=None,
                user_id=user_id,
                arguments=arguments,
                client_context=client_context,
                routing_metadata=routing_metadata,
            )
        except BadRequestError as exc:
            raise BadRequestError(str(exc), getattr(exc, "message_key", EXPERT_TASK_CREATE_FAILED)) from exc
        except Exception as exc:
            raise BadRequestError(str(exc), EXPERT_TASK_CREATE_FAILED) from exc

        timeout = int(route_snapshot.get("timeout_seconds") or settings.EXPERT_UPSTREAM_TIMEOUT_SECONDS)
        task.timeout_seconds = timeout
        task.output_policy = output_policy
        output_policy["suggested_workspace_path"] = (
            f"{output_policy['suggested_workspace_path']}/{task.id}"
        )
        routing_metadata["output_policy"] = output_policy
        task.routing_metadata = routing_metadata
        await self.db.flush()

        await self.logs.attach_task(log, task, stream_mode="event_stream")

        try:
            token_data = await TaskEventTokenService(self.db).create_token(
                task.id,
                user_id,
                org_id,
                ttl_seconds=settings.EXPERT_EVENT_TOKEN_TTL_SECONDS,
            )
        except Exception as exc:
            raise BadRequestError(str(exc), EXPERT_EVENT_TOKEN_CREATE_FAILED) from exc

        event_sse_url = token_data["event_url"]
        event_token = event_sse_url.split("token=", 1)[-1] if "token=" in event_sse_url else ""

        structured_content = {
            "invocationId": log.id,
            "taskId": task.id,
            "taskNo": task.task_no,
            "status": "queued",
            "eventUrl": task.event_url,
            "eventToken": event_token,
            "eventSseUrl": event_sse_url,
            "artifactUrl": task.artifact_url,
            "artifactMode": "pull_only",
            "streaming": True,
            "orchestrationMode": "agent_event_stream",
            "stream": {
                "transport": "sse",
                "events": _STREAM_EVENTS,
            },
        }

        return StartExpertRunResult(
            task=task,
            log=log,
            event_token=event_token,
            event_sse_url=event_sse_url,
            structured_content=structured_content,
        )

    @staticmethod
    def _build_expert_route_snapshot(
        *,
        expert: Expert,
        skill: ExpertSkill,
        agent_profile: str,
        catalog_slug: str,
    ) -> dict[str, Any]:
        return {
            "route_type": "expert_agent_event_stream",
            "catalog_kind": "expert",
            "catalog_slug": catalog_slug,
            "orchestration_mode": "agent_event_stream",
            "hermes_agent_instance_id": expert.hermes_agent_id,
            "agent_profile": agent_profile,
            "runtime_skill_id": skill.skill_name,
            "upstream_tool_name": skill.upstream_tool_name,
            "hermes_instance_name": agent_profile,
            "timeout_seconds": settings.EXPERT_UPSTREAM_TIMEOUT_SECONDS,
            "expert": {
                "kind": "expert",
                "slug": expert.expert_slug,
                "display_name": expert.display_name,
            },
        }

    @staticmethod
    def _build_team_route_snapshot(
        *,
        team: ExpertTeam,
        skill: ExpertTeamSkill,
        agent_profile: str,
        catalog_slug: str,
        orchestration_mode: str,
    ) -> dict[str, Any]:
        return {
            "route_type": "expert_agent_event_stream",
            "catalog_kind": "expert_team",
            "catalog_slug": catalog_slug,
            "orchestration_mode": "agent_event_stream",
            "upstream_orchestration_mode": orchestration_mode,
            "hermes_agent_instance_id": team.hermes_agent_id,
            "agent_profile": agent_profile,
            "runtime_skill_id": skill.skill_name,
            "upstream_tool_name": skill.upstream_tool_name,
            "hermes_instance_name": agent_profile,
            "timeout_seconds": settings.EXPERT_UPSTREAM_TIMEOUT_SECONDS,
            "team": {
                "slug": team.team_slug,
                "display_name": team.display_name,
            },
        }

    @staticmethod
    def _build_client_context(
        *,
        headers: dict[str, str] | None,
        catalog_kind: str,
        catalog_slug: str,
        arguments: dict[str, Any],
        expert_id: str | None = None,
        expert_team_id: str | None = None,
        skill_id: str | None = None,
    ) -> dict[str, Any]:
        meta = _client_meta(headers)
        desktop = _desktop_context(arguments)
        context: dict[str, Any] = {
            "source": "expert_mcp_gateway",
            "client_source": meta["client_source"],
            "client_version": meta["client_version"],
            "client_device_id": meta["client_device_id"],
            "catalog_kind": catalog_kind,
            "catalog_slug": catalog_slug,
        }
        if expert_id:
            context["expert_id"] = expert_id
            context["expert_skill_id"] = skill_id
        if expert_team_id:
            context["expert_team_id"] = expert_team_id
            context["expert_team_skill_id"] = skill_id
        if desktop:
            context["desktop"] = desktop
        return context

    @staticmethod
    def _build_mcp_accepted_result(
        *,
        jsonrpc_id: Any,
        run_result: StartExpertRunResult,
        kind: str,
        slug: str,
        skill_name: str,
    ) -> dict:
        structured = dict(run_result.structured_content)
        structured["kind"] = kind
        structured["slug"] = slug
        structured["skillName"] = skill_name
        return mcp_success(
            jsonrpc_id,
            {
                "content": [
                    {
                        "type": "text",
                        "text": "任务已启动，正在由专家执行。",
                    }
                ],
                "structuredContent": structured,
                "isError": False,
            },
        )
