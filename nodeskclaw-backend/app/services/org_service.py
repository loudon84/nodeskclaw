"""Organization CRUD + membership management service."""

import logging
import re

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import BadRequestError, ConflictError, ForbiddenError, NotFoundError
from app.models.admin_membership import AdminMembership
from app.models.base import not_deleted
from app.models.org_membership import OrgMembership, OrgRole
from app.models.organization import Organization
from app.models.user import User
from app.schemas.member import CreateHumanMemberRequest, UpdateMemberProfileRequest
from app.schemas.organization import MemberInfo, OrgCreate, OrgInfo, OrgUpdate

logger = logging.getLogger(__name__)

_SLUG_RE = re.compile(r"^[a-z0-9][a-z0-9\-]{1,62}[a-z0-9]$")


async def list_orgs(db: AsyncSession) -> list[OrgInfo]:
    """列出所有组织（超管使用），附带成员数（排除 Admin 平台用户）。"""
    admin_user_ids_corr = (
        select(AdminMembership.user_id)
        .where(AdminMembership.org_id == Organization.id, AdminMembership.deleted_at.is_(None))
        .correlate(Organization)
    )
    member_count_sub = (
        select(func.count(OrgMembership.id))
        .where(
            OrgMembership.org_id == Organization.id,
            not_deleted(OrgMembership),
            OrgMembership.user_id.notin_(admin_user_ids_corr),
        )
        .correlate(Organization)
        .scalar_subquery()
        .label("member_count")
    )
    result = await db.execute(
        select(Organization, member_count_sub)
        .where(not_deleted(Organization))
        .order_by(Organization.created_at.desc())
    )
    orgs = []
    for org, count in result.all():
        info = OrgInfo.model_validate(org)
        info.member_count = count or 0
        orgs.append(info)
    return orgs


async def get_org(org_id: str, db: AsyncSession) -> Organization:
    """获取组织详情，不存在抛 404。"""
    result = await db.execute(
        select(Organization).where(Organization.id == org_id, not_deleted(Organization))
    )
    org = result.scalar_one_or_none()
    if org is None:
        raise NotFoundError("组织不存在")
    return org


async def create_org(body: OrgCreate, creator: User, db: AsyncSession) -> OrgInfo:
    """创建组织，并把创建者设为 org_admin。"""
    if not _SLUG_RE.match(body.slug):
        raise BadRequestError("slug 格式不合法（小写字母/数字/短横线，3-64 字符）")

    # 唯一性检查
    exists = await db.execute(
        select(Organization).where(Organization.slug == body.slug, not_deleted(Organization))
    )
    if exists.scalar_one_or_none():
        raise ConflictError(
            f"企业标识符 '{body.slug}' 已被使用",
            message_key="errors.org.slug_already_taken",
        )

    org = Organization(name=body.name, slug=body.slug, plan=body.plan)
    db.add(org)
    await db.flush()

    # 创建者自动成为组织管理员
    membership = OrgMembership(user_id=creator.id, org_id=org.id, role=OrgRole.admin)
    db.add(membership)

    # 如果创建者还没有当前组织，自动切换
    if creator.current_org_id is None:
        creator.current_org_id = org.id

    await db.commit()
    await db.refresh(org)
    logger.info("创建组织: %s (slug=%s) by user %s", org.name, org.slug, creator.id)
    return OrgInfo.model_validate(org)


async def _ensure_membership(
    user: User, org: Organization, role: str, job_title: str | None, db: AsyncSession,
) -> None:
    """确保用户是组织成员，已存在则跳过。"""
    exists = await db.execute(
        select(OrgMembership).where(
            OrgMembership.user_id == user.id,
            OrgMembership.org_id == org.id,
            not_deleted(OrgMembership),
        )
    )
    if exists.scalar_one_or_none() is None:
        db.add(OrgMembership(
            user_id=user.id, org_id=org.id, role=role, job_title=job_title,
        ))
    user.current_org_id = org.id
    await db.commit()
    await db.refresh(user)


