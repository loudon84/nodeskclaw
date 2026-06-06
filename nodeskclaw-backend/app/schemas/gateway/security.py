from datetime import datetime

from pydantic import BaseModel, Field


class SecurityPolicyCreate(BaseModel):
    method_whitelist: list[str] = Field(
        default_factory=lambda: ["tools/list", "tools/call", "resources/list", "resources/read", "prompts/list"],
        min_length=1,
    )
    max_request_body_bytes: int = Field(default=1048576, gt=0)
    global_rate_limit_rpm: int = Field(default=500, gt=0)
    sse_max_connections: int = Field(default=500, gt=0)
    sse_max_connections_per_instance: int = Field(default=100, gt=0)
    origin_check_mode: str = Field(default="relaxed", pattern=r"^(strict|relaxed)$")
    allowed_origins: list[str] = Field(default_factory=list)
    upstream_host_whitelist: list[str] = Field(default_factory=list)
    sensitive_param_names: list[str] = Field(
        default_factory=lambda: ["password", "token", "secret", "key", "credential", "api_key", "private_key"],
    )
    is_active: bool = True


class SecurityPolicyUpdate(BaseModel):
    method_whitelist: list[str] | None = None
    max_request_body_bytes: int | None = None
    global_rate_limit_rpm: int | None = None
    sse_max_connections: int | None = None
    sse_max_connections_per_instance: int | None = None
    origin_check_mode: str | None = None
    allowed_origins: list[str] | None = None
    upstream_host_whitelist: list[str] | None = None
    sensitive_param_names: list[str] | None = None
    is_active: bool | None = None


class SecurityPolicyRead(BaseModel):
    model_config = {"from_attributes": True}

    id: str
    org_id: str
    method_whitelist: list
    max_request_body_bytes: int
    global_rate_limit_rpm: int
    sse_max_connections: int
    sse_max_connections_per_instance: int
    origin_check_mode: str
    allowed_origins: list
    upstream_host_whitelist: list
    sensitive_param_names: list
    is_active: bool
    version: int
    created_at: datetime
    updated_at: datetime


class ApiKeyCreate(BaseModel):
    name: str = Field(min_length=1, max_length=128)
    rate_limit_rpm: int | None = Field(default=None, gt=0)
    allowed_scopes: list[str] = Field(default_factory=list)


class ApiKeyUpdate(BaseModel):
    name: str | None = None
    status: str | None = None
    rate_limit_rpm: int | None = None
    allowed_scopes: list[str] | None = None


class ApiKeyRead(BaseModel):
    model_config = {"from_attributes": True}

    id: str
    name: str
    key_prefix: str
    key_suffix: str
    status: str
    rate_limit_rpm: int | None
    allowed_scopes: list
    org_id: str
    last_used_at: str | None
    created_at: datetime


class ApiKeyCreateResponse(BaseModel):
    id: str
    name: str
    key_value: str
    key_prefix: str
    key_suffix: str
