"""GeneHub skill management and entitlement resolution."""

import json
import logging
import uuid
from datetime import datetime, timezone

from sqlalchemy import and_, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import BadRequestError, ConflictError, ForbiddenError, NotFoundError
from app.models.desktop_hermes_profile import DesktopHermesProfile
from app.models.gene import ContentVisibility, Gene, GeneReviewStatus, GeneSource
from app.models.genehub_entitlement import (
    EntitlementPermission,
    EntitlementTargetType,
    GeneHubEntitlement,
)
from app.models.hermes_installed_skill import HermesInstalledSkill, InstalledSkillStatus
from app.models.hermes_skill_install_job import (
    ACTIVE_JOB_STATUSES,
    HermesSkillInstallJob,
    InstallJobStatus,
    InstallJobType,
    InstallMode,
)
from app.models.org_membership import OrgMembership
from app.schemas.genehub import (
    AdminGeneHubSkillCreate,
    AdminGeneHubSkillInfo,
    AdminGeneHubSkillUpdate,
    AdminInstallJobAssignResult,
    AdminInstallJobInfo,
    CompatibilityItem,
    DesktopSkillInfo,
    GeneHubEntitlementTarget,
)
from app.services.genehub_bundle_service import (
    build_manifest_from_skill,
    is_hermes_desktop_compatible,
)
from app.services.hermes_skill.skill_audit_logger import SkillAuditLogger

logger = logging.getLogger(__name__)

VIEW_PERMISSIONS = frozenset({
    EntitlementPermission.view,
    EntitlementPermission.install,
    EntitlementPermission.update,
    EntitlementPermission.uninstall,
})


async def _get_genehub_gene(db: AsyncSession, gene_id: str, org_id: str) -> Gene:
    result = await db.execute(
        select(Gene).where(
            Gene.id == gene_id,
            Gene.org_id == org_id,
            Gene.deleted_at.is_(None),
        )
    )
    gene = result.scalar_one_or_none()
    if not gene:
        raise NotFoundError(
            "Skill 不存在",
            message_key="errors.genehub.skill_not_found",
        )
    return gene


async def _get_published_gene_by_slug(
    db: AsyncSession,
    *,
    org_id: str,
    slug: str,
    version: str = "latest",
) -> Gene:
    query = select(Gene).where(
        Gene.slug == slug,
        Gene.deleted_at.is_(None),
        Gene.is_published.is_(True),
        Gene.review_status == GeneReviewStatus.approved,
        or_(Gene.org_id == org_id, Gene.visibility == ContentVisibility.public),
    )
    if version and version != "latest":
        query = query.where(Gene.version == version)
    result = await db.execute(query.order_by(Gene.updated_at.desc()))
    gene = result.scalars().first()
    if not gene:
        raise NotFoundError(
            "Skill 不存在或未发布",
            message_key="errors.genehub.skill_not_found",
        )
    manifest = json.loads(gene.manifest) if gene.manifest else {}
    if not is_hermes_desktop_compatible(manifest):
        raise BadRequestError(
            "Skill 不支持 Hermes Desktop",
            message_key="errors.genehub.unsupported_runtime",
        )
    return gene


def _parse_tags(tags_raw: str | None) -> list[str]:
    if not tags_raw:
        return []
    try:
        parsed = json.loads(tags_raw)
        return parsed if isinstance(parsed, list) else []
    except json.JSONDecodeError:
        return []


async def create_skill(
    db: AsyncSession,
    *,
    org_id: str,
    user_id: str,
    data: AdminGeneHubSkillCreate,
) -> AdminGeneHubSkillInfo:
    manifest = build_manifest_from_skill(data)
    gene = Gene(
        id=str(uuid.uuid4()),
        name=data.name,
        slug=data.slug,
        description=data.description,
        short_description=data.short_description,
        category=data.category,
        tags=json.dumps(data.tags, ensure_ascii=False),
        source=GeneSource.manual,
        source_registry="local",
        version=data.version,
        manifest=json.dumps(manifest, ensure_ascii=False),
        review_status=GeneReviewStatus.pending_admin,
        is_published=False,
        created_by=user_id,
        org_id=org_id,
        visibility=data.visibility,
    )
    db.add(gene)
    await db.flush()

    audit = SkillAuditLogger(db)
    await audit.log(
        action="genehub.skill.create",
        target_id=gene.id,
        org_id=org_id,
        actor_id=user_id,
        details={"slug": gene.slug, "version": gene.version},
    )
    return AdminGeneHubSkillInfo.model_validate(gene)


