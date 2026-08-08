"""Source file and ingestion routes."""

from fastapi import APIRouter, Depends, File, UploadFile
from fastapi.responses import Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_db, get_member_context, get_ragflow_client
from app.integrations.ragflow.client import RagflowClient
from app.schemas.common import ApiResponse
from app.schemas.knowledge import AclOut, FileAclCreate, IngestionJobOut, SourceFileOut, SourceFileVersionOut
from app.schemas.principal import KnowledgePrincipal
from app.services import ingestion_service, source_file_service

kb_files_router = APIRouter(prefix="/knowledge-bases", tags=["source-files"])
router = APIRouter(prefix="/source-files", tags=["source-files"])


@kb_files_router.get("/{kb_id}/files", response_model=ApiResponse[list[SourceFileOut]])
async def list_files(
    kb_id: str,
    member: KnowledgePrincipal = Depends(get_member_context),
    db: AsyncSession = Depends(get_db),
):
    items = await source_file_service.list_source_files(db, member, kb_id)
    return ApiResponse(data=[SourceFileOut.model_validate(i) for i in items])


@kb_files_router.post("/{kb_id}/files", response_model=ApiResponse)
async def upload_file(
    kb_id: str,
    file: UploadFile = File(...),
    member: KnowledgePrincipal = Depends(get_member_context),
    db: AsyncSession = Depends(get_db),
    ragflow: RagflowClient = Depends(get_ragflow_client),
):
    content = await file.read()
    sf, version, job = await ingestion_service.ingest_upload(
        db,
        member,
        ragflow,
        knowledge_base_id=kb_id,
        file_name=file.filename or "upload.bin",
        content=content,
        mime_type=file.content_type,
    )
    return ApiResponse(
        message="upload accepted, parsing in background",
        data={
            "source_file": SourceFileOut.model_validate(sf).model_dump(),
            "file_version_id": version.id,
            "job": IngestionJobOut.model_validate(job).model_dump(),
        },
    )


@router.get("/{source_file_id}/versions", response_model=ApiResponse[list[SourceFileVersionOut]])
async def list_versions(
    source_file_id: str,
    member: KnowledgePrincipal = Depends(get_member_context),
    db: AsyncSession = Depends(get_db),
):
    versions = await source_file_service.list_source_file_versions(db, member, source_file_id)
    return ApiResponse(data=[SourceFileVersionOut.model_validate(v) for v in versions])


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
    ragflow: RagflowClient = Depends(get_ragflow_client),
):
    await source_file_service.delete_source_file(db, member, ragflow, source_file_id)
    return ApiResponse(message="deleted")


@router.post("/{source_file_id}/versions", response_model=ApiResponse)
async def upload_version(
    source_file_id: str,
    file: UploadFile = File(...),
    member: KnowledgePrincipal = Depends(get_member_context),
    db: AsyncSession = Depends(get_db),
    ragflow: RagflowClient = Depends(get_ragflow_client),
):
    sf = await source_file_service.get_source_file(db, member, source_file_id)
    content = await file.read()
    sf2, version, job = await ingestion_service.ingest_upload(
        db,
        member,
        ragflow,
        knowledge_base_id=sf.knowledge_base_id,
        file_name=file.filename or sf.file_name,
        content=content,
        mime_type=file.content_type,
        source_file_id=source_file_id,
    )
    return ApiResponse(
        message="upload accepted, parsing in background",
        data={
            "source_file": SourceFileOut.model_validate(sf2).model_dump(),
            "file_version_id": version.id,
            "job": IngestionJobOut.model_validate(job).model_dump(),
        },
    )


@router.post("/{source_file_id}/reparse", response_model=ApiResponse[IngestionJobOut])
async def reparse(
    source_file_id: str,
    member: KnowledgePrincipal = Depends(get_member_context),
    db: AsyncSession = Depends(get_db),
    ragflow: RagflowClient = Depends(get_ragflow_client),
):
    job = await ingestion_service.reparse_source_file(db, member, ragflow, source_file_id)
    return ApiResponse(data=IngestionJobOut.model_validate(job))


@router.get("/{source_file_id}/download")
async def download(
    source_file_id: str,
    member: KnowledgePrincipal = Depends(get_member_context),
    db: AsyncSession = Depends(get_db),
    ragflow: RagflowClient = Depends(get_ragflow_client),
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
