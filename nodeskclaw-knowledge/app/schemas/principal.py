"""Knowledge principal from backend context."""

from pydantic import BaseModel


class KnowledgePrincipal(BaseModel):
    user_id: str
    member_id: str
    org_id: str
    name: str = ""
    employee_no: str | None = None
    department: str | None = None
    job_title: str | None = None
    member_role: str = "member"
    supervisor_member_id: str | None = None
    is_active: bool = True
    is_super_admin: bool = False

    @property
    def role(self) -> str:
        return self.member_role