async def update_org(org_id: str, body: OrgUpdate, db: AsyncSession) -> OrgInfo:
    """更新组织信息。"""
    org = await get_org(org_id, db)
    for field, value in body.model_dump(exclude_unset=True).items():
        setattr(org, field, value)
    await db.commit()
    await db.refresh(org)
    return OrgInfo.model_validate(org)


async def delete_org(org_id: str, db: AsyncSession) -> None:
    """软删除组织（仍有运行中实例时禁止删除）。"""
    from app.models.instance import Instance, InstanceStatus

    org = await get_org(org_id, db)

    active_statuses = {
        InstanceStatus.running, InstanceStatus.creating,
        InstanceStatus.deploying, InstanceStatus.pending, InstanceStatus.updating,
    }
    result = await db.execute(
        select(func.count()).select_from(Instance).where(
            Instance.org_id == org_id,
            Instance.deleted_at.is_(None),
            Instance.status.in_(active_statuses),
        )
    )
    count = result.scalar() or 0
    if count > 0:
        raise ForbiddenError(f"该组织下仍有 {count} 个活跃实例，请先删除或停止所有实例")

    org.soft_delete()
    await db.commit()


# ── 成员管理 ─────────────────────────────────────────────

_MAX_SUPERVISOR_DEPTH = 50


async def validate_supervisor(
    org_id: str,
    target_membership_id: str | None,
    supervisor_membership_id: str | None,
    db: AsyncSession,
) -> None:
    if not supervisor_membership_id:
        return

    if target_membership_id and supervisor_membership_id == target_membership_id:
        raise BadRequestError(
            "不能将自己设为主管",
            message_key="errors.member.supervisor_self",
        )

    sup_result = await db.execute(
        select(OrgMembership).where(
            OrgMembership.id == supervisor_membership_id,
            OrgMembership.org_id == org_id,
            not_deleted(OrgMembership),
        )
    )
    if sup_result.scalar_one_or_none() is None:
        raise BadRequestError(
            "主管不属于当前组织",
            message_key="errors.member.supervisor_not_in_org",
        )

    if not target_membership_id:
        return

    current_id: str | None = supervisor_membership_id
    depth = 0
    while current_id and depth < _MAX_SUPERVISOR_DEPTH:
        if current_id == target_membership_id:
            raise BadRequestError(
                "主管关系形成循环",
                message_key="errors.member.supervisor_cycle",
            )
        row = await db.execute(
            select(OrgMembership.supervisor_membership_id).where(
                OrgMembership.id == current_id,
                not_deleted(OrgMembership),
            )
        )
        current_id = row.scalar_one_or_none()
        depth += 1


def _build_member_info(
    membership: OrgMembership,
    user: User,
    *,
    supervisor_name: str | None = None,
    direct_report_count: int = 0,
    skill_grant_count: int = 0,
    mcp_skill_grant_count: int = 0,
) -> MemberInfo:
    return MemberInfo(
        id=membership.id,
        user_id=membership.user_id,
        org_id=membership.org_id,
        role=membership.role,
        is_super_admin=user.is_super_admin,
        user_name=user.name,
        user_email=user.email,
        username=user.username,
        user_avatar_url=user.avatar_url,
        is_active=user.is_active,
        must_change_password=user.must_change_password,
        department=membership.department,
        job_title=membership.job_title,
        employee_no=membership.employee_no,
        supervisor_membership_id=membership.supervisor_membership_id,
        supervisor_name=supervisor_name,
        direct_report_count=direct_report_count,
        skill_grant_count=skill_grant_count,
        mcp_skill_grant_count=mcp_skill_grant_count,
        created_at=membership.created_at,
    )


