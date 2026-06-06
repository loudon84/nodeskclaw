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
    tags: list | None = None
    created_by: str | None = None
    scanned_at: str | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None


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
