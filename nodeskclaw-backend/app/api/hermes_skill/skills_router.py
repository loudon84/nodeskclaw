import uuid
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_db, require_org_admin, require_org_member
from app.core.exceptions import NotFoundError, ConflictError, ForbiddenError
from app.models.base import not_deleted
from app.models.hermes_skill.skill import HermesSkill
from app.models.hermes_skill.skill_installation import HermesSkillInstallation
from app.models.hermes_skill.skill_release import HermesSkillRelease, SkillReleaseStatus
from app.schemas.hermes_skill.skill import (
    SkillRead,
    SkillCreate,
    SkillUpdate,
    SkillForkBody,
    SkillPublishBody,
    SkillExportRequest,
    SkillImportRequest,
    SkillValidateRequest,
    SkillFilterParams,
    SkillListResult,
    ScanTriggerResult,
)
from app.schemas.hermes_skill.common import READ_ONLY_SOURCE_TYPES
from app.services.hermes_skill.skill_scanner import SkillScanner, ScanError
from app.services.hermes_skill.permission_checker import PermissionChecker
from app.services.hermes_skill.skill_release_service import SkillReleaseService

router = APIRouter()


def _ok(data: Any = None, message: str = "success") -> dict:
    return {"code": 0, "message": message, "data": data}


async def _enrich_skill_read(db: AsyncSession, skill: HermesSkill) -> dict:
    data = SkillRead.model_validate(skill).model_dump()
    published = await SkillReleaseService(db).get_published_by_skill_db_id(skill.id)
    if published:
        data["published_version"] = published.version
        data["published_release_status"] = published.status
        data["published_release_id"] = published.id
        data["published_digest"] = published.digest
    draft = await db.execute(
        select(HermesSkillRelease.id).where(
            not_deleted(HermesSkillRelease),
            HermesSkillRelease.skill_db_id == skill.id,
            HermesSkillRelease.status == SkillReleaseStatus.DRAFT.value,
        ).limit(1)
    )
    data["has_draft_release"] = draft.scalar_one_or_none() is not None
    return data


@router.get("/skills")
async def list_skills(
    source_type: str | None = None,
    is_active: bool | None = None,
    is_mcp_exposed: bool | None = None,
    category: str | None = None,
    agent_type: str | None = None,
    keyword: str | None = None,
    page: int = 1,
    page_size: int = 20,
    user_org=Depends(require_org_member),
    db: AsyncSession = Depends(get_db),
):
    _, org = user_org
    query = select(HermesSkill).where(
        not_deleted(HermesSkill),
        HermesSkill.org_id == org.id,
    )
    count_query = select(func.count()).select_from(HermesSkill).where(
        not_deleted(HermesSkill),
        HermesSkill.org_id == org.id,
    )

    if source_type:
        query = query.where(HermesSkill.source_type == source_type)
        count_query = count_query.where(HermesSkill.source_type == source_type)
    if is_active is not None:
        query = query.where(HermesSkill.is_active == is_active)
        count_query = count_query.where(HermesSkill.is_active == is_active)
    if is_mcp_exposed is not None:
        query = query.where(HermesSkill.is_mcp_exposed == is_mcp_exposed)
        count_query = count_query.where(HermesSkill.is_mcp_exposed == is_mcp_exposed)
    if category:
        query = query.where(HermesSkill.category == category)
        count_query = count_query.where(HermesSkill.category == category)
    if agent_type:
        query = query.where(HermesSkill.agent_type == agent_type)
        count_query = count_query.where(HermesSkill.agent_type == agent_type)
    if keyword:
        pattern = f"%{keyword}%"
        kw_filter = HermesSkill.name.ilike(pattern) | HermesSkill.skill_id.ilike(pattern)
        query = query.where(kw_filter)
        count_query = count_query.where(kw_filter)

    total = (await db.execute(count_query)).scalar() or 0
    offset = (page - 1) * page_size
    query = query.order_by(HermesSkill.created_at.desc()).offset(offset).limit(page_size)

    result = await db.execute(query)
    items = [await _enrich_skill_read(db, s) for s in result.scalars().all()]

    return _ok(SkillListResult(items=items, total=total, page=page, page_size=page_size).model_dump())


