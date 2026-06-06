import uuid
from typing import Any

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_db, require_org_admin, require_org_member
from app.core.exceptions import NotFoundError
from app.models.base import not_deleted
from app.models.hermes_skill.skill_collection import HermesSkillCollection, HermesCollectionSkill
from app.schemas.hermes_skill.skill_collection import CollectionCreate, CollectionRead, CollectionListResult
from app.services.hermes_skill.collection_manager import CollectionManager

router = APIRouter()


def _ok(data: Any = None, message: str = "success") -> dict:
    return {"code": 0, "message": message, "data": data}


@router.get("/skill-collections")
async def list_collections(
    page: int = 1,
    page_size: int = 20,
    user_org=Depends(require_org_member),
    db: AsyncSession = Depends(get_db),
):
    _, org = user_org
    query = select(HermesSkillCollection).where(
        not_deleted(HermesSkillCollection),
        HermesSkillCollection.org_id == org.id,
    )
    count_query = select(func.count()).select_from(HermesSkillCollection).where(
        not_deleted(HermesSkillCollection),
        HermesSkillCollection.org_id == org.id,
    )

    total = (await db.execute(count_query)).scalar() or 0
    offset = (page - 1) * page_size
    query = query.order_by(HermesSkillCollection.created_at.desc()).offset(offset).limit(page_size)

    result = await db.execute(query)
    items = [CollectionRead.model_validate(c).model_dump() for c in result.scalars().all()]

    return _ok(CollectionListResult(items=items, total=total, page=page, page_size=page_size).model_dump())


@router.post("/skill-collections")
async def create_collection(
    body: CollectionCreate,
    user_org=Depends(require_org_admin),
    db: AsyncSession = Depends(get_db),
):
    user, org = user_org
    manager = CollectionManager(db)
    collection = await manager.create_collection(
        org_id=org.id,
        collection_id=body.collection_id,
        name=body.name,
        description=body.description or "",
        agent_type=body.agent_type or "",
        created_by=user.id if user else None,
    )
    await db.commit()
    return _ok(CollectionRead.model_validate(collection).model_dump())


@router.post("/skill-collections/{collection_id}/install")
async def install_collection(
    collection_id: str,
    agent_ids: list[str],
    install_mode: str = "docker_mount",
    conflict_strategy: str = "install_as_new_version",
    user_org=Depends(require_org_admin),
    db: AsyncSession = Depends(get_db),
):
    user, org = user_org
    manager = CollectionManager(db)
    result = await manager.batch_install(
        collection_id=collection_id,
        agent_ids=agent_ids,
        org_id=org.id,
        install_mode=install_mode,
        conflict_strategy=conflict_strategy,
        installed_by=user.id if user else None,
    )
    await db.commit()
    return _ok(result)


@router.post("/skill-collections/{collection_id}/export")
async def export_collection(
    collection_id: str,
    user_org=Depends(require_org_admin),
    db: AsyncSession = Depends(get_db),
):
    _, org = user_org
    manager = CollectionManager(db)
    manifest = await manager.export_manifest(collection_id, org.id)
    return _ok({"manifest": manifest})


@router.delete("/skill-collections/{collection_id}")
async def delete_collection(
    collection_id: str,
    user_org=Depends(require_org_admin),
    db: AsyncSession = Depends(get_db),
):
    _, org = user_org
    manager = CollectionManager(db)
    await manager.delete_collection(collection_id, org.id)
    await db.commit()
    return _ok()
