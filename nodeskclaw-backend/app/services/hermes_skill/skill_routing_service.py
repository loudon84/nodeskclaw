import logging
from dataclasses import dataclass
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import BadRequestError, NotFoundError
from app.models.base import not_deleted
from app.models.hermes_skill.skill import HermesSkill
from app.models.hermes_skill.skill_installation import HermesSkillInstallation

logger = logging.getLogger(__name__)

ROUTING_REASON_EXPLICIT_FULL = "matched_by_explicit_routing"
ROUTING_REASON_EXPLICIT_AGENT = "matched_by_explicit_agent"
ROUTING_REASON_WORKSPACE = "matched_by_workspace"
ROUTING_REASON_DEFAULT = "matched_by_default_installation"
ROUTING_REASON_PRIORITY = "matched_by_priority"
ROUTING_REASON_LATEST = "matched_by_latest_installation"
ROUTING_REASON_SINGLE = "matched_single_installation"


@dataclass
class RoutingResult:
    matched: bool
    installation: HermesSkillInstallation | None
    skill: HermesSkill | None
    reason: str
    installation_id: str | None = None
    skill_id: str | None = None
    agent_id: str | None = None
    profile_id: str | None = None
    workspace_id: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "matched": self.matched,
            "installation_id": self.installation_id,
            "skill_id": self.skill_id,
            "agent_id": self.agent_id,
            "profile_id": self.profile_id,
            "workspace_id": self.workspace_id,
            "reason": self.reason,
        }


