"""Knowledge Model JSON CRUD with immutable revision support."""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.exceptions import NotFoundError
from app.models.base import not_deleted
from app.models.knowledge_model import KnowledgeModel
from app.models.knowledge_model_revision import KnowledgeModelRevision
from app.schemas.principal import KnowledgePrincipal


def _content_hash(
    *,
    entities: list | None,
    relations: list | None,
    terms: list | None,
    extraction_policy: dict | None,
) -> str:
    payload = {
        "entities": entities or [],
        "relations": relations or [],
        "terms": terms or [],
        "extraction_policy": extraction_policy or {},
    }
    raw = json.dumps(payload, ensure_ascii=False, sort_keys=True).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def _sync_model_from_revision(model: KnowledgeModel, revision: KnowledgeModelRevision) -> None:
    model.entities = revision.entities or []
    model.relations = revision.relations or []
    model.terms = revision.terms or []
    model.extraction_policy = revision.extraction_policy or {}
    model.version = int(revision.revision_number)
    model.active_revision_id = revision.id


async def _next_revision_number(db: AsyncSession, model_id: str) -> int:
    current = await db.scalar(
        select(func.max(KnowledgeModelRevision.revision_number)).where(
            KnowledgeModelRevision.knowledge_model_id == model_id,
            not_deleted(KnowledgeModelRevision),
        )
    )
    return int(current or 0) + 1


async def _create_revision(
    db: AsyncSession,
    member: KnowledgePrincipal,
    model: KnowledgeModel,
    *,
    status: str,
    entities: list | None,
    relations: list | None,
    terms: list | None,
    extraction_policy: dict | None,
    publish: bool = False,
) -> KnowledgeModelRevision:
    revision_number = await _next_revision_number(db, model.id)
    entities_val = entities or []
    relations_val = relations or []
    terms_val = terms or []
    policy_val = extraction_policy or {}
    revision = KnowledgeModelRevision(
        org_id=model.org_id,
        knowledge_model_id=model.id,
        revision_number=revision_number,
        status=status,
        content_hash=_content_hash(
            entities=entities_val,
            relations=relations_val,
            terms=terms_val,
            extraction_policy=policy_val,
        ),
        entities=entities_val,
        relations=relations_val,
        terms=terms_val,
        extraction_policy=policy_val,
        created_by_member_id=member.member_id,
        published_at=datetime.now(UTC) if publish else None,
    )
    db.add(revision)
    await db.flush()
    return revision


async def get_active_revision(
    db: AsyncSession,
    model: KnowledgeModel,
) -> KnowledgeModelRevision | None:
    if not model.active_revision_id:
        return None
    revision = await db.get(KnowledgeModelRevision, model.active_revision_id)
    if revision is None or revision.deleted_at is not None:
        return None
    return revision


async def get_revision(
    db: AsyncSession,
    member: KnowledgePrincipal,
    model_id: str,
    revision_id: str,
) -> KnowledgeModelRevision:
    await get_model(db, member, model_id)
    revision = await db.get(KnowledgeModelRevision, revision_id)
    if (
        revision is None
        or revision.deleted_at is not None
        or revision.org_id != member.org_id
        or revision.knowledge_model_id != model_id
    ):
        raise NotFoundError(
            message="知识模型版本不存在",
            message_key="errors.knowledge.model_revision_not_found",
        )
    return revision


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
    await db.flush()
    if settings.KNOWLEDGE_V23_MODEL_REVISION_ENABLED:
        revision = await _create_revision(
            db,
            member,
            row,
            status="active",
            entities=entities,
            relations=relations,
            terms=terms,
            extraction_policy=extraction_policy,
            publish=True,
        )
        _sync_model_from_revision(row, revision)
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

    if settings.KNOWLEDGE_V23_MODEL_REVISION_ENABLED:
        active = await get_active_revision(db, row)
        next_entities = entities if entities is not None else (active.entities if active else row.entities)
        next_relations = relations if relations is not None else (active.relations if active else row.relations)
        next_terms = terms if terms is not None else (active.terms if active else row.terms)
        next_policy = (
            extraction_policy
            if extraction_policy is not None
            else (active.extraction_policy if active else row.extraction_policy)
        )
        revision = await _create_revision(
            db,
            member,
            row,
            status="draft",
            entities=next_entities,
            relations=next_relations,
            terms=next_terms,
            extraction_policy=next_policy,
        )
        await db.commit()
        await db.refresh(row)
        await db.refresh(revision)
        return row

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


