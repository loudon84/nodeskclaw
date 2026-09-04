import logging
from typing import Any

from sqlalchemy import exists, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError, BadRequestError, ForbiddenError
from app.models.base import not_deleted
from app.models.connector.edge_node import EdgeNode
from app.models.connector.instance import ConnectorInstance, ConnectorPlacement
from app.models.connector.tool import ConnectorTool
from app.models.hermes_skill.skill import HermesSkill
from app.services.connector.connector_service import ConnectorService
from app.api.internal_edge import is_edge_node_online
from app.models.hermes_skill.skill_installation import HermesSkillInstallation
from app.models.hermes_skill.hermes_task import TaskStatus
from app.models.hermes_skill.skill_release import HermesSkillRelease, SkillReleaseStatus
from app.services.hermes_skill.agent_alias_resolver import AgentAliasResolver
from app.services.hermes_skill.hermes_skill_authorization_service import HermesSkillAuthorizationService
from app.services.hermes_skill.permission_checker import PermissionChecker
from app.services.hermes_skill.skill_routing_service import SkillRoutingService
from app.schemas.hermes_skill.runtime_skill_run import StartRuntimeSkillRunRequest
from app.services.hermes_skill.runtime_skill_run_service import RuntimeSkillRunService
from app.services.hermes_skill.task_service import TaskService
from app.services.hermes_skill.skill_release_service import SkillReleaseService
from app.services.mcp_skill_gateway.mcp_execution_mode import (
    ASYNC_EVENT_MODE,
    WAIT_MODE,
    resolve_mcp_execution_mode,
    strip_mcp_control_args,
)
from app.services.mcp_skill_gateway.mcp_task_dedup_service import McpTaskDedupService
from app.services.mcp_skill_gateway.mcp_task_wait_service import McpTaskWaitService
from app.services.mcp_skill_gateway.output_policy_service import OutputPolicyService
from app.services.expert_gateway.expert_mcp_auth_guard import ExpertMcpAuthGuard
from app.services.hermes_external.hermes_docker_binding_service import HermesDockerBindingService
from app.core.config import settings
from app.services.hermes_skill.task_event_token_service import TaskEventTokenService

logger = logging.getLogger(__name__)

RUNTIME_SKILL_ROUTE_TYPE = "hermes_api_server"
RUNTIME_SKILL_FORBIDDEN_ARGUMENT_KEYS = ("_routing", "_execution", "route_config")


