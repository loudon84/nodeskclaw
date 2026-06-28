from __future__ import annotations

from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.expert import Expert
from app.models.expert_team import ExpertTeam
from app.services.expert_gateway.catalog_resolver import CatalogItem, CatalogResolver
from app.services.expert_gateway.errors import (
    EXPERT_CATALOG_DISABLED,
    EXPERT_CATALOG_NOT_FOUND,
    EXPERT_CATALOG_NOT_PUBLISHED,
    EXPERT_DISABLED,
    EXPERT_INVALID_JSONRPC,
    EXPERT_NOT_PUBLISHED,
    EXPERT_PERMISSION_DENIED,
    EXPERT_ROUTE_OVERRIDE_FORBIDDEN,
    EXPERT_RUNTIME_NOT_READY,
    EXPERT_SKILL_CALL_DISABLED,
    EXPERT_SKILL_NOT_FOUND,
    EXPERT_SKILL_NOT_PUBLIC,
    EXPERT_TEAM_MEMBERS_REQUIRED,
    EXPERT_TEAM_ORCHESTRATION_DISABLED,
    EXPERT_UPSTREAM_MCP_ERROR,
    mcp_error_v2,
    mcp_success,
)
from app.services.expert_gateway.expert_catalog_service import ExpertCatalogService
from app.services.expert_gateway.expert_invocation_log_service import ExpertInvocationLogService
from app.services.expert_gateway.expert_mcp_proxy_service import ExpertMcpProxyService
from app.services.expert_gateway.expert_permission_service import ExpertPermissionService
from app.services.expert_gateway.expert_run_service import ExpertRunService
from app.services.expert_gateway.expert_route_guard import find_route_override_keys
from app.services.expert_gateway.expert_skill_service import ExpertSkillService
from app.services.expert_gateway.expert_team_orchestrator import ExpertTeamOrchestrator
from app.services.expert_gateway.expert_team_service import ExpertTeamService
from app.services.expert_gateway.expert_team_skill_service import ExpertTeamSkillService

_GATEWAY_VERSION = "v6.2"

_EVENT_STREAM_ANNOTATIONS: dict[str, Any] = {
    "callMode": "async_sse",
    "streaming": True,
    "eventStream": {
        "transport": "sse",
        "authMode": "bearer_or_sse_token",
        "resume": True,
    },
    "artifactMode": "pull_only",
    "resultMode": "task_result",
}


