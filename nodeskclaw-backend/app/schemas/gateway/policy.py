from datetime import datetime

from pydantic import BaseModel, Field


class PolicyCreate(BaseModel):
    name: str = Field(min_length=1, max_length=128)
    scope: str = Field(pattern=r"^(global|org|instance|tool)$")
    scope_ref_id: str | None = None
    rate_limit_rpm: int | None = Field(default=None, gt=0)
    max_connections: int | None = Field(default=None, gt=0)
    timeout_seconds: int = Field(default=30, gt=0)
    retry_count: int = Field(default=0, ge=0)
    sensitive_tools: list[str] = Field(default_factory=list)
    is_active: bool = True


class PolicyUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=128)
    scope: str | None = None
    scope_ref_id: str | None = None
    rate_limit_rpm: int | None = None
    max_connections: int | None = None
    timeout_seconds: int | None = None
    retry_count: int | None = None
    sensitive_tools: list[str] | None = None
    is_active: bool | None = None


class PolicyRead(BaseModel):
    model_config = {"from_attributes": True}

    id: str
    name: str
    scope: str
    scope_ref_id: str | None
    rate_limit_rpm: int | None
    max_connections: int | None
    timeout_seconds: int
    retry_count: int
    sensitive_tools: list
    is_active: bool
    org_id: str
    created_at: datetime
    updated_at: datetime


class PolicyList(BaseModel):
    items: list[PolicyRead]
    total: int
