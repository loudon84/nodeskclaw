"""Source file and ingestion routes."""

from datetime import datetime

from fastapi import APIRouter, Depends, File, Form, Query, UploadFile
from fastapi.responses import Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_db, get_member_context, get_runtime_adapter
from app.runtime.ragflow import RagflowRuntimeAdapter
from app.schemas.common import ApiResponse, PageData
from app.schemas.knowledge import (
    AclOut,
    FileAclCreate,
    IngestionJobOut,
    SourceFileMetadataOut,
    SourceFileMetadataPatch,
    SourceFileOut,
    SourceFileVersionOut,
)
from app.schemas.principal import KnowledgePrincipal
from app.services import ingestion_facade, ingestion_service, metadata_service, source_file_service, source_lifecycle_service

kb_files_router = APIRouter(prefix="/knowledge-bases", tags=["source-files"])
router = APIRouter(prefix="/source-files", tags=["source-files"])


@kb_files_router.get("/{kb_id}/files", response_model=ApiResponse[PageData[SourceFileOut]])
async def list_files(
    kb_id: str,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    q: str | None = None,
    sort_by: str = Query("created_at"),
    sort_order: str = Query("desc"),
    member: KnowledgePrincipal = Depends(get_member_context),
    db: AsyncSession = Depends(get_db),
):
    items, total = await source_file_service.list_source_files(
        db,
        member,
        kb_id,
        page=page,
        page_size=page_size,
        q=q,
        sort_by=sort_by,
        sort_order=sort_order,
    )
    return ApiResponse(
        data=PageData(
            items=[SourceFileOut.model_validate(i) for i in items],
            total=total,
            page=page,
            page_size=page_size,
        )
    )


@router.get("", response_model=ApiResponse[PageData[SourceFileOut]])
async def list_global_files(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    q: str | None = None,
    knowledge_base_id: str | None = None,
    parse_status: str | None = None,
    status: str | None = None,
    mime_type: str | None = None,
    owner_member_id: str | None = None,
    created_from: datetime | None = None,
    created_to: datetime | None = None,
    sort_by: str = Query("created_at"),
    sort_order: str = Query("desc"),
    member: KnowledgePrincipal = Depends(get_member_context),
    db: AsyncSession = Depends(get_db),
):
    items, total = await source_file_service.list_global_source_files(
        db,
        member,
        page=page,
        page_size=page_size,
        q=q,
        knowledge_base_id=knowledge_base_id,
        parse_status=parse_status,
        status=status,
        mime_type=mime_type,
        owner_member_id=owner_member_id,
        created_from=created_from,
        created_to=created_to,
        sort_by=sort_by,
        sort_order=sort_order,
    )
    return ApiResponse(
        data=PageData(
            items=[SourceFileOut.model_validate(i) for i in items],
            total=total,
            page=page,
            page_size=page_size,
        )
    )


@kb_files_router.post("/{kb_id}/files", response_model=ApiResponse)
async def upload_file(
    kb_id: str,
    file: UploadFile = File(...),
    metadata: str = Form("{}"),
    member: KnowledgePrincipal = Depends(get_member_context),
    db: AsyncSession = Depends(get_db),
    ragflow: RagflowRuntimeAdapter = Depends(get_runtime_adapter),
):
    parsed_metadata = metadata_service.parse_metadata_form(metadata)
    spool, size, digest = await ingestion_service.read_upload_spooled(file)
    try:
        sf, version, job = await ingestion_facade.ingest_from_member(
            db,
            member,
            ragflow,
            knowledge_base_id=kb_id,
            file_name=file.filename or "upload.bin",
            mime_type=file.content_type,
            file_obj=spool,
            file_size=size,
            sha256=digest,
            metadata=parsed_metadata,
        )
    finally:
        spool.close()
    return ApiResponse(
        message="upload accepted, parsing in background",
        data={
            "source_file": SourceFileOut.model_validate(sf).model_dump(),
            "file_version_id": version.id,
            "job": IngestionJobOut.model_validate(job).model_dump(),
        },
    )


