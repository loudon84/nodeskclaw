from datetime import datetime

from pydantic import BaseModel, Field


class SkillReleaseRead(BaseModel):
    model_config = {"from_attributes": True}

    id: str
    org_id: str
    skill_db_id: str
    skill_id: str
    tool_name: str | None = None
    version: str
    status: str
    digest: str
    title: str | None = None
    description: str | None = None
    category: str | None = None
    input_schema: dict | None = None
    output_schema: dict | None = None
    output_policy: dict | None = None
    extra_metadata: dict | None = None
    requirements: dict | None = None
    published_at: datetime | None = None
    published_by: str | None = None
    deprecated_at: datetime | None = None
    created_by: str | None = None
    notes: str | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None


class SkillReleaseCreateRequest(BaseModel):
    notes: str | None = None
    version: str | None = Field(default=None, max_length=32)
    connector_instance_ids: list[str] = Field(default_factory=list)
    knowledge_refs: list[str] = Field(default_factory=list)


class SkillReleaseListResult(BaseModel):
    items: list[SkillReleaseRead]
    total: int
