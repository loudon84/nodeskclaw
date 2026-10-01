from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.base import not_deleted
from app.models.connector.binding import SkillConnectorBinding
from app.models.connector.definition import ConnectorDefinition
from app.models.connector.instance import ConnectorInstance
from app.models.connector.tool import ConnectorTool
from app.models.expert_skill import ExpertSkill
from app.models.hermes_skill.skill import HermesSkill
from app.models.hermes_skill.skill_release import HermesSkillRelease
from app.services.remote_agent_provider_service import RemoteAgentRouteError

_ALLOWED_KINDS = frozenset({"rest", "mcp", "db"})
_DESCRIPTOR_KEYS = (
    "binding_id",
    "connector_instance_id",
    "connector_kind",
    "placement",
    "skill_release_id",
)


def binding_not_found() -> RemoteAgentRouteError:
    return RemoteAgentRouteError(
        "CONNECTOR_BINDING_NOT_FOUND",
        404,
        40403,
        "errors.remote_agent.binding_not_found",
        "连接器绑定不存在",
    )


def binding_disabled() -> RemoteAgentRouteError:
    return RemoteAgentRouteError(
        "CONNECTOR_BINDING_DISABLED",
        409,
        40906,
        "errors.remote_agent.binding_disabled",
        "连接器实例未启用",
    )


def binding_placement_unsupported() -> RemoteAgentRouteError:
    return RemoteAgentRouteError(
        "CONNECTOR_BINDING_PLACEMENT_UNSUPPORTED",
        409,
        40907,
        "errors.remote_agent.binding_placement_unsupported",
        "远程专家只接受中心连接器",
    )


def binding_scope_denied() -> RemoteAgentRouteError:
    return RemoteAgentRouteError(
        "CONNECTOR_SCOPE_DENIED",
        403,
        40302,
        "errors.remote_agent.binding_scope_denied",
        "连接器绑定不属于当前专家的已发布技能",
    )


def classify_binding_row(
    *,
    caller_org_id: str,
    binding_org_id: str | None,
    binding_deleted: bool,
    instance_present: bool,
    instance_deleted: bool,
    instance_active: bool,
    placement: str | None,
    kind: str | None,
    release_status: str | None,
    skill_tool_name: str | None,
    expert_public_tool_names: set[str],
    binding_id: str,
    connector_instance_id: str | None,
    skill_release_id: str | None,
) -> dict[str, str] | RemoteAgentRouteError:
    if (
        binding_org_id is None
        or binding_deleted
        or binding_org_id != caller_org_id
        or not instance_present
        or instance_deleted
    ):
        return binding_not_found()
    if not instance_active:
        return binding_disabled()
    if placement != "central":
        return binding_placement_unsupported()
    tool_name = (skill_tool_name or "").strip()
    if (
        kind not in _ALLOWED_KINDS
        or release_status != "published"
        or not tool_name
        or tool_name not in expert_public_tool_names
    ):
        return binding_scope_denied()
    return {
        "binding_id": binding_id,
        "connector_instance_id": connector_instance_id or "",
        "connector_kind": kind,
        "placement": "central",
        "skill_release_id": skill_release_id or "",
    }


def descriptor_field_names() -> tuple[str, ...]:
    return _DESCRIPTOR_KEYS


async def expert_public_tool_names(db: AsyncSession, *, org_id: str, expert_id: str) -> set[str]:
    result = await db.execute(
        select(ExpertSkill.upstream_tool_name).where(
            not_deleted(ExpertSkill),
            ExpertSkill.org_id == org_id,
            ExpertSkill.expert_id == expert_id,
            ExpertSkill.is_public.is_(True),
        )
    )
    return {str(name).strip() for name in result.scalars().all() if str(name or "").strip()}


