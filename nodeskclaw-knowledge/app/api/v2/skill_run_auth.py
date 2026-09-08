"""Skill Run authorization proofs for Backend Runtime consumption."""

from __future__ import annotations

import hashlib
import hmac

from fastapi import APIRouter, Depends, Header
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.deps import get_db, require_knowledge_service_token
from app.core.exceptions import ForbiddenError
from app.models.enums import SetPermission
from app.models.knowledge_set import KnowledgeSet
from app.schemas.common import ApiResponse
from app.schemas.principal import KnowledgePrincipal
from app.services import permission_service

router = APIRouter(prefix="/skill-run", tags=["v2-skill-run-auth"])


class SkillRunAuthProofRequest(BaseModel):
    org_id: str
    member_id: str
    knowledge_set_ids: list[str] = Field(default_factory=list)


class SkillRunAuthProofItem(BaseModel):
    set_id: str
    allowed: bool
    auth_version: str


class SkillRunAuthProofResult(BaseModel):
    proofs: list[SkillRunAuthProofItem] = Field(default_factory=list)


def _auth_version_for_set(knowledge_set: KnowledgeSet) -> str:
    updated = knowledge_set.updated_at.isoformat() if knowledge_set.updated_at else ""
    digest = hashlib.sha256(f"{knowledge_set.id}:{updated}".encode()).hexdigest()
    return digest[:16]


@router.post("/auth-proofs", response_model=ApiResponse[SkillRunAuthProofResult])
async def issue_skill_run_auth_proofs(
    body: SkillRunAuthProofRequest,
    db: AsyncSession = Depends(get_db),
    _: None = Depends(require_knowledge_service_token),
) -> ApiResponse[SkillRunAuthProofResult]:
    member = KnowledgePrincipal(
        user_id="service",
        member_id=body.member_id,
        org_id=body.org_id,
        name="Skill Run Service",
        department="",
        member_role="member",
        is_active=True,
        is_super_admin=False,
    )
    proofs: list[SkillRunAuthProofItem] = []
    for set_id in body.knowledge_set_ids:
        ks = await db.get(KnowledgeSet, set_id)
        if ks is None or ks.deleted_at is not None or ks.org_id != body.org_id:
            proofs.append(SkillRunAuthProofItem(set_id=set_id, allowed=False, auth_version=""))
            continue
        allowed = await permission_service.has_set_permission(
            db,
            member,
            ks,
            SetPermission.read.value,
        )
        proofs.append(
            SkillRunAuthProofItem(
                set_id=set_id,
                allowed=allowed,
                auth_version=_auth_version_for_set(ks) if allowed else "",
            )
        )
    return ApiResponse(data=SkillRunAuthProofResult(proofs=proofs))