async def _enrich_members(
    rows: list[tuple[OrgMembership, User]], db: AsyncSession,
) -> list[MemberInfo]:
    if not rows:
        return []

    from app.services.member_skill_service import count_member_grants

    membership_ids = [m.id for m, _ in rows]
    supervisor_ids = {m.supervisor_membership_id for m, _ in rows if m.supervisor_membership_id}

    supervisor_names: dict[str, str] = {}
    if supervisor_ids:
        sup_result = await db.execute(
            select(OrgMembership.id, User.name)
            .join(User, OrgMembership.user_id == User.id)
            .where(OrgMembership.id.in_(supervisor_ids), not_deleted(OrgMembership))
        )
        supervisor_names = {sid: name for sid, name in sup_result.all()}

    report_result = await db.execute(
        select(OrgMembership.supervisor_membership_id, func.count())
        .where(
            OrgMembership.supervisor_membership_id.in_(membership_ids),
            not_deleted(OrgMembership),
        )
        .group_by(OrgMembership.supervisor_membership_id)
    )
    report_counts = {sid: cnt for sid, cnt in report_result.all()}

    grant_counts = await count_member_grants(membership_ids, db)

    members = []
    for membership, user in rows:
        total, mcp = grant_counts.get(membership.id, (0, 0))
        members.append(_build_member_info(
            membership, user,
            supervisor_name=supervisor_names.get(membership.supervisor_membership_id or ""),
            direct_report_count=report_counts.get(membership.id, 0),
            skill_grant_count=total,
            mcp_skill_grant_count=mcp,
        ))
    return members

async def list_members(
    org_id: str, db: AsyncSession, *, current_user_id: str | None = None,
) -> list[MemberInfo]:
    """列出组织成员（排除 Admin 平台用户，但始终包含当前用户）。"""
    admin_user_ids = (
        select(AdminMembership.user_id)
        .where(
            AdminMembership.org_id == org_id,
            AdminMembership.deleted_at.is_(None),
        )
    )
    admin_filter = User.id.notin_(admin_user_ids)
    if current_user_id:
        admin_filter = or_(admin_filter, User.id == current_user_id)

    result = await db.execute(
        select(OrgMembership, User)
        .join(User, OrgMembership.user_id == User.id)
        .where(
            OrgMembership.org_id == org_id,
            not_deleted(OrgMembership),
            not_deleted(User),
            admin_filter,
        )
    )
    return await _enrich_members(list(result.all()), db)


async def add_member(org_id: str, user_id: str, role: str, db: AsyncSession) -> MemberInfo:
    """添加成员到组织。"""
    # 检查用户存在
    user_result = await db.execute(
        select(User).where(User.id == user_id, User.deleted_at.is_(None))
    )
    user = user_result.scalar_one_or_none()
    if user is None:
        raise NotFoundError("用户不存在")

    # 检查是否已是成员
    exists = await db.execute(
        select(OrgMembership).where(
            OrgMembership.user_id == user_id,
            OrgMembership.org_id == org_id,
            not_deleted(OrgMembership),
        )
    )
    if exists.scalar_one_or_none():
        raise ConflictError("该用户已是组织成员")

    membership = OrgMembership(user_id=user_id, org_id=org_id, role=role)
    db.add(membership)

    # 如果用户还没有当前组织，自动设置
    if user.current_org_id is None:
        user.current_org_id = org_id

    await db.commit()
    await db.refresh(membership)

    return MemberInfo(
        id=membership.id,
        user_id=membership.user_id,
        org_id=membership.org_id,
        role=membership.role,
        is_super_admin=user.is_super_admin,
        user_name=user.name,
        user_email=user.email,
        user_avatar_url=user.avatar_url,
        created_at=membership.created_at,
    )


async def update_member_role(org_id: str, membership_id: str, role: str, db: AsyncSession) -> MemberInfo:
    """修改成员角色。"""
    result = await db.execute(
        select(OrgMembership, User)
        .join(User, OrgMembership.user_id == User.id)
        .where(
            OrgMembership.id == membership_id,
            OrgMembership.org_id == org_id,
            not_deleted(OrgMembership),
            not_deleted(User),
        )
    )
    row = result.first()
    if row is None:
        raise NotFoundError("成员记录不存在")

    membership, user = row

    if membership.role == OrgRole.admin and role != OrgRole.admin:
        admin_count = await db.execute(
            select(func.count()).where(
                OrgMembership.org_id == org_id,
                OrgMembership.role == OrgRole.admin,
                not_deleted(OrgMembership),
            )
        )
        if admin_count.scalar_one() <= 1:
            raise ForbiddenError("组织至少需要一个管理员")

    membership.role = role
    await db.commit()

    enriched = await _enrich_members([(membership, user)], db)
    return enriched[0]