async def update_skill(
    db: AsyncSession,
    *,
    gene_id: str,
    org_id: str,
    user_id: str,
    data: AdminGeneHubSkillUpdate,
) -> AdminGeneHubSkillInfo:
    gene = await _get_genehub_gene(db, gene_id, org_id)
    was_published = gene.is_published

    if data.name is not None:
        gene.name = data.name
    if data.description is not None:
        gene.description = data.description
    if data.short_description is not None:
        gene.short_description = data.short_description
    if data.category is not None:
        gene.category = data.category
    if data.tags is not None:
        gene.tags = json.dumps(data.tags, ensure_ascii=False)
    if data.version is not None:
        gene.version = data.version
    if data.visibility is not None:
        gene.visibility = data.visibility

    if any(v is not None for v in [data.skill_content, data.scripts, data.compatibility]):
        current_manifest = json.loads(gene.manifest) if gene.manifest else {}
        compatibility = data.compatibility
        if compatibility is None:
            compatibility = [
                CompatibilityItem(**item) for item in current_manifest.get("compatibility", [])
            ]
        create_data = AdminGeneHubSkillCreate(
            name=data.name or gene.name,
            slug=gene.slug,
            description=data.description if data.description is not None else gene.description,
            short_description=data.short_description if data.short_description is not None else gene.short_description,
            category=data.category if data.category is not None else gene.category,
            tags=data.tags if data.tags is not None else _parse_tags(gene.tags),
            version=data.version or gene.version,
            skill_content=data.skill_content or current_manifest.get("skill", {}).get("content", ""),
            scripts=data.scripts if data.scripts is not None else current_manifest.get("scripts", {}),
            compatibility=compatibility,
            visibility=data.visibility or gene.visibility,
        )
        manifest = build_manifest_from_skill(create_data)
        gene.manifest = json.dumps(manifest, ensure_ascii=False)

    if was_published:
        gene.is_published = False
        gene.review_status = GeneReviewStatus.pending_admin

    await db.flush()

    audit = SkillAuditLogger(db)
    await audit.log(
        action="genehub.skill.update",
        target_id=gene.id,
        org_id=org_id,
        actor_id=user_id,
        details={"slug": gene.slug, "reset_review": was_published},
    )
    return AdminGeneHubSkillInfo.model_validate(gene)


async def review_skill(
    db: AsyncSession,
    *,
    gene_id: str,
    org_id: str,
    user_id: str,
    action: str,
    reason: str | None = None,
) -> AdminGeneHubSkillInfo:
    gene = await _get_genehub_gene(db, gene_id, org_id)
    if action == "approve":
        gene.review_status = GeneReviewStatus.approved
    else:
        gene.review_status = GeneReviewStatus.rejected
        gene.is_published = False

    await db.flush()

    audit = SkillAuditLogger(db)
    await audit.log(
        action=f"genehub.skill.review.{action}",
        target_id=gene.id,
        org_id=org_id,
        actor_id=user_id,
        details={"reason": reason, "review_status": gene.review_status},
    )
    return AdminGeneHubSkillInfo.model_validate(gene)


async def publish_skill(
    db: AsyncSession,
    *,
    gene_id: str,
    org_id: str,
    user_id: str,
) -> AdminGeneHubSkillInfo:
    gene = await _get_genehub_gene(db, gene_id, org_id)
    if gene.review_status != GeneReviewStatus.approved:
        raise BadRequestError(
            "Skill 未通过审核",
            message_key="errors.genehub.skill_not_approved",
        )

    gene.is_published = True
    await db.flush()

    audit = SkillAuditLogger(db)
    await audit.log(
        action="genehub.skill.publish",
        target_id=gene.id,
        org_id=org_id,
        actor_id=user_id,
        details={"slug": gene.slug, "version": gene.version},
    )
    return AdminGeneHubSkillInfo.model_validate(gene)


