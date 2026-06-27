from __future__ import annotations

from typing import Any

from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.base import not_deleted
from app.models.expert import Expert
from app.models.expert_team import ExpertTeam
from app.services.expert_gateway.errors import (
    EXPERT_DISABLED,
    EXPERT_INVALID_JSONRPC,
    EXPERT_NOT_FOUND,
    EXPERT_NOT_PUBLISHED,
    EXPERT_PERMISSION_DENIED,
    EXPERT_ROUTE_OVERRIDE_FORBIDDEN,
    EXPERT_RUNTIME_NOT_READY,
    EXPERT_SKILL_CALL_DISABLED,
    EXPERT_SKILL_NOT_FOUND,
    EXPERT_SKILL_NOT_PUBLIC,
    mcp_error_v2,
    mcp_success,
)
from app.services.expert_gateway.expert_catalog_service import ExpertCatalogService
from app.services.expert_gateway.expert_invocation_log_service import ExpertInvocationLogService
from app.services.expert_gateway.expert_mcp_proxy_service import ExpertMcpProxyService
from app.services.expert_gateway.expert_permission_service import ExpertPermissionService
from app.services.expert_gateway.expert_route_guard import find_route_override_keys
from app.services.expert_gateway.expert_skill_service import ExpertSkillService
from app.services.expert_gateway.expert_team_orchestrator import ExpertTeamOrchestrator
from app.services.expert_gateway.expert_team_service import ExpertTeamService


