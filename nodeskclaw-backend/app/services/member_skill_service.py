"""Member-level MCP Skill authorization service."""

from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import BadRequestError, ForbiddenError, NotFoundError
from app.models.base import not_deleted
from app.models.hermes_skill.skill import HermesSkill
from app.models.org_member_skill_grant import OrgMemberSkillGrant
from app.models.org_membership import OrgMembership, OrgRole
from app.models.user import User
from app.schemas.member import (
    AvailableMcpSkillItem,
    MemberSkillGrantItem,
    MemberSkillGrantListResponse,
    MemberSkillGrantSaveResult,
    ReplaceMemberSkillGrantsRequest,
)


async def assert_can_manage_member(
    actor_user_id: str,
    org_id: str,
    target_membership_id: str,
    action: str,
    db: AsyncSession,
) -> None:
    actor_result = await db.execute(
        select(OrgMembership).where(
            OrgMembership.user_id == actor_user_id,
            OrgMembership.org_id == org_id,
            not_deleted(OrgMembership),
        )
    )
    actor_membership = actor_result.scalar_one_or_none()
    if actor_membership is None:
        raise ForbiddenError("您不是该组织的成员")

    if actor_membership.role == OrgRole.admin:
        return

    if action in ("profile", "skill"):
        target_result = await db.execute(
            select(OrgMembership).where(
                OrgMembership.id == target_membership_id,
                OrgMembership.org_id == org_id,
                not_deleted(OrgMembership),
            )
        )
        target = target_result.scalar_one_or_none()
        if target and target.supervisor_membership_id == actor_membership.id:
            return

    raise ForbiddenError("无权限执行此操作", message_key="errors.common.forbidden")


async def _get_membership_or_404(
    org_id: str, membership_id: str, db: AsyncSession,
) -> OrgMembership:
    result = await db.execute(
        select(OrgMembership).where(
            OrgMembership.id == membership_id,
            OrgMembership.org_id == org_id,
            not_deleted(OrgMembership),
        )
    )
    membership = result.scalar_one_or_none()
    if membership is None:
        raise NotFoundError("成员记录不存在", message_key="errors.org.member_not_found")
    return membership


async def list_available_mcp_skills(org_id: str, db: AsyncSession) -> list[AvailableMcpSkillItem]:
    result = await db.execute(
        select(HermesSkill).where(
            not_deleted(HermesSkill),
            HermesSkill.org_id == org_id,
            HermesSkill.is_active.is_(True),
            HermesSkill.is_mcp_exposed.is_(True),
        ).order_by(HermesSkill.name)
    )
    return [
        AvailableMcpSkillItem(
            id=skill.id,
            skill_id=skill.skill_id,
            name=skill.name,
            tool_name=skill.tool_name,
            runtime=skill.runtime,
            is_active=skill.is_active,
            is_mcp_exposed=skill.is_mcp_exposed,
        )
        for skill in result.scalars().all()
    ]


async def list_member_skill_grants(
    org_id: str, membership_id: str, db: AsyncSession,
) -> MemberSkillGrantListResponse:
    membership = await _get_membership_or_404(org_id, membership_id, db)

    user_result = await db.execute(
        select(User).where(User.id == membership.user_id, not_deleted(User))
    )
    user = user_result.scalar_one_or_none()

    skills_result = await db.execute(
        select(HermesSkill).where(
            not_deleted(HermesSkill),
            HermesSkill.org_id == org_id,
            HermesSkill.is_active.is_(True),
            HermesSkill.is_mcp_exposed.is_(True),
        ).order_by(HermesSkill.name)
    )
    skills = list(skills_result.scalars().all())

    grants_result = await db.execute(
        select(OrgMemberSkillGrant).where(
            OrgMemberSkillGrant.membership_id == membership_id,
            OrgMemberSkillGrant.org_id == org_id,
            not_deleted(OrgMemberSkillGrant),
        )
    )
    grants_by_skill = {g.skill_db_id: g for g in grants_result.scalars().all()}

    items = []
    for skill in skills:
        grant = grants_by_skill.get(skill.id)
        items.append(MemberSkillGrantItem(
            skill_db_id=skill.id,
            skill_id=skill.skill_id,
            name=skill.name,
            tool_name=skill.tool_name,
            runtime=skill.runtime,
            is_active=skill.is_active,
            is_mcp_exposed=skill.is_mcp_exposed,
            granted=grant is not None,
            can_list=grant.can_list if grant else False,
            can_invoke=grant.can_invoke if grant else False,
            can_manage=grant.can_manage if grant else False,
            expires_at=grant.expires_at if grant else None,
        ))

    return MemberSkillGrantListResponse(
        member={
            "id": membership.id,
            "user_id": membership.user_id,
            "name": user.name if user else None,
            "email": user.email if user else None,
        },
        items=items,
    )