async def publish_revision(
    db: AsyncSession,
    member: KnowledgePrincipal,
    model_id: str,
    revision_id: str,
) -> KnowledgeModel:
    row = await get_model(db, member, model_id)
    revision = await get_revision(db, member, model_id, revision_id)
    if revision.status == "active":
        return row
    active_rows = await db.scalars(
        select(KnowledgeModelRevision).where(
            KnowledgeModelRevision.knowledge_model_id == model_id,
            KnowledgeModelRevision.org_id == member.org_id,
            KnowledgeModelRevision.status == "active",
            not_deleted(KnowledgeModelRevision),
        )
    )
    for old in active_rows.all():
        if old.id != revision_id:
            old.status = "archived"
    revision.status = "active"
    revision.published_at = datetime.now(UTC)
    _sync_model_from_revision(row, revision)
    await db.commit()
    await db.refresh(row)
    return row


async def list_revisions(
    db: AsyncSession,
    member: KnowledgePrincipal,
    model_id: str,
) -> list[KnowledgeModelRevision]:
    await get_model(db, member, model_id)
    rows = await db.scalars(
        select(KnowledgeModelRevision)
        .where(
            KnowledgeModelRevision.knowledge_model_id == model_id,
            KnowledgeModelRevision.org_id == member.org_id,
            not_deleted(KnowledgeModelRevision),
        )
        .order_by(KnowledgeModelRevision.revision_number.desc())
    )
    return list(rows.all())


async def list_models(db: AsyncSession, member: KnowledgePrincipal) -> list[KnowledgeModel]:
    rows = await db.scalars(
        select(KnowledgeModel)
        .where(KnowledgeModel.org_id == member.org_id, not_deleted(KnowledgeModel))
        .order_by(KnowledgeModel.updated_at.desc())
    )
    return list(rows.all())


def model_to_dict(row: KnowledgeModel, *, revision: KnowledgeModelRevision | None = None) -> dict:
    payload = revision or row
    return {
        "id": row.id,
        "name": row.name,
        "description": row.description,
        "version": row.version,
        "active_revision_id": row.active_revision_id,
        "entities": getattr(payload, "entities", row.entities) or [],
        "relations": getattr(payload, "relations", row.relations) or [],
        "terms": getattr(payload, "terms", row.terms) or [],
        "extraction_policy": getattr(payload, "extraction_policy", row.extraction_policy) or {},
    }


async def ensure_revision_backfill(db: AsyncSession, model: KnowledgeModel, member_id: str) -> None:
    if model.active_revision_id or not settings.KNOWLEDGE_V23_MODEL_REVISION_ENABLED:
        return
    revision = await _create_revision(
        db,
        member=KnowledgePrincipal(
            user_id=member_id,
            member_id=member_id,
            org_id=model.org_id,
            name="system",
        ),
        model=model,
        status="active",
        entities=model.entities,
        relations=model.relations,
        terms=model.terms,
        extraction_policy=model.extraction_policy,
        publish=True,
    )
    _sync_model_from_revision(model, revision)


async def get_model_for_compile(db: AsyncSession, model_id: str) -> KnowledgeModel | None:
    model = await db.get(KnowledgeModel, model_id)
    if model is None or model.deleted_at is not None:
        return None
    if settings.KNOWLEDGE_V23_MODEL_REVISION_ENABLED and model.active_revision_id:
        revision = await get_active_revision(db, model)
        if revision is not None:
            model.entities = revision.entities or []
            model.relations = revision.relations or []
            model.terms = revision.terms or []
            model.extraction_policy = revision.extraction_policy or {}
    return model
