from typing import Any

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_db, require_org_admin, require_org_member
from app.core.exceptions import NotFoundError
from app.models.base import not_deleted
from app.models.hermes_skill.hermes_task import HermesTask, TaskStatus
from app.models.hermes_skill.skill import HermesSkill
from app.models.hermes_skill.skill_installation import HermesSkillInstallation
from app.models.hermes_skill.skill_import import HermesSkillImport
from app.schemas.hermes_skill.skill import SkillRead
from app.schemas.hermes_skill.skill_installation import (
    InstallationCreate,
    InstallationRead,
)
from app.schemas.hermes_skill.task import TaskRead, TaskListResult
from app.services.hermes_skill.skill_installer import SkillInstaller
from app.services.hermes_skill.skill_audit_logger import SkillAuditLogger
from app.services.hermes_skill.git_importer import GitImporter
from app.services.hermes_skill.task_service import TaskService
from app.services.hermes_skill.permission_checker import PermissionChecker

router = APIRouter()


def _ok(data: Any = None, message: str = "success") -> dict:
    return {"code": 0, "message": message, "data": data}


@router.get("/installations")
async def list_installations_compat(
    skill_id: str | None = None,
    agent_id: str | None = None,
    status: str | None = None,
    page: int = 1,
    page_size: int = 20,
    user_org=Depends(require_org_member),
    db: AsyncSession = Depends(get_db),
):
    _, org = user_org
    query = select(HermesSkillInstallation).where(
        not_deleted(HermesSkillInstallation),
        HermesSkillInstallation.org_id == org.id,
    )
    count_query = select(func.count()).select_from(HermesSkillInstallation).where(
        not_deleted(HermesSkillInstallation),
        HermesSkillInstallation.org_id == org.id,
    )
    if skill_id:
        query = query.where(HermesSkillInstallation.skill_id == skill_id)
        count_query = count_query.where(HermesSkillInstallation.skill_id == skill_id)
    if agent_id:
        query = query.where(HermesSkillInstallation.agent_id == agent_id)
        count_query = count_query.where(HermesSkillInstallation.agent_id == agent_id)
    if status:
        query = query.where(HermesSkillInstallation.status == status)
        count_query = count_query.where(HermesSkillInstallation.status == status)

    total = (await db.execute(count_query)).scalar() or 0
    offset = (page - 1) * page_size
    query = query.order_by(HermesSkillInstallation.created_at.desc()).offset(offset).limit(page_size)
    result = await db.execute(query)
    items = [InstallationRead.model_validate(i).model_dump() for i in result.scalars().all()]
    return _ok({"items": items, "total": total, "page": page, "page_size": page_size})


@router.post("/installations")
async def create_installation_compat(
    body: InstallationCreate,
    user_org=Depends(require_org_admin),
    db: AsyncSession = Depends(get_db),
):
    user, org = user_org
    if user:
        await PermissionChecker.require_permission(db, user.id, org.id, "skill:install")
    installer = SkillInstaller(db)
    installation = await installer.install(
        skill_id=body.skill_id,
        agent_id=body.agent_id,
        org_id=org.id,
        profile_id=body.profile_id,
        workspace_id=body.workspace_id,
        install_mode=body.install_mode,
        conflict_strategy=body.conflict_strategy,
        installed_by=user.id if user else None,
    )
    await db.commit()
    return _ok(InstallationRead.model_validate(installation).model_dump())


@router.delete("/installations/{installation_id}")
async def delete_installation_compat(
    installation_id: str,
    user_org=Depends(require_org_admin),
    db: AsyncSession = Depends(get_db),
):
    _, org = user_org
    installer = SkillInstaller(db)
    installation = await installer.uninstall(installation_id, org.id)
    await db.commit()
    return _ok(InstallationRead.model_validate(installation).model_dump())


@router.post("/installations/{installation_id}/sync")
async def sync_installation_compat(
    installation_id: str,
    user_org=Depends(require_org_admin),
    db: AsyncSession = Depends(get_db),
):
    user, org = user_org
    if user:
        await PermissionChecker.require_permission(db, user.id, org.id, "skill:install")
    installer = SkillInstaller(db)
    installation = await installer.sync_installation(installation_id, org.id)
    await db.commit()
    return _ok(InstallationRead.model_validate(installation).model_dump())