async def remove_member(org_id: str, membership_id: str, db: AsyncSession) -> None:
    """移除成员（软删除）。"""
    result = await db.execute(
        select(OrgMembership).where(
            OrgMembership.id == membership_id,
            OrgMembership.org_id == org_id,
            not_deleted(OrgMembership),
        )
    )
    membership = result.scalar_one_or_none()
    if membership is None:
        raise NotFoundError("成员记录不存在")

    # 检查是否是最后一个 admin
    admin_count = await db.execute(
        select(func.count()).where(
            OrgMembership.org_id == org_id,
            OrgMembership.role == OrgRole.admin,
            not_deleted(OrgMembership),
        )
    )
    if membership.role == OrgRole.admin and admin_count.scalar_one() <= 1:
        raise ForbiddenError("组织至少需要一个管理员")

    subordinates = await db.execute(
        select(OrgMembership).where(
            OrgMembership.supervisor_membership_id == membership_id,
            OrgMembership.org_id == org_id,
            not_deleted(OrgMembership),
        )
    )
    for sub in subordinates.scalars().all():
        sub.supervisor_membership_id = None

    membership.soft_delete()
    await db.commit()


async def switch_org(user: User, org_id: str, db: AsyncSession) -> OrgInfo:
    """切换用户当前组织。"""
    # 检查是否是该组织的成员（超管可切换任意组织）
    if not user.is_super_admin:
        result = await db.execute(
            select(OrgMembership).where(
                OrgMembership.user_id == user.id,
                OrgMembership.org_id == org_id,
                not_deleted(OrgMembership),
            )
        )
        if result.scalar_one_or_none() is None:
            raise ForbiddenError("您不是该组织的成员")

    org = await get_org(org_id, db)
    user.current_org_id = org_id
    await db.commit()
    return OrgInfo.model_validate(org)


async def list_user_orgs(user: User, db: AsyncSession) -> list[OrgInfo]:
    """列出用户所属的所有组织，附带成员数（排除 Admin 平台用户）。"""
    if user.is_super_admin:
        return await list_orgs(db)

    admin_user_ids_corr = (
        select(AdminMembership.user_id)
        .where(AdminMembership.org_id == Organization.id, AdminMembership.deleted_at.is_(None))
        .correlate(Organization)
    )
    member_count_sub = (
        select(func.count(OrgMembership.id))
        .where(
            OrgMembership.org_id == Organization.id,
            not_deleted(OrgMembership),
            OrgMembership.user_id.notin_(admin_user_ids_corr),
        )
        .correlate(Organization)
        .scalar_subquery()
        .label("member_count")
    )
    result = await db.execute(
        select(Organization, member_count_sub)
        .join(OrgMembership, OrgMembership.org_id == Organization.id)
        .where(
            OrgMembership.user_id == user.id,
            not_deleted(OrgMembership),
            not_deleted(Organization),
        )
        .order_by(Organization.created_at.desc())
    )
    orgs = []
    for org, count in result.all():
        info = OrgInfo.model_validate(org)
        info.member_count = count or 0
        orgs.append(info)
    return orgs


