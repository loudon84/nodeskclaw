"""SourceFile Chunk Thin Gateway — permission, resolve, forward, normalize, audit."""

from __future__ import annotations

import hashlib
import logging
import time
import uuid
from dataclasses import dataclass
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.integrations.ragflow.exceptions import RagflowError
from app.models.enums import AuditAction
from app.models.source_file_version import SourceFileVersion
from app.runtime.ragflow import RagflowRuntimeAdapter
from app.schemas.knowledge import (
    SourceFileChunkAvailabilityResult,
    SourceFileChunkOut,
    SourceFileChunkPageOut,
)
from app.schemas.principal import KnowledgePrincipal
from app.services import chunk_errors, knowledge_base_service, runtime_binding_service, source_file_service
from app.services.audit_service import write_audit
from app.services.source_lifecycle_service import _require_update_or_manage

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class RuntimeDocumentRef:
    source_file_id: str
    file_version_id: str
    dataset_id: str
    document_id: str


@dataclass(frozen=True)
class SourceFileChunkImage:
    content: bytes
    content_type: str


def _chunk_id_digest(chunk_id: str) -> str:
    return hashlib.sha256(chunk_id.encode("utf-8")).hexdigest()[:12]


def _provider_image_token(raw: dict[str, Any]) -> str | None:
    for key in ("image_id", "img_id"):
        value = raw.get(key)
        if value is None:
            continue
        text = str(value).strip()
        if text:
            return text
    return None


def _normalize_chunk(raw: dict[str, Any]) -> SourceFileChunkOut:
    available = raw.get("available")
    if available is not None and not isinstance(available, bool):
        available = None
    keywords = raw.get("important_keywords") or raw.get("keywords") or []
    if not isinstance(keywords, list):
        keywords = []
    questions = raw.get("questions") or []
    if not isinstance(questions, list):
        questions = []
    positions = raw.get("positions")
    if positions is not None and not isinstance(positions, list):
        positions = None
    content = raw.get("content")
    if content is None:
        content = ""
    return SourceFileChunkOut(
        id=str(raw.get("id") or ""),
        content=str(content),
        available=available if isinstance(available, bool) else None,
        has_image=_provider_image_token(raw) is not None,
        positions=positions,
        important_keywords=[str(x) for x in keywords],
        questions=[str(x) for x in questions],
    )


async def resolve_active_runtime_document(
    db: AsyncSession,
    member: KnowledgePrincipal,
    source_file_id: str,
) -> RuntimeDocumentRef:
    sf = await source_file_service.get_source_file(db, member, source_file_id)
    if not sf.active_version_id:
        raise chunk_errors.chunk_no_active_version()
    version = await db.get(SourceFileVersion, sf.active_version_id)
    if version is None or version.deleted_at is not None or version.source_file_id != sf.id:
        raise chunk_errors.chunk_active_version_invalid()
    if not version.ragflow_document_id:
        raise chunk_errors.chunk_runtime_document_missing()
    kb = await knowledge_base_service.get_knowledge_base(db, member, sf.knowledge_base_id)
    dataset_id = await runtime_binding_service.get_dataset_id(db, kb)
    if not dataset_id:
        raise chunk_errors.chunk_runtime_binding_missing()
    return RuntimeDocumentRef(
        source_file_id=sf.id,
        file_version_id=version.id,
        dataset_id=dataset_id,
        document_id=version.ragflow_document_id,
    )


