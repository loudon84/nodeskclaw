"""External Docker Hermes profile and core file API."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_db
from app.core.security import get_current_user
from app.models.instance_member import InstanceRole
from app.models.user import User
from app.schemas.common import ApiResponse
from app.schemas.external_docker_profiles import (
    CoreFileReadResponse,
    CoreFileSaveRequest,
    CoreFileSaveResponse,
    CoreFileValidateRequest,
    CoreFileValidateResponse,
    ProfileCreateRequest,
    ProfileCreateResponse,
    ProfileDeleteResponse,
    ProfileListItem,
    ProfileListResponse,
)
from app.services import instance_member_service
from app.services.hermes_external._common import require_external_docker_instance
from app.services.hermes_external import core_file_service, profile_service

router = APIRouter()


@router.get(
    "/{instance_id}/external-docker/profiles",
    response_model=ApiResponse[ProfileListResponse],
)
async def list_profiles(
    instance_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    await instance_member_service.check_instance_access(
        instance_id, current_user, InstanceRole.viewer, db,
    )
    instance = await require_external_docker_instance(instance_id, db, current_user.current_org_id)
    return ApiResponse(data=profile_service.list_profiles(instance))


@router.post(
    "/{instance_id}/external-docker/profiles",
    response_model=ApiResponse[ProfileCreateResponse],
)
async def create_profile(
    instance_id: str,
    body: ProfileCreateRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    await instance_member_service.check_instance_access(
        instance_id, current_user, InstanceRole.admin, db,
    )
    instance = await require_external_docker_instance(instance_id, db, current_user.current_org_id)
    return ApiResponse(data=profile_service.create_profile(
        instance,
        body.profile,
        from_profile=body.from_profile,
    ))


@router.delete(
    "/{instance_id}/external-docker/profiles/{profile}",
    response_model=ApiResponse[ProfileDeleteResponse],
)
async def delete_profile(
    instance_id: str,
    profile: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    await instance_member_service.check_instance_access(
        instance_id, current_user, InstanceRole.admin, db,
    )
    instance = await require_external_docker_instance(instance_id, db, current_user.current_org_id)
    return ApiResponse(data=profile_service.delete_profile(instance, profile))


@router.get(
    "/{instance_id}/external-docker/profiles/{profile}",
    response_model=ApiResponse[ProfileListItem],
)
async def get_profile(
    instance_id: str,
    profile: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    await instance_member_service.check_instance_access(
        instance_id, current_user, InstanceRole.viewer, db,
    )
    instance = await require_external_docker_instance(instance_id, db, current_user.current_org_id)
    return ApiResponse(data=profile_service.get_profile(instance, profile))


@router.get(
    "/{instance_id}/external-docker/profiles/{profile}/core-files/{kind}",
    response_model=ApiResponse[CoreFileReadResponse],
)
async def read_core_file(
    instance_id: str,
    profile: str,
    kind: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    await instance_member_service.check_instance_access(
        instance_id, current_user, InstanceRole.admin, db,
    )
    instance = await require_external_docker_instance(instance_id, db, current_user.current_org_id)
    return ApiResponse(data=core_file_service.read_core_file(instance, profile, kind))


@router.post(
    "/{instance_id}/external-docker/profiles/{profile}/core-files/{kind}/validate",
    response_model=ApiResponse[CoreFileValidateResponse],
)
async def validate_core_file(
    instance_id: str,
    profile: str,
    kind: str,
    body: CoreFileValidateRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    await instance_member_service.check_instance_access(
        instance_id, current_user, InstanceRole.admin, db,
    )
    await require_external_docker_instance(instance_id, db, current_user.current_org_id)
    return ApiResponse(data=core_file_service.validate_core_file(kind, body.content))


@router.put(
    "/{instance_id}/external-docker/profiles/{profile}/core-files/{kind}",
    response_model=ApiResponse[CoreFileSaveResponse],
)
async def save_core_file(
    instance_id: str,
    profile: str,
    kind: str,
    body: CoreFileSaveRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    await instance_member_service.check_instance_access(
        instance_id, current_user, InstanceRole.admin, db,
    )
    instance = await require_external_docker_instance(instance_id, db, current_user.current_org_id)
    return ApiResponse(data=await core_file_service.save_core_file(
        instance,
        profile,
        kind,
        body.content,
        restart_after_save=body.restart_after_save,
    ))
