from datetime import datetime

from pydantic import BaseModel, Field


class CollectionCreate(BaseModel):
    collection_id: str
    name: str
    description: str | None = None
    agent_type: str | None = None
    version: str = "1.0.0"


class CollectionRead(BaseModel):
    model_config = {"from_attributes": True}

    id: str
    org_id: str
    collection_id: str
    name: str
    description: str | None = None
    agent_type: str | None = None
    version: str = "1.0.0"
    is_read_only: bool = False
    is_active: bool = True
    created_by: str | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None


class CollectionListResult(BaseModel):
    items: list[CollectionRead]
    total: int
    page: int
    page_size: int