def _runtime_session_and_attachment_refs(client_context: dict | None) -> tuple[str | None, list[str]]:
    ctx = dict(client_context or {})
    session_id = ctx.get("session_id") or ctx.get("run_session_id")
    attachment_refs = list(ctx.get("attachment_refs") or [])
    if isinstance(session_id, str):
        session_id = session_id.strip() or None
    else:
        session_id = None
    return session_id, attachment_refs


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
            exists(
                select(HermesSkillRelease.id).where(
                    not_deleted(HermesSkillRelease),
                    HermesSkillRelease.skill_db_id == HermesSkill.id,
                    HermesSkillRelease.status == SkillReleaseStatus.PUBLISHED.value,
                )
            ),
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

        tools = []
        for skill in skills:
            tools.append(await self._skill_to_tool_dict(skill, org_id, user_id))
        tools.extend(await self._list_public_connector_tools(org_id, keyword=keyword, category=category))
        return tools

    async def _list_public_connector_tools(
        self,
        org_id: str,
        *,
        keyword: str | None = None,
        category: str | None = None,
    ) -> list[dict[str, Any]]:
        query = (
            select(ConnectorTool, ConnectorInstance)
            .join(ConnectorInstance, ConnectorInstance.id == ConnectorTool.instance_id)
            .where(
                not_deleted(ConnectorTool),
                not_deleted(ConnectorInstance),
                ConnectorTool.org_id == org_id,
                ConnectorTool.is_public.is_(True),
                ConnectorInstance.is_active.is_(True),
            )
            .order_by(ConnectorTool.tool_name.asc())
        )
        if keyword:
            query = query.where(
                ConnectorTool.tool_name.ilike(f"%{keyword}%")
                | ConnectorTool.title.ilike(f"%{keyword}%")
                | ConnectorTool.description.ilike(f"%{keyword}%")
            )
        rows = (await self.db.execute(query)).all()
        tools: list[dict[str, Any]] = []
        edge_node_cache: dict[str, Any] = {}
        for connector_tool, instance in rows:
            if instance.placement == ConnectorPlacement.EDGE.value:
                node_id = instance.edge_node_id
                if not node_id:
                    continue
                if node_id not in edge_node_cache:
                    node_result = await self.db.execute(
                        select(EdgeNode).where(
                            not_deleted(EdgeNode),
                            EdgeNode.org_id == org_id,
                            EdgeNode.id == node_id,
                        )
                    )
                    edge_node_cache[node_id] = node_result.scalar_one_or_none()
                node = edge_node_cache[node_id]
                if not node or not is_edge_node_online(node):
                    continue
            meta = dict(connector_tool.extra_metadata or {})
            tool_category = meta.get("category") or "connector"
            if category and tool_category != category:
                continue
            placement = instance.placement or ConnectorPlacement.CENTRAL.value
            raw_ann = meta.get("annotations") if isinstance(meta.get("annotations"), dict) else {}
            requires_approval = bool(
                raw_ann.get("requiresApproval", meta.get("requires_approval") or meta.get("requiresApproval", False))
            )
            annotations = {
                "riskLevel": raw_ann.get("riskLevel") or meta.get("riskLevel") or "low",
                "requiresApproval": requires_approval,
                "approvalMode": raw_ann.get("approvalMode") or meta.get("approval_mode") or ("server" if requires_approval else "none"),
                "streaming": bool(raw_ann.get("streaming", meta.get("streaming", False))),
                "artifacts": bool(raw_ann.get("artifacts", meta.get("artifacts", False))),
            }
            tools.append(
                {
                    "name": connector_tool.tool_name,
                    "title": connector_tool.title or connector_tool.tool_name,
                    "description": connector_tool.description or "",
                    "inputSchema": connector_tool.input_schema or {},
                    "version": meta.get("version"),
                    "category": tool_category,
                    "capabilityKind": "connector",
                    "interactionMode": meta.get("interactionMode") or "form",
                    "supportsAttachments": bool(meta.get("supportsAttachments", False)),
                    "annotations": annotations,
                    "approvalMode": annotations["approvalMode"],
                    "requiresApproval": requires_approval,
                    "authorized": True,
                    "grantStatus": "active",
                    "kind": "connector",
                    "sourceType": "connector",
                    "serverManagedRoute": True,
                    "executionModes": [ASYNC_EVENT_MODE],
                    "defaultExecutionMode": ASYNC_EVENT_MODE,
                    "artifactMode": "pull_only",
                    "resultMode": "pull_on_complete",
                    "routeOverrideAllowed": False,
                    "requiresRouteOverride": False,
                    "forbiddenArgumentKeys": list(RUNTIME_SKILL_FORBIDDEN_ARGUMENT_KEYS),
                }
            )
        return tools

    async def _call_connector_tool(
        self,
        *,
        tool_name: str,
        arguments: dict[str, Any],
        raw_args: dict[str, Any],
        org_id: str,
        user_id: str,
        client_context: dict | None,
        request_trace_id: str | None,
        request_snapshot: dict | None,
    ) -> dict[str, Any]:
        if self._has_explicit_runtime_route_override(raw_args):
            raise BadRequestError(
                "组织级 MCP 不允许覆盖 Connector 路由",
                "errors.connector.route_override_not_allowed",
            )
        bundle = await ConnectorService(self.db).get_public_tool_bundle(org_id, tool_name)
        instance = bundle["instance"]
        definition = bundle["definition"]
        connector_tool = bundle["tool"]
        connector_metadata = dict(connector_tool.extra_metadata or {})
        connector_annotations = dict(connector_metadata.get("annotations") or {})
        connector_config = dict(instance.config or {})
        network_policy = dict(connector_config.get("network_policy") or {})
        server_requires_approval = bool(
            connector_annotations.get("requiresApproval")
            or connector_metadata.get("requires_approval")
            or connector_metadata.get("requiresApproval")
        )
        effective_client_context = dict(client_context or {})
        effective_client_context["requires_approval"] = bool(
            effective_client_context.get("requires_approval") or server_requires_approval
        )
        if instance.placement != ConnectorPlacement.CENTRAL.value:
            if instance.placement == ConnectorPlacement.EDGE.value:
                if not instance.edge_node_id:
                    raise BadRequestError(
                        "Edge Connector 未绑定节点，请联系管理员配置 edge_node_id",
                        "errors.connector.edge_node_required",
                    )
                node_result = await self.db.execute(
                    select(EdgeNode).where(
                        not_deleted(EdgeNode),
                        EdgeNode.org_id == org_id,
                        EdgeNode.id == instance.edge_node_id,
                    )
                )
                node = node_result.scalar_one_or_none()
                if not node or not is_edge_node_online(node):
                    raise BadRequestError(
                        "Edge 离线，请联系管理员",
                        "errors.connector.edge_offline",
                    )
            else:
                raise BadRequestError(
                    "该 Connector placement 不受支持",
                    "errors.connector.invalid_placement",
                )
        request = StartRuntimeSkillRunRequest(
            org_id=org_id,
            user_id=user_id or "",
            tool_name=tool_name,
            runtime_skill_id=tool_name,
            agent_profile="connector",
            hermes_agent_instance_id="connector-central",
            agent_id=None,
            arguments=arguments,
            client_context=effective_client_context,
            output_policy={"artifact_mode": "pull_only"},
            task_source="org_mcp",
            skill_id=tool_name,
            request_trace_id=request_trace_id,
            request_snapshot=request_snapshot,
            execution_mode=ASYNC_EVENT_MODE,
            entrypoint="mcp_skill_gateway",
            catalog_kind="connector",
            catalog_slug=tool_name,
            upstream_tool_name=tool_name,
            extra_route_snapshot={
                "route_type": "connector",
                "connector_kind": definition.kind,
                "connector_tool_name": connector_tool.tool_name,
                "connector_title": connector_tool.title,
                "connector_description": connector_tool.description,
                "connector_config": connector_config,
                "connector_secret_ref_id": instance.secret_ref_id,
                "network_policy": network_policy,
                "connector_binding_refs": [connector_tool.id],
                "knowledge_refs": [],
                "placement": instance.placement,
                "edge_node_id": instance.edge_node_id,
            },
            routing_metadata_extras={
                "connector_tool_id": connector_tool.id,
                "connector_instance_id": instance.id,
                "connector_definition_id": definition.id,
                "routing_reason": "connector_public_tool",
            },
        )
        result = await RuntimeSkillRunService(self.db).start(request)
        return result.structured_content

    async def _skill_to_tool_dict(
        self,
        skill: HermesSkill,
        org_id: str,
        user_id: str,
    ) -> dict[str, Any]:
        published = await SkillReleaseService(self.db).get_published_by_skill_db_id(skill.id)
        release_extra = dict(published.extra_metadata or {}) if published else {}
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

        authorized = True
        grant_status = "active"
        if user_id:
            authz = HermesSkillAuthorizationService(self.db)
            authorized = await authz.can_invoke(org_id, user_id, skill.id, skill.skill_id)
            if not authorized:
                grant_status = "denied"

        input_schema = (published.input_schema if published else skill.input_schema) or {}
        explicit_mode = release_extra.get("interactionMode")
        if explicit_mode in ("chat", "form"):
            interaction_mode = explicit_mode
            prompt_field = release_extra.get("promptField")
        else:
            props = input_schema.get("properties") if isinstance(input_schema, dict) else None
            if isinstance(props, dict) and isinstance(props.get("prompt"), dict) and props.get("prompt", {}).get("type") == "string":
                interaction_mode = "chat"
                prompt_field = "prompt"
            else:
                interaction_mode = "form"
                prompt_field = None

        supports_attachments = bool(release_extra.get("supportsAttachments", False))

        raw_ann = release_extra.get("annotations") if isinstance(release_extra.get("annotations"), dict) else {}
        requires_approval = bool(
            raw_ann.get("requiresApproval", release_extra.get("requires_approval") or release_extra.get("requiresApproval", False))
        )
        annotations = {
            "riskLevel": raw_ann.get("riskLevel") or release_extra.get("riskLevel") or "low",
            "requiresApproval": requires_approval,
            "approvalMode": raw_ann.get("approvalMode") or release_extra.get("approval_mode") or ("server" if requires_approval else "none"),
            "streaming": bool(raw_ann.get("streaming", release_extra.get("streaming", False))),
            "artifacts": bool(raw_ann.get("artifacts", release_extra.get("artifacts", False))),
        }

        tool: dict[str, Any] = {
            "name": skill.tool_name,
            "title": (published.title if published else None) or skill.title or skill.name,
            "description": (published.description if published else None) or skill.description or "",
            "inputSchema": input_schema,
            "version": published.version if published else skill.version,
            "category": (published.category if published else None) or skill.category,
            "capabilityKind": "skill",
            "interactionMode": interaction_mode,
            "supportsAttachments": supports_attachments,
            "annotations": annotations,
            "approvalMode": annotations["approvalMode"],
            "requiresApproval": requires_approval,
            "authorized": authorized,
            "grantStatus": grant_status,
        }
        if prompt_field and interaction_mode == "chat":
            tool["promptField"] = prompt_field

        if published:
            tool["skillReleaseId"] = published.id
            tool["skillReleaseDigest"] = published.digest
        if release_extra.get("ui_schema"):
            tool["uiSchema"] = release_extra["ui_schema"]
        if release_extra.get("examples"):
            tool["examples"] = release_extra["examples"]
        if release_extra.get("primary_artifact_policy"):
            tool["primaryArtifactPolicy"] = release_extra["primary_artifact_policy"]
        if skill.source_type == RUNTIME_SKILL_ROUTE_TYPE:
            tool.update(
                await self._build_runtime_skill_tool_metadata(
                    skill,
                    org_id,
                    installation,
                )
            )
        return tool

    async def _build_runtime_skill_tool_metadata(
        self,
        skill: HermesSkill,
        org_id: str,
        installation: HermesSkillInstallation | None,
    ) -> dict[str, Any]:
        route_meta = {}
        if installation and isinstance(installation.routing_metadata, dict):
            route_meta = installation.routing_metadata
        runtime_profile = route_meta.get("agent_profile") or (
            installation.profile_id if installation else None
        )
        route_health = await self._resolve_runtime_route_health(
            org_id,
            route_meta,
            runtime_profile,
        )
        output_policy = OutputPolicyService.resolve(
            skill=skill,
            installation=installation,
            tool_name=skill.tool_name or "",
        )
        default_mode = resolve_mcp_execution_mode(None, skill, output_policy)
        return {
            "sourceType": RUNTIME_SKILL_ROUTE_TYPE,
            "serverManagedRoute": True,
            "executionModes": [default_mode],
            "defaultExecutionMode": default_mode,
            "sseTimelineEnabled": True,
            "artifactMode": "pull_only",
            "resultMode": "pull_on_complete",
            "routeOverrideAllowed": False,
            "requiresRouteOverride": False,
            "forbiddenArgumentKeys": list(RUNTIME_SKILL_FORBIDDEN_ARGUMENT_KEYS),
            "routeHealth": {"ok": bool(route_health.get("ok"))},
        }

    async def _resolve_runtime_route_health(
        self,
        org_id: str,
        route_meta: dict[str, Any],
        profile_name: str | None,
    ) -> dict[str, bool]:
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
        request_headers: dict[str, str] | None = None,
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
            try:
                return await self._call_connector_tool(
                    tool_name=tool_name,
                    arguments=agent_arguments,
                    raw_args=raw_args,
                    org_id=org_id,
                    user_id=user_id,
                    client_context=client_context,
                    request_trace_id=request_trace_id,
                    request_snapshot=request_snapshot,
                )
            except NotFoundError:
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
        idempotency_key = ExpertMcpAuthGuard.extract_idempotency_key(request_headers)
        employee_runtime_start = (
            skill.source_type == RUNTIME_SKILL_ROUTE_TYPE or settings.SKILL_AGENT_ENABLED
        )
        if fingerprint and not employee_runtime_start:
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
            client_ctx = dict(client_context or {})
            published = await SkillReleaseService(self.db).get_published_by_skill_db_id(skill.id)
            release_extra = (published.extra_metadata if published else None) or (skill.extra_metadata or {})
            if release_extra.get("requires_approval") or release_extra.get("requiresApproval"):
                client_ctx["requires_approval"] = True
            session_id, attachment_refs = _runtime_session_and_attachment_refs(client_context)
            run_request = StartRuntimeSkillRunRequest(
                org_id=org_id,
                user_id=user_id or "",
                tool_name=tool_name,
                runtime_skill_id=str(route_meta.get("runtime_skill_id") or skill.skill_id),
                agent_profile=str(route_meta.get("agent_profile") or installation.profile_id or ""),
                hermes_agent_instance_id=str(route_meta.get("hermes_agent_instance_id") or ""),
                agent_id=installation.agent_id,
                arguments=agent_arguments,
                client_context=client_ctx,
                output_policy=output_policy,
                task_source="org_mcp",
                skill_id=skill.skill_id,
                installation_id=installation.id,
                workspace_id=None,
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
                idempotency_key=idempotency_key,
                session_id=session_id,
                attachment_refs=attachment_refs,
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
        elif settings.SKILL_AGENT_ENABLED:
            client_ctx = dict(client_context or {})
            published = await SkillReleaseService(self.db).get_published_by_skill_db_id(skill.id)
            release_extra = (published.extra_metadata if published else None) or (skill.extra_metadata or {})
            if release_extra.get("requires_approval") or release_extra.get("requiresApproval"):
                client_ctx["requires_approval"] = True
            session_id, attachment_refs = _runtime_session_and_attachment_refs(client_context)
            run_request = StartRuntimeSkillRunRequest(
                org_id=org_id,
                user_id=user_id or "",
                tool_name=tool_name,
                runtime_skill_id=skill.skill_id,
                agent_profile=str(installation.profile_id or ""),
                hermes_agent_instance_id="",
                agent_id=installation.agent_id,
                arguments=agent_arguments,
                client_context=client_ctx,
                output_policy=output_policy,
                task_source="org_mcp",
                skill_id=skill.skill_id,
                installation_id=installation.id,
                workspace_id=None,
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
                idempotency_key=idempotency_key,
                session_id=session_id,
                attachment_refs=attachment_refs,
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

        if settings.SKILL_AGENT_ENABLED and runtime_run_result is not None:
            await self.db.commit()
            return self._merge_org_mcp_async_payload(
                runtime_run_result.structured_content,
                tool_name=tool_name,
                agent_alias=agent_alias,
                installation=installation,
                routing_result=routing_result,
                deduped=False,
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

    _EMPLOYEE_PUBLIC_FORBIDDEN_KEYS = (
        "task_id",
        "task_no",
        "agent_alias",
        "agent_id",
        "profile_id",
        "workspace_id",
        "installation_id",
        "routing_reason",
        "event_token_url",
        "wait_strategy",
        "event_url",
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
        if settings.SKILL_AGENT_ENABLED:
            payload.setdefault("tool_name", tool_name)
            payload["retryable"] = False
            for key in McpToolMapper._EMPLOYEE_PUBLIC_FORBIDDEN_KEYS:
                payload.pop(key, None)
            if deduped:
                payload["deduped"] = True
            return payload
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
        status = task.status.value
        if settings.SKILL_AGENT_ENABLED:
            if status in ("queued", "accepted"):
                status = "QUEUED"
            elif status == "waiting_approval":
                status = "WAITING_APPROVAL"
            payload: dict[str, Any] = {
                "run_id": task.id,
                "status": status,
                "execution_mode": ASYNC_EVENT_MODE,
                "tool_name": tool_name,
                "event_stream": f"/api/v1/runs/{task.id}/events",
                "result_url": f"/api/v1/runs/{task.id}/result",
                "artifact_url": f"/api/v1/runs/{task.id}/artifacts",
                "artifact_mode": output_policy.get("artifact_mode", "pull_only"),
                "server_artifacts": task.server_artifacts or [],
                "message": (
                    "Run waiting approval"
                    if status == "WAITING_APPROVAL"
                    else "Run accepted"
                ),
                "retryable": False,
                "committed": True,
            }
            if deduped:
                payload["deduped"] = True
            return payload

        token_data = await TaskEventTokenService(self.db).create_token(
            task.id,
            user_id,
            org_id,
            ttl_seconds=settings.MCP_TASK_SSE_TOKEN_TTL_SECONDS,
        )
        if status in ("queued", "accepted"):
            status = "running"
        payload = {
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