async def replace_member_skill_grants(
    org_id: str,
    membership_id: str,
    body: ReplaceMemberSkillGrantsRequest,
    actor: User,
    db: AsyncSession,
) -> MemberSkillGrantSaveResult:
    await assert_can_manage_member(actor.id, org_id, membership_id, "skill", db)
    membership = await _get_membership_or_404(org_id, membership_id, db)

    skill_ids = [g.skill_db_id for g in body.grants]
    valid_skills: dict[str, HermesSkill] = {}
    if skill_ids:
        skills_result = await db.execute(
            select(HermesSkill).where(
                HermesSkill.id.in_(skill_ids),
                HermesSkill.org_id == org_id,
                not_deleted(HermesSkill),
                HermesSkill.is_active.is_(True),
                HermesSkill.is_mcp_exposed.is_(True),
            )
        )
        valid_skills = {s.id: s for s in skills_result.scalars().all()}
        for sid in skill_ids:
            if sid not in valid_skills:
                raise BadRequestError(
                    f"Skill {sid} 不存在或未启用 MCP 暴露",
                    message_key="errors.member.skill_not_grantable",
                )

        actor_membership_result = await db.execute(
            select(OrgMembership).where(
                OrgMembership.user_id == actor.id,
                OrgMembership.org_id == org_id,
                not_deleted(OrgMembership),
            )
        )
        actor_membership = actor_membership_result.scalar_one_or_none()
        if actor_membership and actor_membership.role != OrgRole.admin:
            actor_grants_result = await db.execute(
                select(OrgMemberSkillGrant).where(
                    OrgMemberSkillGrant.membership_id == actor_membership.id,
                    OrgMemberSkillGrant.org_id == org_id,
                    not_deleted(OrgMemberSkillGrant),
                    OrgMemberSkillGrant.can_invoke.is_(True),
                )
            )
            actor_skill_ids = {g.skill_db_id for g in actor_grants_result.scalars().all()}
            for sid in skill_ids:
                if sid not in actor_skill_ids:
                    raise ForbiddenError(
                        "不能授予自己没有的 Skill",
                        message_key="errors.member.cannot_grant_unowned_skill",
                    )

    existing_result = await db.execute(
        select(OrgMemberSkillGrant).where(
            OrgMemberSkillGrant.membership_id == membership_id,
            OrgMemberSkillGrant.org_id == org_id,
            not_deleted(OrgMemberSkillGrant),
        )
    )
    existing = {g.skill_db_id: g for g in existing_result.scalars().all()}
    requested_ids = {g.skill_db_id for g in body.grants}

    for skill_db_id, grant in existing.items():
        if skill_db_id not in requested_ids:
            grant.soft_delete()

    for payload in body.grants:
        skill = valid_skills[payload.skill_db_id]
        if payload.skill_db_id in existing:
            grant = existing[payload.skill_db_id]
            grant.can_list = payload.can_list
            grant.can_invoke = payload.can_invoke
            grant.can_manage = payload.can_manage
            grant.expires_at = payload.expires_at
            grant.reason = payload.reason
            grant.granted_by = actor.id
        else:
            db.add(OrgMemberSkillGrant(
                org_id=org_id,
                membership_id=membership_id,
                user_id=membership.user_id,
                skill_db_id=payload.skill_db_id,
                skill_id=skill.skill_id,
                can_list=payload.can_list,
                can_invoke=payload.can_invoke,
                can_manage=payload.can_manage,
                grant_source="manual",
                granted_by=actor.id,
                expires_at=payload.expires_at,
                reason=payload.reason,
            ))

    await db.commit()

    count_result = await db.execute(
        select(func.count()).select_from(OrgMemberSkillGrant).where(
            OrgMemberSkillGrant.membership_id == membership_id,
            OrgMemberSkillGrant.org_id == org_id,
            not_deleted(OrgMemberSkillGrant),
        )
    )
    mcp_count_result = await db.execute(
        select(func.count()).select_from(OrgMemberSkillGrant).where(
            OrgMemberSkillGrant.membership_id == membership_id,
            OrgMemberSkillGrant.org_id == org_id,
            not_deleted(OrgMemberSkillGrant),
            OrgMemberSkillGrant.can_invoke.is_(True),
            OrgMemberSkillGrant.can_list.is_(True),
        )
    )
    return MemberSkillGrantSaveResult(
        skill_grant_count=count_result.scalar_one() or 0,
        mcp_skill_grant_count=mcp_count_result.scalar_one() or 0,
    )


