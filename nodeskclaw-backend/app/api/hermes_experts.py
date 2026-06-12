"""Hermes WebUI expert instance API."""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, File, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_db
from app.core.exceptions import BadRequestError
from app.core.security import get_current_user
from app.models.instance_member import InstanceRole
from app.models.user import User
from app.schemas.common import ApiResponse
from app.services.hermes_expert.expert_instance_service import ExpertInstanceService
from app.services.hermes_expert.expert_skill_service import ExpertSkillService
from app.services.hermes_expert.expert_template_service import ExpertTemplateService
from app.services.hermes_expert.schemas import (
    CreateExpertInstanceRequest,
    CreateExpertInstanceResponse,
    ExpertHealthInfo,
    ExpertInstanceInfo,
    ExpertSkillInfo,
    ExpertTemplateInfo,
    InstallBuiltinSkillRequest,
    InstallGitSkillRequest,
)
from app.services import instance_member_service

logger = logging.getLogger(__name__)

router = APIRouter()
_instance_service = ExpertInstanceService()
_template_service = ExpertTemplateService()
_skill_service = ExpertSkillService()


@router.get("/templates", response_model=ApiResponse[list[ExpertTemplateInfo]])
async def list_templates(
    _current_user: User = Depends(get_current_user),
):
    return ApiResponse(data=_template_service.list_templates())


@router.get("/templates/{template_slug}", response_model=ApiResponse[ExpertTemplateInfo])
async def get_template(
    template_slug: str,
    _current_user: User = Depends(get_current_user),
):
    return ApiResponse(data=_template_service.get_template(template_slug))


