import json
import logging
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.base import not_deleted
from app.models.hermes_skill.hermes_agent_instance import HermesAgentInstance
from app.models.hermes_skill.hermes_agent_runtime_state import AgentRuntimeStatus
from app.models.hermes_skill.skill_installation import HermesSkillInstallation
from app.models.instance import Instance
from app.services.hermes_external.hermes_bound_agent_scope_service import HermesBoundAgentScopeService
from app.services.hermes_skill.hermes_agent_runtime_service import HermesAgentRuntimeService

logger = logging.getLogger(__name__)

REASON_MATCHED_BY_ALIAS = "matched_by_agent_alias"
REASON_MATCHED_BY_HERMES_ALIAS = "matched_by_hermes_agent_alias"
REASON_MATCHED_BY_NAME = "matched_by_name"
REASON_MATCHED_BY_SLUG = "matched_by_slug"
REASON_MATCHED_BY_AGENT_ID = "matched_by_agent_id"
REASON_MATCHED_BY_BOUND_PROFILE = "matched_by_bound_profile"


@dataclass
class AliasResolution:
    agent_id: str
    agent_alias: str
    profile_id: str | None
    workspace_id: str | None
    runtime_status: str
    accepting_tasks: bool
    reason: str
    name: str = ""
    description: str = ""
    health: str = "ok"
    profile_name: str | None = None
    container_name: str | None = None
    gateway_url: str | None = None
    task_dispatchable: bool = False

    def to_dict(self) -> dict:
        return {
            "agent_alias": self.agent_alias,
            "agent_id": self.agent_id,
            "instance_id": self.agent_id,
            "name": self.name,
            "employee_name": self.name,
            "description": self.description,
            "profile_id": self.profile_id,
            "workspace_id": self.workspace_id,
            "profile_name": self.profile_name or self.profile_id,
            "container_name": self.container_name,
            "gateway_url": self.gateway_url,
            "runtime_status": self.runtime_status,
            "accepting_tasks": self.accepting_tasks,
            "task_dispatchable": self.task_dispatchable,
            "health": self.health,
            "reason": self.reason,
        }


def _parse_advanced_config(raw: str | dict | None) -> dict:
    if not raw:
        return {}
    if isinstance(raw, dict):
        return raw
    try:
        data = json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        return {}
    return data if isinstance(data, dict) else {}