async def grant_entitlements(
    db: AsyncSession,
    *,
    org_id: str,
    gene_id: str,
    targets: list,
    created_by: str,
) -> int:
    await _get_genehub_gene(db, gene_id, org_id)
    created_count = 0

    for target in targets:
        for permission in target.permissions:
            existing = await db.execute(
                select(GeneHubEntitlement).where(
                    GeneHubEntitlement.org_id == org_id,
                    GeneHubEntitlement.gene_id == gene_id,
                    GeneHubEntitlement.target_type == target.target_type,
                    GeneHubEntitlement.target_id == target.target_id,
                    GeneHubEntitlement.permission == permission,
                    GeneHubEntitlement.deleted_at.is_(None),
                )
            )
            if existing.scalar_one_or_none():
                continue

            entitlement = GeneHubEntitlement(
                id=str(uuid.uuid4()),
                org_id=org_id,
                gene_id=gene_id,
                target_type=target.target_type,
                target_id=target.target_id,
                permission=permission,
                profile_scope=target.profile_scope,
                created_by=created_by,
            )
            db.add(entitlement)
            created_count += 1

    await db.flush()
    return created_count


async def resolve_user_gene_permissions(
    db: AsyncSession,
    *,
    org_id: str,
    user_id: str,
    gene_id: str,
    profile_name: str | None = None,
) -> set[str]:
    membership_result = await db.execute(
        select(OrgMembership).where(
            OrgMembership.org_id == org_id,
            OrgMembership.user_id == user_id,
            OrgMembership.deleted_at.is_(None),
        )
    )
    membership = membership_result.scalar_one_or_none()

    target_specs: list[tuple[str, str]] = [
        (EntitlementTargetType.user, user_id),
        (EntitlementTargetType.organization, org_id),
    ]
    if membership:
        if membership.role:
            target_specs.append((EntitlementTargetType.role, membership.role))
        if membership.department:
            target_specs.append((EntitlementTargetType.department, membership.department))

    permissions: set[str] = set()
    for target_type, target_id in target_specs:
        result = await db.execute(
            select(GeneHubEntitlement).where(
                GeneHubEntitlement.org_id == org_id,
                GeneHubEntitlement.gene_id == gene_id,
                GeneHubEntitlement.target_type == target_type,
                GeneHubEntitlement.target_id == target_id,
                GeneHubEntitlement.deleted_at.is_(None),
            )
        )
        for entitlement in result.scalars().all():
            if entitlement.profile_scope and profile_name:
                if entitlement.profile_scope != profile_name:
                    continue
            permissions.add(entitlement.permission)

    if EntitlementPermission.install in permissions:
        permissions.add(EntitlementPermission.view)
    return permissions


async def _resolve_target_user_ids(
    db: AsyncSession,
    *,
    org_id: str,
    target_type: str,
    target_ids: list[str],
) -> list[str]:
    if target_type == EntitlementTargetType.user:
        return target_ids
    if target_type == EntitlementTargetType.organization:
        result = await db.execute(
            select(OrgMembership.user_id).where(
                OrgMembership.org_id == org_id,
                OrgMembership.deleted_at.is_(None),
            )
        )
        return list(result.scalars().all())
    return []


async def _find_active_job(
    db: AsyncSession,
    *,
    org_id: str,
    user_id: str,
    profile_id: str | None,
    gene_slug: str,
    job_type: str,
) -> HermesSkillInstallJob | None:
    query = select(HermesSkillInstallJob).where(
        HermesSkillInstallJob.org_id == org_id,
        HermesSkillInstallJob.user_id == user_id,
        HermesSkillInstallJob.gene_slug == gene_slug,
        HermesSkillInstallJob.job_type == job_type,
        HermesSkillInstallJob.status.in_(ACTIVE_JOB_STATUSES),
        HermesSkillInstallJob.deleted_at.is_(None),
    )
    if profile_id:
        query = query.where(
            or_(
                HermesSkillInstallJob.profile_id == profile_id,
                HermesSkillInstallJob.profile_id.is_(None),
            )
        )
    result = await db.execute(query)
    return result.scalars().first()


