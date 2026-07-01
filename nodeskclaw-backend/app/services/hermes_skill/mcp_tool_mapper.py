import logging
from typing import Any

from sqlalchemy import exists, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError, BadRequestError, ForbiddenError
from app.models.base import not_deleted
from app.models.hermes_skill.skill import HermesSkill
from app.models.hermes_skill.skill_installation import HermesSkillInstallation
from app.models.hermes_skill.hermes_task import TaskStatus
from app.services.hermes_skill.agent_alias_resolver import AgentAliasResolver
from app.services.hermes_skill.hermes_skill_authorization_service import HermesSkillAuthorizationService
from app.services.hermes_skill.permission_checker import PermissionChecker
from app.services.hermes_skill.skill_routing_service import SkillRoutingService
from app.schemas.hermes_skill.runtime_skill_run import StartRuntimeSkillRunRequest
from app.services.hermes_skill.runtime_skill_run_service import RuntimeSkillRunService
from app.services.hermes_skill.task_service import TaskService
from app.services.mcp_skill_gateway.mcp_execution_mode import (
    ASYNC_EVENT_MODE,
    WAIT_MODE,
    resolve_mcp_execution_mode,
    strip_mcp_control_args,
)
from app.services.mcp_skill_gateway.mcp_task_dedup_service import McpTaskDedupService
from app.services.mcp_skill_gateway.mcp_task_wait_service import McpTaskWaitService
from app.services.mcp_skill_gateway.output_policy_service import OutputPolicyService
from app.core.config import settings
from app.services.hermes_skill.task_event_token_service import TaskEventTokenService

logger = logging.getLogger(__name__)

RUNTIME_SKILL_ROUTE_TYPE = "hermes_api_server"
RUNTIME_SKILL_FORBIDDEN_ARGUMENT_KEYS = ("_routing", "_execution", "route_config")