class ExpertMcpGatewayService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.resolver = CatalogResolver(db)
        self.catalog = ExpertCatalogService(db)
        self.skills = ExpertSkillService(db)
        self.team_skills = ExpertTeamSkillService(db)
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
                        "version": _GATEWAY_VERSION,
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

    async def dispatch_catalog_item(
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

        item = await self.resolver.resolve(org_id, slug)
        if item is None:
            return mcp_error_v2(jsonrpc_id, EXPERT_CATALOG_NOT_FOUND, f"Catalog item {slug} not found")

        method = body.get("method", "")
        if method == "initialize":
            return mcp_success(
                jsonrpc_id,
                {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {"tools": {}},
                    "serverInfo": {
                        "name": "nodeskclaw-expert-mcp-gateway",
                        "version": _GATEWAY_VERSION,
                    },
                },
            )

        if method == "ping":
            return mcp_success(jsonrpc_id, {})

        if method == "tools/list":
            return await self._dispatch_tools_list(org_id, user_id, item, jsonrpc_id)

        if method == "tools/call":
            return await self._dispatch_tools_call(
                org_id,
                user_id,
                item,
                body,
                headers=headers,
                jsonrpc_id=jsonrpc_id,
            )

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
        return await self.dispatch_catalog_item(org_id, user_id, slug, body, headers=headers)

    async def _dispatch_tools_list(self, org_id: str, user_id: str, item: CatalogItem, jsonrpc_id: Any) -> dict:
        if not await ExpertPermissionService.has(self.db, user_id, org_id, "expert_skill:view"):
            return mcp_error_v2(jsonrpc_id, EXPERT_PERMISSION_DENIED, "expert_skill:view required")
        if not item.published or not item.enabled:
            return mcp_error_v2(jsonrpc_id, EXPERT_CATALOG_NOT_PUBLISHED, "Catalog item is not published")

        if item.kind == "expert":
            expert = item.source_record
            assert isinstance(expert, Expert)
            ready = await self.catalog.runtime_ready(org_id, expert)
            skills = await self.skills.list_public_skills(org_id, expert.id)
            tools = [
                ExpertSkillService.build_tool_descriptor(expert, skill, runtime_ready=ready)
                for skill in skills
            ]
            return mcp_success(jsonrpc_id, {"tools": tools})

        team = item.source_record
        assert isinstance(team, ExpertTeam)
        if item.orchestration_mode == "gateway_sequential":
            tools = await self.team_orchestrator.list_team_tools(org_id, team)
            return mcp_success(jsonrpc_id, {"tools": tools})

        ready = await self.catalog.runtime_ready_for_agent(org_id, team.hermes_agent_id)
        skills = await self.team_skills.list_public_skills(org_id, team.id)
        tools = [
            ExpertTeamSkillService.build_tool_descriptor(
                team,
                skill,
                runtime_ready=ready,
                orchestration_mode=item.orchestration_mode,
            )
            for skill in skills
        ]
        return mcp_success(jsonrpc_id, {"tools": tools})

    async def _dispatch_tools_call(
        self,
        org_id: str,
        user_id: str,
        item: CatalogItem,
        body: dict,
        *,
        headers: dict[str, str] | None = None,
        jsonrpc_id: Any = 1,
    ) -> dict:
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

        if item.kind == "expert":
            expert = item.source_record
            assert isinstance(expert, Expert)
            return await self._call_expert_skill(
                org_id,
                user_id,
                expert,
                skill_name,
                arguments,
                jsonrpc_id=jsonrpc_id,
                headers=headers,
                catalog_item=item,
            )

        team = item.source_record
        assert isinstance(team, ExpertTeam)
        if item.orchestration_mode == "gateway_sequential":
            members = await self.teams.list_members(org_id, team.id)
            if len(members) < 2:
                return mcp_error_v2(jsonrpc_id, EXPERT_TEAM_MEMBERS_REQUIRED, "At least 2 team members required")
            return await self.team_orchestrator.call_team_skill(
                org_id,
                user_id,
                team,
                skill_name,
                arguments,
                jsonrpc_id=jsonrpc_id,
                client_meta=self._client_meta(headers),
            )

        if item.orchestration_mode != "upstream_skill":
            return mcp_error_v2(jsonrpc_id, EXPERT_TEAM_ORCHESTRATION_DISABLED, "Unsupported orchestration mode")

        return await self._call_team_upstream_skill(
            org_id,
            user_id,
            team,
            item,
            skill_name,
            arguments,
            jsonrpc_id=jsonrpc_id,
            headers=headers,
        )

    async def _call_expert_skill(
        self,
        org_id: str,
        user_id: str,
        expert: Expert,
        skill_name: str,
        arguments: dict[str, Any],
        *,
        jsonrpc_id: Any,
        headers: dict[str, str] | None = None,
        catalog_item: CatalogItem | None = None,
    ) -> dict:
        if not expert.published:
            return mcp_error_v2(jsonrpc_id, EXPERT_NOT_PUBLISHED, "Expert is not published")
        if not expert.enabled:
            return mcp_error_v2(jsonrpc_id, EXPERT_DISABLED, "Expert is disabled")
        if not await self.catalog.runtime_ready(org_id, expert):
            return mcp_error_v2(jsonrpc_id, EXPERT_RUNTIME_NOT_READY, "Runtime is not ready")

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
                catalog_kind="expert",
                catalog_slug=expert.expert_slug,
                orchestration_mode="upstream_skill",
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

        run_mode = self._resolve_run_mode(headers)
        agent_profile = await self.catalog.resolve_agent_profile(org_id, expert)
        slug = catalog_item.slug if catalog_item else expert.expert_slug
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
            catalog_kind="expert",
            catalog_slug=slug,
            orchestration_mode="agent_event_stream" if run_mode == "event_stream" else "upstream_skill",
            **self._client_meta(headers),
        )

        if run_mode == "event_stream":
            try:
                return await ExpertRunService(self.db).start_expert_skill_run(
                    org_id,
                    user_id,
                    expert,
                    skill,
                    arguments,
                    catalog_slug=slug,
                    headers=headers,
                    log=log,
                    jsonrpc_id=jsonrpc_id,
                )
            except Exception as exc:
                await self.logs.mark_failed(
                    log,
                    error_code=EXPERT_UPSTREAM_MCP_ERROR,
                    error_message=str(exc),
                )
                return mcp_error_v2(jsonrpc_id, EXPERT_UPSTREAM_MCP_ERROR, str(exc))

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
                    error_code=str(error.get("error", {}).get("data", {}).get("errorCode") or EXPERT_UPSTREAM_MCP_ERROR),
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
                        "slug": slug,
                        "kind": "expert",
                        "skillName": skill.skill_name,
                        "orchestrationMode": "upstream_skill",
                        "status": "completed",
                    }
                )
            await self.logs.mark_completed(log, result=structured)
            return mcp_success(jsonrpc_id, structured)
        except Exception as exc:
            await self.logs.mark_failed(
                log,
                error_code=EXPERT_UPSTREAM_MCP_ERROR,
                error_message=str(exc),
            )
            return mcp_error_v2(jsonrpc_id, EXPERT_UPSTREAM_MCP_ERROR, str(exc))

    async def _call_team_upstream_skill(
        self,
        org_id: str,
        user_id: str,
        team: ExpertTeam,
        item: CatalogItem,
        skill_name: str,
        arguments: dict[str, Any],
        *,
        jsonrpc_id: Any,
        headers: dict[str, str] | None = None,
    ) -> dict:
        if not team.published:
            return mcp_error_v2(jsonrpc_id, EXPERT_CATALOG_NOT_PUBLISHED, "Expert team is not published")
        if not team.enabled:
            return mcp_error_v2(jsonrpc_id, EXPERT_CATALOG_DISABLED, "Expert team is disabled")
        if not team.hermes_agent_id:
            return mcp_error_v2(jsonrpc_id, EXPERT_RUNTIME_NOT_READY, "Team Hermes Agent is not configured")
        if not await self.catalog.runtime_ready_for_agent(org_id, team.hermes_agent_id):
            return mcp_error_v2(jsonrpc_id, EXPERT_RUNTIME_NOT_READY, "Runtime is not ready")

        skill = await self.team_skills.get_skill_by_name(org_id, team.id, skill_name)
        if skill is None:
            return mcp_error_v2(jsonrpc_id, EXPERT_SKILL_NOT_FOUND, f"Skill {skill_name} not found")
        if not skill.is_public:
            return mcp_error_v2(jsonrpc_id, EXPERT_SKILL_NOT_PUBLIC, "Skill is not public")
        if not skill.call_enabled:
            return mcp_error_v2(jsonrpc_id, EXPERT_SKILL_CALL_DISABLED, "Skill call is disabled")
        if not str(arguments.get("prompt") or "").strip():
            return mcp_error_v2(jsonrpc_id, EXPERT_INVALID_JSONRPC, "prompt is required")

        run_mode = self._resolve_run_mode(headers)
        agent_profile = await self.catalog.resolve_agent_profile_by_id(org_id, team.hermes_agent_id)
        log = await self.logs.create_started(
            org_id=org_id,
            user_id=user_id,
            expert_team_id=team.id,
            expert_slug=team.team_slug,
            skill_name=skill.skill_name,
            upstream_tool_name=skill.upstream_tool_name,
            agent_alias=agent_profile,
            jsonrpc_id=str(jsonrpc_id),
            request_payload=arguments,
            invocation_type="expert_team",
            catalog_kind="expert_team",
            catalog_slug=item.slug,
            orchestration_mode="agent_event_stream" if run_mode == "event_stream" else item.orchestration_mode,
            **self._client_meta(headers),
        )

        if run_mode == "event_stream":
            try:
                return await ExpertRunService(self.db).start_team_skill_run(
                    org_id,
                    user_id,
                    team,
                    skill,
                    arguments,
                    catalog_slug=item.slug,
                    orchestration_mode=item.orchestration_mode,
                    headers=headers,
                    log=log,
                    jsonrpc_id=jsonrpc_id,
                )
            except Exception as exc:
                await self.logs.mark_failed(
                    log,
                    error_code=EXPERT_UPSTREAM_MCP_ERROR,
                    error_message=str(exc),
                )
                return mcp_error_v2(jsonrpc_id, EXPERT_UPSTREAM_MCP_ERROR, str(exc))

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
                    error_code=str(error.get("error", {}).get("data", {}).get("errorCode") or EXPERT_UPSTREAM_MCP_ERROR),
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
                        "slug": item.slug,
                        "kind": "expert_team",
                        "skillName": skill.skill_name,
                        "orchestrationMode": item.orchestration_mode,
                        "status": "completed",
                    }
                )
            await self.logs.mark_completed(log, result=structured)
            return mcp_success(jsonrpc_id, structured)
        except Exception as exc:
            await self.logs.mark_failed(
                log,
                error_code=EXPERT_UPSTREAM_MCP_ERROR,
                error_message=str(exc),
            )
            return mcp_error_v2(jsonrpc_id, EXPERT_UPSTREAM_MCP_ERROR, str(exc))

    async def _list_catalog_tools(self, org_id: str, user_id: str) -> list[dict[str, Any]]:
        tools: list[dict[str, Any]] = []
        experts = await self.catalog.list_published_experts(org_id)
        for expert in experts:
            if not await ExpertPermissionService.has(self.db, user_id, org_id, "expert:view"):
                continue
            ready = await self.catalog.runtime_ready(org_id, expert)
            public_count = await self.catalog._count_public_skills(org_id, expert.id)
            callable_count = await self.catalog._count_callable_skills(org_id, expert.id)
            if public_count <= 0:
                continue
            tools.append(
                {
                    "name": expert.expert_slug,
                    "description": expert.description or expert.display_name,
                    "inputSchema": {"type": "object", "properties": {}},
                    "annotations": {
                        "kind": "expert",
                        "slug": expert.expert_slug,
                        "displayName": expert.display_name,
                        "category": expert.category,
                        "tags": list(expert.tags or []),
                        "status": "ready" if ready else "offline",
                        "publicSkillCount": public_count,
                        "callableSkillCount": callable_count,
                        **_EVENT_STREAM_ANNOTATIONS,
                    },
                }
            )

        teams = await self.teams.list_published_teams(org_id)
        for team in teams:
            mode = team.orchestration_mode or "upstream_skill"
            if mode == "sequential_gateway":
                mode = "gateway_sequential"
            if mode == "gateway_sequential":
                public_count = 1
                callable_count = 1
                status = "ready"
            else:
                public_count = await self.team_skills.count_public_skills(org_id, team.id)
                callable_count = await self.team_skills.count_callable_skills(org_id, team.id)
                ready = await self.catalog.runtime_ready_for_agent(org_id, team.hermes_agent_id)
                status = "ready" if ready else "offline"
            if public_count <= 0:
                continue
            team_annotations: dict[str, Any] = {
                "kind": "expert_team",
                "slug": team.team_slug,
                "displayName": team.display_name,
                "category": team.category,
                "tags": list(team.tags or []),
                "status": status,
                "orchestrationMode": mode,
                "publicSkillCount": public_count,
                "callableSkillCount": callable_count,
                **_EVENT_STREAM_ANNOTATIONS,
            }
            if mode == "gateway_sequential":
                team_annotations["memberStream"] = True
            elif mode == "upstream_skill":
                team_annotations["memberStream"] = True
            tools.append(
                {
                    "name": team.team_slug,
                    "description": team.description or team.display_name,
                    "inputSchema": {"type": "object", "properties": {}},
                    "annotations": team_annotations,
                }
            )
        return tools

    @staticmethod
    def _resolve_run_mode(headers: dict[str, str] | None) -> str:
        headers = headers or {}
        raw = (
            headers.get("x-nodeskclaw-expert-run-mode")
            or headers.get("X-NoDeskClaw-Expert-Run-Mode")
            or "event_stream"
        )
        mode = str(raw).strip().lower()
        if mode == "sync_legacy":
            return "sync_legacy"
        return "event_stream"

    @staticmethod
    def _client_meta(headers: dict[str, str] | None) -> dict[str, str | None]:
        headers = headers or {}
        return {
            "client_source": headers.get("x-client") or headers.get("X-Client"),
            "client_version": headers.get("x-proxy-version") or headers.get("X-Proxy-Version"),
            "client_device_id": headers.get("x-device-id") or headers.get("X-Device-Id"),
        }
