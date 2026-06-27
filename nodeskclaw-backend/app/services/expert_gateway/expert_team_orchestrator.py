from __future__ import annotations

from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.expert_team import ExpertTeam
from app.services.expert_gateway.errors import (
    EXPERT_SKILL_NOT_FOUND,
    EXPERT_UPSTREAM_MCP_ERROR,
    mcp_error_v2,
    mcp_success,
)
from app.services.expert_gateway.expert_catalog_service import ExpertCatalogService
from app.services.expert_gateway.expert_invocation_log_service import ExpertInvocationLogService
from app.services.expert_gateway.expert_mcp_proxy_service import ExpertMcpProxyService
from app.services.expert_gateway.expert_skill_service import ExpertSkillService
from app.services.expert_gateway.expert_team_service import ExpertTeamService


class ExpertTeamOrchestrator:
    DEFAULT_TEAM_SKILL = "team-run"

    def __init__(self, db: AsyncSession):
        self.db = db
        self.teams = ExpertTeamService(db)
        self.catalog = ExpertCatalogService(db)
        self.skills = ExpertSkillService(db)
        self.logs = ExpertInvocationLogService(db)

    async def list_team_tools(self, org_id: str, team: ExpertTeam) -> list[dict[str, Any]]:
        return [
            {
                "name": self.DEFAULT_TEAM_SKILL,
                "description": team.description or team.display_name,
                "inputSchema": {
                    "type": "object",
                    "required": ["prompt"],
                    "properties": {
                        "prompt": {"type": "string", "title": "任务要求"},
                        "context": {"type": "object"},
                    },
                },
                "annotations": {
                    "kind": "expert_team_skill",
                    "slug": team.team_slug,
                    "displayName": team.display_name,
                    "callEnabled": True,
                    "orchestrationMode": "gateway_sequential",
                },
            }
        ]

    async def call_team_skill(
        self,
        org_id: str,
        user_id: str,
        team: ExpertTeam,
        skill_name: str,
        arguments: dict[str, Any],
        *,
        jsonrpc_id: Any,
        client_meta: dict[str, str | None] | None = None,
    ) -> dict:
        if skill_name != self.DEFAULT_TEAM_SKILL:
            return mcp_error_v2(jsonrpc_id, EXPERT_SKILL_NOT_FOUND, f"Skill {skill_name} not found")

        parent_log = await self.logs.create_started(
            org_id=org_id,
            user_id=user_id,
            expert_team_id=team.id,
            expert_slug=team.team_slug,
            skill_name=skill_name,
            jsonrpc_id=str(jsonrpc_id),
            request_payload=arguments,
            invocation_type="expert_team",
            catalog_kind="expert_team",
            catalog_slug=team.team_slug,
            orchestration_mode="gateway_sequential",
            **(client_meta or {}),
        )

        members = await self.teams.list_members(org_id, team.id)
        sections: list[str] = []
        prompt = str(arguments.get("prompt") or "").strip()

        for member in members:
            expert = await self.catalog.get_by_id(org_id, member.expert_id)
            if expert is None:
                continue
            public_skills = await self.skills.list_public_skills(org_id, expert.id)
            callable = [s for s in public_skills if s.call_enabled]
            if not callable:
                if member.required:
                    await self.logs.mark_failed(
                        parent_log,
                        error_code=EXPERT_UPSTREAM_MCP_ERROR,
                        error_message=f"Required member {expert.expert_slug} has no callable skill",
                    )
                    return mcp_error_v2(
                        jsonrpc_id,
                        EXPERT_UPSTREAM_MCP_ERROR,
                        f"Required member {expert.expert_slug} has no callable skill",
                    )
                continue

            skill = callable[0]
            agent_profile = await self.catalog.resolve_agent_profile(org_id, expert)
            member_args = {
                "prompt": prompt,
                "context": {
                    **(arguments.get("context") if isinstance(arguments.get("context"), dict) else {}),
                    "teamSlug": team.team_slug,
                    "memberRole": member.role,
                },
            }
            child_log = await self.logs.create_started(
                org_id=org_id,
                user_id=user_id,
                expert_id=expert.id,
                expert_skill_id=skill.id,
                expert_slug=expert.expert_slug,
                skill_name=skill.skill_name,
                upstream_tool_name=skill.upstream_tool_name,
                agent_alias=agent_profile,
                jsonrpc_id=f"{jsonrpc_id}-{expert.expert_slug}",
                request_payload=member_args,
                parent_invocation_id=parent_log.id,
                invocation_type="expert_skill",
                catalog_kind="expert",
                catalog_slug=expert.expert_slug,
                orchestration_mode="gateway_sequential",
                **(client_meta or {}),
            )
            response = await ExpertMcpProxyService.call_upstream_tool(
                self.db,
                org_id,
                user_id,
                agent_profile,
                skill.upstream_tool_name,
                member_args,
                jsonrpc_id=f"{jsonrpc_id}-{expert.expert_slug}",
            )
            result, error = ExpertMcpProxyService.parse_upstream_result(response)
            if error:
                await self.logs.mark_failed(
                    child_log,
                    error_code=str(error.get("error", {}).get("data", {}).get("errorCode") or EXPERT_UPSTREAM_MCP_ERROR),
                    error_message=str(error.get("error", {}).get("message") or ""),
                    error_detail=error.get("error", {}).get("data") if isinstance(error.get("error"), dict) else None,
                )
                if member.required:
                    await self.logs.mark_failed(
                        parent_log,
                        error_code=str(error.get("error", {}).get("data", {}).get("errorCode") or EXPERT_UPSTREAM_MCP_ERROR),
                        error_message=str(error.get("error", {}).get("message") or ""),
                        error_detail=error.get("error", {}).get("data") if isinstance(error.get("error"), dict) else None,
                    )
                    return error
                continue

            await self.logs.mark_completed(child_log, result=result)
            text_parts: list[str] = []
            for item in (result or {}).get("content") or []:
                if isinstance(item, dict) and item.get("type") == "text":
                    text_parts.append(str(item.get("text") or ""))
            body_text = "\n".join(text_parts).strip() or str(result)
            sections.append(f"## {expert.display_name}\n\n{body_text}")

        merged = f"# {team.display_name}\n\n" + "\n\n".join(sections)
        result_payload = {
            "content": [{"type": "text", "text": merged}],
            "structuredContent": {
                "invocationId": parent_log.id,
                "slug": team.team_slug,
                "kind": "expert_team",
                "skillName": skill_name,
                "orchestrationMode": "gateway_sequential",
                "status": "completed",
            },
            "isError": False,
        }
        await self.logs.mark_completed(parent_log, result=result_payload)
        return mcp_success(jsonrpc_id, result_payload)
