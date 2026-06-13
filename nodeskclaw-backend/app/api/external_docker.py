"""External Docker Hermes instance management API."""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_db
from app.core.security import get_current_user
from app.models.instance_member import InstanceRole
from app.models.user import User
from app.schemas.common import ApiResponse
from app.schemas.external_docker import (
    ExternalDockerBackupsResponse,
    ExternalDockerCreateBackupResponse,
    ExternalDockerDetachResponse,
    ExternalDockerFilesResponse,
    ExternalDockerLifecycleResponse,
    ExternalDockerLogsResponse,
    ExternalDockerModelConfigResponse,
    ExternalDockerOverviewResponse,
    ExternalDockerSkillsResponse,
    ExternalDockerStatusResponse,
    ExternalDockerWebuiAccessResponse,
    ExternalDockerWebuiPasswordResponse,
)
from app.services import instance_member_service
from app.services.hermes_external._common import require_external_docker_instance
from app.services.hermes_external import backup_service, file_service, lifecycle_service
from app.services.hermes_external import model_config_service, skill_service, status_service

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/{instance_id}/external-docker/overview", response_model=ApiResponse[ExternalDockerOverviewResponse])
async def get_overview(
    instance_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    await instance_member_service.check_instance_access(
        instance_id, current_user, InstanceRole.viewer, db,
    )
    instance = await require_external_docker_instance(instance_id, db, current_user.current_org_id)
    return ApiResponse(data=await status_service.get_overview(instance))


@router.get("/{instance_id}/external-docker/status", response_model=ApiResponse[ExternalDockerStatusResponse])
async def get_status(
    instance_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    await instance_member_service.check_instance_access(
        instance_id, current_user, InstanceRole.viewer, db,
    )
    instance = await require_external_docker_instance(instance_id, db, current_user.current_org_id)
    return ApiResponse(data=await status_service.get_status(instance))


@router.get("/{instance_id}/external-docker/webui-access", response_model=ApiResponse[ExternalDockerWebuiAccessResponse])
async def get_webui_access(
    instance_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    await instance_member_service.check_instance_access(
        instance_id, current_user, InstanceRole.viewer, db,
    )
    instance = await require_external_docker_instance(instance_id, db, current_user.current_org_id)
    return ApiResponse(data=await lifecycle_service.get_webui_access(instance))


@router.post("/{instance_id}/external-docker/webui-password", response_model=ApiResponse[ExternalDockerWebuiPasswordResponse])
async def get_webui_password(
    instance_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    await instance_member_service.check_instance_access(
        instance_id, current_user, InstanceRole.admin, db,
    )
    instance = await require_external_docker_instance(instance_id, db, current_user.current_org_id)
    return ApiResponse(data=await lifecycle_service.get_webui_password(instance))


@router.get("/{instance_id}/external-docker/model-config", response_model=ApiResponse[ExternalDockerModelConfigResponse])
async def get_model_config(
    instance_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    await instance_member_service.check_instance_access(
        instance_id, current_user, InstanceRole.viewer, db,
    )
    instance = await require_external_docker_instance(instance_id, db, current_user.current_org_id)
    return ApiResponse(data=model_config_service.get_model_config(instance))


@router.get("/{instance_id}/external-docker/skills", response_model=ApiResponse[ExternalDockerSkillsResponse])
async def list_skills(
    instance_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    await instance_member_service.check_instance_access(
        instance_id, current_user, InstanceRole.viewer, db,
    )
    instance = await require_external_docker_instance(instance_id, db, current_user.current_org_id)
    return ApiResponse(data=skill_service.list_skills(instance))


@router.get("/{instance_id}/external-docker/files", response_model=ApiResponse[ExternalDockerFilesResponse])
async def list_files(
    instance_id: str,
    scope: str = Query(default="workspace"),
    path: str = Query(default=""),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    await instance_member_service.check_instance_access(
        instance_id, current_user, InstanceRole.admin, db,
    )
    instance = await require_external_docker_instance(instance_id, db, current_user.current_org_id)
    return ApiResponse(data=file_service.list_files(instance, scope=scope, path=path))


@router.get("/{instance_id}/external-docker/backups", response_model=ApiResponse[ExternalDockerBackupsResponse])
async def list_backups(
    instance_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    await instance_member_service.check_instance_access(
        instance_id, current_user, InstanceRole.admin, db,
    )
    instance = await require_external_docker_instance(instance_id, db, current_user.current_org_id)
    return ApiResponse(data=backup_service.list_backups(instance))


@router.post("/{instance_id}/external-docker/backups", response_model=ApiResponse[ExternalDockerCreateBackupResponse])
async def create_backup(
    instance_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    await instance_member_service.check_instance_access(
        instance_id, current_user, InstanceRole.admin, db,
    )
    instance = await require_external_docker_instance(instance_id, db, current_user.current_org_id)
    return ApiResponse(data=backup_service.create_backup(instance))


@router.post("/{instance_id}/external-docker/start", response_model=ApiResponse[ExternalDockerLifecycleResponse])
async def start_instance(
    instance_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    await instance_member_service.check_instance_access(
        instance_id, current_user, InstanceRole.admin, db,
    )
    instance = await require_external_docker_instance(instance_id, db, current_user.current_org_id)
    return ApiResponse(data=await lifecycle_service.start(instance))


@router.post("/{instance_id}/external-docker/stop", response_model=ApiResponse[ExternalDockerLifecycleResponse])
async def stop_instance(
    instance_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    await instance_member_service.check_instance_access(
        instance_id, current_user, InstanceRole.admin, db,
    )
    instance = await require_external_docker_instance(instance_id, db, current_user.current_org_id)
    return ApiResponse(data=await lifecycle_service.stop(instance))


@router.post("/{instance_id}/external-docker/restart", response_model=ApiResponse[ExternalDockerLifecycleResponse])
async def restart_instance(
    instance_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    await instance_member_service.check_instance_access(
        instance_id, current_user, InstanceRole.admin, db,
    )
    instance = await require_external_docker_instance(instance_id, db, current_user.current_org_id)
    return ApiResponse(data=await lifecycle_service.restart(instance))


@router.post("/{instance_id}/external-docker/detach", response_model=ApiResponse[ExternalDockerDetachResponse])
async def detach_instance(
    instance_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    await instance_member_service.check_instance_access(
        instance_id, current_user, InstanceRole.admin, db,
    )
    await require_external_docker_instance(instance_id, db, current_user.current_org_id)
    return ApiResponse(data=await lifecycle_service.detach(instance_id, db))


@router.get("/{instance_id}/external-docker/logs", response_model=ApiResponse[ExternalDockerLogsResponse])
async def get_logs(
    instance_id: str,
    tail: int = Query(default=200, ge=1, le=2000),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    await instance_member_service.check_instance_access(
        instance_id, current_user, InstanceRole.admin, db,
    )
    instance = await require_external_docker_instance(instance_id, db, current_user.current_org_id)
    return ApiResponse(data=await lifecycle_service.get_logs(instance, tail=tail))