class ExpertMcpGatewayService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.catalog = ExpertCatalogService(db)
        self.skills = ExpertSkillService(db)
        self.teams = ExpertTeamService(db)
        self.logs = ExpertInvocationLogService(db)
        self.team_orchestrator = ExpertTeamOrchestrator(db)

    async def dispatch_root(
        self,
        org_id: str,
        user_id: str,
        body: dict,
        *,
        headers: dict[str, str] | None = None,
    ) -> dict:
        jsonrpc_id = body.get("id", 1)
        if body.get("jsonrpc") != "2.0":
            return mcp_error_v2(jsonrpc_id, EXPERT_INVALID_JSONRPC, "jsonrpc must be '2.0'")

        method = body.get("method", "")
        if method == "initialize":
            params = body.get("params") if isinstance(body.get("params"), dict) else {}
            client_info = params.get("clientInfo") if isinstance(params.get("clientInfo"), dict) else {}
            return mcp_success(
                jsonrpc_id,
                {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {"tools": {}},
                    "serverInfo": {
                        "name": "nodeskclaw-expert-mcp-gateway",
                        "version": "v6.0",
                        "client": client_info,
                    },
                },
            )

        if method == "ping":
            return mcp_success(jsonrpc_id, {})

        if method == "tools/list":
            if not await ExpertPermissionService.has(self.db, user_id, org_id, "expert:view"):
                return mcp_error_v2(jsonrpc_id, EXPERT_PERMISSION_DENIED, "expert:view required")
            tools = await self._list_catalog_tools(org_id, user_id)
            return mcp_success(jsonrpc_id, {"tools": tools})

        return mcp_error_v2(jsonrpc_id, "MCP_METHOD_NOT_FOUND", f"Method not found: {method}")

    async def dispatch_slug(
        self,
        org_id: str,
        user_id: str,
        slug: str,
        body: dict,
        *,
        headers: dict[str, str] | None = None,
    ) -> dict:
        jsonrpc_id = body.get("id", 1)
        if body.get("jsonrpc") != "2.0":
            return mcp_error_v2(jsonrpc_id, EXPERT_INVALID_JSONRPC, "jsonrpc must be '2.0'")

        method = body.get("method", "")
        team = await self.teams.get_by_slug(org_id, slug)
        if team is not None:
            return await self._dispatch_team(org_id, user_id, team, body, headers=headers)

        expert = await self.catalog.get_by_slug(org_id, slug)
        if expert is None:
            return mcp_error_v2(jsonrpc_id, EXPERT_NOT_FOUND, f"Expert {slug} not found")

        if method == "initialize":
            return mcp_success(
                jsonrpc_id,
                {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {"tools": {}},
                    "serverInfo": {
                        "name": f"expert-{slug}",
                        "version": "v6.0",
                    },
                },
            )

        if method == "ping":
            return mcp_success(jsonrpc_id, {})

        if method == "tools/list":
            if not await ExpertPermissionService.has(self.db, user_id, org_id, "expert_skill:view"):
                return mcp_error_v2(jsonrpc_id, EXPERT_PERMISSION_DENIED, "expert_skill:view required")
            if not expert.published or not expert.enabled:
                return mcp_error_v2(jsonrpc_id, EXPERT_NOT_PUBLISHED, "Expert is not published")
            ready = await self.catalog.runtime_ready(org_id, expert)
            skills = await self.skills.list_public_skills(org_id, expert.id)
            tools = [
                ExpertSkillService.build_tool_descriptor(expert, skill, runtime_ready=ready)
                for skill in skills
            ]
            return mcp_success(jsonrpc_id, {"tools": tools})

        if method == "tools/call":
            return await self._call_expert_skill(
                org_id,
                user_id,
                expert,
                body,
                headers=headers,
            )

        return mcp_error_v2(jsonrpc_id, "MCP_METHOD_NOT_FOUND", f"Method not found: {method}")

    async def _dispatch_team(
        self,
        org_id: str,
        user_id: str,
        team: ExpertTeam,
        body: dict,
        *,
        headers: dict[str, str] | None = None,
    ) -> dict:
        jsonrpc_id = body.get("id", 1)
        method = body.get("method", "")

        if method == "initialize":
            return mcp_success(
                jsonrpc_id,
                {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {"tools": {}},
                    "serverInfo": {"name": f"expert-team-{team.team_slug}", "version": "v6.0"},
                },
            )

        if method == "ping":
            return mcp_success(jsonrpc_id, {})

        if method == "tools/list":
            if not await ExpertPermissionService.has(self.db, user_id, org_id, "expert_skill:view"):
                return mcp_error_v2(jsonrpc_id, EXPERT_PERMISSION_DENIED, "expert_skill:view required")
            if not team.published or not team.enabled:
                return mcp_error_v2(jsonrpc_id, EXPERT_NOT_PUBLISHED, "Expert team is not published")
            tools = await self.team_orchestrator.list_team_tools(org_id, team)
            return mcp_success(jsonrpc_id, {"tools": tools})

        if method == "tools/call":
            if not await ExpertPermissionService.has(self.db, user_id, org_id, "expert_skill:invoke"):
                return mcp_error_v2(jsonrpc_id, EXPERT_PERMISSION_DENIED, "expert_skill:invoke required")
            params = body.get("params") if isinstance(body.get("params"), dict) else {}
            skill_name = str(params.get("name") or "").strip()
            arguments = params.get("arguments") if isinstance(params.get("arguments"), dict) else {}
            forbidden = find_route_override_keys(arguments)
            if forbidden:
                return mcp_error_v2(
                    jsonrpc_id,
                    EXPERT_ROUTE_OVERRIDE_FORBIDDEN,
                    data={"forbiddenKeys": forbidden},
                )
            return await self.team_orchestrator.call_team_skill(
                org_id,
                user_id,
                team,
                skill_name,
                arguments,
                jsonrpc_id=jsonrpc_id,
                client_meta=self._client_meta(headers),
            )

        return mcp_error_v2(jsonrpc_id, "MCP_METHOD_NOT_FOUND", f"Method not found: {method}")

    async def _call_expert_skill(
        self,
        org_id: str,
        user_id: str,
        expert: Expert,
        body: dict,
        *,
        headers: dict[str, str] | None = None,
    ) -> dict:
        jsonrpc_id = body.get("id", 1)
        if not await ExpertPermissionService.has(self.db, user_id, org_id, "expert_skill:invoke"):
            return mcp_error_v2(jsonrpc_id, EXPERT_PERMISSION_DENIED, "expert_skill:invoke required")
        if not expert.published:
            return mcp_error_v2(jsonrpc_id, EXPERT_NOT_PUBLISHED, "Expert is not published")
        if not expert.enabled:
            return mcp_error_v2(jsonrpc_id, EXPERT_DISABLED, "Expert is disabled")
        if not await self.catalog.runtime_ready(org_id, expert):
            return mcp_error_v2(jsonrpc_id, EXPERT_RUNTIME_NOT_READY, "Runtime is not ready")

        params = body.get("params") if isinstance(body.get("params"), dict) else {}
        skill_name = str(params.get("name") or "").strip()
        arguments = params.get("arguments") if isinstance(params.get("arguments"), dict) else {}
        forbidden = find_route_override_keys(arguments)
        if forbidden:
            log = await self.logs.create_started(
                org_id=org_id,
                user_id=user_id,
                expert_id=expert.id,
                expert_slug=expert.expert_slug,
                skill_name=skill_name,
                jsonrpc_id=str(jsonrpc_id),
                request_payload=arguments,
                **self._client_meta(headers),
            )
            await self.logs.mark_rejected(
                log,
                error_code=EXPERT_ROUTE_OVERRIDE_FORBIDDEN,
                error_message="Route override forbidden",
                error_detail={"forbiddenKeys": forbidden},
            )
            return mcp_error_v2(
                jsonrpc_id,
                EXPERT_ROUTE_OVERRIDE_FORBIDDEN,
                data={"forbiddenKeys": forbidden},
            )

        skill = await self.skills.get_skill_by_name(org_id, expert.id, skill_name)
        if skill is None:
            return mcp_error_v2(jsonrpc_id, EXPERT_SKILL_NOT_FOUND, f"Skill {skill_name} not found")
        if not skill.is_public:
            return mcp_error_v2(jsonrpc_id, EXPERT_SKILL_NOT_PUBLIC, "Skill is not public")
        if not skill.call_enabled:
            return mcp_error_v2(jsonrpc_id, EXPERT_SKILL_CALL_DISABLED, "Skill call is disabled")
        if not str(arguments.get("prompt") or "").strip():
            return mcp_error_v2(jsonrpc_id, EXPERT_INVALID_JSONRPC, "prompt is required")

        agent_profile = await self.catalog.resolve_agent_profile(org_id, expert)
        log = await self.logs.create_started(
            org_id=org_id,
            user_id=user_id,
            expert_id=expert.id,
            expert_skill_id=skill.id,
            expert_slug=expert.expert_slug,
            skill_name=skill.skill_name,
            upstream_tool_name=skill.upstream_tool_name,
            agent_alias=agent_profile,
            jsonrpc_id=str(jsonrpc_id),
            request_payload=arguments,
            **self._client_meta(headers),
        )

        try:
            response = await ExpertMcpProxyService.call_upstream_tool(
                self.db,
                org_id,
                user_id,
                agent_profile,
                skill.upstream_tool_name,
                arguments,
                jsonrpc_id=jsonrpc_id,
            )
            result, error = ExpertMcpProxyService.parse_upstream_result(response)
            if error:
                await self.logs.mark_failed(
                    log,
                    error_code=str(error.get("error", {}).get("data", {}).get("errorCode") or "EXPERT_UPSTREAM_MCP_ERROR"),
                    error_message=str(error.get("error", {}).get("message") or ""),
                    error_detail=error.get("error", {}).get("data") if isinstance(error.get("error"), dict) else None,
                )
                return error

            structured = dict(result or {})
            structured.setdefault("structuredContent", {})
            if isinstance(structured["structuredContent"], dict):
                structured["structuredContent"].update(
                    {
                        "invocationId": log.id,
                        "expertSlug": expert.expert_slug,
                        "skillName": skill.skill_name,
                        "status": "completed",
                    }
                )
            await self.logs.mark_completed(log, result=structured)
            return mcp_success(jsonrpc_id, structured)
        except Exception as exc:
            await self.logs.mark_failed(
                log,
                error_code="EXPERT_UPSTREAM_MCP_ERROR",
                error_message=str(exc),
            )
            return mcp_error_v2(jsonrpc_id, "EXPERT_UPSTREAM_MCP_ERROR", str(exc))

    async def _list_catalog_tools(self, org_id: str, user_id: str) -> list[dict[str, Any]]:
        tools: list[dict[str, Any]] = []
        experts = await self.catalog.list_published_experts(org_id)
        for expert in experts:
            if not await ExpertPermissionService.has(self.db, user_id, org_id, "expert:view"):
                continue
            ready = await self.catalog.runtime_ready(org_id, expert)
            public_count = await self.catalog._count_public_skills(org_id, expert.id)
            callable_count = await self.catalog._count_callable_skills(org_id, expert.id)
            tools.append(
                {
                    "name": expert.expert_slug,
                    "description": expert.description or expert.display_name,
                    "inputSchema": {"type": "object", "properties": {}},
                    "annotations": {
                        "kind": "expert",
                        "expertSlug": expert.expert_slug,
                        "displayName": expert.display_name,
                        "category": expert.category,
                        "tags": list(expert.tags or []),
                        "status": "ready" if ready else "offline",
                        "publicSkillCount": public_count,
                        "callableSkillCount": callable_count,
                    },
                }
            )

        teams = await self.teams.list_published_teams(org_id)
        for team in teams:
            tools.append(
                {
                    "name": team.team_slug,
                    "description": team.description or team.display_name,
                    "inputSchema": {"type": "object", "properties": {}},
                    "annotations": {
                        "kind": "expert_team",
                        "teamSlug": team.team_slug,
                        "displayName": team.display_name,
                        "category": team.category,
                        "tags": list(team.tags or []),
                        "status": "ready",
                    },
                }
            )
        return tools

    @staticmethod
    def _client_meta(headers: dict[str, str] | None) -> dict[str, str | None]:
        headers = headers or {}
        return {
            "client_source": headers.get("x-client") or headers.get("X-Client"),
            "client_version": headers.get("x-proxy-version") or headers.get("X-Proxy-Version"),
            "client_device_id": headers.get("x-device-id") or headers.get("X-Device-Id"),
        }