class McpToolMapper:
    def __init__(self, db: AsyncSession):
        self.db = db

    @staticmethod
    def _has_explicit_runtime_route_override(raw_args: dict) -> bool:
        return (
            "_routing" in raw_args
            or "_execution" in raw_args
            or "route_config" in raw_args
        )

    async def list_tools(
        self,
        org_id: str,
        user_id: str = "",
        *,
        agent_id: str | None = None,
        agent_alias: str | None = None,
        profile: str | None = None,
        workspace_id: str | None = None,
        category: str | None = None,
        keyword: str | None = None,
    ) -> list[dict[str, Any]]:
        has_view = True
        has_invoke = True
        if user_id:
            has_view = await PermissionChecker.has_permission(self.db, user_id, org_id, "skill:view")
            has_invoke = await PermissionChecker.has_permission(self.db, user_id, org_id, "skill:invoke")
        if not has_view or not has_invoke:
            return []

        if agent_alias and not agent_id:
            resolution = await AgentAliasResolver(self.db).resolve(org_id, agent_alias)
            if resolution:
                agent_id = resolution.agent_id
                profile = profile or resolution.profile_id
                workspace_id = workspace_id or resolution.workspace_id

        installed_subq = (
            select(HermesSkillInstallation.skill_id)
            .where(
                not_deleted(HermesSkillInstallation),
                HermesSkillInstallation.org_id == org_id,
                HermesSkillInstallation.status == "installed",
            )
            .correlate(HermesSkill)
        )
        if agent_id:
            installed_subq = installed_subq.where(HermesSkillInstallation.agent_id == agent_id)
        if profile:
            installed_subq = installed_subq.where(HermesSkillInstallation.profile_id == profile)
        if workspace_id:
            installed_subq = installed_subq.where(HermesSkillInstallation.workspace_id == workspace_id)

        conditions = [
            not_deleted(HermesSkill),
            HermesSkill.org_id == org_id,
            HermesSkill.is_active.is_(True),
            HermesSkill.is_mcp_exposed.is_(True),
            HermesSkill.tool_name.isnot(None),
            HermesSkill.tool_name != "",
            exists(installed_subq.where(HermesSkillInstallation.skill_id == HermesSkill.skill_id)),
        ]
        if category:
            conditions.append(HermesSkill.category == category)
        if keyword:
            conditions.append(
                HermesSkill.tool_name.ilike(f"%{keyword}%")
                | HermesSkill.name.ilike(f"%{keyword}%")
                | HermesSkill.title.ilike(f"%{keyword}%")
            )

        result = await self.db.execute(select(HermesSkill).where(*conditions))
        skills = list(result.scalars().all())

        if user_id:
            role = await PermissionChecker.get_user_role(self.db, user_id, org_id)
            if role not in PermissionChecker.ADMIN_OPERATOR_ROLES:
                authz = HermesSkillAuthorizationService(self.db)
                skills = [
                    s for s in skills
                    if await authz.can_list(org_id, user_id, s.id, s.skill_id)
                ]

        alias_resolver = AgentAliasResolver(self.db)
        tools = []
        for skill in skills:
            tools.append(await self._skill_to_tool_dict(skill, org_id, agent_id, agent_alias, alias_resolver, user_id))
        return tools

    async def _skill_to_tool_dict(
        self,
        skill: HermesSkill,
        org_id: str,
        agent_id: str | None,
        agent_alias: str | None,
        alias_resolver: AgentAliasResolver,
        user_id: str,
    ) -> dict[str, Any]:
        extra = skill.extra_metadata or {}
        resolved_alias = agent_alias
        resolved_agent_id = agent_id
        profile_id = None
        workspace_id = None
        installation = None
        inst_result = await self.db.execute(
            select(HermesSkillInstallation).where(
                not_deleted(HermesSkillInstallation),
                HermesSkillInstallation.org_id == org_id,
                HermesSkillInstallation.skill_id == skill.skill_id,
                HermesSkillInstallation.status == "installed",
            ).limit(1)
        )
        installation = inst_result.scalar_one_or_none()
        if installation:
            resolved_agent_id = resolved_agent_id or installation.agent_id
            profile_id = installation.profile_id
            workspace_id = installation.workspace_id
        if resolved_agent_id and not resolved_alias:
            resolution = await alias_resolver.resolve(org_id, resolved_agent_id)
            if resolution:
                resolved_alias = resolution.agent_alias
                profile_id = profile_id or resolution.profile_id
                workspace_id = workspace_id or resolution.workspace_id

        authorized = True
        grant_status = "active"
        if user_id:
            authz = HermesSkillAuthorizationService(self.db)
            authorized = await authz.can_invoke(org_id, user_id, skill.id, skill.skill_id)
            if not authorized:
                grant_status = "denied"

        tool: dict[str, Any] = {
            "name": skill.tool_name,
            "title": skill.title or skill.name,
            "description": skill.description or "",
            "inputSchema": skill.input_schema or {},
            "version": skill.version,
            "category": skill.category,
            "agentAlias": resolved_alias,
            "agentId": resolved_agent_id,
            "profileId": profile_id,
            "workspaceId": workspace_id,
            "approvalMode": "server",
            "requiresApproval": False,
            "authorized": authorized,
            "grantStatus": grant_status,
        }
        if extra.get("ui_schema"):
            tool["uiSchema"] = extra["ui_schema"]
        if extra.get("examples"):
            tool["examples"] = extra["examples"]
        if extra.get("primary_artifact_policy"):
            tool["primaryArtifactPolicy"] = extra["primary_artifact_policy"]
        if skill.source_type == RUNTIME_SKILL_ROUTE_TYPE:
            tool.update(
                await self._build_runtime_skill_tool_metadata(
                    skill,
                    org_id,
                    installation,
                    profile_id,
                )
            )
        return tool

    async def _build_runtime_skill_tool_metadata(
        self,
        skill: HermesSkill,
        org_id: str,
        installation: HermesSkillInstallation | None,
        profile_id: str | None,
    ) -> dict[str, Any]:
        route_meta = {}
        if installation and isinstance(installation.routing_metadata, dict):
            route_meta = installation.routing_metadata
        runtime_profile = route_meta.get("agent_profile") or profile_id
        route_health = await self._resolve_runtime_route_health(
            org_id,
            route_meta,
            runtime_profile,
        )
        return {
            "sourceType": RUNTIME_SKILL_ROUTE_TYPE,
            "routeType": route_meta.get("route_type") or RUNTIME_SKILL_ROUTE_TYPE,
            "serverManagedRoute": True,
            "runtimeSkillId": route_meta.get("runtime_skill_id") or skill.skill_id,
            "runtimeInstanceId": route_meta.get("hermes_agent_instance_id"),
            "runtimeInstanceName": runtime_profile,
            "runtimeProfile": runtime_profile,
            "executionModes": [ASYNC_EVENT_MODE],
            "defaultExecutionMode": ASYNC_EVENT_MODE,
            "sseTimelineEnabled": True,
            "eventStreamProvider": "nodeskclaw_task_events",
            "artifactMode": "pull_only",
            "resultMode": "pull_on_complete",
            "routeOverrideAllowed": False,
            "requiresRouteOverride": False,
            "forbiddenArgumentKeys": list(RUNTIME_SKILL_FORBIDDEN_ARGUMENT_KEYS),
            "routeHealth": route_health,
        }

    async def _resolve_runtime_route_health(
        self,
        org_id: str,
        route_meta: dict[str, Any],
        profile_name: str | None,
    ) -> dict[str, bool]:
        from app.services.hermes_external.hermes_docker_binding_service import HermesDockerBindingService

        profile = profile_name or route_meta.get("agent_profile")
        instance_id = route_meta.get("hermes_agent_instance_id")
        if not profile:
            return {
                "ok": False,
                "instance_bound": False,
                "api_server_enabled": False,
            }
        record = await HermesDockerBindingService(self.db).get_by_profile(org_id, str(profile))
        instance_bound = bool(record and instance_id and record.id == instance_id)
        api_server_enabled = bool(
            instance_bound
            and record.gateway_url
            and record.gateway_runtime_status not in {"stopped", "error"}
        )
        return {
            "ok": instance_bound and api_server_enabled,
            "instance_bound": instance_bound,
            "api_server_enabled": api_server_enabled,
        }

    async def call_tool(
        self,
        tool_name: str,
        arguments: dict,
        org_id: str,
        user_id: str = "",
        jsonrpc_id: Any = None,
        *,
        client_context: dict | None = None,
        profile_name: str | None = None,
        auth_ctx: Any = None,
        request_trace_id: str | None = None,
        request_snapshot: dict | None = None,
    ) -> dict[str, Any]:
        if user_id:
            await PermissionChecker.require_permission(self.db, user_id, org_id, "skill:view")
            await PermissionChecker.require_permission(self.db, user_id, org_id, "skill:invoke")

        raw_args, wait_override = strip_mcp_control_args(arguments)
        agent_arguments, explicit_routing = SkillRoutingService.extract_routing(raw_args)
        alias_resolver = AgentAliasResolver(self.db)
        routing_service = SkillRoutingService(self.db)
        routing: dict = {}

        skill = await routing_service.get_exposed_skill(tool_name, org_id)
        if not skill:
            from app.services.hermes_skill.skill_audit_logger import SkillAuditLogger
            audit_logger = SkillAuditLogger(self.db)
            await audit_logger.log(
                action="hermes.skill.routing.failed",
                target_id=tool_name,
                org_id=org_id,
                actor_id=user_id or "",
                details={"tool_name": tool_name, "error": "errors.skill.tool_not_found"},
            )
            raise NotFoundError(
                f"MCP Tool {tool_name} 不存在",
                "errors.skill.tool_not_found",
            )

        try:
            if skill.source_type == "hermes_api_server":
                if self._has_explicit_runtime_route_override(raw_args):
                    override_keys = [
                        key for key in ("_routing", "_execution", "route_config")
                        if key in raw_args
                    ]
                    logger.warning(
                        "MCP runtime skill route override denied tool=%s user=%s keys=%s",
                        tool_name,
                        user_id or "",
                        override_keys,
                    )
                    raise BadRequestError(
                        "组织级 MCP 不允许覆盖 Hermes 实例路由",
                        "errors.skill.route_override_not_allowed",
                        details={
                            "tool_name": tool_name,
                            "override_keys": override_keys,
                            "expected_mode": "server_managed_fixed_route",
                            "suggested_arguments": {
                                "prompt": "string",
                                "context": "object",
                            },
                        },
                    )

                routing_result = await routing_service.resolve_runtime_skill_fixed_route(
                    tool_name=tool_name,
                    org_id=org_id,
                )
                routing = {}
                logger.debug(
                    "MCP runtime skill fixed route selected tool=%s installation=%s profile_from_token_ignored=%s",
                    tool_name,
                    routing_result.installation.id if routing_result.installation else "",
                    bool(profile_name),
                )
            else:
                routing = await alias_resolver.enrich_routing(
                    org_id,
                    explicit_routing,
                    profile_name=profile_name,
                )
                routing_result = await routing_service.resolve_by_tool_name(
                    tool_name=tool_name,
                    org_id=org_id,
                    routing=routing,
                )

            installation = routing_result.installation
            if not installation:
                raise NotFoundError(
                    f"Skill {tool_name} 未安装到任何 Agent",
                    "errors.skill.installation_not_found",
                )
        except (NotFoundError, BadRequestError) as exc:
            from app.services.hermes_skill.skill_audit_logger import SkillAuditLogger
            audit_logger = SkillAuditLogger(self.db)
            await audit_logger.log(
                action="hermes.skill.routing.failed",
                target_id=tool_name,
                org_id=org_id,
                actor_id=user_id or "",
                details={"tool_name": tool_name, "error": exc.message_key},
            )
            if routing.get("agent_alias"):
                await audit_logger.log(
                    action="hermes.skill.routing.alias_failed",
                    target_id=str(routing.get("agent_alias")),
                    org_id=org_id,
                    actor_id=user_id or "",
                    details={"tool_name": tool_name, "agent_alias": routing.get("agent_alias")},
                )
            raise

        if user_id:
            authz_service = HermesSkillAuthorizationService(self.db)
            if not await authz_service.can_invoke(org_id, user_id, skill.id, skill.skill_id):
                from app.core import hooks
                await hooks.emit(
                    "operation_audit",
                    action="mcp.skill_call_denied",
                    target_type="hermes_skill",
                    target_id=skill.id,
                    actor_id=user_id,
                    org_id=org_id,
                    details={"skill_id": skill.skill_id, "tool_name": tool_name},
                )
                raise ForbiddenError(
                    "无权调用该 Skill",
                    "errors.skill.permission_denied",
                )

        if skill.input_schema:
            try:
                import jsonschema
                jsonschema.validate(instance=agent_arguments, schema=skill.input_schema)
            except ImportError:
                pass
            except jsonschema.ValidationError as exc:
                raise BadRequestError(
                    f"arguments 不符合 input_schema: {exc.message}",
                    "errors.skill.input_schema_validation_failed",
                )

        agent_alias = routing.get("agent_alias")
        if not agent_alias:
            resolution = await alias_resolver.resolve(org_id, installation.agent_id)
            if resolution:
                agent_alias = resolution.agent_alias

        routing_metadata = {
            "agent_alias": agent_alias,
            "agent_id": installation.agent_id,
            "profile_id": installation.profile_id,
            "workspace_id": installation.workspace_id,
            "installation_id": installation.id,
            "routing_reason": routing_result.reason,
        }
        output_policy = OutputPolicyService.resolve(
            skill=skill,
            installation=installation,
            tool_name=tool_name,
        )
        routing_metadata["output_policy"] = output_policy
        if installation.routing_metadata:
            routing_metadata["route_snapshot"] = dict(installation.routing_metadata)
            if skill.source_type == "hermes_api_server":
                routing_metadata["task_source"] = "org_mcp"

        execution_mode = resolve_mcp_execution_mode(
            auth_ctx,
            skill,
            output_policy,
            wait_override=wait_override,
        )
        route_diagnostics: dict[str, Any] | None = None
        if skill.source_type == RUNTIME_SKILL_ROUTE_TYPE:
            routing_metadata["execution_contract"] = {
                "mode": execution_mode,
                "timeline_provider": "nodeskclaw_task_events",
                "runtime_invocation": "chat_completions",
                "desktop_route_override_allowed": False,
            }
            route_health = await self._resolve_runtime_route_health(
                org_id,
                installation.routing_metadata or {},
                installation.profile_id,
            )
            route_diagnostics = {
                "skill_source_type": skill.source_type,
                "selected_installation_id": installation.id if installation else None,
                "route_type": (installation.routing_metadata or {}).get("route_type"),
                "routing_reason": routing_result.reason,
                "execution_contract": routing_metadata["execution_contract"],
                "route_override_keys": [],
                "route_health": route_health,
            }
            logger.info(
                "mcp.tools_call.route_resolved trace_id=%s tool=%s source_type=%s route_type=%s "
                "runtime_invocation=chat_completions execution_mode=%s client_source=%s",
                request_trace_id or "",
                tool_name,
                skill.source_type,
                route_diagnostics["route_type"],
                execution_mode,
                (client_context or {}).get("source", ""),
            )

        fingerprint = (client_context or {}).get("request_fingerprint")
        if fingerprint:
            existing = await McpTaskDedupService(self.db).find_dedupe_task(org_id, fingerprint)
            if existing:
                from app.services.hermes_skill.skill_audit_logger import SkillAuditLogger
                audit_logger = SkillAuditLogger(self.db)
                existing_routing = existing.routing_metadata or {}
                existing_output = existing_routing.get("output_policy") or output_policy
                existing_alias = existing_routing.get("agent_alias") or agent_alias
                await audit_logger.log(
                    action="mcp.task.dedup.hit",
                    target_id=existing.id,
                    org_id=org_id,
                    actor_id=user_id or "",
                    details={
                        "task_id": existing.id,
                        "task_no": existing.task_no,
                        "tool_name": tool_name,
                        "request_fingerprint": fingerprint,
                    },
                )
                if execution_mode == WAIT_MODE:
                    return await self._finalize_wait_response(
                        existing.id,
                        org_id,
                        tool_name=tool_name,
                        agent_alias=existing_alias,
                        installation=installation,
                        deduped=True,
                        existing_task=existing,
                    )
                if execution_mode == ASYNC_EVENT_MODE:
                    return await self._finalize_async_event_response(
                        existing,
                        org_id,
                        tool_name=tool_name,
                        agent_alias=existing_alias,
                        installation=installation,
                        routing_result=routing_result,
                        output_policy=existing_output,
                        user_id=user_id or "",
                        deduped=True,
                    )
                return self._build_task_response(
                    task=existing,
                    tool_name=tool_name,
                    agent_alias=existing_alias,
                    installation=installation,
                    routing_result=routing_result,
                    output_policy=existing_output,
                    deduped=True,
                )

        logger.info(
            "hermes_task.create.begin trace_id=%s tool=%s source_type=%s execution_mode=%s",
            request_trace_id or "", tool_name,
            skill.source_type or "", execution_mode,
        )

        runtime_run_result = None
        if skill.source_type == RUNTIME_SKILL_ROUTE_TYPE:
            route_meta = installation.routing_metadata or {}
            run_request = StartRuntimeSkillRunRequest(
                org_id=org_id,
                user_id=user_id or "",
                tool_name=tool_name,
                runtime_skill_id=str(route_meta.get("runtime_skill_id") or skill.skill_id),
                agent_profile=str(route_meta.get("agent_profile") or installation.profile_id or ""),
                hermes_agent_instance_id=str(route_meta.get("hermes_agent_instance_id") or ""),
                agent_id=installation.agent_id,
                arguments=agent_arguments,
                client_context=client_context or {},
                output_policy=output_policy,
                task_source="org_mcp",
                skill_id=skill.skill_id,
                installation_id=installation.id,
                workspace_id=installation.workspace_id,
                request_trace_id=request_trace_id,
                request_snapshot=request_snapshot,
                route_diagnostics=route_diagnostics,
                execution_mode=execution_mode,
                entrypoint="mcp_skill_gateway",
                routing_metadata_extras={
                    "agent_alias": agent_alias,
                    "agent_id": installation.agent_id,
                    "profile_id": installation.profile_id,
                    "workspace_id": installation.workspace_id,
                    "routing_reason": routing_result.reason,
                },
            )
            logger.info(
                "mcp.tools_call.delegated_to_runtime_skill_run trace_id=%s tool=%s "
                "entrypoint=mcp_skill_gateway task_source=org_mcp route_type=%s "
                "runtime_invocation=chat_completions",
                request_trace_id or "",
                tool_name,
                RUNTIME_SKILL_ROUTE_TYPE,
            )
            runtime_run_result = await RuntimeSkillRunService(self.db).start(run_request)
            task = runtime_run_result.task
        else:
            task = await TaskService(self.db).create_task(
                org_id=org_id,
                skill_id=skill.skill_id,
                tool_name=tool_name,
                agent_id=installation.agent_id,
                profile_id=installation.profile_id,
                workspace_id=installation.workspace_id,
                installation_id=installation.id,
                user_id=user_id or None,
                arguments=agent_arguments,
                client_context=client_context,
                routing_metadata=routing_metadata,
            )
            task.request_trace_id = request_trace_id
            task.request_snapshot = request_snapshot
            task.route_diagnostics = route_diagnostics
            await self.db.flush()

        logger.info(
            "hermes_task.create.done trace_id=%s task_id=%s task_no=%s tool=%s",
            request_trace_id or "", task.id, task.task_no, tool_name,
        )

        from app.services.hermes_skill.skill_audit_logger import SkillAuditLogger
        audit_logger = SkillAuditLogger(self.db)
        await audit_logger.log(
            action="hermes.skill.routing.resolved",
            target_id=task.id,
            org_id=org_id,
            actor_id=user_id or "",
            details={
                "task_id": task.id,
                "installation_id": installation.id,
                "routing_reason": routing_result.reason,
                "agent_id": installation.agent_id,
                "profile_id": installation.profile_id,
                "workspace_id": installation.workspace_id,
            },
        )
        if agent_alias:
            await audit_logger.log(
                action="hermes.skill.routing.alias_resolved",
                target_id=task.id,
                org_id=org_id,
                actor_id=user_id or "",
                details={"agent_alias": agent_alias, "agent_id": installation.agent_id},
            )
        await audit_logger.log(
            action="hermes.skill.invoked",
            target_id=task.id,
            org_id=org_id,
            actor_id=user_id or "",
            details={
                "task_id": task.id,
                "task_no": task.task_no,
                "skill_id": skill.skill_id,
                "tool_name": tool_name,
                "agent_id": installation.agent_id,
            },
        )
        if fingerprint:
            await audit_logger.log(
                action="mcp.task.dedup.created",
                target_id=task.id,
                org_id=org_id,
                actor_id=user_id or "",
                details={
                    "task_id": task.id,
                    "task_no": task.task_no,
                    "tool_name": tool_name,
                    "request_fingerprint": fingerprint,
                },
            )

        await self.db.flush()

        if execution_mode == WAIT_MODE:
            await self.db.commit()
            return await self._finalize_wait_response(
                task.id,
                org_id,
                tool_name=tool_name,
                agent_alias=agent_alias,
                installation=installation,
                deduped=False,
                existing_task=task,
            )

        if execution_mode == ASYNC_EVENT_MODE:
            await self.db.commit()
            if runtime_run_result is not None:
                return self._merge_org_mcp_async_payload(
                    runtime_run_result.structured_content,
                    tool_name=tool_name,
                    agent_alias=agent_alias,
                    installation=installation,
                    routing_result=routing_result,
                    deduped=False,
                )
            return await self._build_async_event_response(
                task=task,
                tool_name=tool_name,
                agent_alias=agent_alias,
                installation=installation,
                routing_result=routing_result,
                output_policy=output_policy,
                org_id=org_id,
                user_id=user_id or "",
                deduped=False,
            )

        return self._build_task_response(
            task=task,
            tool_name=tool_name,
            agent_alias=agent_alias,
            installation=installation,
            routing_result=routing_result,
            output_policy=output_policy,
            deduped=False,
        )

    async def _finalize_wait_response(
        self,
        task_id: str,
        org_id: str,
        *,
        tool_name: str,
        agent_alias: str | None,
        installation: Any,
        deduped: bool,
        existing_task: Any,
    ) -> dict[str, Any]:
        wait_service = McpTaskWaitService()
        if existing_task.status == TaskStatus.COMPLETED:
            wait_result = await wait_service.build_result_for_task(existing_task)
        elif existing_task.status in {
            TaskStatus.FAILED,
            TaskStatus.TIMEOUT,
            TaskStatus.CANCELLED,
        }:
            wait_result = wait_service._build_failed_result(existing_task)
        else:
            wait_result = await wait_service.wait_for_task_result(task_id, org_id)
        return self._merge_wait_result(
            wait_result,
            tool_name=tool_name,
            agent_alias=agent_alias,
            installation=installation,
            deduped=deduped,
        )

    def _merge_wait_result(
        self,
        wait_result: dict[str, Any],
        *,
        tool_name: str,
        agent_alias: str | None,
        installation: Any,
        deduped: bool,
    ) -> dict[str, Any]:
        payload = dict(wait_result)
        payload.update({
            "tool_name": tool_name,
            "agent_alias": agent_alias,
            "agent_id": installation.agent_id,
            "profile_id": installation.profile_id,
            "workspace_id": installation.workspace_id,
            "installation_id": installation.id,
            "committed": True,
        })
        if deduped:
            payload["deduped"] = True
        return payload

    async def _finalize_async_event_response(
        self,
        existing_task: Any,
        org_id: str,
        *,
        tool_name: str,
        agent_alias: str | None,
        installation: Any,
        routing_result: Any,
        output_policy: dict,
        user_id: str,
        deduped: bool,
    ) -> dict[str, Any]:
        if existing_task.status == TaskStatus.COMPLETED:
            wait_service = McpTaskWaitService()
            wait_result = await wait_service.build_result_for_task(existing_task)
            return self._merge_wait_result(
                wait_result,
                tool_name=tool_name,
                agent_alias=agent_alias,
                installation=installation,
                deduped=deduped,
            )
        if existing_task.status in {
            TaskStatus.FAILED,
            TaskStatus.TIMEOUT,
            TaskStatus.CANCELLED,
        }:
            wait_service = McpTaskWaitService()
            wait_result = wait_service._build_failed_result(existing_task)
            merged = self._merge_wait_result(
                wait_result,
                tool_name=tool_name,
                agent_alias=agent_alias,
                installation=installation,
                deduped=deduped,
            )
            merged["committed"] = True
            return merged
        return await self._build_async_event_response(
            task=existing_task,
            tool_name=tool_name,
            agent_alias=agent_alias,
            installation=installation,
            routing_result=routing_result,
            output_policy=output_policy,
            org_id=org_id,
            user_id=user_id,
            deduped=deduped,
        )

    @staticmethod
    def _merge_org_mcp_async_payload(
        structured_content: dict[str, Any],
        *,
        tool_name: str,
        agent_alias: str | None,
        installation: Any,
        routing_result: Any,
        deduped: bool,
    ) -> dict[str, Any]:
        payload = dict(structured_content)
        payload.update({
            "tool_name": tool_name,
            "agent_alias": agent_alias,
            "agent_id": installation.agent_id,
            "profile_id": installation.profile_id,
            "workspace_id": installation.workspace_id,
            "installation_id": installation.id,
            "routing_reason": routing_result.reason,
            "retryable": False,
        })
        if deduped:
            payload["deduped"] = True
        return payload

    async def _build_async_event_response(
        self,
        *,
        task: Any,
        tool_name: str,
        agent_alias: str | None,
        installation: Any,
        routing_result: Any,
        output_policy: dict,
        org_id: str,
        user_id: str,
        deduped: bool,
    ) -> dict[str, Any]:
        token_data = await TaskEventTokenService(self.db).create_token(
            task.id,
            user_id,
            org_id,
            ttl_seconds=settings.MCP_TASK_SSE_TOKEN_TTL_SECONDS,
        )
        status = task.status.value
        if status in ("queued", "accepted"):
            status = "running"
        payload: dict[str, Any] = {
            "tool_name": tool_name,
            "agent_alias": agent_alias,
            "agent_id": installation.agent_id,
            "profile_id": installation.profile_id,
            "workspace_id": installation.workspace_id,
            "installation_id": installation.id,
            "task_id": task.id,
            "task_no": task.task_no,
            "status": status,
            "execution_mode": ASYNC_EVENT_MODE,
            "event_stream": token_data["event_url"],
            "event_url": task.event_url,
            "event_token_url": f"/api/v1/hermes/tasks/{task.id}/events-token",
            "artifact_url": task.artifact_url,
            "result_url": f"/api/v1/hermes/tasks/{task.id}/result",
            "artifact_mode": output_policy.get("artifact_mode", "pull_only"),
            "server_artifacts": task.server_artifacts or [],
            "routing_reason": routing_result.reason,
            "wait_strategy": {
                "type": "sse",
                "fallback": "poll",
                "poll_url": f"/api/v1/hermes/tasks/{task.id}",
                "poll_tool": "nodeskclaw_task_wait",
                "result_url": f"/api/v1/hermes/tasks/{task.id}/result",
            },
            "message": "任务已启动，请等待事件流通知完成",
            "retryable": False,
            "committed": True,
        }
        if deduped:
            payload["deduped"] = True
        return payload

    def _build_task_response(
        self,
        *,
        task: Any,
        tool_name: str,
        agent_alias: str | None,
        installation: Any,
        routing_result: Any,
        output_policy: dict,
        deduped: bool,
    ) -> dict[str, Any]:
        payload = {
            "tool_name": tool_name,
            "agent_alias": agent_alias,
            "agent_id": installation.agent_id,
            "profile_id": installation.profile_id,
            "workspace_id": installation.workspace_id,
            "status": task.status.value,
            "task_id": task.id,
            "task_no": task.task_no,
            "event_url": task.event_url,
            "event_token_url": f"/api/v1/hermes/tasks/{task.id}/events-token",
            "artifact_url": task.artifact_url,
            "result_url": f"/api/v1/hermes/tasks/{task.id}/result",
            "artifact_mode": output_policy.get("artifact_mode", "pull_only"),
            "server_artifacts": task.server_artifacts or [],
            "routing_reason": routing_result.reason,
            "installation_id": installation.id,
        }
        if deduped:
            payload["deduped"] = True
        return payload