async def create_human_member(
    org_id: str,
    body: CreateHumanMemberRequest,
    actor: User,
    db: AsyncSession,
) -> MemberInfo:
    await get_org(org_id, db)

    if body.role not in (OrgRole.member, OrgRole.operator, OrgRole.admin):
        raise BadRequestError("角色不合法", message_key="errors.member.invalid_role")

    email = str(body.email).strip().lower()
    username = (body.username or email.split("@")[0]).strip().lower()

    if body.supervisor_membership_id:
        await validate_supervisor(org_id, None, body.supervisor_membership_id, db)

    username_exists = await db.execute(
        select(User).where(
            func.lower(User.username) == username,
            not_deleted(User),
        )
    )
    existing_username_user = username_exists.scalar_one_or_none()

    user_result = await db.execute(
        select(User).where(func.lower(User.email) == email, not_deleted(User))
    )
    user = user_result.scalar_one_or_none()

    if user is None:
        if existing_username_user:
            raise ConflictError(
                "用户名已被占用",
                message_key="errors.member.username_taken",
            )
        from app.services.auth_service import _hash_password
        user = User(
            name=body.name.strip(),
            email=email,
            username=username,
            password_hash=_hash_password(body.default_password),
            must_change_password=body.must_change_password,
            current_org_id=org_id,
        )
        db.add(user)
        await db.flush()
    else:
        member_exists = await db.execute(
            select(OrgMembership).where(
                OrgMembership.user_id == user.id,
                OrgMembership.org_id == org_id,
                not_deleted(OrgMembership),
            )
        )
        if member_exists.scalar_one_or_none():
            raise ConflictError(
                "用户已是当前组织成员",
                message_key="errors.member.already_in_org",
            )
        if existing_username_user and existing_username_user.id != user.id:
            raise ConflictError(
                "用户名已被占用",
                message_key="errors.member.username_taken",
            )

    membership = OrgMembership(
        user_id=user.id,
        org_id=org_id,
        role=body.role,
        department=body.department,
        job_title=body.job_title,
        employee_no=body.employee_no,
        supervisor_membership_id=body.supervisor_membership_id,
    )
    db.add(membership)
    await db.flush()

    await validate_supervisor(org_id, membership.id, body.supervisor_membership_id, db)

    if user.current_org_id is None:
        user.current_org_id = org_id
    if body.must_change_password:
        user.must_change_password = True

    await db.commit()
    await db.refresh(membership)
    await db.refresh(user)

    if body.skill_ids:
        from app.services.member_skill_service import create_initial_skill_grants
        await create_initial_skill_grants(
            org_id, membership.id, user.id, body.skill_ids, actor, db,
        )

    enriched = await _enrich_members([(membership, user)], db)
    return enriched[0]


async def update_member_profile(
    org_id: str,
    membership_id: str,
    body: UpdateMemberProfileRequest,
    db: AsyncSession,
) -> MemberInfo:
    result = await db.execute(
        select(OrgMembership, User)
        .join(User, OrgMembership.user_id == User.id)
        .where(
            OrgMembership.id == membership_id,
            OrgMembership.org_id == org_id,
            not_deleted(OrgMembership),
            not_deleted(User),
        )
    )
    row = result.first()
    if row is None:
        raise NotFoundError("成员记录不存在")

    membership, user = row
    data = body.model_dump(exclude_unset=True)

    if "supervisor_membership_id" in data:
        await validate_supervisor(
            org_id, membership_id, data["supervisor_membership_id"], db,
        )
        membership.supervisor_membership_id = data["supervisor_membership_id"]

    if "name" in data and data["name"] is not None:
        user.name = data["name"].strip()
    if "username" in data and data["username"] is not None:
        new_username = data["username"].strip().lower()
        dup = await db.execute(
            select(User).where(
                func.lower(User.username) == new_username,
                User.id != user.id,
                not_deleted(User),
            )
        )
        if dup.scalar_one_or_none():
            raise ConflictError(
                "用户名已被占用",
                message_key="errors.member.username_taken",
            )
        user.username = new_username
    if "is_active" in data and data["is_active"] is not None:
        user.is_active = data["is_active"]
    if "department" in data:
        membership.department = data["department"]
    if "job_title" in data:
        membership.job_title = data["job_title"]
    if "employee_no" in data:
        membership.employee_no = data["employee_no"]

    await db.commit()
    await db.refresh(membership)
    await db.refresh(user)

    enriched = await _enrich_members([(membership, user)], db)
    return enriched[0]
