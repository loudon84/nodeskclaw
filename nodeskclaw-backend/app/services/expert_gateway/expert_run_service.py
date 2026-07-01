from __future__ import annotations

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
from app.schemas.hermes_skill.runtime_skill_run import StartRuntimeSkillRunRequest
from app.services.expert_gateway.errors import (
    EXPERT_EVENT_TOKEN_CREATE_FAILED,
    EXPERT_TASK_CREATE_FAILED,
    mcp_success,
)
from app.services.expert_gateway.expert_catalog_service import ExpertCatalogService
from app.services.expert_gateway.expert_invocation_log_service import ExpertInvocationLogService
from app.services.hermes_skill.runtime_skill_run_service import RuntimeSkillRunService


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
        run_result = await self._start_runtime_skill_run(
            org_id=org_id,
            user_id=user_id,
            skill=skill,
            agent=agent,
            agent_profile=agent_profile,
            arguments=arguments,
            client_context=client_context,
            output_policy=output_policy,
            log=log,
            catalog_kind="expert",
            catalog_slug=catalog_slug,
            hermes_agent_instance_id=expert.hermes_agent_id,
            extra_route_snapshot={
                "expert": {
                    "kind": "expert",
                    "slug": expert.expert_slug,
                    "display_name": expert.display_name,
                },
            },
        )
        return self._build_mcp_accepted_result(
            jsonrpc_id=jsonrpc_id,
            structured_content=run_result.structured_content,
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
        run_result = await self._start_runtime_skill_run(
            org_id=org_id,
            user_id=user_id,
            skill=skill,
            agent=agent,
            agent_profile=agent_profile,
            arguments=arguments,
            client_context=client_context,
            output_policy=output_policy,
            log=log,
            catalog_kind="expert_team",
            catalog_slug=catalog_slug,
            hermes_agent_instance_id=team.hermes_agent_id,
            extra_route_snapshot={
                "upstream_orchestration_mode": orchestration_mode,
                "team": {
                    "slug": team.team_slug,
                    "display_name": team.display_name,
                },
            },
        )
        return self._build_mcp_accepted_result(
            jsonrpc_id=jsonrpc_id,
            structured_content=run_result.structured_content,
        )

    async def _start_runtime_skill_run(
        self,
        *,
        org_id: str,
        user_id: str,
        skill: ExpertSkill | ExpertTeamSkill,
        agent: HermesAgentInstance,
        agent_profile: str,
        arguments: dict[str, Any],
        client_context: dict[str, Any],
        output_policy: dict[str, Any],
        log: ExpertInvocationLog,
        catalog_kind: str,
        catalog_slug: str,
        extra_route_snapshot: dict[str, Any],
        hermes_agent_instance_id: str | None = None,
    ):
        binding_id = hermes_agent_instance_id or agent.id
        run_request = StartRuntimeSkillRunRequest(
            org_id=org_id,
            user_id=user_id,
            tool_name=skill.upstream_tool_name,
            runtime_skill_id=skill.skill_name,
            agent_profile=agent_profile,
            hermes_agent_instance_id=binding_id,
            agent_id=agent.instance_id,
            arguments=arguments,
            client_context=client_context,
            output_policy=output_policy,
            task_source="expert_mcp",
            skill_id=skill.skill_name,
            installation_id=None,
            timeout_seconds=settings.EXPERT_UPSTREAM_TIMEOUT_SECONDS,
            execution_mode="async_event",
            entrypoint="expert_mcp_gateway",
            catalog_kind=catalog_kind,
            catalog_slug=catalog_slug,
            skill_name=skill.skill_name,
            invocation_id=log.id,
            upstream_tool_name=skill.upstream_tool_name,
            extra_route_snapshot=extra_route_snapshot,
            sse_token_ttl_seconds=settings.EXPERT_EVENT_TOKEN_TTL_SECONDS,
        )
        try:
            run_result = await RuntimeSkillRunService(self.db).start(run_request)
        except BadRequestError as exc:
            message_key = getattr(exc, "message_key", EXPERT_TASK_CREATE_FAILED)
            if message_key == "errors.expert.event_token_create_failed":
                raise BadRequestError(str(exc), EXPERT_EVENT_TOKEN_CREATE_FAILED) from exc
            raise BadRequestError(str(exc), EXPERT_TASK_CREATE_FAILED) from exc
        except Exception as exc:
            raise BadRequestError(str(exc), EXPERT_TASK_CREATE_FAILED) from exc

        await self.logs.attach_task(log, run_result.task, stream_mode="event_stream")
        return run_result

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
        structured_content: dict[str, Any],
    ) -> dict:
        return mcp_success(
            jsonrpc_id,
            {
                "content": [
                    {
                        "type": "text",
                        "text": "任务已启动，正在由专家执行。",
                    }
                ],
                "structuredContent": structured_content,
                "isError": False,
            },
        )
