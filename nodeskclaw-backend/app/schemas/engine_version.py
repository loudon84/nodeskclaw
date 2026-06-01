"""Pydantic schemas for the engine version catalog API."""

from datetime import datetime

from pydantic import BaseModel


class EngineVersionCreate(BaseModel):
    runtime: str
    version: str
    image_tag: str
    release_notes: str | None = None


class EngineVersionUpdate(BaseModel):
    status: str | None = None
    is_default: bool | None = None
    release_notes: str | None = None


class EngineVersionInfo(BaseModel):
    id: str
    runtime: str
    version: str
    image_tag: str
    status: str
    release_notes: str | None = None
    is_default: bool
    published_by: str | None = None
    created_at: datetime

    model_config = {"from_attributes": True}