async def list_source_file_chunks(
    db: AsyncSession,
    member: KnowledgePrincipal,
    ragflow: RagflowRuntimeAdapter,
    source_file_id: str,
    *,
    page: int = 1,
    page_size: int = 50,
    keywords: str | None = None,
) -> SourceFileChunkPageOut:
    started = time.perf_counter()
    kw = keywords.strip() if isinstance(keywords, str) else None
    if kw == "":
        kw = None
    ref = await resolve_active_runtime_document(db, member, source_file_id)
    logger.info(
        "chunk_list stage=FETCH_PROVIDER source_file_id=%s file_version_id=%s page=%s page_size=%s keywords_present=%s",
        ref.source_file_id,
        ref.file_version_id,
        page,
        page_size,
        bool(kw),
    )
    try:
        page_data = await ragflow.read_document_chunks_page(
            ref.dataset_id,
            ref.document_id,
            page=page,
            page_size=page_size,
            keywords=kw,
        )
    except RagflowError as exc:
        if exc.message_key == "errors.knowledge.chunk_contract_invalid":
            raise chunk_errors.chunk_contract_invalid(exc.message) from exc
        raise chunk_errors.chunk_provider_unavailable(exc.message) from exc
    except Exception as exc:
        raise chunk_errors.chunk_provider_unavailable() from exc

    duration_ms = int((time.perf_counter() - started) * 1000)
    logger.info(
        "chunk_list stage=RETURN source_file_id=%s file_version_id=%s status=ok duration_ms=%s total=%s",
        ref.source_file_id,
        ref.file_version_id,
        duration_ms,
        page_data.total,
    )
    return SourceFileChunkPageOut(
        source_file_id=ref.source_file_id,
        file_version_id=ref.file_version_id,
        items=[_normalize_chunk(c) for c in page_data.chunks],
        total=page_data.total,
        page=page,
        page_size=page_size,
    )


async def get_source_file_chunk_image(
    db: AsyncSession,
    member: KnowledgePrincipal,
    ragflow: RagflowRuntimeAdapter,
    source_file_id: str,
    chunk_id: str,
    *,
    file_version_id: str,
) -> SourceFileChunkImage:
    from app.core.exceptions import AppException

    started = time.perf_counter()
    operation_id = uuid.uuid4().hex
    ref = await resolve_active_runtime_document(db, member, source_file_id)
    if file_version_id != ref.file_version_id:
        logger.info(
            "chunk_image stage=VERSION_GUARD operation_id=%s source_file_id=%s file_version_id=%s chunk_id_digest=%s error_code=KNOWLEDGE_CHUNK_VERSION_CONFLICT",
            operation_id,
            ref.source_file_id,
            file_version_id,
            _chunk_id_digest(chunk_id),
        )
        raise chunk_errors.chunk_version_conflict()

    digest = _chunk_id_digest(chunk_id)
    logger.info(
        "chunk_image stage=RESOLVE_CHUNK operation_id=%s source_file_id=%s file_version_id=%s chunk_id_digest=%s",
        operation_id,
        ref.source_file_id,
        ref.file_version_id,
        digest,
    )
    try:
        page_data = await ragflow.read_document_chunks_page(
            ref.dataset_id,
            ref.document_id,
            page=1,
            page_size=1,
            keywords=None,
            id=chunk_id,
        )
    except RagflowError as exc:
        if exc.message_key == "errors.knowledge.chunk_contract_invalid":
            raise chunk_errors.chunk_contract_invalid(exc.message) from exc
        raise chunk_errors.chunk_provider_unavailable(exc.message) from exc
    except AppException:
        raise
    except Exception as exc:
        raise chunk_errors.chunk_provider_unavailable() from exc

    matched = next(
        (c for c in page_data.chunks if isinstance(c, dict) and str(c.get("id") or "") == chunk_id),
        None,
    )
    if matched is None:
        logger.info(
            "chunk_image stage=CHUNK_RESOLVED operation_id=%s source_file_id=%s file_version_id=%s chunk_id_digest=%s error_code=KNOWLEDGE_CHUNK_NOT_FOUND",
            operation_id,
            ref.source_file_id,
            ref.file_version_id,
            digest,
        )
        raise chunk_errors.chunk_not_found()

    token = _provider_image_token(matched)
    if token is None:
        logger.info(
            "chunk_image stage=IMAGE_REF_RESOLVED operation_id=%s source_file_id=%s file_version_id=%s chunk_id_digest=%s error_code=KNOWLEDGE_CHUNK_IMAGE_NOT_FOUND",
            operation_id,
            ref.source_file_id,
            ref.file_version_id,
            digest,
        )
        raise chunk_errors.chunk_image_not_found()

    try:
        image = await ragflow.get_document_image(token)
    except AppException:
        raise
    except RagflowError as exc:
        if exc.message_key == "errors.knowledge.chunk_contract_invalid":
            raise chunk_errors.chunk_contract_invalid(exc.message) from exc
        raise chunk_errors.chunk_provider_unavailable(exc.message) from exc
    except Exception as exc:
        raise chunk_errors.chunk_provider_unavailable() from exc

    duration_ms = int((time.perf_counter() - started) * 1000)
    logger.info(
        "chunk_image stage=RETURN operation_id=%s source_file_id=%s file_version_id=%s chunk_id_digest=%s mime_type=%s byte_count=%s duration_ms=%s error_code=",
        operation_id,
        ref.source_file_id,
        ref.file_version_id,
        digest,
        image.content_type,
        len(image.content),
        duration_ms,
    )
    return SourceFileChunkImage(content=image.content, content_type=image.content_type)


