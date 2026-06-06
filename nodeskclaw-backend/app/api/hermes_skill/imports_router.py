import uuid
from typing import Any

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_db, require_org_admin
from app.core.exceptions import NotFoundError
from app.models.hermes_skill.skill_import import HermesSkillImport
from app.services.hermes_skill.git_importer import GitImporter

router = APIRouter()


def _ok(data: Any = None, message: str = "success") -> dict:
    return {"code": 0, "message": message, "data": data}


@router.post("/skill-imports/preview")
async def preview_import(
    source_url: str,
    source_type: str = "github",
    branch: str = "main",
    target_category: str = "",
    user_org=Depends(require_org_admin),
    db: AsyncSession = Depends(get_db),
):
    user, org = user_org
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
    return _ok({"id": import_record.id, "status": import_record.status})


@router.post("/skill-imports")
async def execute_import(
    import_id: str,
    user_org=Depends(require_org_admin),
    db: AsyncSession = Depends(get_db),
):
    _, org = user_org
    importer = GitImporter(db)
    import_record = await importer.execute_import(import_id, org.id)
    await db.commit()
    return _ok({
        "id": import_record.id,
        "status": import_record.status,
        "imported_skills": import_record.imported_skills,
        "failed_skills": import_record.failed_skills,
    })


@router.get("/skill-imports/{import_id}")
async def get_import(
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