class AgentAliasResolver:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.runtime_svc = HermesAgentRuntimeService(db)
        self.scope = HermesBoundAgentScopeService(db)

    async def resolve(self, org_id: str, alias: str) -> AliasResolution | None:
        if not alias:
            return None
        instances = await self._list_bound_instances(org_id)
        normalized = alias.strip()
        for reason, matcher in (
            (REASON_MATCHED_BY_ALIAS, self._match_agent_alias),
            (REASON_MATCHED_BY_HERMES_ALIAS, self._match_hermes_agent_alias),
            (REASON_MATCHED_BY_NAME, self._match_name),
            (REASON_MATCHED_BY_SLUG, self._match_slug),
            (REASON_MATCHED_BY_AGENT_ID, self._match_agent_id),
        ):
            for instance in instances:
                if matcher(instance, normalized):
                    return await self._build_resolution(org_id, instance, normalized, reason)

        for record, instance in await self.scope.list_bound_pairs(org_id):
            if record.profile_name == normalized or record.container_name == normalized:
                return await self._build_resolution_from_pair(
                    org_id, record, instance, normalized, REASON_MATCHED_BY_BOUND_PROFILE,
                )
        return None

    async def list_available_agents(
        self,
        org_id: str,
        *,
        dispatchable_only: bool = True,
    ) -> list[AliasResolution]:
        pairs = (
            await self.scope.list_dispatchable_pairs(org_id)
            if dispatchable_only
            else await self.scope.list_bound_pairs(org_id)
        )
        results: list[AliasResolution] = []
        for record, instance in pairs:
            if dispatchable_only and not self.scope.is_dispatchable(record, instance):
                continue
            advanced = _parse_advanced_config(instance.advanced_config)
            alias = (
                advanced.get("agent_alias")
                or advanced.get("hermes_agent_alias")
                or record.profile_name
                or instance.slug
                or instance.name
                or instance.id
            )
            results.append(await self._build_resolution_from_pair(
                org_id, record, instance, str(alias), REASON_MATCHED_BY_BOUND_PROFILE,
            ))
        return results

    async def enrich_routing(
        self,
        org_id: str,
        routing: dict,
        *,
        profile_name: str | None = None,
    ) -> dict:
        enriched = dict(routing or {})
        agent_alias = enriched.pop("agent_alias", None)
        if agent_alias and not enriched.get("agent_id"):
            resolution = await self.resolve(org_id, str(agent_alias))
            if resolution:
                enriched["agent_id"] = resolution.agent_id
                enriched.setdefault("profile_id", resolution.profile_id)
                enriched.setdefault("workspace_id", resolution.workspace_id)
                enriched["agent_alias"] = resolution.agent_alias
        profile = enriched.pop("profile_name", None) or profile_name
        if profile and not enriched.get("profile_id"):
            enriched["profile_id"] = profile
        return enriched

    async def _list_bound_instances(self, org_id: str) -> list[Instance]:
        pairs = await self.scope.list_bound_pairs(org_id)
        return [instance for _record, instance in pairs]

    async def _build_resolution_from_pair(
        self,
        org_id: str,
        record: HermesAgentInstance,
        instance: Instance,
        alias: str,
        reason: str,
    ) -> AliasResolution:
        resolution = await self._build_resolution(org_id, instance, alias, reason)
        resolution.profile_name = record.profile_name
        resolution.container_name = record.container_name
        resolution.gateway_url = record.gateway_url
        resolution.task_dispatchable = self.scope.is_dispatchable(record, instance)
        return resolution

    async def _build_resolution(
        self,
        org_id: str,
        instance: Instance,
        alias: str,
        reason: str,
    ) -> AliasResolution:
        state = await self.runtime_svc.get_or_create_state(org_id, instance.id)
        installation = await self._get_primary_installation(org_id, instance.id)
        health = state.last_health_status or (
            "ok" if state.runtime_status == AgentRuntimeStatus.ENABLED.value else "degraded"
        )
        advanced = _parse_advanced_config(instance.advanced_config)
        resolved_alias = (
            advanced.get("agent_alias")
            or advanced.get("hermes_agent_alias")
            or alias
        )
        return AliasResolution(
            agent_id=instance.id,
            agent_alias=str(resolved_alias),
            profile_id=installation.profile_id if installation else None,
            workspace_id=installation.workspace_id if installation else None,
            runtime_status=state.runtime_status,
            accepting_tasks=state.accepting_tasks,
            reason=reason,
            name=instance.name,
            description=advanced.get("description", "") or "",
            health=health,
        )

    async def _get_primary_installation(
        self, org_id: str, agent_id: str,
    ) -> HermesSkillInstallation | None:
        result = await self.db.execute(
            select(HermesSkillInstallation).where(
                not_deleted(HermesSkillInstallation),
                HermesSkillInstallation.org_id == org_id,
                HermesSkillInstallation.agent_id == agent_id,
                HermesSkillInstallation.status == "installed",
            ).order_by(
                HermesSkillInstallation.is_default.desc(),
                HermesSkillInstallation.priority.desc(),
            ).limit(1)
        )
        return result.scalar_one_or_none()

    @staticmethod
    def _match_agent_alias(instance: Instance, alias: str) -> bool:
        advanced = _parse_advanced_config(instance.advanced_config)
        return str(advanced.get("agent_alias", "")) == alias

    @staticmethod
    def _match_hermes_agent_alias(instance: Instance, alias: str) -> bool:
        advanced = _parse_advanced_config(instance.advanced_config)
        return str(advanced.get("hermes_agent_alias", "")) == alias

    @staticmethod
    def _match_name(instance: Instance, alias: str) -> bool:
        return instance.name == alias

    @staticmethod
    def _match_slug(instance: Instance, alias: str) -> bool:
        return instance.slug == alias

    @staticmethod
    def _match_agent_id(instance: Instance, alias: str) -> bool:
        return instance.id == alias