def _map_patch_provider_error(exc: RagflowError) -> Exception:
    key = exc.message_key or ""
    lower = (exc.message or "").lower()
    if key == "errors.knowledge.chunk_mutation_uncertain":
        return chunk_errors.chunk_mutation_uncertain(exc.message)
    if "not found" in lower or "does not exist" in lower or "chunk" in lower and "404" in lower:
        return chunk_errors.chunk_not_found()
    if "not support" in lower or "unsupported" in lower or "method not allowed" in lower:
        return chunk_errors.chunk_update_unsupported(exc.message)
    if key in {"errors.knowledge.ragflow_bad_request"} and ("chunk" in lower or "not found" in lower):
        return chunk_errors.chunk_not_found()
    if key == "errors.knowledge.ragflow_unavailable":
        return chunk_errors.chunk_mutation_uncertain(exc.message)
    if exc.status_code == 404:
        return chunk_errors.chunk_not_found()
    if exc.status_code == 501:
        return chunk_errors.chunk_update_unsupported(exc.message)
    return chunk_errors.chunk_provider_unavailable(exc.message)


async def set_source_file_chunk_available(
    db: AsyncSession,
    member: KnowledgePrincipal,
    ragflow: RagflowRuntimeAdapter,
    source_file_id: str,
    chunk_id: str,
    *,
    file_version_id: str,
    available: bool,
) -> SourceFileChunkAvailabilityResult:
    started = time.perf_counter()
    sf = await source_file_service.get_source_file(db, member, source_file_id)
    await _require_update_or_manage(db, member, sf)
    if not sf.active_version_id:
        raise chunk_errors.chunk_no_active_version()
    if file_version_id != sf.active_version_id:
        raise chunk_errors.chunk_version_conflict()

    version = await db.get(SourceFileVersion, sf.active_version_id)
    if version is None or version.deleted_at is not None or version.source_file_id != sf.id:
        raise chunk_errors.chunk_active_version_invalid()
    if not version.ragflow_document_id:
        raise chunk_errors.chunk_runtime_document_missing()

    kb = await knowledge_base_service.get_knowledge_base(db, member, sf.knowledge_base_id)
    dataset_id = await runtime_binding_service.get_dataset_id(db, kb)
    if not dataset_id:
        raise chunk_errors.chunk_runtime_binding_missing()

    digest = _chunk_id_digest(chunk_id)
    logger.info(
        "chunk_update stage=MUTATE_PROVIDER source_file_id=%s file_version_id=%s chunk_id_digest=%s target_available=%s",
        sf.id,
        version.id,
        digest,
        available,
    )
    try:
        await ragflow.set_document_chunk_available(
            dataset_id,
            version.ragflow_document_id,
            chunk_id,
            available,
        )
    except RagflowError as exc:
        raise _map_patch_provider_error(exc) from exc
    except Exception as exc:
        raise chunk_errors.chunk_mutation_uncertain() from exc

    try:
        await write_audit(
            db,
            org_id=member.org_id,
            member_id=member.member_id,
            action=AuditAction.chunk_availability_update.value,
            resource_type="source_file",
            resource_id=sf.id,
            details={
                "file_version_id": version.id,
                "chunk_id_digest": digest,
                "available": available,
            },
        )
        await db.commit()
    except Exception:
        logger.error(
            "chunk_update audit_failed provider_mutation_confirmed=true source_file_id=%s chunk_id_digest=%s",
            sf.id,
            digest,
        )
        raise

    duration_ms = int((time.perf_counter() - started) * 1000)
    logger.info(
        "chunk_update stage=RETURN source_file_id=%s status=ok duration_ms=%s chunk_id_digest=%s",
        sf.id,
        duration_ms,
        digest,
    )
    return SourceFileChunkAvailabilityResult(
        source_file_id=sf.id,
        file_version_id=version.id,
        chunk_id=chunk_id,
        available=available,
    )