async def _create_install_job(
    db: AsyncSession,
    *,
    org_id: str,
    user_id: str,
    gene: Gene,
    job_type: str,
    install_mode: str,
    requested_by: str,
    profile_id: str | None = None,
    desktop_device_id: str | None = None,
) -> HermesSkillInstallJob:
    manifest = json.loads(gene.manifest) if gene.manifest else {}
    skill_name = manifest.get("skill", {}).get("name", gene.slug)

    existing = await _find_active_job(
        db,
        org_id=org_id,
        user_id=user_id,
        profile_id=profile_id,
        gene_slug=gene.slug,
        job_type=job_type,
    )
    if existing:
        return existing

    job = HermesSkillInstallJob(
        id=str(uuid.uuid4()),
        org_id=org_id,
        user_id=user_id,
        desktop_device_id=desktop_device_id,
        profile_id=profile_id,
        gene_id=gene.id,
        gene_slug=gene.slug,
        gene_version=gene.version,
        skill_name=skill_name,
        job_type=job_type,
        status=InstallJobStatus.pending,
        install_mode=install_mode,
        requested_by=requested_by,
    )
    db.add(job)
    await db.flush()
    return job


async def create_assign_jobs(
    db: AsyncSession,
    *,
    org_id: str,
    gene_slug: str,
    version: str,
    target_type: str,
    target_ids: list[str],
    profile_name: str | None,
    job_type: str,
    requested_by: str,
) -> AdminInstallJobAssignResult:
    gene = await _get_published_gene_by_slug(db, org_id=org_id, slug=gene_slug, version=version)
    user_ids = await _resolve_target_user_ids(
        db, org_id=org_id, target_type=target_type, target_ids=target_ids
    )

    created_jobs: list[HermesSkillInstallJob] = []
    created_count = 0
    skipped = 0

    for user_id in user_ids:
        profile_id = None
        desktop_device_id = None
        if profile_name:
            profile_result = await db.execute(
                select(DesktopHermesProfile).where(
                    DesktopHermesProfile.org_id == org_id,
                    DesktopHermesProfile.user_id == user_id,
                    DesktopHermesProfile.profile_name == profile_name,
                    DesktopHermesProfile.deleted_at.is_(None),
                )
            )
            profile = profile_result.scalar_one_or_none()
            if profile:
                profile_id = profile.id
                desktop_device_id = profile.desktop_device_id

        await grant_entitlements(
            db,
            org_id=org_id,
            gene_id=gene.id,
            targets=[
                GeneHubEntitlementTarget(
                    target_type=EntitlementTargetType.user,
                    target_id=user_id,
                    permissions=[
                        EntitlementPermission.view,
                        EntitlementPermission.install,
                        EntitlementPermission.update,
                        EntitlementPermission.uninstall,
                    ],
                    profile_scope=profile_name,
                )
            ],
            created_by=requested_by,
        )

        existing_before = await _find_active_job(
            db,
            org_id=org_id,
            user_id=user_id,
            profile_id=profile_id,
            gene_slug=gene.slug,
            job_type=job_type,
        )
        job = await _create_install_job(
            db,
            org_id=org_id,
            user_id=user_id,
            gene=gene,
            job_type=job_type,
            install_mode=InstallMode.assigned,
            requested_by=requested_by,
            profile_id=profile_id,
            desktop_device_id=desktop_device_id,
        )
        if existing_before:
            skipped += 1
        else:
            created_count += 1
        created_jobs.append(job)

    return AdminInstallJobAssignResult(
        created=created_count,
        skipped=skipped,
        jobs=[AdminInstallJobInfo.model_validate(job) for job in created_jobs],
    )


async def create_self_service_job(
    db: AsyncSession,
    *,
    org_id: str,
    user_id: str,
    profile_id: str,
    gene_slug: str,
    version: str,
    job_type: str,
) -> HermesSkillInstallJob:
    profile_result = await db.execute(
        select(DesktopHermesProfile).where(
            DesktopHermesProfile.id == profile_id,
            DesktopHermesProfile.user_id == user_id,
            DesktopHermesProfile.org_id == org_id,
            DesktopHermesProfile.deleted_at.is_(None),
        )
    )
    profile = profile_result.scalar_one_or_none()
    if not profile:
        raise NotFoundError(
            "Profile 不存在",
            message_key="errors.desktop.profile_not_found",
        )

    gene = await _get_published_gene_by_slug(db, org_id=org_id, slug=gene_slug, version=version)
    permissions = await resolve_user_gene_permissions(
        db,
        org_id=org_id,
        user_id=user_id,
        gene_id=gene.id,
        profile_name=profile.profile_name,
    )
    if EntitlementPermission.install not in permissions:
        raise ForbiddenError(
            "无安装权限",
            message_key="errors.genehub.install_job_permission_denied",
        )

    return await _create_install_job(
        db,
        org_id=org_id,
        user_id=user_id,
        gene=gene,
        job_type=job_type,
        install_mode=InstallMode.self_service,
        requested_by=user_id,
        profile_id=profile.id,
        desktop_device_id=profile.desktop_device_id,
    )