@router.get("/skills/{skill_db_id}")
async def get_skill(
    skill_db_id: str,
    user_org=Depends(require_org_member),
    db: AsyncSession = Depends(get_db),
):
    _, org = user_org
    skill = await db.get(HermesSkill, skill_db_id)
    if not skill or skill.deleted_at is not None or skill.org_id != org.id:
        raise NotFoundError("Skill 不存在", "errors.skill.not_found")
    return _ok(await _enrich_skill_read(db, skill))


class SkillOutputPolicyBody(BaseModel):
    artifact_mode: str | None = None
    store_to_gateway: bool | None = None
    format: str | None = None
    suggested_workspace_dir: str | None = None
    filename_template: str | None = None
    kb_ingest: dict | None = None


@router.patch("/skills/{skill_db_id}/output-policy")
async def update_skill_output_policy(
    skill_db_id: str,
    body: SkillOutputPolicyBody,
    user_org=Depends(require_org_admin),
    db: AsyncSession = Depends(get_db),
):
    _, org = user_org
    skill = await db.get(HermesSkill, skill_db_id)
    if not skill or skill.deleted_at is not None or skill.org_id != org.id:
        raise NotFoundError("Skill 不存在", "errors.skill.not_found")
    policy = dict(skill.output_policy or {})
    payload = body.model_dump(exclude_none=True)
    policy.update(payload)
    policy["artifact_mode"] = "pull_only"
    skill.output_policy = policy
    await db.flush()
    await db.commit()
    return _ok({"skill_id": skill.id, "output_policy": skill.output_policy})


@router.post("/skills/scan")
async def trigger_scan(
    source_types: list[str] = Query(None),
    user_org=Depends(require_org_admin),
    db: AsyncSession = Depends(get_db),
):
    user, org = user_org
    if user:
        await PermissionChecker.require_permission(db, user.id, org.id, "skill:scan")
    scanner = SkillScanner(db)
    result = await scanner.scan_all(org_id=org.id, source_types=source_types or None)
    scan_data = ScanTriggerResult(
        scanned_count=result.scanned_count,
        added_count=result.added_count,
        updated_count=result.updated_count,
        deleted_count=result.deleted_count,
        failed_count=result.failed_count,
        is_partial=result.is_partial,
    ).model_dump()
    scan_data["errors"] = [
        {"path": e.path, "message": e.message} for e in result.errors
    ]
    return _ok(scan_data)


@router.post("/skills/{skill_db_id}/enable")
async def enable_skill(
    skill_db_id: str,
    user_org=Depends(require_org_admin),
    db: AsyncSession = Depends(get_db),
):
    _, org = user_org
    skill = await db.get(HermesSkill, skill_db_id)
    if not skill or skill.deleted_at is not None or skill.org_id != org.id:
        raise NotFoundError("Skill 不存在", "errors.skill.not_found")
    skill.is_active = True
    await db.commit()
    await db.refresh(skill)
    return _ok(SkillRead.model_validate(skill).model_dump())


@router.post("/skills/{skill_db_id}/disable")
async def disable_skill(
    skill_db_id: str,
    user_org=Depends(require_org_admin),
    db: AsyncSession = Depends(get_db),
):
    _, org = user_org
    skill = await db.get(HermesSkill, skill_db_id)
    if not skill or skill.deleted_at is not None or skill.org_id != org.id:
        raise NotFoundError("Skill 不存在", "errors.skill.not_found")
    skill.is_active = False
    await db.commit()
    await db.refresh(skill)
    return _ok(SkillRead.model_validate(skill).model_dump())


