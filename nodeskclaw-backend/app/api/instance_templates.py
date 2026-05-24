"""Instance template API routes."""

from fastapi import APIRouter, Depends, File, Form, Query, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.deps import get_current_org, get_db
from app.core.exceptions import BadRequestError
from app.schemas.common import ApiResponse, PaginatedResponse, Pagination
from app.schemas.instance_template import (
    AgentBundleImportRequest,
    InstanceTemplateCreate,
    InstanceTemplateFromInstance,
    InstanceTemplateInfo,
    InstanceTemplateUpdate,
)
from app.services.agent_bundle_service import MAX_ZIP_BYTES, parse_agent_bundle_zip
from app.services import instance_template_service as svc

router = APIRouter()
UPLOAD_READ_CHUNK_BYTES = 64 * 1024


async def _read_upload_file_limited(file: UploadFile, max_bytes: int = MAX_ZIP_BYTES) -> bytes:
    chunks: list[bytes] = []
    total = 0
    while True:
        chunk = await file.read(UPLOAD_READ_CHUNK_BYTES)
        if not chunk:
            break
        total += len(chunk)
        if total > max_bytes:
            raise BadRequestError("Agent Bundle 上传文件过大")
        chunks.append(chunk)
    return b"".join(chunks)


@router.get("/instance-templates", response_model=PaginatedResponse)
async def list_templates(
    keyword: str | None = Query(None),
    featured: bool = Query(False),
    visibility: str | None = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    org_info=Depends(get_current_org),
):
    user, org = org_info
    items, total = await svc.list_templates(
        db, org_id=org.id, visibility=visibility, keyword=keyword, featured_only=featured, page=page, page_size=page_size,
    )
    return PaginatedResponse(
        data=[item.model_dump(mode="json") for item in items],
        pagination=Pagination(page=page, page_size=page_size, total=total),
    )


@router.get("/instance-templates/featured", response_model=ApiResponse)
async def featured_templates(
    db: AsyncSession = Depends(get_db),
    org_info=Depends(get_current_org),
):
    user, org = org_info
    items, _ = await svc.list_templates(db, org_id=org.id, featured_only=True, page=1, page_size=10)
    return ApiResponse(data=[item.model_dump(mode="json") for item in items])


@router.get("/instance-templates/{template_id}", response_model=ApiResponse)
async def get_template(
    template_id: str,
    db: AsyncSession = Depends(get_db),
    org_info=Depends(get_current_org),
):
    _user, org = org_info
    item = await svc.get_template(db, template_id, org.id)
    return ApiResponse(data=item.model_dump(mode="json"))


@router.post("/instance-templates", response_model=ApiResponse)
async def create_template(
    body: InstanceTemplateCreate,
    db: AsyncSession = Depends(get_db),
    org_info=Depends(get_current_org),
):
    user, org = org_info
    item = await svc.create_template(db, body, user_id=user.id, org_id=org.id)
    return ApiResponse(data=item.model_dump(mode="json"))


@router.post("/instance-templates/import-agent-bundle", response_model=ApiResponse)
async def import_agent_bundle(
    file: UploadFile = File(...),
    name: str | None = Form(None),
    slug: str | None = Form(None),
    description: str | None = Form(None),
    short_description: str | None = Form(None),
    icon: str | None = Form(None),
    db: AsyncSession = Depends(get_db),
    org_info=Depends(get_current_org),
):
    user, org = org_info
    data = await _read_upload_file_limited(file)
    manifest = parse_agent_bundle_zip(file.filename or "agent-bundle.zip", data)
    item = await svc.import_agent_bundle_manifest(
        db,
        manifest,
        user_id=user.id,
        org_id=org.id,
        name=name,
        slug=slug,
        description=description,
        short_description=short_description,
        icon=icon,
    )
    return ApiResponse(data=item.model_dump(mode="json"))


@router.post("/instance-templates/import-agent-bundle-path", response_model=ApiResponse)
async def import_agent_bundle_path(
    body: AgentBundleImportRequest,
    db: AsyncSession = Depends(get_db),
    org_info=Depends(get_current_org),
):
    if not settings.DEBUG:
        raise BadRequestError("本地路径导入仅允许在 DEBUG 开发环境使用")
    user, org = org_info
    item = await svc.import_agent_bundle_template(db, body, user_id=user.id, org_id=org.id)
    return ApiResponse(data=item.model_dump(mode="json"))


@router.post("/instance-templates/from-instance/{instance_id}", response_model=ApiResponse)
async def create_from_instance(
    instance_id: str,
    body: InstanceTemplateFromInstance,
    db: AsyncSession = Depends(get_db),
    org_info=Depends(get_current_org),
):
    user, org = org_info
    item = await svc.create_from_instance(db, instance_id, body, user_id=user.id, org_id=org.id)
    return ApiResponse(data=item.model_dump(mode="json"))


@router.put("/instance-templates/{template_id}", response_model=ApiResponse)
async def update_template(
    template_id: str,
    body: InstanceTemplateUpdate,
    db: AsyncSession = Depends(get_db),
    org_info=Depends(get_current_org),
):
    _user, org = org_info
    item = await svc.update_template(db, template_id, body, org.id)
    return ApiResponse(data=item.model_dump(mode="json"))


@router.delete("/instance-templates/{template_id}", response_model=ApiResponse)
async def delete_template(
    template_id: str,
    db: AsyncSession = Depends(get_db),
    org_info=Depends(get_current_org),
):
    _user, org = org_info
    result = await svc.delete_template(db, template_id, org.id)
    return ApiResponse(data=result)
