from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import BadRequestError, NotFoundError
from app.models.base import not_deleted
from app.models.expert_team import ExpertTeam
from app.models.expert_team_skill import ExpertTeamSkill
from app.models.hermes_skill.hermes_agent_instance import HermesAgentInstance
from app.schemas.expert_skill import ExpertSkillSyncResult
from app.schemas.expert_team_skill import ExpertTeamSkillItem, ExpertTeamSkillUpdateBody
from app.services.expert_gateway.expert_catalog_service import ExpertCatalogService
from app.services.expert_gateway.expert_mcp_proxy_service import ExpertMcpProxyService


class ExpertTeamSkillService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def _get_team(self, org_id: str, team_id: str) -> ExpertTeam:
        stmt = select(ExpertTeam).where(
            ExpertTeam.org_id == org_id,
            ExpertTeam.id == team_id,
            not_deleted(ExpertTeam),
        )
        team = (await self.db.execute(stmt)).scalar_one_or_none()
        if team is None:
            raise NotFoundError(message="专家团队不存在", message_key="errors.expert.team_not_found")
        return team

    async def list_skills(self, org_id: str, team_id: str) -> list[ExpertTeamSkillItem]:
        stmt = (
            select(ExpertTeamSkill)
            .where(
                ExpertTeamSkill.org_id == org_id,
                ExpertTeamSkill.expert_team_id == team_id,
                not_deleted(ExpertTeamSkill),
            )
            .order_by(ExpertTeamSkill.sort_order.asc(), ExpertTeamSkill.created_at.asc())
        )
        rows = (await self.db.execute(stmt)).scalars().all()
        return [self._to_item(row) for row in rows]

    async def list_public_skills(self, org_id: str, team_id: str) -> list[ExpertTeamSkill]:
        stmt = (
            select(ExpertTeamSkill)
            .where(
                ExpertTeamSkill.org_id == org_id,
                ExpertTeamSkill.expert_team_id == team_id,
                ExpertTeamSkill.is_public.is_(True),
                not_deleted(ExpertTeamSkill),
            )
            .order_by(ExpertTeamSkill.sort_order.asc(), ExpertTeamSkill.created_at.asc())
        )
        return list((await self.db.execute(stmt)).scalars().all())

    async def get_skill_by_name(self, org_id: str, team_id: str, skill_name: str) -> ExpertTeamSkill | None:
        stmt = select(ExpertTeamSkill).where(
            ExpertTeamSkill.org_id == org_id,
            ExpertTeamSkill.expert_team_id == team_id,
            ExpertTeamSkill.skill_name == skill_name,
            not_deleted(ExpertTeamSkill),
        )
        return (await self.db.execute(stmt)).scalar_one_or_none()

    async def update_skill(
        self,
        org_id: str,
        user_id: str,
        skill_id: str,
        body: ExpertTeamSkillUpdateBody,
    ) -> ExpertTeamSkillItem:
        skill = await self._get_skill(org_id, skill_id)
        if body.skill_name is not None:
            skill.skill_name = body.skill_name.strip()
        if body.display_name is not None:
            skill.display_name = body.display_name
        if body.description is not None:
            skill.description = body.description
        if body.public is not None:
            skill.is_public = body.public
        if body.call_enabled is not None:
            skill.call_enabled = body.call_enabled
        if body.risk_level is not None:
            skill.risk_level = body.risk_level
        if body.approval_mode is not None:
            skill.approval_mode = body.approval_mode
        if body.output_formats is not None:
            skill.output_formats = body.output_formats
        if body.sort_order is not None:
            skill.sort_order = body.sort_order
        self._apply_flag_rules(skill, body.public, body.call_enabled)
        skill.updated_by = user_id
        await self.db.flush()
        return self._to_item(skill)

    async def sync_tools(self, org_id: str, user_id: str, team_id: str) -> ExpertSkillSyncResult:
        team = await self._get_team(org_id, team_id)
        if not team.hermes_agent_id:
            raise BadRequestError(
                message="请先绑定 Hermes Agent",
                message_key="errors.expert.team_agent_required",
            )
        agent_profile = await self._resolve_agent_profile(org_id, team)
        upstream_tools = await ExpertMcpProxyService.list_upstream_tools(
            self.db, org_id, user_id, agent_profile,
        )
        existing_stmt = select(ExpertTeamSkill).where(
            ExpertTeamSkill.org_id == org_id,
            ExpertTeamSkill.expert_team_id == team_id,
            not_deleted(ExpertTeamSkill),
        )
        existing_rows = list((await self.db.execute(existing_stmt)).scalars().all())
        by_upstream = {row.upstream_tool_name: row for row in existing_rows}
        seen_upstream: set[str] = set()
        created = 0
        updated = 0
        now = datetime.now(timezone.utc)

        for tool in upstream_tools:
            if not isinstance(tool, dict):
                continue
            upstream_name = str(tool.get("name") or "").strip()
            if not upstream_name:
                continue
            seen_upstream.add(upstream_name)
            row = by_upstream.get(upstream_name)
            description = str(tool.get("description") or "")
            input_schema = tool.get("inputSchema") if isinstance(tool.get("inputSchema"), dict) else {}
            if row is None:
                skill_name = ExpertCatalogService.default_skill_name_from_upstream(upstream_name)
                base_name = skill_name
                suffix = 1
                while await self.get_skill_by_name(org_id, team_id, skill_name):
                    suffix += 1
                    skill_name = f"{base_name}-{suffix}"
                row = ExpertTeamSkill(
                    org_id=org_id,
                    expert_team_id=team_id,
                    skill_name=skill_name,
                    upstream_tool_name=upstream_name,
                    display_name=skill_name,
                    description=description,
                    input_schema=input_schema,
                    created_by=user_id,
                    updated_by=user_id,
                    last_synced_at=now,
                )
                self.db.add(row)
                created += 1
            else:
                row.description = description or row.description
                row.input_schema = input_schema
                row.stale = False
                row.last_synced_at = now
                row.updated_by = user_id
                updated += 1

        stale = 0
        for row in existing_rows:
            if row.upstream_tool_name not in seen_upstream:
                row.stale = True
                row.last_synced_at = now
                stale += 1

        await self.db.flush()
        return ExpertSkillSyncResult(
            created=created,
            updated=updated,
            stale=stale,
            total_upstream=len(seen_upstream),
        )

    async def count_public_skills(self, org_id: str, team_id: str) -> int:
        stmt = select(func.count()).select_from(ExpertTeamSkill).where(
            ExpertTeamSkill.org_id == org_id,
            ExpertTeamSkill.expert_team_id == team_id,
            ExpertTeamSkill.is_public.is_(True),
            not_deleted(ExpertTeamSkill),
        )
        return int((await self.db.execute(stmt)).scalar_one())

    async def count_callable_skills(self, org_id: str, team_id: str) -> int:
        stmt = select(func.count()).select_from(ExpertTeamSkill).where(
            ExpertTeamSkill.org_id == org_id,
            ExpertTeamSkill.expert_team_id == team_id,
            ExpertTeamSkill.is_public.is_(True),
            ExpertTeamSkill.call_enabled.is_(True),
            not_deleted(ExpertTeamSkill),
        )
        return int((await self.db.execute(stmt)).scalar_one())

    async def _get_skill(self, org_id: str, skill_id: str) -> ExpertTeamSkill:
        stmt = select(ExpertTeamSkill).where(
            ExpertTeamSkill.org_id == org_id,
            ExpertTeamSkill.id == skill_id,
            not_deleted(ExpertTeamSkill),
        )
        row = (await self.db.execute(stmt)).scalar_one_or_none()
        if row is None:
            raise NotFoundError(message="团队能力不存在", message_key="errors.expert.team_skill_not_found")
        return row

    async def _resolve_agent_profile(self, org_id: str, team: ExpertTeam) -> str:
        stmt = select(HermesAgentInstance).where(
            HermesAgentInstance.org_id == org_id,
            HermesAgentInstance.id == team.hermes_agent_id,
            not_deleted(HermesAgentInstance),
        )
        agent = (await self.db.execute(stmt)).scalar_one_or_none()
        if agent is None:
            raise NotFoundError(
                message="Hermes Agent 实例不存在",
                message_key="errors.hermes.agent_instance_not_found",
            )
        return agent.profile_name

    @staticmethod
    def _apply_flag_rules(
        skill: ExpertTeamSkill,
        public: bool | None,
        call_enabled: bool | None,
    ) -> None:
        if public is False:
            skill.call_enabled = False
        elif call_enabled is True:
            skill.is_public = True
        elif not skill.is_public:
            skill.call_enabled = False

    @staticmethod
    def _to_item(row: ExpertTeamSkill) -> ExpertTeamSkillItem:
        return ExpertTeamSkillItem(
            id=row.id,
            org_id=row.org_id,
            expert_team_id=row.expert_team_id,
            skill_name=row.skill_name,
            upstream_tool_name=row.upstream_tool_name,
            display_name=row.display_name,
            description=row.description,
            input_schema=dict(row.input_schema or {}),
            public=row.is_public,
            call_enabled=row.call_enabled,
            risk_level=row.risk_level,
            approval_mode=row.approval_mode,
            output_formats=list(row.output_formats or []),
            sort_order=row.sort_order,
            stale=row.stale,
            last_synced_at=row.last_synced_at,
            created_at=row.created_at,
            updated_at=row.updated_at,
        )

    @staticmethod
    def build_tool_descriptor(
        team: ExpertTeam,
        skill: ExpertTeamSkill,
        *,
        runtime_ready: bool,
        orchestration_mode: str,
    ) -> dict[str, Any]:
        return {
            "name": skill.skill_name,
            "description": skill.description or skill.display_name or skill.skill_name,
            "inputSchema": skill.input_schema or {"type": "object", "properties": {}},
            "annotations": {
                "kind": "expert_team_skill",
                "slug": team.team_slug,
                "displayName": skill.display_name or skill.skill_name,
                "public": skill.is_public,
                "callEnabled": skill.call_enabled,
                "riskLevel": skill.risk_level,
                "approvalMode": skill.approval_mode,
                "outputFormats": list(skill.output_formats or []),
                "orchestrationMode": orchestration_mode,
                "status": "ready" if runtime_ready else "offline",
            },
        }