@router.post("/skills")
async def create_skill(
    body: SkillCreate,
    user_org=Depends(require_org_admin),
    db: AsyncSession = Depends(get_db),
):
    user, org = user_org
    if user:
        await PermissionChecker.require_permission(db, user.id, org.id, "skill:create")

    # Check for existing skill with same skill_id in org
    existing = await db.execute(
        select(HermesSkill).where(
            not_deleted(HermesSkill),
            HermesSkill.org_id == org.id,
            HermesSkill.skill_id == body.skill_id,
        )
    )
    if existing.scalar_one_or_none():
        raise ConflictError(f"Skill ID 已存在: {body.skill_id}", "errors.skill.already_exists")

    skill = HermesSkill(
        id=str(uuid.uuid4()),
        org_id=org.id,
        skill_id=body.skill_id,
        name=body.name,
        tool_name=body.tool_name or body.skill_id,
        title=body.title,
        description=body.description,
        version=body.version,
        agent_type=body.agent_type,
        category=body.category,
        runtime=body.runtime,
        source_type="central",
        is_active=True,
        is_mcp_exposed=body.is_mcp_exposed,
        input_schema=body.input_schema or {},
        output_schema=body.output_schema or {},
        output_policy=body.output_policy or {},
        tags=body.tags or [],
        extra_metadata=body.extra_metadata or {},
        created_by=user.id if user else None,
    )
    db.add(skill)
    await db.flush()

    # Create draft release
    release_svc = SkillReleaseService(db)
    await release_svc.create_draft_from_skill(
        org_id=org.id,
        skill_id=skill.skill_id,
        operator_user_id=user.id if user else "system",
        notes="Initial draft",
        version=skill.version,
    )
    await db.commit()
    await db.refresh(skill)
    return _ok(await _enrich_skill_read(db, skill))


@router.patch("/skills/{skill_db_id}")
async def update_skill(
    skill_db_id: str,
    body: SkillUpdate,
    user_org=Depends(require_org_admin),
    db: AsyncSession = Depends(get_db),
):
    user, org = user_org
    if user:
        await PermissionChecker.require_permission(db, user.id, org.id, "skill:update")

    skill = await db.get(HermesSkill, skill_db_id)
    if not skill or skill.deleted_at is not None or skill.org_id != org.id:
        raise NotFoundError("Skill 不存在", "errors.skill.not_found")

    payload = body.model_dump(exclude_unset=True)
    for field, val in payload.items():
        setattr(skill, field, val)

    await db.commit()
    await db.refresh(skill)
    return _ok(await _enrich_skill_read(db, skill))


@router.post("/skills/{skill_db_id}/publish")
async def publish_skill(
    skill_db_id: str,
    body: SkillPublishBody | None = None,
    user_org=Depends(require_org_admin),
    db: AsyncSession = Depends(get_db),
):
    user, org = user_org
    if user:
        await PermissionChecker.require_permission(db, user.id, org.id, "skill:publish")

    skill = await db.get(HermesSkill, skill_db_id)
    if not skill or skill.deleted_at is not None or skill.org_id != org.id:
        raise NotFoundError("Skill 不存在", "errors.skill.not_found")

    release_svc = SkillReleaseService(db)
    # Find draft release or create one
    draft_res = await db.execute(
        select(HermesSkillRelease).where(
            not_deleted(HermesSkillRelease),
            HermesSkillRelease.skill_db_id == skill.id,
            HermesSkillRelease.status == SkillReleaseStatus.DRAFT.value,
        ).order_by(HermesSkillRelease.created_at.desc()).limit(1)
    )
    draft = draft_res.scalar_one_or_none()
    if not draft:
        draft = await release_svc.create_draft_from_skill(
            org_id=org.id,
            skill_id=skill.skill_id,
            operator_user_id=user.id if user else "system",
            notes=(body.notes if body else None) or "Auto draft for publish",
            version=(body.version if body else None) or skill.version,
        )

    published = await release_svc.publish(
        org_id=org.id,
        skill_id=skill.skill_id,
        release_id=draft.id,
        operator_user_id=user.id if user else "system",
    )
    skill.is_active = True
    await db.commit()
    await db.refresh(skill)
    data = await _enrich_skill_read(db, skill)
    data["published_release"] = {
        "id": published.id,
        "version": published.version,
        "digest": published.digest,
        "status": published.status,
    }
    return _ok(data)


@router.post("/skills/{skill_db_id}/archive")
async def archive_skill(
    skill_db_id: str,
    user_org=Depends(require_org_admin),
    db: AsyncSession = Depends(get_db),
):
    user, org = user_org
    if user:
        await PermissionChecker.require_permission(db, user.id, org.id, "skill:archive")

    skill = await db.get(HermesSkill, skill_db_id)
    if not skill or skill.deleted_at is not None or skill.org_id != org.id:
        raise NotFoundError("Skill 不存在", "errors.skill.not_found")

    skill.is_active = False
    skill.is_mcp_exposed = False
    # Deprecate published releases
    release_svc = SkillReleaseService(db)
    published = await release_svc.get_published_by_skill_db_id(skill.id)
    if published:
        await release_svc.deprecate(org_id=org.id, skill_id=skill.skill_id, release_id=published.id)

    await db.commit()
    await db.refresh(skill)
    return _ok(await _enrich_skill_read(db, skill))