@router.patch("/skills/{skill_id}")
async def toggle_skill_compat(
    skill_id: str,
    body: dict,
    user_org=Depends(require_org_admin),
    db: AsyncSession = Depends(get_db),
):
    user, org = user_org
    is_active = body.get("is_active")
    if is_active is None:
        from app.core.exceptions import BadRequestError
        raise BadRequestError("is_active 必填", "errors.skill.is_active_required")

    skill = await db.get(HermesSkill, skill_id)
    if not skill or skill.deleted_at is not None or skill.org_id != org.id:
        raise NotFoundError("Skill 不存在", "errors.skill.not_found")

    skill.is_active = is_active
    await db.flush()
    await db.refresh(skill)

    audit_logger = SkillAuditLogger(db)
    action = "hermes.skill.installed" if is_active else "hermes.skill.uninstalled"
    await audit_logger.log(
        action=action,
        target_id=skill.id,
        org_id=org.id,
        actor_id=user.id if user else "",
        details={"skill_id": skill.skill_id, "is_active": is_active},
    )
    await db.commit()
    return _ok(SkillRead.model_validate(skill).model_dump())


@router.get("/tasks")
async def list_tasks_compat(
    status: str | None = None,
    skill_id: str | None = None,
    tool_name: str | None = None,
    agent_id: str | None = None,
    profile_id: str | None = None,
    workspace_id: str | None = None,
    user_id: str | None = None,
    page: int = 1,
    page_size: int = 20,
    user_org=Depends(require_org_member),
    db: AsyncSession = Depends(get_db),
):
    _, org = user_org
    service = TaskService(db)
    tasks, total = await service.list_tasks(
        org_id=org.id,
        skill_id=skill_id,
        status=status,
        tool_name=tool_name,
        agent_id=agent_id,
        profile_id=profile_id,
        workspace_id=workspace_id,
        user_id=user_id,
        page=page,
        page_size=page_size,
    )
    items = [TaskRead.model_validate(t).model_dump() for t in tasks]
    return _ok(TaskListResult(items=items, total=total, page=page, page_size=page_size).model_dump())


@router.post("/imports/preview")
async def preview_import_compat(
    source_url: str,
    source_type: str = "github",
    branch: str = "main",
    target_category: str = "",
    user_org=Depends(require_org_admin),
    db: AsyncSession = Depends(get_db),
):
    user, org = user_org
    if user:
        await PermissionChecker.require_permission(db, user.id, org.id, "skill:import")
    importer = GitImporter(db)
    import_record = await importer.preview(
        org_id=org.id,
        source_url=source_url,
        source_type=source_type,
        branch=branch,
        target_category=target_category,
        created_by=user.id if user else None,
    )
    await db.commit()

    skills = import_record.details.get("skills", []) if import_record.details else []
    return _ok({
        "import_id": import_record.id,
        "status": import_record.status,
        "skills": skills,
        "total_skills": import_record.total_skills,
        "failed_skills": import_record.failed_skills,
    })


@router.post("/imports/execute")
async def execute_import_compat(
    body: dict,
    user_org=Depends(require_org_admin),
    db: AsyncSession = Depends(get_db),
):
    user, org = user_org
    if user:
        await PermissionChecker.require_permission(db, user.id, org.id, "skill:import")
    import_id = body.get("import_id")
    selected_skill_ids = body.get("selected_skill_ids")
    conflict_strategy = body.get("conflict_strategy", "install_as_new_version")

    if not import_id:
        from app.core.exceptions import BadRequestError
        raise BadRequestError("import_id 必填", "errors.skill.import_id_required")

    importer = GitImporter(db)
    import_record = await importer.execute_import(
        import_id,
        org.id,
        selected_skill_ids=selected_skill_ids,
    )
    await db.commit()
    return _ok({
        "id": import_record.id,
        "status": import_record.status,
        "imported_skills": import_record.imported_skills,
        "failed_skills": import_record.failed_skills,
    })


@router.get("/imports/{import_id}")
async def get_import_compat(
    import_id: str,
    user_org=Depends(require_org_admin),
    db: AsyncSession = Depends(get_db),
):
    _, org = user_org
    import_record = await db.get(HermesSkillImport, import_id)
    if not import_record or import_record.org_id != org.id:
        raise NotFoundError("导入记录不存在", "errors.skill.import_not_found")
    return _ok({
        "id": import_record.id,
        "status": import_record.status,
        "source_url": import_record.source_url,
        "total_skills": import_record.total_skills,
        "imported_skills": import_record.imported_skills,
        "failed_skills": import_record.failed_skills,
    })