async def list_admin_install_jobs(
    db: AsyncSession,
    *,
    org_id: str,
    status: str | None = None,
    user_id: str | None = None,
) -> list[AdminInstallJobInfo]:
    query = select(HermesSkillInstallJob).where(
        HermesSkillInstallJob.org_id == org_id,
        HermesSkillInstallJob.deleted_at.is_(None),
    )
    if status:
        query = query.where(HermesSkillInstallJob.status == status)
    if user_id:
        query = query.where(HermesSkillInstallJob.user_id == user_id)
    result = await db.execute(query.order_by(HermesSkillInstallJob.created_at.desc()))
    return [AdminInstallJobInfo.model_validate(job) for job in result.scalars().all()]


async def list_desktop_visible_skills(
    db: AsyncSession,
    *,
    org_id: str,
    user_id: str,
    profile_id: str,
    keyword: str | None = None,
    category: str | None = None,
    tag: str | None = None,
) -> list[DesktopSkillInfo]:
    profile_result = await db.execute(
        select(DesktopHermesProfile).where(
            DesktopHermesProfile.id == profile_id,
            DesktopHermesProfile.user_id == user_id,
            DesktopHermesProfile.org_id == org_id,
            DesktopHermesProfile.deleted_at.is_(None),
        )
    )
    profile = profile_result.scalar_one_or_none()
    if not profile:
        raise NotFoundError(
            "Profile 不存在",
            message_key="errors.desktop.profile_not_found",
        )

    genes_result = await db.execute(
        select(Gene).where(
            Gene.deleted_at.is_(None),
            Gene.is_published.is_(True),
            Gene.review_status == GeneReviewStatus.approved,
            or_(Gene.org_id == org_id, Gene.visibility == ContentVisibility.public),
        )
    )
    visible_skills: list[DesktopSkillInfo] = []

    for gene in genes_result.scalars().all():
        manifest = json.loads(gene.manifest) if gene.manifest else {}
        if not is_hermes_desktop_compatible(manifest):
            continue

        permissions = await resolve_user_gene_permissions(
            db,
            org_id=org_id,
            user_id=user_id,
            gene_id=gene.id,
            profile_name=profile.profile_name,
        )
        if not permissions & VIEW_PERMISSIONS:
            continue

        if keyword and keyword.lower() not in f"{gene.name} {gene.slug} {gene.description or ''}".lower():
            continue
        if category and gene.category != category:
            continue
        tags = _parse_tags(gene.tags)
        if tag and tag not in tags:
            continue

        installed_result = await db.execute(
            select(HermesInstalledSkill).where(
                HermesInstalledSkill.profile_id == profile_id,
                HermesInstalledSkill.gene_slug == gene.slug,
                HermesInstalledSkill.deleted_at.is_(None),
            )
        )
        installed = installed_result.scalar_one_or_none()

        pending_result = await db.execute(
            select(HermesSkillInstallJob).where(
                HermesSkillInstallJob.profile_id == profile_id,
                HermesSkillInstallJob.gene_slug == gene.slug,
                HermesSkillInstallJob.status.in_(ACTIVE_JOB_STATUSES),
                HermesSkillInstallJob.deleted_at.is_(None),
            )
        )
        pending_job = pending_result.scalar_one_or_none()

        installed_status = "not_installed"
        update_available = False
        if pending_job:
            installed_status = "pending"
        elif installed and installed.status == InstalledSkillStatus.installed:
            installed_status = "installed"
            if installed.gene_version != gene.version:
                installed_status = "update_available"
                update_available = True
        elif installed and installed.status == InstalledSkillStatus.failed:
            installed_status = "failed"

        visible_skills.append(
            DesktopSkillInfo(
                gene_id=gene.id,
                slug=gene.slug,
                name=gene.name,
                description=gene.description,
                short_description=gene.short_description,
                version=gene.version,
                category=gene.category,
                tags=tags,
                permissions=sorted(permissions),
                installed_status=installed_status,
                update_available=update_available,
            )
        )

    return visible_skills