async def create_initial_skill_grants(
    org_id: str,
    membership_id: str,
    user_id: str,
    skill_ids: list[str],
    actor: User,
    db: AsyncSession,
) -> None:
    if not skill_ids:
        return
    from app.schemas.member import MemberSkillGrantPayload
    body = ReplaceMemberSkillGrantsRequest(
        grants=[
            MemberSkillGrantPayload(
                skill_db_id=sid, can_list=True, can_invoke=True, can_manage=False,
            )
            for sid in skill_ids
        ]
    )
    await replace_member_skill_grants(org_id, membership_id, body, actor, db)


async def require_invoke_skill(
    db: AsyncSession,
    org_id: str,
    user_id: str,
    skill_db_id: str,
) -> None:
    now = datetime.now(timezone.utc)

    membership_result = await db.execute(
        select(OrgMembership).where(
            OrgMembership.user_id == user_id,
            OrgMembership.org_id == org_id,
            not_deleted(OrgMembership),
        )
    )
    if membership_result.scalar_one_or_none() is None:
        raise ForbiddenError(
            "SKILL_NOT_GRANTED",
            message_key="errors.member.skill_not_granted",
        )

    grant_result = await db.execute(
        select(OrgMemberSkillGrant).where(
            OrgMemberSkillGrant.org_id == org_id,
            OrgMemberSkillGrant.user_id == user_id,
            OrgMemberSkillGrant.skill_db_id == skill_db_id,
            not_deleted(OrgMemberSkillGrant),
            OrgMemberSkillGrant.can_invoke.is_(True),
        )
    )
    grant = grant_result.scalar_one_or_none()
    if grant is None:
        raise ForbiddenError(
            "SKILL_NOT_GRANTED",
            message_key="errors.member.skill_not_granted",
        )

    if grant.expires_at and grant.expires_at <= now:
        raise ForbiddenError(
            "SKILL_NOT_GRANTED",
            message_key="errors.member.skill_not_granted",
        )

    skill_result = await db.execute(
        select(HermesSkill).where(
            HermesSkill.id == skill_db_id,
            HermesSkill.org_id == org_id,
            not_deleted(HermesSkill),
            HermesSkill.is_active.is_(True),
            HermesSkill.is_mcp_exposed.is_(True),
        )
    )
    if skill_result.scalar_one_or_none() is None:
        raise ForbiddenError(
            "SKILL_NOT_GRANTED",
            message_key="errors.member.skill_not_granted",
        )


async def count_member_grants(
    membership_ids: list[str], db: AsyncSession,
) -> dict[str, tuple[int, int]]:
    if not membership_ids:
        return {}

    total_result = await db.execute(
        select(
            OrgMemberSkillGrant.membership_id,
            func.count(OrgMemberSkillGrant.id),
        ).where(
            OrgMemberSkillGrant.membership_id.in_(membership_ids),
            not_deleted(OrgMemberSkillGrant),
        ).group_by(OrgMemberSkillGrant.membership_id)
    )
    totals = {mid: cnt for mid, cnt in total_result.all()}

    mcp_result = await db.execute(
        select(
            OrgMemberSkillGrant.membership_id,
            func.count(OrgMemberSkillGrant.id),
        ).where(
            OrgMemberSkillGrant.membership_id.in_(membership_ids),
            not_deleted(OrgMemberSkillGrant),
            OrgMemberSkillGrant.can_invoke.is_(True),
            OrgMemberSkillGrant.can_list.is_(True),
        ).group_by(OrgMemberSkillGrant.membership_id)
    )
    mcp_counts = {mid: cnt for mid, cnt in mcp_result.all()}

    return {
        mid: (totals.get(mid, 0), mcp_counts.get(mid, 0))
        for mid in membership_ids
    }
