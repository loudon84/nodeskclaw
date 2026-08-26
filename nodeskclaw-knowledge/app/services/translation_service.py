"""Translation service — Document→Page→Revision with optimistic lock."""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.exceptions import BadRequestError, ConflictError, ForbiddenError, NotFoundError
from app.models.base import not_deleted
from app.models.translation import TranslationDocument, TranslationJob, TranslationPage, TranslationRevision
from app.schemas.principal import KnowledgePrincipal
from app.services import artifact_store, source_file_service
from app.workers.job_leasing import claim_next, clear_lease_if_owner


async def create_translation(
    db: AsyncSession,
    member: KnowledgePrincipal,
    *,
    source_file_id: str,
    file_version_id: str,
    target_lang: str,
    page_count: int = 1,
) -> TranslationDocument:
    if not settings.KNOWLEDGE_TRANSLATION_ENABLED:
        raise BadRequestError(
            message="Translation 未启用",
            message_key="errors.knowledge.translation_disabled",
        )
    sf = await source_file_service.get_source_file(db, member, source_file_id)
    if sf.org_id != member.org_id:
        raise ForbiddenError()
    doc = TranslationDocument(
        org_id=member.org_id,
        source_file_id=source_file_id,
        file_version_id=file_version_id,
        target_lang=target_lang,
        status="pending",
        created_by_member_id=member.member_id,
    )
    db.add(doc)
    await db.flush()
    for page_no in range(1, max(page_count, 1) + 1):
        page = TranslationPage(document_id=doc.id, page_no=page_no, status="pending")
        db.add(page)
        await db.flush()
        db.add(
            TranslationJob(
                org_id=member.org_id,
                document_id=doc.id,
                page_id=page.id,
                status="queued",
            )
        )
    await db.commit()
    await db.refresh(doc)
    return doc


async def get_translation(
    db: AsyncSession, member: KnowledgePrincipal, document_id: str
) -> TranslationDocument:
    doc = await db.get(TranslationDocument, document_id)
    if doc is None or doc.deleted_at is not None or doc.org_id != member.org_id:
        raise NotFoundError(message="译文不存在", message_key="errors.knowledge.translation_not_found")
    return doc


async def save_page_revision(
    db: AsyncSession,
    member: KnowledgePrincipal,
    *,
    page_id: str,
    content: str,
    expected_revision: int,
) -> TranslationRevision:
    page = await db.get(TranslationPage, page_id)
    if page is None or page.deleted_at is not None:
        raise NotFoundError(message="译文页不存在", message_key="errors.knowledge.translation_page_not_found")
    doc = await get_translation(db, member, page.document_id)
    if page.current_revision != expected_revision:
        raise ConflictError(
            message="译文页版本冲突",
            message_key="errors.knowledge.translation_revision_conflict",
        )
    new_rev = int(page.current_revision) + 1
    relative = f"translations/{doc.id}/{page.id}/r{new_rev}.txt"
    uri = artifact_store.write_bytes(relative, content.encode("utf-8"))
    revision = TranslationRevision(
        page_id=page.id,
        revision=new_rev,
        content=content,
        artifact_uri=uri,
        created_by_member_id=member.member_id,
    )
    db.add(revision)
    page.current_revision = new_rev
    page.artifact_uri = uri
    page.status = "completed"
    await db.commit()
    await db.refresh(revision)
    return revision


async def claim_next_translation_job(db: AsyncSession, *, lease_owner: str):
    if not settings.KNOWLEDGE_TRANSLATION_ENABLED:
        return None
    claimed = await claim_next(
        db,
        TranslationJob,
        statuses=["queued"],
        lease_owner=lease_owner,
        lease_seconds=120,
        commit=True,
    )
    if claimed is None:
        return None
    job, token = claimed
    job.status = "running"
    job.attempt_count = int(job.attempt_count or 0) + 1
    await db.commit()
    await db.refresh(job)
    return job, token


async def process_translation_job(db: AsyncSession, job: TranslationJob) -> None:
    """Placeholder stage: mark page partial/completed without replacing Source Version."""
    if not job.page_id:
        job.status = "failed"
        job.error_message = "missing_page"
        job.finished_at = datetime.now(UTC)
        return
    page = await db.get(TranslationPage, job.page_id)
    if page is None:
        job.status = "failed"
        job.error_message = "page_missing"
        job.finished_at = datetime.now(UTC)
        return
    page.status = "partial"
    job.status = "completed"
    job.finished_at = datetime.now(UTC)
    await db.flush()


async def finalize_translation_job(
    db: AsyncSession, job: TranslationJob, *, lease_owner: str, lease_token: str
) -> bool:
    return await clear_lease_if_owner(
        db,
        TranslationJob,
        job_id=job.id,
        lease_owner=lease_owner,
        lease_token=lease_token,
        values={
            "status": job.status,
            "error_message": job.error_message,
            "finished_at": job.finished_at,
            "attempt_count": job.attempt_count,
        },
    )


async def list_pages(db: AsyncSession, document_id: str) -> list[TranslationPage]:
    rows = await db.scalars(
        select(TranslationPage)
        .where(TranslationPage.document_id == document_id, not_deleted(TranslationPage))
        .order_by(TranslationPage.page_no.asc())
    )
    return list(rows.all())
