"""Knowledge Model JSON CRUD."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError
from app.models.base import not_deleted
from app.models.knowledge_model import KnowledgeModel
from app.schemas.principal import KnowledgePrincipal


async def create_model(
    db: AsyncSession,
    member: KnowledgePrincipal,
    *,
    name: str,
    description: str | None = None,
    entities: list | None = None,
    relations: list | None = None,
    terms: list | None = None,
    extraction_policy: dict | None = None,
) -> KnowledgeModel:
    row = KnowledgeModel(
        org_id=member.org_id,
        name=name,
        description=description,
        entities=entities or [],
        relations=relations or [],
        terms=terms or [],
        extraction_policy=extraction_policy or {},
        created_by_member_id=member.member_id,
    )
    db.add(row)
    await db.commit()
    await db.refresh(row)
    return row


async def get_model(db: AsyncSession, member: KnowledgePrincipal, model_id: str) -> KnowledgeModel:
    row = await db.get(KnowledgeModel, model_id)
    if row is None or row.deleted_at is not None or row.org_id != member.org_id:
        raise NotFoundError(message="知识模型不存在", message_key="errors.knowledge.model_not_found")
    return row


async def update_model(
    db: AsyncSession,
    member: KnowledgePrincipal,
    model_id: str,
    *,
    name: str | None = None,
    description: str | None = None,
    entities: list | None = None,
    relations: list | None = None,
    terms: list | None = None,
    extraction_policy: dict | None = None,
) -> KnowledgeModel:
    row = await get_model(db, member, model_id)
    if name is not None:
        row.name = name
    if description is not None:
        row.description = description
    if entities is not None:
        row.entities = entities
    if relations is not None:
        row.relations = relations
    if terms is not None:
        row.terms = terms
    if extraction_policy is not None:
        row.extraction_policy = extraction_policy
    row.version = int(row.version or 1) + 1
    await db.commit()
    await db.refresh(row)
    return row


async def list_models(db: AsyncSession, member: KnowledgePrincipal) -> list[KnowledgeModel]:
    rows = await db.scalars(
        select(KnowledgeModel)
        .where(KnowledgeModel.org_id == member.org_id, not_deleted(KnowledgeModel))
        .order_by(KnowledgeModel.updated_at.desc())
    )
    return list(rows.all())