@router.get("/instances", response_model=ApiResponse[list[ExpertInstanceInfo]])
async def list_expert_instances(
    org_id: str | None = None,
    refresh_status: bool = False,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    effective_org_id = org_id or current_user.current_org_id
    return ApiResponse(data=await _instance_service.list_instances(
        db, effective_org_id, refresh_status=refresh_status,
    ))


@router.post("/instances", response_model=ApiResponse[CreateExpertInstanceResponse])
async def create_expert_instance(
    body: CreateExpertInstanceRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    effective_org_id = body.org_id or current_user.current_org_id
    if not effective_org_id:
        raise BadRequestError("缺少目标组织", "errors.org.org_required")
    data = await _instance_service.create_instance(body, current_user, db, org_id=effective_org_id)
    return ApiResponse(data=data)


@router.get("/instances/{instance_id}", response_model=ApiResponse[ExpertInstanceInfo])
async def get_expert_instance(
    instance_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    await instance_member_service.check_instance_access(
        instance_id, current_user, InstanceRole.viewer, db,
    )
    return ApiResponse(data=await _instance_service.get_instance(instance_id, db))


@router.get("/instances/{instance_id}/logs", response_model=ApiResponse[dict])
async def get_expert_logs(
    instance_id: str,
    tail: int = 100,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    await instance_member_service.check_instance_access(
        instance_id, current_user, InstanceRole.viewer, db,
    )
    logs = await _instance_service.get_logs(instance_id, db, tail=tail)
    return ApiResponse(data={"logs": logs})


@router.get("/instances/{instance_id}/health", response_model=ApiResponse[ExpertHealthInfo])
async def get_expert_health(
    instance_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    await instance_member_service.check_instance_access(
        instance_id, current_user, InstanceRole.viewer, db,
    )
    return ApiResponse(data=await _instance_service.health(instance_id, db))


@router.post("/instances/{instance_id}/restart", response_model=ApiResponse[dict])
async def restart_expert_instance(
    instance_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    await instance_member_service.check_instance_access(
        instance_id, current_user, InstanceRole.editor, db,
    )
    await _instance_service.restart(instance_id, db)
    return ApiResponse(data={"status": "restarting"})


@router.post("/instances/{instance_id}/stop", response_model=ApiResponse[dict])
async def stop_expert_instance(
    instance_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    await instance_member_service.check_instance_access(
        instance_id, current_user, InstanceRole.editor, db,
    )
    await _instance_service.stop(instance_id, db)
    return ApiResponse(data={"status": "stopped"})


@router.post("/instances/{instance_id}/start", response_model=ApiResponse[dict])
async def start_expert_instance(
    instance_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    await instance_member_service.check_instance_access(
        instance_id, current_user, InstanceRole.editor, db,
    )
    await _instance_service.start(instance_id, db)
    return ApiResponse(data={"status": "running"})


@router.post("/instances/{instance_id}/sync-status", response_model=ApiResponse[dict])
async def sync_expert_instance_status(
    instance_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    await instance_member_service.check_instance_access(
        instance_id, current_user, InstanceRole.viewer, db,
    )
    return ApiResponse(data=await _instance_service.sync_status(instance_id, db))


@router.post("/instances/{instance_id}/actions/detach", response_model=ApiResponse[dict])
async def detach_expert_instance(
    instance_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    await instance_member_service.check_instance_access(
        instance_id, current_user, InstanceRole.admin, db,
    )
    await _instance_service.detach(instance_id, db)
    return ApiResponse(data={"status": "detached"})


@router.delete("/instances/{instance_id}", response_model=ApiResponse[dict])
async def delete_expert_instance(
    instance_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    await instance_member_service.check_instance_access(
        instance_id, current_user, InstanceRole.admin, db,
    )
    await _instance_service.delete(instance_id, db)
    return ApiResponse(data={"status": "deleted"})


@router.get("/instances/{instance_id}/skills", response_model=ApiResponse[list[ExpertSkillInfo]])
async def list_instance_skills(
    instance_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    await instance_member_service.check_instance_access(
        instance_id, current_user, InstanceRole.viewer, db,
    )
    instance = await _instance_service._get_expert_instance(instance_id, db)
    return ApiResponse(data=_skill_service.list_skills(instance))


@router.get(
    "/instances/{instance_id}/skills/{skill_slug}",
    response_model=ApiResponse[ExpertSkillInfo],
)
async def get_instance_skill(
    instance_id: str,
    skill_slug: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    await instance_member_service.check_instance_access(
        instance_id, current_user, InstanceRole.viewer, db,
    )
    instance = await _instance_service._get_expert_instance(instance_id, db)
    return ApiResponse(data=_skill_service.get_skill(instance, skill_slug))


@router.post(
    "/instances/{instance_id}/skills/builtin",
    response_model=ApiResponse[list[ExpertSkillInfo]],
)
async def install_builtin_skill(
    instance_id: str,
    body: InstallBuiltinSkillRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    await instance_member_service.check_instance_access(
        instance_id, current_user, InstanceRole.editor, db,
    )
    instance = await _instance_service._get_expert_instance(instance_id, db)
    items = _skill_service.install_builtin_bundle(instance, body.bundle)
    return ApiResponse(data=items)


@router.post(
    "/instances/{instance_id}/skills/upload",
    response_model=ApiResponse[ExpertSkillInfo],
)
async def upload_instance_skill(
    instance_id: str,
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    await instance_member_service.check_instance_access(
        instance_id, current_user, InstanceRole.editor, db,
    )
    instance = await _instance_service._get_expert_instance(instance_id, db)
    payload = await file.read()
    item = _skill_service.upload_skill_zip(instance, payload)
    return ApiResponse(data=item)


@router.post(
    "/instances/{instance_id}/skills/git",
    response_model=ApiResponse[ExpertSkillInfo],
)
async def install_git_skill(
    instance_id: str,
    body: InstallGitSkillRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    await instance_member_service.check_instance_access(
        instance_id, current_user, InstanceRole.editor, db,
    )
    instance = await _instance_service._get_expert_instance(instance_id, db)
    item = _skill_service.install_from_git(
        instance,
        repo=body.repo,
        ref=body.ref,
        skill_slug=body.skill_slug,
    )
    return ApiResponse(data=item)


@router.post(
    "/instances/{instance_id}/skills/{skill_slug}/enable",
    response_model=ApiResponse[ExpertSkillInfo],
)
async def enable_instance_skill(
    instance_id: str,
    skill_slug: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    await instance_member_service.check_instance_access(
        instance_id, current_user, InstanceRole.editor, db,
    )
    instance = await _instance_service._get_expert_instance(instance_id, db)
    return ApiResponse(data=_skill_service.enable_skill(instance, skill_slug))


@router.post(
    "/instances/{instance_id}/skills/{skill_slug}/disable",
    response_model=ApiResponse[ExpertSkillInfo],
)
async def disable_instance_skill(
    instance_id: str,
    skill_slug: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    await instance_member_service.check_instance_access(
        instance_id, current_user, InstanceRole.editor, db,
    )
    instance = await _instance_service._get_expert_instance(instance_id, db)
    return ApiResponse(data=_skill_service.disable_skill(instance, skill_slug))


@router.delete("/instances/{instance_id}/skills/{skill_slug}", response_model=ApiResponse[dict])
async def delete_instance_skill(
    instance_id: str,
    skill_slug: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    await instance_member_service.check_instance_access(
        instance_id, current_user, InstanceRole.editor, db,
    )
    instance = await _instance_service._get_expert_instance(instance_id, db)
    _skill_service.delete_skill(instance, skill_slug)
    return ApiResponse(data={"status": "deleted"})


@router.post(
    "/instances/{instance_id}/skills/rescan",
    response_model=ApiResponse[list[ExpertSkillInfo]],
)
async def rescan_instance_skills(
    instance_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    await instance_member_service.check_instance_access(
        instance_id, current_user, InstanceRole.editor, db,
    )
    instance = await _instance_service._get_expert_instance(instance_id, db)
    return ApiResponse(data=_skill_service.rescan_skills(instance))
