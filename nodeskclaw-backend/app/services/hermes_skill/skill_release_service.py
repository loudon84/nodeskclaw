from __future__ import annotations

import hashlib
import json
import logging
import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import BadRequestError, ConflictError, NotFoundError
from app.models.base import not_deleted
from app.models.connector.binding import SkillConnectorBinding
from app.models.connector.instance import ConnectorInstance
from app.models.hermes_skill.skill import HermesSkill
from app.models.hermes_skill.skill_release import HermesSkillRelease, SkillReleaseStatus

logger = logging.getLogger(__name__)


def compute_skill_content_digest(skill: HermesSkill) -> str:
    payload = {
        "skill_id": skill.skill_id,
        "tool_name": skill.tool_name,
        "name": skill.name,
        "title": skill.title,
        "description": skill.description,
        "version": skill.version,
        "category": skill.category,
        "input_schema": skill.input_schema,
        "output_schema": skill.output_schema,
        "output_policy": skill.output_policy,
        "extra_metadata": skill.extra_metadata,
        "tags": skill.tags,
    }
    raw = json.dumps(payload, sort_keys=True, ensure_ascii=False, default=str)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def snapshot_hash(*, skill_release_id: str, digest: str, route_snapshot: dict[str, Any]) -> str:
    raw = json.dumps(
        {
            "skill_release_id": skill_release_id,
            "digest": digest,
            "route_type": route_snapshot.get("route_type"),
            "runtime_skill_id": route_snapshot.get("runtime_skill_id"),
            "agent_profile": route_snapshot.get("agent_profile"),
            "connector_kind": route_snapshot.get("connector_kind"),
            "connector_tool_name": route_snapshot.get("connector_tool_name"),
            "placement": route_snapshot.get("placement"),
        },
        sort_keys=True,
        ensure_ascii=False,
        default=str,
    )
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