class SkillRoutingService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def resolve_by_tool_name(
        self,
        tool_name: str,
        org_id: str,
        routing: dict | None = None,
        user_workspace_id: str | None = None,
        allow_explicit_routing: bool = True,
    ) -> RoutingResult:
        skill = await self._get_skill_by_tool_name(tool_name, org_id)
        if not skill:
            raise NotFoundError(f"MCP Tool {tool_name} 不存在", "errors.skill.tool_not_found")

        installations = await self._list_installed(skill.skill_id, org_id)
        if not installations:
            raise NotFoundError(
                f"Skill {tool_name} 未安装到任何 Agent",
                "errors.skill.installation_not_found",
            )

        routing = routing or {}
        if routing and not allow_explicit_routing:
            routing = {}

        return self._select_installation(skill, installations, routing, user_workspace_id)

    async def resolve_test(
        self,
        tool_name: str,
        org_id: str,
        routing: dict | None = None,
        workspace_id: str | None = None,
    ) -> RoutingResult:
        try:
            result = await self.resolve_by_tool_name(
                tool_name=tool_name,
                org_id=org_id,
                routing=routing,
                user_workspace_id=workspace_id,
            )
            return result
        except (NotFoundError, BadRequestError) as exc:
            return RoutingResult(
                matched=False,
                installation=None,
                skill=None,
                reason=exc.message_key or "routing_failed",
            )

    async def _get_skill_by_tool_name(self, tool_name: str, org_id: str) -> HermesSkill | None:
        result = await self.db.execute(
            select(HermesSkill).where(
                not_deleted(HermesSkill),
                HermesSkill.org_id == org_id,
                HermesSkill.tool_name == tool_name,
                HermesSkill.is_mcp_exposed.is_(True),
                HermesSkill.is_active.is_(True),
            )
        )
        return result.scalar_one_or_none()

    async def _list_installed(self, skill_id: str, org_id: str) -> list[HermesSkillInstallation]:
        result = await self.db.execute(
            select(HermesSkillInstallation).where(
                not_deleted(HermesSkillInstallation),
                HermesSkillInstallation.skill_id == skill_id,
                HermesSkillInstallation.org_id == org_id,
                HermesSkillInstallation.status == "installed",
            ).order_by(HermesSkillInstallation.created_at.desc())
        )
        return list(result.scalars().all())

    def _select_installation(
        self,
        skill: HermesSkill,
        installations: list[HermesSkillInstallation],
        routing: dict,
        user_workspace_id: str | None,
    ) -> RoutingResult:
        if len(installations) == 1 and not routing and not user_workspace_id:
            inst = installations[0]
            return self._result(skill, inst, ROUTING_REASON_SINGLE)

        agent_id = routing.get("agent_id")
        profile_id = routing.get("profile_id")
        workspace_id = routing.get("workspace_id") or user_workspace_id

        if agent_id and profile_id and workspace_id:
            matches = [
                i for i in installations
                if i.agent_id == agent_id
                and (i.profile_id or "") == profile_id
                and (i.workspace_id or "") == workspace_id
            ]
            if len(matches) == 1:
                return self._result(skill, matches[0], ROUTING_REASON_EXPLICIT_FULL)
            if len(matches) > 1:
                raise BadRequestError(
                    "多个 installation 匹配显式路由参数",
                    "errors.skill.installation_ambiguous",
                )
            raise NotFoundError(
                "未找到匹配的 installation",
                "errors.skill.installation_not_found",
            )

        if agent_id:
            matches = [i for i in installations if i.agent_id == agent_id]
            if profile_id:
                matches = [i for i in matches if (i.profile_id or "") == profile_id]
            if workspace_id:
                matches = [i for i in matches if (i.workspace_id or "") == workspace_id]
            if len(matches) == 1:
                return self._result(skill, matches[0], ROUTING_REASON_EXPLICIT_AGENT)
            if len(matches) > 1:
                raise BadRequestError(
                    "多个 installation 匹配 agent_id",
                    "errors.skill.installation_ambiguous",
                )
            raise NotFoundError(
                "未找到匹配 agent_id 的 installation",
                "errors.skill.installation_not_found",
            )

        if workspace_id:
            matches = [i for i in installations if (i.workspace_id or "") == workspace_id]
            if len(matches) == 1:
                return self._result(skill, matches[0], ROUTING_REASON_WORKSPACE)
            if len(matches) > 1:
                pass
            elif len(matches) == 0:
                pass
            else:
                return self._result(skill, matches[0], ROUTING_REASON_WORKSPACE)

        defaults = [i for i in installations if getattr(i, "is_default", False)]
        if len(defaults) == 1:
            return self._result(skill, defaults[0], ROUTING_REASON_DEFAULT)
        if len(defaults) > 1:
            raise BadRequestError(
                "多个 default installation 冲突",
                "errors.skill.installation_ambiguous",
            )

        if len(installations) > 1:
            by_priority = sorted(
                installations,
                key=lambda i: (getattr(i, "priority", 0) or 0, i.created_at or ""),
                reverse=True,
            )
            top_priority = getattr(by_priority[0], "priority", 0) or 0
            top_matches = [
                i for i in by_priority
                if (getattr(i, "priority", 0) or 0) == top_priority
            ]
            if len(top_matches) == 1:
                return self._result(skill, top_matches[0], ROUTING_REASON_PRIORITY)
            if top_priority > 0 and len(top_matches) > 1:
                raise BadRequestError(
                    "多个 installation 具有相同最高 priority",
                    "errors.skill.installation_ambiguous",
                )

        if workspace_id:
            ws_matches = [i for i in installations if (i.workspace_id or "") == workspace_id]
            if len(ws_matches) == 1:
                return self._result(skill, ws_matches[0], ROUTING_REASON_WORKSPACE)

        if len(installations) == 1:
            return self._result(skill, installations[0], ROUTING_REASON_LATEST)

        raise BadRequestError(
            "无法确定目标 installation，请通过 _routing 显式指定",
            "errors.skill.installation_ambiguous",
        )

    def _result(
        self,
        skill: HermesSkill,
        installation: HermesSkillInstallation,
        reason: str,
    ) -> RoutingResult:
        return RoutingResult(
            matched=True,
            installation=installation,
            skill=skill,
            reason=reason,
            installation_id=installation.id,
            skill_id=skill.skill_id,
            agent_id=installation.agent_id,
            profile_id=installation.profile_id,
            workspace_id=installation.workspace_id,
        )

    @staticmethod
    def extract_routing(arguments: dict) -> tuple[dict, dict]:
        args = dict(arguments or {})
        routing = args.pop("_routing", None)
        if routing is not None and not isinstance(routing, dict):
            raise BadRequestError(
                "_routing 必须是对象",
                "errors.skill.input_schema_validation_failed",
            )
        return args, routing or {}
