from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from sqlalchemy import and_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import BadRequestError, NotFoundError
from app.models.base import not_deleted
from app.models.expert import Expert
from app.models.expert_skill import ExpertSkill
from app.schemas.expert_skill import ExpertSkillItem, ExpertSkillSyncResult, ExpertSkillUpdateBody
from app.services.expert_gateway.expert_catalog_service import ExpertCatalogService
from app.services.expert_gateway.expert_mcp_proxy_service import ExpertMcpProxyService


class ExpertSkillService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.catalog = ExpertCatalogService(db)

    async def list_skills(self, org_id: str, expert_id: str) -> list[ExpertSkillItem]:
        stmt = (
            select(ExpertSkill)
            .where(
                ExpertSkill.org_id == org_id,
                ExpertSkill.expert_id == expert_id,
                not_deleted(ExpertSkill),
            )
            .order_by(ExpertSkill.sort_order.asc(), ExpertSkill.created_at.asc())
        )
        rows = (await self.db.execute(stmt)).scalars().all()
        return [self._to_item(row) for row in rows]

    async def list_public_skills(self, org_id: str, expert_id: str) -> list[ExpertSkill]:
        stmt = (
            select(ExpertSkill)
            .where(
                ExpertSkill.org_id == org_id,
                ExpertSkill.expert_id == expert_id,
                ExpertSkill.is_public.is_(True),
                not_deleted(ExpertSkill),
            )
            .order_by(ExpertSkill.sort_order.asc(), ExpertSkill.created_at.asc())
        )
        return list((await self.db.execute(stmt)).scalars().all())

    async def get_skill_by_name(self, org_id: str, expert_id: str, skill_name: str) -> ExpertSkill | None:
        stmt = select(ExpertSkill).where(
            ExpertSkill.org_id == org_id,
            ExpertSkill.expert_id == expert_id,
            ExpertSkill.skill_name == skill_name,
            not_deleted(ExpertSkill),
        )
        return (await self.db.execute(stmt)).scalar_one_or_none()

    async def update_skill(
        self,
        org_id: str,
        user_id: str,
        skill_id: str,
        body: ExpertSkillUpdateBody,
    ) -> ExpertSkillItem:
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
        now = datetime.now(timezone.utc)
        stmt = (
            update(ExpertSkill)
            .where(
                ExpertSkill.org_id == org_id,
                ExpertSkill.id == skill_id,
                not_deleted(ExpertSkill),
            )
            .values(
                skill_name=skill.skill_name,
                display_name=skill.display_name,
                description=skill.description,
                is_public=skill.is_public,
                call_enabled=skill.call_enabled,
                risk_level=skill.risk_level,
                approval_mode=skill.approval_mode,
                output_formats=skill.output_formats,
                sort_order=skill.sort_order,
                updated_by=user_id,
                updated_at=now,
            )
            .returning(ExpertSkill)
        )
        row = (await self.db.execute(stmt)).scalar_one()
        return self._to_item(row)

    async def set_visibility(
        self,
        org_id: str,
        user_id: str,
        skill_id: str,
        enabled: bool,
    ) -> ExpertSkillItem:
        return await self.update_skill(
            org_id,
            user_id,
            skill_id,
            ExpertSkillUpdateBody(public=enabled, call_enabled=enabled),
        )

    async def sync_tools(
        self,
        org_id: str,
        user_id: str,
        expert_id: str,
    ) -> ExpertSkillSyncResult:
        expert = await self.catalog.get_by_id(org_id, expert_id)
        if expert is None:
            raise NotFoundError(message="专家不存在", message_key="errors.expert.not_found")
        agent_profile = await self.catalog.resolve_agent_profile(org_id, expert)
        upstream_tools = await ExpertMcpProxyService.list_upstream_tools(
            self.db, org_id, user_id, agent_profile,
        )
        existing_stmt = select(ExpertSkill).where(
            ExpertSkill.org_id == org_id,
            ExpertSkill.expert_id == expert_id,
            not_deleted(ExpertSkill),
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
                while await self.get_skill_by_name(org_id, expert_id, skill_name):
                    suffix += 1
                    skill_name = f"{base_name}-{suffix}"
                row = ExpertSkill(
                    org_id=org_id,
                    expert_id=expert_id,
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

    async def _get_skill(self, org_id: str, skill_id: str) -> ExpertSkill:
        stmt = select(ExpertSkill).where(
            ExpertSkill.org_id == org_id,
            ExpertSkill.id == skill_id,
            not_deleted(ExpertSkill),
        )
        row = (await self.db.execute(stmt)).scalar_one_or_none()
        if row is None:
            raise NotFoundError(message="专家能力不存在", message_key="errors.expert.skill_not_found")
        return row

    @staticmethod
    def _apply_flag_rules(
        skill: ExpertSkill,
        public: bool | None,
        call_enabled: bool | None,
    ) -> None:
        if public is False:
            skill.is_public = False
            skill.call_enabled = False
        elif call_enabled is True:
            skill.is_public = True
            skill.call_enabled = True
        elif not skill.is_public:
            skill.call_enabled = False

    @staticmethod
    def _to_item(row: ExpertSkill) -> ExpertSkillItem:
        return ExpertSkillItem(
            id=row.id,
            org_id=row.org_id,
            expert_id=row.expert_id,
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
    def build_tool_descriptor(expert: Expert, skill: ExpertSkill, *, runtime_ready: bool) -> dict[str, Any]:
        return {
            "name": skill.skill_name,
            "description": skill.description or skill.display_name or skill.skill_name,
            "inputSchema": skill.input_schema or {"type": "object", "properties": {}},
            "annotations": {
                "kind": "expert_skill",
                "slug": expert.expert_slug,
                "displayName": skill.display_name or skill.skill_name,
                "public": skill.is_public,
                "callEnabled": skill.call_enabled,
                "riskLevel": skill.risk_level,
                "approvalMode": skill.approval_mode,
                "outputFormats": list(skill.output_formats or []),
                "status": "ready" if runtime_ready else "offline",
                "callMode": "async_sse",
                "streaming": True,
                "eventStream": {
                    "transport": "sse",
                    "authMode": "bearer_or_sse_token",
                    "resume": True,
                },
                "artifactMode": "pull_only",
                "resultMode": "task_result",
            },
        }
