"""API v2 Translations — document translation lifecycle."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.deps import get_db, get_member_context
from app.core.exceptions import BadRequestError
from app.schemas.common import ApiResponse
from app.schemas.principal import KnowledgePrincipal
from app.services import translation_service

router = APIRouter(tags=["v2-translations"])


def _require_translation() -> None:
    if not settings.KNOWLEDGE_API_V2_ENABLED or not settings.KNOWLEDGE_TRANSLATION_ENABLED:
        raise BadRequestError(
            message="Translation 未启用",
            message_key="errors.knowledge.translation_disabled",
        )


@router.post("/translations")
async def create_translation(
    body: dict,
    member: KnowledgePrincipal = Depends(get_member_context),
    db: AsyncSession = Depends(get_db),
):
    _require_translation()
    doc = await translation_service.create_translation(
        db,
        member,
        source_file_id=body["source_file_id"],
        file_version_id=body["file_version_id"],
        target_lang=body["target_lang"],
        page_count=int(body.get("page_count") or 1),
    )
    return ApiResponse(
        data={"id": doc.id, "status": doc.status, "target_lang": doc.target_lang}
    )


@router.get("/translations/{document_id}")
async def get_translation(
    document_id: str,
    member: KnowledgePrincipal = Depends(get_member_context),
    db: AsyncSession = Depends(get_db),
):
    _require_translation()
    doc = await translation_service.get_translation(db, member, document_id)
    pages = await translation_service.list_pages(db, document_id)
    return ApiResponse(
        data={
            "id": doc.id,
            "status": doc.status,
            "target_lang": doc.target_lang,
            "pages": [
                {
                    "id": p.id,
                    "page_no": p.page_no,
                    "status": p.status,
                    "current_revision": p.current_revision,
                }
                for p in pages
            ],
        }
    )


@router.post("/translations/pages/{page_id}/revisions")
async def save_translation_revision(
    page_id: str,
    body: dict,
    member: KnowledgePrincipal = Depends(get_member_context),
    db: AsyncSession = Depends(get_db),
):
    _require_translation()
    rev = await translation_service.save_page_revision(
        db,
        member,
        page_id=page_id,
        content=body.get("content") or "",
        expected_revision=int(body.get("expected_revision") or 0),
    )
    return ApiResponse(data={"id": rev.id, "revision": rev.revision, "artifact_uri": rev.artifact_uri})