@router.get("/{source_file_id}/metadata", response_model=ApiResponse[SourceFileMetadataOut])
async def get_metadata(
    source_file_id: str,
    member: KnowledgePrincipal = Depends(get_member_context),
    db: AsyncSession = Depends(get_db),
):
    data = await metadata_service.get_source_file_metadata(db, member, source_file_id)
    return ApiResponse(data=SourceFileMetadataOut.model_validate(data))


@router.patch("/{source_file_id}/metadata", response_model=ApiResponse[SourceFileMetadataOut])
async def patch_metadata(
    source_file_id: str,
    body: SourceFileMetadataPatch,
    member: KnowledgePrincipal = Depends(get_member_context),
    db: AsyncSession = Depends(get_db),
    ragflow: RagflowRuntimeAdapter = Depends(get_runtime_adapter),
):
    data = await metadata_service.patch_source_file_metadata(
        db,
        member,
        ragflow,
        source_file_id,
        body.metadata,
    )
    return ApiResponse(data=SourceFileMetadataOut.model_validate(data))


@router.get("/{source_file_id}/versions", response_model=ApiResponse[list[SourceFileVersionOut]])
async def list_versions(
    source_file_id: str,
    member: KnowledgePrincipal = Depends(get_member_context),
    db: AsyncSession = Depends(get_db),
):
    versions = await source_file_service.list_source_file_versions(db, member, source_file_id)
    return ApiResponse(data=[SourceFileVersionOut.model_validate(v) for v in versions])


@router.post("/{source_file_id}/versions/{version_id}/activate", response_model=ApiResponse[SourceFileOut])
async def activate_version(
    source_file_id: str,
    version_id: str,
    member: KnowledgePrincipal = Depends(get_member_context),
    db: AsyncSession = Depends(get_db),
    ragflow: RagflowRuntimeAdapter = Depends(get_runtime_adapter),
):
    sf = await source_lifecycle_service.activate_source_file_version(
        db, member, ragflow, source_file_id, version_id
    )
    return ApiResponse(data=SourceFileOut.model_validate(sf))


@router.post("/{source_file_id}/archive", response_model=ApiResponse[SourceFileOut])
async def archive_file(
    source_file_id: str,
    member: KnowledgePrincipal = Depends(get_member_context),
    db: AsyncSession = Depends(get_db),
    ragflow: RagflowRuntimeAdapter = Depends(get_runtime_adapter),
):
    sf = await source_lifecycle_service.archive_source_file(db, member, ragflow, source_file_id)
    return ApiResponse(data=SourceFileOut.model_validate(sf))


@router.post("/{source_file_id}/unarchive", response_model=ApiResponse[SourceFileOut])
async def unarchive_file(
    source_file_id: str,
    member: KnowledgePrincipal = Depends(get_member_context),
    db: AsyncSession = Depends(get_db),
    ragflow: RagflowRuntimeAdapter = Depends(get_runtime_adapter),
):
    sf = await source_lifecycle_service.unarchive_source_file(db, member, ragflow, source_file_id)
    return ApiResponse(data=SourceFileOut.model_validate(sf))


@router.get("/{source_file_id}/versions/{version_id}", response_model=ApiResponse[SourceFileVersionOut])
async def get_version(
    source_file_id: str,
    version_id: str,
    member: KnowledgePrincipal = Depends(get_member_context),
    db: AsyncSession = Depends(get_db),
):
    version = await source_file_service.get_source_file_version(db, member, source_file_id, version_id)
    return ApiResponse(data=SourceFileVersionOut.model_validate(version))


@router.get("/{source_file_id}", response_model=ApiResponse[SourceFileOut])
async def get_file(
    source_file_id: str,
    member: KnowledgePrincipal = Depends(get_member_context),
    db: AsyncSession = Depends(get_db),
):
    sf = await source_file_service.get_source_file(db, member, source_file_id)
    enriched = await source_file_service.enrich_source_file(sf, db)
    return ApiResponse(data=SourceFileOut.model_validate(enriched))


@router.delete("/{source_file_id}", response_model=ApiResponse)
async def delete_file(
    source_file_id: str,
    member: KnowledgePrincipal = Depends(get_member_context),
    db: AsyncSession = Depends(get_db),
    ragflow: RagflowRuntimeAdapter = Depends(get_runtime_adapter),
):
    await source_file_service.delete_source_file(db, member, ragflow, source_file_id)
    return ApiResponse(message="deleted")


