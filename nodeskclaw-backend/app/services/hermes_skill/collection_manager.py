import logging
import uuid

import yaml
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError, ForbiddenError, BadRequestError
from app.models.base import not_deleted
from app.models.hermes_skill.skill import HermesSkill
from app.models.hermes_skill.skill_collection import HermesSkillCollection, HermesCollectionSkill
from app.models.hermes_skill.skill_installation import HermesSkillInstallation
from app.schemas.hermes_skill.common import InstallMode
from app.services.hermes_skill.skill_installer import SkillInstaller

logger = logging.getLogger(__name__)


class CollectionManager:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.installer = SkillInstaller(db)

    async def create_collection(
        self,
        org_id: str,
        collection_id: str,
        name: str,
        description: str = "",
        agent_type: str = "",
        version: str = "1.0.0",
        is_read_only: bool = False,
        created_by: str | None = None,
    ) -> HermesSkillCollection:
        collection = HermesSkillCollection(
            id=str(uuid.uuid4()),
            org_id=org_id,
            collection_id=collection_id,
            name=name,
            description=description,
            agent_type=agent_type,
            version=version,
            is_read_only=is_read_only,
            created_by=created_by,
        )
        self.db.add(collection)
        await self.db.flush()
        return collection

    async def get_collection(self, collection_id: str, org_id: str) -> HermesSkillCollection | None:
        result = await self.db.execute(
            select(HermesSkillCollection).where(
                not_deleted(HermesSkillCollection),
                HermesSkillCollection.id == collection_id,
                HermesSkillCollection.org_id == org_id,
            )
        )
        return result.scalar_one_or_none()

    async def add_skill(
        self,
        collection_id: str,
        skill_id: str,
        org_id: str,
        version_constraint: str | None = None,
        sort_order: int = 0,
        is_required: bool = True,
    ) -> HermesCollectionSkill:
        collection = await self.get_collection(collection_id, org_id)
        if not collection:
            raise NotFoundError("集合不存在", "errors.skill.collection_not_found")
        if collection.is_read_only:
            raise ForbiddenError("只读集合不允许修改", "errors.skill.collection_read_only")

        link = HermesCollectionSkill(
            id=str(uuid.uuid4()),
            org_id=org_id,
            collection_id=collection_id,
            skill_id=skill_id,
            version_constraint=version_constraint,
            sort_order=sort_order,
            is_required=is_required,
        )
        self.db.add(link)
        await self.db.flush()
        return link

    async def remove_skill(self, collection_id: str, skill_id: str, org_id: str) -> None:
        collection = await self.get_collection(collection_id, org_id)
        if not collection:
            raise NotFoundError("集合不存在", "errors.skill.collection_not_found")
        if collection.is_read_only:
            raise ForbiddenError("只读集合不允许修改", "errors.skill.collection_read_only")

        result = await self.db.execute(
            select(HermesCollectionSkill).where(
                not_deleted(HermesCollectionSkill),
                HermesCollectionSkill.collection_id == collection_id,
                HermesCollectionSkill.skill_id == skill_id,
            )
        )
        link = result.scalar_one_or_none()
        if link:
            link.soft_delete()
            await self.db.flush()

    async def batch_install(
        self,
        collection_id: str,
        agent_ids: list[str],
        org_id: str,
        install_mode: str = InstallMode.DOCKER_MOUNT,
        conflict_strategy: str = "install_as_new_version",
        installed_by: str | None = None,
    ) -> dict:
        collection = await self.get_collection(collection_id, org_id)
        if not collection:
            raise NotFoundError("集合不存在", "errors.skill.collection_not_found")

        result = await self.db.execute(
            select(HermesCollectionSkill).where(
                not_deleted(HermesCollectionSkill),
                HermesCollectionSkill.collection_id == collection_id,
            ).order_by(HermesCollectionSkill.sort_order)
        )
        skill_links = result.scalars().all()

        results: dict[str, list] = {"success": [], "failed": [], "skipped": [], "partial_failed": []}
        has_required_failure = False

        for agent_id in agent_ids:
            for link in skill_links:
                try:
                    installation = await self.installer.install(
                        skill_id=link.skill_id,
                        agent_id=agent_id,
                        org_id=org_id,
                        install_mode=install_mode,
                        conflict_strategy=conflict_strategy,
                        installed_by=installed_by,
                    )
                    results["success"].append({
                        "skill_id": link.skill_id,
                        "agent_id": agent_id,
                        "installation_id": installation.id,
                    })
                except Exception as exc:
                    entry = {
                        "skill_id": link.skill_id,
                        "agent_id": agent_id,
                        "error": str(exc),
                    }
                    if link.is_required:
                        has_required_failure = True
                        results["failed"].append(entry)
                    else:
                        results["partial_failed"].append(entry)

        if has_required_failure:
            results["status"] = "partial_failed"
        else:
            results["status"] = "completed"

        return results

    async def export_manifest(self, collection_id: str, org_id: str) -> str:
        collection = await self.get_collection(collection_id, org_id)
        if not collection:
            raise NotFoundError("集合不存在", "errors.skill.collection_not_found")

        result = await self.db.execute(
            select(HermesCollectionSkill).where(
                not_deleted(HermesCollectionSkill),
                HermesCollectionSkill.collection_id == collection_id,
            ).order_by(HermesCollectionSkill.sort_order)
        )

        manifest = {
            "collection_id": collection.collection_id,
            "name": collection.name,
            "description": collection.description,
            "agent_type": collection.agent_type,
            "version": collection.version,
            "skills": [
                {
                    "skill_id": link.skill_id,
                    "version": link.version_constraint,
                    "required": link.is_required,
                }
                for link in result.scalars().all()
            ],
        }
        return yaml.dump(manifest, allow_unicode=True, default_flow_style=False)

    async def delete_collection(self, collection_id: str, org_id: str) -> None:
        collection = await self.get_collection(collection_id, org_id)
        if not collection:
            raise NotFoundError("集合不存在", "errors.skill.collection_not_found")
        collection.soft_delete()
        await self.db.flush()