@router.post("/skills/{skill_db_id}/fork")
async def fork_skill(
    skill_db_id: str,
    body: SkillForkBody,
    user_org=Depends(require_org_admin),
    db: AsyncSession = Depends(get_db),
):
    user, org = user_org
    if user:
        await PermissionChecker.require_permission(db, user.id, org.id, "skill:create")

    skill = await db.get(HermesSkill, skill_db_id)
    if not skill or skill.deleted_at is not None or skill.org_id != org.id:
        raise NotFoundError("Skill 不存在", "errors.skill.not_found")

    existing = await db.execute(
        select(HermesSkill).where(
            not_deleted(HermesSkill),
            HermesSkill.org_id == org.id,
            HermesSkill.skill_id == body.target_skill_id,
        )
    )
    if existing.scalar_one_or_none():
        raise ConflictError(f"目标 Skill ID 已存在: {body.target_skill_id}", "errors.skill.already_exists")

    forked = HermesSkill(
        id=str(uuid.uuid4()),
        org_id=org.id,
        skill_id=body.target_skill_id,
        name=body.target_name or f"{skill.name} (Fork)",
        tool_name=body.target_skill_id,
        title=skill.title,
        description=skill.description,
        version="1.0.0",
        agent_type=skill.agent_type,
        category=skill.category,
        runtime=skill.runtime,
        source_type="central",
        is_active=True,
        is_mcp_exposed=False,
        input_schema=dict(skill.input_schema or {}),
        output_schema=dict(skill.output_schema or {}),
        output_policy=dict(skill.output_policy or {}),
        tags=list(skill.tags or []),
        extra_metadata=dict(skill.extra_metadata or {}),
        created_by=user.id if user else None,
    )
    db.add(forked)
    await db.flush()

    release_svc = SkillReleaseService(db)
    await release_svc.create_draft_from_skill(
        org_id=org.id,
        skill_id=forked.skill_id,
        operator_user_id=user.id if user else "system",
        notes=f"Forked from {skill.skill_id}",
        version=forked.version,
    )
    await db.commit()
    await db.refresh(forked)
    return _ok(await _enrich_skill_read(db, forked))


@router.post("/skills/export")
async def export_skills(
    body: SkillExportRequest,
    user_org=Depends(require_org_member),
    db: AsyncSession = Depends(get_db),
):
    _, org = user_org
    query = select(HermesSkill).where(
        not_deleted(HermesSkill),
        HermesSkill.org_id == org.id,
    )
    if body.skill_db_ids:
        query = query.where(HermesSkill.id.in_(body.skill_db_ids))
    elif body.skill_ids:
        query = query.where(HermesSkill.skill_id.in_(body.skill_ids))

    result = await db.execute(query)
    skills = result.scalars().all()
    exported = []
    for s in skills:
        exported.append({
            "skill_id": s.skill_id,
            "name": s.name,
            "tool_name": s.tool_name,
            "title": s.title,
            "description": s.description,
            "version": s.version,
            "agent_type": s.agent_type,
            "category": s.category,
            "runtime": s.runtime,
            "input_schema": s.input_schema,
            "output_schema": s.output_schema,
            "output_policy": s.output_policy,
            "tags": s.tags,
            "extra_metadata": s.extra_metadata,
        })
    return _ok({"skills": exported, "total": len(exported)})


