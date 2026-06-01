"""Agent-only file grant download API."""

from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.file_downloads import build_storage_download_response
from app.core.deps import get_db
from app.core.security import get_current_agent_instance
from app.models.instance import Instance
from app.services import file_reference_service

router = APIRouter()


@router.get("/workspaces/{workspace_id}/agent-file-grants/{grant_id}/download")
async def download_agent_file_grant(
    workspace_id: str,
    grant_id: str,
    request: Request,
    db: AsyncSession = Depends(get_db),
    agent: Instance = Depends(get_current_agent_instance),
):
    grant = await file_reference_service.get_agent_grant_for_download(
        db,
        workspace_id=workspace_id,
        grant_id=grant_id,
        agent=agent,
    )
    source_file = await file_reference_service.resolve_grant_source_file(db, grant)
    file_reference_service.ensure_scan_allows_download(source_file["scan_status"])
    await file_reference_service.mark_agent_grant_accessed(db, grant)
    return await build_storage_download_response(
        storage_key=source_file["storage_key"],
        filename=source_file["filename"],
        content_type=source_file["content_type"],
        range_header=request.headers.get("range"),
    )
