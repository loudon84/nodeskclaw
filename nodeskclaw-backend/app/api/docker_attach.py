"""Docker container attach API endpoints."""

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi import status as http_status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import hooks
from app.core.deps import get_db
from app.core.exceptions import BadRequestError, ConflictError
from app.core.security import get_current_user
from app.models.org_membership import OrgMembership
from app.models.user import User
from app.schemas.common import ApiResponse
from app.schemas.docker_attach import (
    AttachableContainerInfo,
    AttachExistingInstanceRequest,
    AttachExistingInstanceResponse,
)
from app.services import docker_attach_service

docker_router = APIRouter()
instance_attach_router = APIRouter()


async def _ensure_org_member(user: User, org_id: str, db: AsyncSession) -> None:
    if user.is_super_admin:
        return
    membership = (
        await db.execute(
            select(OrgMembership).where(
                OrgMembership.user_id == user.id,
                OrgMembership.org_id == org_id,
                OrgMembership.deleted_at.is_(None),
            )
        )
    ).scalar_one_or_none()
    if not membership:
        raise HTTPException(
            status_code=http_status.HTTP_403_FORBIDDEN,
            detail={
                "error_code": 40312,
                "message_key": "errors.org.org_member_required",
                "message": "You are not a member of this organization",
            },
        )


@docker_router.get("/attachable-containers", response_model=ApiResponse[list[AttachableContainerInfo]])
async def list_attachable_containers(
    cluster_id: str = Query(..., min_length=1),
    runtime: str = Query("hermes-webui-expert"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    org_id = current_user.current_org_id
    if not org_id:
        raise BadRequestError("缺少目标组织", "errors.org.org_required")
    await _ensure_org_member(current_user, org_id, db)
    items = await docker_attach_service.list_attachable_containers(
        db,
        cluster_id=cluster_id,
        org_id=org_id,
        runtime=runtime,
    )
    return ApiResponse(data=items)


@instance_attach_router.post("/attach-existing", response_model=ApiResponse[AttachExistingInstanceResponse])
async def attach_existing_container(
    body: AttachExistingInstanceRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    org_id = current_user.current_org_id
    if not org_id:
        raise BadRequestError("缺少目标组织", "errors.org.org_required")
    await _ensure_org_member(current_user, org_id, db)
    try:
        instance = await docker_attach_service.attach_existing_container(
            db,
            current_user,
            body,
            org_id,
        )
    except IntegrityError:
        await db.rollback()
        raise ConflictError(
            message=f"实例标识 '{body.slug}' 已存在，请更换标识",
            message_key="errors.instance.slug_conflict",
        )

    await hooks.emit(
        "operation_audit",
        action="instance.attach_existing_container",
        target_type="instance",
        target_id=instance.id,
        actor_id=current_user.id,
        org_id=org_id,
        details={
            "profile": body.profile,
            "container_name": body.container_name,
            "host_port": body.host_port,
            "data_dir": body.data_dir,
            "compose_path": body.compose_path,
            "source": "portal",
        },
    )
    return ApiResponse(data=AttachExistingInstanceResponse(instance_id=instance.id))