async def authorize_connector_bindings(
    db: AsyncSession,
    *,
    org_id: str,
    expert_id: str,
    binding_ids: list[str],
) -> list[dict[str, str]]:
    public_names = await expert_public_tool_names(db, org_id=org_id, expert_id=expert_id)
    descriptors: list[dict[str, str]] = []
    for binding_id in binding_ids:
        result = await db.execute(
            select(SkillConnectorBinding, ConnectorInstance, ConnectorDefinition, HermesSkillRelease, HermesSkill)
            .join(ConnectorInstance, ConnectorInstance.id == SkillConnectorBinding.connector_instance_id)
            .join(ConnectorDefinition, ConnectorDefinition.id == ConnectorInstance.definition_id)
            .join(HermesSkillRelease, HermesSkillRelease.id == SkillConnectorBinding.skill_release_id)
            .join(HermesSkill, HermesSkill.id == HermesSkillRelease.skill_db_id)
            .where(SkillConnectorBinding.id == binding_id)
        )
        row = result.first()
        if row is None:
            raise binding_not_found()
        binding, instance, definition, release, skill = row
        outcome = classify_binding_row(
            caller_org_id=org_id,
            binding_org_id=binding.org_id,
            binding_deleted=binding.deleted_at is not None,
            instance_present=instance is not None,
            instance_deleted=instance.deleted_at is not None,
            instance_active=bool(instance.is_active),
            placement=instance.placement,
            kind=definition.kind,
            release_status=release.status if release.deleted_at is None else None,
            skill_tool_name=None if skill.deleted_at is not None else skill.tool_name,
            expert_public_tool_names=public_names,
            binding_id=binding.id,
            connector_instance_id=instance.id,
            skill_release_id=release.id,
        )
        if isinstance(outcome, RemoteAgentRouteError):
            raise outcome
        descriptors.append(outcome)
    return descriptors


async def list_public_connector_tools(
    db: AsyncSession,
    *,
    org_id: str,
    binding_ids: list[str],
) -> list[dict[str, Any]]:
    if not binding_ids:
        return []
    result = await db.execute(
        select(
            ConnectorTool.tool_name,
            ConnectorTool.description,
            ConnectorTool.input_schema,
            SkillConnectorBinding.id,
            ConnectorInstance.id,
            ConnectorDefinition.kind,
            ConnectorInstance.placement,
            SkillConnectorBinding.skill_release_id,
        )
        .join(ConnectorInstance, ConnectorInstance.id == ConnectorTool.instance_id)
        .join(ConnectorDefinition, ConnectorDefinition.id == ConnectorInstance.definition_id)
        .join(
            SkillConnectorBinding,
            SkillConnectorBinding.connector_instance_id == ConnectorInstance.id,
        )
        .where(
            not_deleted(ConnectorTool),
            not_deleted(ConnectorInstance),
            not_deleted(ConnectorDefinition),
            not_deleted(SkillConnectorBinding),
            SkillConnectorBinding.org_id == org_id,
            ConnectorInstance.org_id == org_id,
            ConnectorTool.org_id == org_id,
            SkillConnectorBinding.id.in_(binding_ids),
            ConnectorInstance.is_active.is_(True),
            ConnectorInstance.placement == "central",
            ConnectorTool.is_public.is_(True),
            ConnectorDefinition.kind.in_(tuple(_ALLOWED_KINDS)),
        )
    )
    tools: list[dict[str, Any]] = []
    for row in result.all():
        tools.append(
            {
                "tool_name": row[0],
                "description": row[1] or "",
                "input_schema": row[2] or {"type": "object"},
                "binding_id": row[3],
                "connector_instance_id": row[4],
                "connector_kind": row[5],
                "placement": row[6],
                "skill_release_id": row[7],
                "mode": "REQUIRE_APPROVAL",
            }
        )
    return tools


async def resolve_connector_call_route(
    db: AsyncSession,
    *,
    org_id: str,
    binding_ids: list[str],
    tool_name: str,
) -> dict[str, Any] | None:
    tools = await list_public_connector_tools(db, org_id=org_id, binding_ids=binding_ids)
    match = next((tool for tool in tools if tool["tool_name"] == tool_name), None)
    if match is None:
        return None
    result = await db.execute(
        select(ConnectorInstance.config, ConnectorInstance.secret_ref_id, ConnectorDefinition.kind)
        .join(ConnectorDefinition, ConnectorDefinition.id == ConnectorInstance.definition_id)
        .where(
            not_deleted(ConnectorInstance),
            ConnectorInstance.id == match["connector_instance_id"],
            ConnectorInstance.org_id == org_id,
            ConnectorInstance.is_active.is_(True),
            ConnectorInstance.placement == "central",
        )
    )
    row = result.first()
    if row is None:
        return None
    return {
        "connector_kind": row[2],
        "connector_config": dict(row[0] or {}),
        "connector_secret_ref_id": row[1],
        "tool_name": tool_name,
        "binding_id": match["binding_id"],
    }
