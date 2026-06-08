"""Member management schemas."""

from datetime import datetime

from pydantic import BaseModel, EmailStr, Field

from app.schemas.organization import MemberInfo


class CreateHumanMemberRequest(BaseModel):
    email: EmailStr
    username: str | None = Field(default=None, max_length=64)
    name: str = Field(min_length=1, max_length=128)
    default_password: str = Field(min_length=6, max_length=128)
    role: str = "member"
    department: str | None = Field(default=None, max_length=128)
    job_title: str | None = Field(default=None, max_length=128)
    employee_no: str | None = Field(default=None, max_length=64)
    supervisor_membership_id: str | None = None
    must_change_password: bool = True
    skill_ids: list[str] = []


class UpdateMemberProfileRequest(BaseModel):
    name: str | None = Field(default=None, max_length=128)
    username: str | None = Field(default=None, max_length=64)
    department: str | None = Field(default=None, max_length=128)
    job_title: str | None = Field(default=None, max_length=128)
    employee_no: str | None = Field(default=None, max_length=64)
    supervisor_membership_id: str | None = None
    is_active: bool | None = None


class MemberSkillGrantPayload(BaseModel):
    skill_db_id: str
    can_list: bool = True
    can_invoke: bool = True
    can_manage: bool = False
    expires_at: datetime | None = None
    reason: str | None = None


class ReplaceMemberSkillGrantsRequest(BaseModel):
    grants: list[MemberSkillGrantPayload]


class MemberSkillGrantItem(BaseModel):
    skill_db_id: str
    skill_id: str
    name: str
    tool_name: str | None = None
    runtime: str | None = None
    is_active: bool
    is_mcp_exposed: bool
    can_list: bool = False
    can_invoke: bool = False
    can_manage: bool = False
    granted: bool = False
    expires_at: datetime | None = None


class MemberSkillGrantListResponse(BaseModel):
    member: dict
    items: list[MemberSkillGrantItem]


class MemberSkillGrantSaveResult(BaseModel):
    ok: bool = True
    skill_grant_count: int
    mcp_skill_grant_count: int


class AvailableMcpSkillItem(BaseModel):
    id: str
    skill_id: str
    name: str
    tool_name: str | None = None
    runtime: str | None = None
    is_active: bool
    is_mcp_exposed: bool


class CreateHumanMemberResponse(BaseModel):
    member: MemberInfo