@router.post("/skills/import")
async def import_skills(
    body: SkillImportRequest,
    user_org=Depends(require_org_admin),
    db: AsyncSession = Depends(get_db),
):
    user, org = user_org
    if user:
        await PermissionChecker.require_permission(db, user.id, org.id, "skill:create")

    imported_ids = []
    for item in body.skills:
        skill_id = item.get("skill_id")
        if not skill_id:
            continue
        existing_res = await db.execute(
            select(HermesSkill).where(
                not_deleted(HermesSkill),
                HermesSkill.org_id == org.id,
                HermesSkill.skill_id == skill_id,
            )
        )
        existing = existing_res.scalar_one_or_none()
        if existing and not body.override:
            continue
        if existing and body.override:
            existing.name = item.get("name", existing.name)
            existing.tool_name = item.get("tool_name", existing.tool_name)
            existing.title = item.get("title", existing.title)
            existing.description = item.get("description", existing.description)
            existing.version = item.get("version", existing.version)
            existing.category = item.get("category", existing.category)
            existing.agent_type = item.get("agent_type", existing.agent_type)
            existing.runtime = item.get("runtime", existing.runtime)
            existing.input_schema = item.get("input_schema", existing.input_schema)
            existing.output_schema = item.get("output_schema", existing.output_schema)
            existing.output_policy = item.get("output_policy", existing.output_policy)
            existing.tags = item.get("tags", existing.tags)
            existing.extra_metadata = item.get("extra_metadata", existing.extra_metadata)
            imported_ids.append(existing.skill_id)
        else:
            skill = HermesSkill(
                id=str(uuid.uuid4()),
                org_id=org.id,
                skill_id=skill_id,
                name=item.get("name", skill_id),
                tool_name=item.get("tool_name", skill_id),
                title=item.get("title"),
                description=item.get("description"),
                version=item.get("version", "1.0.0"),
                agent_type=item.get("agent_type"),
                category=item.get("category"),
                runtime=item.get("runtime"),
                source_type="central",
                is_active=True,
                is_mcp_exposed=item.get("is_mcp_exposed", False),
                input_schema=item.get("input_schema") or {},
                output_schema=item.get("output_schema") or {},
                output_policy=item.get("output_policy") or {},
                tags=item.get("tags") or [],
                extra_metadata=item.get("extra_metadata") or {},
                created_by=user.id if user else None,
            )
            db.add(skill)
            await db.flush()
            release_svc = SkillReleaseService(db)
            await release_svc.create_draft_from_skill(
                org_id=org.id,
                skill_id=skill.skill_id,
                operator_user_id=user.id if user else "system",
                notes="Imported skill",
                version=skill.version,
            )
            imported_ids.append(skill.skill_id)

    await db.commit()
    return _ok({"imported": imported_ids, "count": len(imported_ids)})


@router.get("/skills/{skill_db_id}/versions")
async def list_skill_versions(
    skill_db_id: str,
    user_org=Depends(require_org_member),
    db: AsyncSession = Depends(get_db),
):
    _, org = user_org
    skill = await db.get(HermesSkill, skill_db_id)
    if not skill or skill.deleted_at is not None or skill.org_id != org.id:
        raise NotFoundError("Skill 不存在", "errors.skill.not_found")

    release_svc = SkillReleaseService(db)
    releases = await release_svc.list_releases(org.id, skill.skill_id)
    items = []
    for r in releases:
        items.append({
            "id": r.id,
            "version": r.version,
            "status": r.status,
            "digest": r.digest,
            "notes": r.notes,
            "published_at": r.published_at,
            "deprecated_at": r.deprecated_at,
            "created_at": r.created_at,
        })
    return _ok({"items": items, "total": len(items)})


@router.post("/skills/validate")
async def validate_skill(
    body: SkillValidateRequest,
    user_org=Depends(require_org_member),
):
    errors = []
    if not body.skill_id or not body.skill_id.strip():
        errors.append("skill_id 不能为空")
    if body.input_schema and not isinstance(body.input_schema, dict):
        errors.append("input_schema 必须为字典结构")
    if body.output_schema and not isinstance(body.output_schema, dict):
        errors.append("output_schema 必须为字典结构")

    return _ok({
        "valid": len(errors) == 0,
        "errors": errors,
    })


@router.delete("/skills/{skill_db_id}")
async def delete_skill(
    skill_db_id: str,
    user_org=Depends(require_org_admin),
    db: AsyncSession = Depends(get_db),
):
    _, org = user_org
    skill = await db.get(HermesSkill, skill_db_id)
    if not skill or skill.deleted_at is not None or skill.org_id != org.id:
        raise NotFoundError("Skill 不存在", "errors.skill.not_found")

    active_install = await db.execute(
        select(HermesSkillInstallation).where(
            not_deleted(HermesSkillInstallation),
            HermesSkillInstallation.skill_id == skill.skill_id,
            HermesSkillInstallation.status == "installed",
        )
    )
    if active_install.scalar_one_or_none():
        raise ConflictError("存在活跃安装，无法删除", "errors.skill.has_active_installations")

    skill.soft_delete()
    await db.commit()
    return _ok()