class SkillReleaseService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_skill(self, org_id: str, skill_id: str) -> HermesSkill:
        result = await self.db.execute(
            select(HermesSkill).where(
                not_deleted(HermesSkill),
                HermesSkill.org_id == org_id,
                HermesSkill.skill_id == skill_id,
            )
        )
        skill = result.scalar_one_or_none()
        if not skill:
            raise NotFoundError("Skill 不存在", "errors.skill.not_found")
        return skill

    async def get_published(self, org_id: str, skill_id: str) -> HermesSkillRelease | None:
        result = await self.db.execute(
            select(HermesSkillRelease).where(
                not_deleted(HermesSkillRelease),
                HermesSkillRelease.org_id == org_id,
                HermesSkillRelease.skill_id == skill_id,
                HermesSkillRelease.status == SkillReleaseStatus.PUBLISHED.value,
            )
        )
        return result.scalar_one_or_none()

    async def get_published_by_skill_db_id(self, skill_db_id: str) -> HermesSkillRelease | None:
        result = await self.db.execute(
            select(HermesSkillRelease).where(
                not_deleted(HermesSkillRelease),
                HermesSkillRelease.skill_db_id == skill_db_id,
                HermesSkillRelease.status == SkillReleaseStatus.PUBLISHED.value,
            )
        )
        return result.scalar_one_or_none()

    async def list_releases(self, org_id: str, skill_id: str) -> list[HermesSkillRelease]:
        skill = await self.get_skill(org_id, skill_id)
        result = await self.db.execute(
            select(HermesSkillRelease)
            .where(
                not_deleted(HermesSkillRelease),
                HermesSkillRelease.org_id == org_id,
                HermesSkillRelease.skill_db_id == skill.id,
            )
            .order_by(HermesSkillRelease.created_at.desc())
        )
        return list(result.scalars().all())

    async def create_draft_from_skill(
        self,
        *,
        org_id: str,
        skill_id: str,
        operator_user_id: str,
        notes: str | None = None,
        version: str | None = None,
        connector_instance_ids: list[str] | None = None,
        knowledge_refs: list[str] | None = None,
    ) -> HermesSkillRelease:
        skill = await self.get_skill(org_id, skill_id)
        release_version = (version or skill.version or "1.0.0").strip()
        if not release_version:
            raise BadRequestError("Release version 不能为空", "errors.skill.release_version_required")

        existing = await self.db.execute(
            select(HermesSkillRelease).where(
                not_deleted(HermesSkillRelease),
                HermesSkillRelease.skill_db_id == skill.id,
                HermesSkillRelease.version == release_version,
            )
        )
        if existing.scalar_one_or_none():
            raise ConflictError(
                f"Release version 已存在: {release_version}",
                "errors.skill.release_version_conflict",
                message_params={"version": release_version},
            )

        digest = compute_skill_content_digest(skill)
        release = HermesSkillRelease(
            id=str(uuid.uuid4()),
            org_id=org_id,
            skill_db_id=skill.id,
            skill_id=skill.skill_id,
            tool_name=skill.tool_name,
            version=release_version,
            status=SkillReleaseStatus.DRAFT.value,
            digest=digest,
            title=skill.title,
            description=skill.description,
            category=skill.category,
            input_schema=skill.input_schema,
            output_schema=skill.output_schema,
            output_policy=skill.output_policy,
            extra_metadata=dict(skill.extra_metadata or {}),
            payload={
                "name": skill.name,
                "tags": skill.tags,
                "source_type": skill.source_type,
                "source_ref": skill.source_ref,
            },
            requirements={
                "connector_binding_ids": [],
                "knowledge_refs": [str(ref).strip() for ref in (knowledge_refs or []) if str(ref).strip()],
            },
            created_by=operator_user_id,
            notes=notes,
        )
        self.db.add(release)
        await self.db.flush()
        if connector_instance_ids:
            binding_ids: list[str] = []
            for connector_instance_id in connector_instance_ids:
                instance_id = str(connector_instance_id).strip()
                if not instance_id:
                    continue
                instance_result = await self.db.execute(
                    select(ConnectorInstance).where(
                        not_deleted(ConnectorInstance),
                        ConnectorInstance.org_id == org_id,
                        ConnectorInstance.id == instance_id,
                    )
                )
                instance = instance_result.scalar_one_or_none()
                if not instance:
                    raise NotFoundError("Connector 实例不存在", "errors.connector.instance_not_found")
                binding = SkillConnectorBinding(
                    org_id=org_id,
                    skill_release_id=release.id,
                    connector_instance_id=instance.id,
                )
                self.db.add(binding)
                await self.db.flush()
                binding_ids.append(binding.id)
            release.requirements = {
                **dict(release.requirements or {}),
                "connector_binding_ids": binding_ids,
            }
        return release

    async def publish(self, *, org_id: str, skill_id: str, release_id: str, operator_user_id: str) -> HermesSkillRelease:
        skill = await self.get_skill(org_id, skill_id)
        release = await self._get_release(org_id, skill.id, release_id)
        if release.status == SkillReleaseStatus.PUBLISHED.value:
            return release
        if release.status not in (SkillReleaseStatus.DRAFT.value, SkillReleaseStatus.DEPRECATED.value):
            raise BadRequestError(
                f"当前状态不可发布: {release.status}",
                "errors.skill.release_invalid_status",
                message_params={"status": release.status},
            )

        current = await self.get_published_by_skill_db_id(skill.id)
        now = datetime.now(timezone.utc)
        if current and current.id != release.id:
            current.status = SkillReleaseStatus.DEPRECATED.value
            current.deprecated_at = now

        release.status = SkillReleaseStatus.PUBLISHED.value
        release.published_at = now
        release.published_by = operator_user_id
        release.deprecated_at = None
        await self.db.flush()
        return release

    async def deprecate(self, *, org_id: str, skill_id: str, release_id: str) -> HermesSkillRelease:
        skill = await self.get_skill(org_id, skill_id)
        release = await self._get_release(org_id, skill.id, release_id)
        if release.status == SkillReleaseStatus.DEPRECATED.value:
            return release
        if release.status != SkillReleaseStatus.PUBLISHED.value:
            raise BadRequestError(
                f"仅 published Release 可废弃: {release.status}",
                "errors.skill.release_invalid_status",
                message_params={"status": release.status},
            )
        release.status = SkillReleaseStatus.DEPRECATED.value
        release.deprecated_at = datetime.now(timezone.utc)
        await self.db.flush()
        return release

    async def ensure_draft_on_register(
        self,
        *,
        org_id: str,
        skill: HermesSkill,
        operator_user_id: str,
    ) -> HermesSkillRelease | None:
        version = (skill.version or "1.0.0").strip()
        existing = await self.db.execute(
            select(HermesSkillRelease).where(
                not_deleted(HermesSkillRelease),
                HermesSkillRelease.skill_db_id == skill.id,
                HermesSkillRelease.version == version,
            )
        )
        if existing.scalar_one_or_none():
            return None
        return await self.create_draft_from_skill(
            org_id=org_id,
            skill_id=skill.skill_id,
            operator_user_id=operator_user_id,
            notes="auto draft from register-to-org-mcp",
            version=version,
        )

    async def _get_release(self, org_id: str, skill_db_id: str, release_id: str) -> HermesSkillRelease:
        result = await self.db.execute(
            select(HermesSkillRelease).where(
                not_deleted(HermesSkillRelease),
                HermesSkillRelease.org_id == org_id,
                HermesSkillRelease.skill_db_id == skill_db_id,
                HermesSkillRelease.id == release_id,
            )
        )
        release = result.scalar_one_or_none()
        if not release:
            raise NotFoundError("SkillRelease 不存在", "errors.skill.release_not_found")
        return release