@router.post("/{source_file_id}/versions", response_model=ApiResponse)
async def upload_version(
    source_file_id: str,
    file: UploadFile = File(...),
    metadata: str | None = Form(None),
    member: KnowledgePrincipal = Depends(get_member_context),
    db: AsyncSession = Depends(get_db),
    ragflow: RagflowRuntimeAdapter = Depends(get_runtime_adapter),
):
    sf = await source_file_service.get_source_file(db, member, source_file_id)
    parsed_metadata = metadata_service.parse_metadata_form(metadata) if metadata is not None else None
    spool, size, digest = await ingestion_service.read_upload_spooled(file)
    try:
        sf2, version, job = await ingestion_facade.ingest_from_member(
            db,
            member,
            ragflow,
            knowledge_base_id=sf.knowledge_base_id,
            file_name=file.filename or sf.file_name,
            mime_type=file.content_type,
            file_obj=spool,
            file_size=size,
            sha256=digest,
            source_file_id=source_file_id,
            metadata=parsed_metadata,
        )
    finally:
        spool.close()
    return ApiResponse(
        message="upload accepted, parsing in background",
        data={
            "source_file": SourceFileOut.model_validate(sf2).model_dump(),
            "file_version_id": version.id,
            "job": IngestionJobOut.model_validate(job).model_dump(),
        },
    )


@router.post("/{source_file_id}/detach", response_model=ApiResponse[SourceFileOut])
async def detach_file(
    source_file_id: str,
    member: KnowledgePrincipal = Depends(get_member_context),
    db: AsyncSession = Depends(get_db),
):
    sf = await ingestion_facade.detach_source_file(db, member, source_file_id)
    return ApiResponse(data=SourceFileOut.model_validate(sf))


@router.post("/{source_file_id}/reparse", response_model=ApiResponse[IngestionJobOut])
async def reparse(
    source_file_id: str,
    member: KnowledgePrincipal = Depends(get_member_context),
    db: AsyncSession = Depends(get_db),
    ragflow: RagflowRuntimeAdapter = Depends(get_runtime_adapter),
):
    job = await ingestion_service.reparse_source_file(db, member, ragflow, source_file_id)
    return ApiResponse(data=IngestionJobOut.model_validate(job))


@router.get("/{source_file_id}/download")
async def download(
    source_file_id: str,
    member: KnowledgePrincipal = Depends(get_member_context),
    db: AsyncSession = Depends(get_db),
    ragflow: RagflowRuntimeAdapter = Depends(get_runtime_adapter),
):
    sf, _version, content = await source_file_service.download_source_file(db, member, ragflow, source_file_id)
    return Response(
        content=content,
        media_type=sf.mime_type or "application/octet-stream",
        headers={"Content-Disposition": f'attachment; filename="{sf.file_name}"'},
    )


@router.get("/{source_file_id}/acl", response_model=ApiResponse[list[AclOut]])
async def list_acl(
    source_file_id: str,
    member: KnowledgePrincipal = Depends(get_member_context),
    db: AsyncSession = Depends(get_db),
):
    rows = await source_file_service.list_file_acl(db, member, source_file_id)
    return ApiResponse(data=[AclOut.model_validate(r) for r in rows])


@router.post("/{source_file_id}/acl", response_model=ApiResponse[AclOut])
async def create_acl(
    source_file_id: str,
    body: FileAclCreate,
    member: KnowledgePrincipal = Depends(get_member_context),
    db: AsyncSession = Depends(get_db),
):
    row = await source_file_service.add_file_acl(
        db,
        member,
        source_file_id,
        subject_type=body.subject_type.value,
        subject_id=body.subject_id,
        permission=body.permission.value,
        effect=body.effect.value,
    )
    return ApiResponse(data=AclOut.model_validate(row))


@router.delete("/{source_file_id}/acl/{acl_id}", response_model=ApiResponse)
async def delete_acl(
    source_file_id: str,
    acl_id: str,
    member: KnowledgePrincipal = Depends(get_member_context),
    db: AsyncSession = Depends(get_db),
):
    await source_file_service.delete_file_acl(db, member, source_file_id, acl_id)
    return ApiResponse(message="deleted")
