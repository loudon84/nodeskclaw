import logging
import uuid
from datetime import datetime, timezone

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError
from app.models.base import not_deleted
from app.models.hermes_skill.hermes_skill_authorization_grant import HermesSkillAuthorizationGrant
from app.models.org_member_skill_grant import OrgMemberSkillGrant
from app.services.hermes_skill.permission_checker import PermissionChecker

logger = logging.getLogger(__name__)


class HermesSkillAuthorizationService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def can_list(
        self,
        org_id: str,
        user_id: str,
        skill_db_id: str,
        skill_id: str,
        *,
        agent_id: str | None = None,
    ) -> bool:
        role = await PermissionChecker.get_user_role(self.db, user_id, org_id)
        if role in PermissionChecker.ADMIN_OPERATOR_ROLES:
            return True
        return await self._check_permission(
            org_id, user_id, skill_db_id, skill_id, "can_list", agent_id=agent_id,
        )

    async def can_invoke(
        self,
        org_id: str,
        user_id: str,
        skill_db_id: str,
        skill_id: str,
        *,
        agent_id: str | None = None,
    ) -> bool:
        role = await PermissionChecker.get_user_role(self.db, user_id, org_id)
        if role in PermissionChecker.ADMIN_OPERATOR_ROLES:
            return True
        return await self._check_permission(
            org_id, user_id, skill_db_id, skill_id, "can_invoke", agent_id=agent_id,
        )

    async def list_grants(
        self,
        org_id: str,
        skill_id: str | None = None,
        workspace_id: str | None = None,
    ) -> list[HermesSkillAuthorizationGrant]:
        stmt = select(HermesSkillAuthorizationGrant).where(
            not_deleted(HermesSkillAuthorizationGrant),
            HermesSkillAuthorizationGrant.org_id == org_id,
        )
        if skill_id:
            stmt = stmt.where(HermesSkillAuthorizationGrant.skill_id == skill_id)
        if workspace_id:
            stmt = stmt.where(HermesSkillAuthorizationGrant.workspace_id == workspace_id)
        result = await self.db.execute(stmt.order_by(HermesSkillAuthorizationGrant.created_at.desc()))
        return list(result.scalars().all())

    async def create_grant(
        self,
        org_id: str,
        skill_id: str,
        subject_type: str,
        subject_id: str,
        *,
        skill_db_id: str | None = None,
        workspace_id: str | None = None,
        can_list: bool = True,
        can_invoke: bool = False,
        can_install: bool = False,
        can_manage: bool = False,
        expires_at: datetime | None = None,
        granted_by: str | None = None,
    ) -> HermesSkillAuthorizationGrant:
        grant = HermesSkillAuthorizationGrant(
            id=str(uuid.uuid4()),
            org_id=org_id,
            skill_id=skill_id,
            skill_db_id=skill_db_id,
            subject_type=subject_type,
            subject_id=subject_id,
            workspace_id=workspace_id,
            can_list=can_list,
            can_invoke=can_invoke,
            can_install=can_install,
            can_manage=can_manage,
            expires_at=expires_at,
            granted_by=granted_by,
        )
        self.db.add(grant)
        await self.db.flush()
        return grant

    async def bulk_grant(
        self,
        org_id: str,
        skill_id: str,
        subject_type: str,
        subject_ids: list[str],
        *,
        skill_db_id: str | None = None,
        workspace_id: str | None = None,
        can_list: bool = True,
        can_invoke: bool = False,
        can_install: bool = False,
        can_manage: bool = False,
        granted_by: str | None = None,
    ) -> list[HermesSkillAuthorizationGrant]:
        grants = []
        for subject_id in subject_ids:
            grant = await self.create_grant(
                org_id=org_id,
                skill_id=skill_id,
                subject_type=subject_type,
                subject_id=subject_id,
                skill_db_id=skill_db_id,
                workspace_id=workspace_id,
                can_list=can_list,
                can_invoke=can_invoke,
                can_install=can_install,
                can_manage=can_manage,
                granted_by=granted_by,
            )
            grants.append(grant)
        return grants

    async def revoke_grant(self, org_id: str, grant_id: str) -> None:
        result = await self.db.execute(
            select(HermesSkillAuthorizationGrant).where(
                not_deleted(HermesSkillAuthorizationGrant),
                HermesSkillAuthorizationGrant.org_id == org_id,
                HermesSkillAuthorizationGrant.id == grant_id,
            )
        )
        grant = result.scalar_one_or_none()
        if not grant:
            raise NotFoundError("授权记录不存在", "errors.hermes.authorization_not_found")
        grant.soft_delete()
        await self.db.flush()

    async def _check_permission(
        self,
        org_id: str,
        user_id: str,
        skill_db_id: str,
        skill_id: str,
        perm: str,
        *,
        agent_id: str | None = None,
    ) -> bool:
        now = datetime.now(timezone.utc)
        if await self._user_grant_allows(org_id, user_id, skill_db_id, perm, now):
            return True
        if await self._subject_grant_allows(org_id, "user", user_id, skill_id, perm, now):
            return True
        role = await PermissionChecker.get_user_role(self.db, user_id, org_id)
        if role and await self._subject_grant_allows(org_id, "role", role, skill_id, perm, now):
            return True
        if agent_id and await self._subject_grant_allows(org_id, "agent", agent_id, skill_id, perm, now):
            return True
        return await self._subject_grant_allows(org_id, "org", org_id, skill_id, perm, now)

    async def _user_grant_allows(
        self,
        org_id: str,
        user_id: str,
        skill_db_id: str,
        perm: str,
        now: datetime,
    ) -> bool:
        result = await self.db.execute(
            select(OrgMemberSkillGrant).where(
                not_deleted(OrgMemberSkillGrant),
                OrgMemberSkillGrant.org_id == org_id,
                OrgMemberSkillGrant.user_id == user_id,
                OrgMemberSkillGrant.skill_db_id == skill_db_id,
                or_(
                    OrgMemberSkillGrant.expires_at.is_(None),
                    OrgMemberSkillGrant.expires_at > now,
                ),
            )
        )
        grant = result.scalar_one_or_none()
        if not grant:
            return False
        return getattr(grant, perm, False)

    async def _subject_grant_allows(
        self,
        org_id: str,
        subject_type: str,
        subject_id: str,
        skill_id: str,
        perm: str,
        now: datetime,
    ) -> bool:
        result = await self.db.execute(
            select(HermesSkillAuthorizationGrant).where(
                not_deleted(HermesSkillAuthorizationGrant),
                HermesSkillAuthorizationGrant.org_id == org_id,
                HermesSkillAuthorizationGrant.subject_type == subject_type,
                HermesSkillAuthorizationGrant.subject_id == subject_id,
                HermesSkillAuthorizationGrant.skill_id == skill_id,
                or_(
                    HermesSkillAuthorizationGrant.expires_at.is_(None),
                    HermesSkillAuthorizationGrant.expires_at > now,
                ),
            )
        )
        for grant in result.scalars().all():
            if getattr(grant, perm, False):
                return True
        return False
