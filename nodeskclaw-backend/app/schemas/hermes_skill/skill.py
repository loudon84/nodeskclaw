from datetime import datetime

from pydantic import BaseModel, Field


class SkillRead(BaseModel):
    model_config = {"from_attributes": True}

    id: str
    org_id: str
    skill_id: str
    tool_name: str | None = None
    name: str
    title: str | None = None
    description: str | None = None
    version: str = "1.0.0"
    agent_type: str | None = None
    category: str | None = None
    runtime: str | None = None
    source_type: str = "central"
    source_url: str | None = None
    source_hash: str | None = None
    canonical_path: str | None = None
    is_central: bool = False
    is_read_only: bool = False
    is_active: bool = True
    is_mcp_exposed: bool = False
    input_schema: dict | None = None
    output_schema: dict | None = None
    output_policy: dict | None = None
    extra_metadata: dict | None = None
    tags: list | None = None
    created_by: str | None = None
    scanned_at: str | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None
    published_version: str | None = None
    published_release_status: str | None = None
    published_release_id: str | None = None
    published_digest: str | None = None
    has_draft_release: bool = False


class SkillCreate(BaseModel):
    skill_id: str = Field(..., min_length=1, max_length=64)
    name: str = Field(..., min_length=1, max_length=128)
    tool_name: str | None = None
    title: str | None = None
    description: str | None = None
    version: str = "1.0.0"
    agent_type: str | None = None
    category: str | None = None
    runtime: str | None = None
    is_mcp_exposed: bool = False
    input_schema: dict | None = None
    output_schema: dict | None = None
    output_policy: dict | None = None
    tags: list[str] | None = None
    extra_metadata: dict | None = None


class SkillUpdate(BaseModel):
    name: str | None = None
    tool_name: str | None = None
    title: str | None = None
    description: str | None = None
    version: str | None = None
    agent_type: str | None = None
    category: str | None = None
    runtime: str | None = None
    is_mcp_exposed: bool | None = None
    is_active: bool | None = None
    input_schema: dict | None = None
    output_schema: dict | None = None
    output_policy: dict | None = None
    tags: list[str] | None = None
    extra_metadata: dict | None = None


class SkillForkBody(BaseModel):
    target_skill_id: str = Field(..., min_length=1, max_length=64)
    target_name: str | None = None


class SkillPublishBody(BaseModel):
    version: str | None = None
    notes: str | None = None


class SkillExportRequest(BaseModel):
    skill_ids: list[str] | None = None
    skill_db_ids: list[str] | None = None


class SkillImportRequest(BaseModel):
    skills: list[dict]
    override: bool = False


class SkillValidateRequest(BaseModel):
    skill_id: str
    name: str | None = None
    tool_name: str | None = None
    input_schema: dict | None = None
    output_schema: dict | None = None


class SkillFilterParams(BaseModel):
    source_type: str | None = None
    is_active: bool | None = None
    is_mcp_exposed: bool | None = None
    category: str | None = None
    agent_type: str | None = None
    keyword: str | None = None
    page: int = Field(default=1, gt=0)
    page_size: int = Field(default=20, gt=0, le=100)


class SkillListResult(BaseModel):
    items: list[SkillRead]
    total: int
    page: int
    page_size: int


class ScanTriggerResult(BaseModel):
    scanned_count: int = 0
    added_count: int = 0
    updated_count: int = 0
    deleted_count: int = 0
    failed_count: int = 0
    is_partial: bool = False

