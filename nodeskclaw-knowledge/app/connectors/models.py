"""Connector discovery and fetch payload models."""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class SourceDescriptor(BaseModel):
    external_object_id: str
    name: str
    path: str | None = None
    canonical_uri: str | None = None
    mime_type: str | None = None
    size: int | None = None
    external_revision: str | None = None
    etag: str | None = None
    modified_at: datetime | None = None
    source_metadata: dict[str, Any] = Field(default_factory=dict)
    is_deleted: bool = False


class DiscoveryPage(BaseModel):
    objects: list[SourceDescriptor] = Field(default_factory=list)
    next_cursor: dict[str, Any] | None = None
    has_more: bool = False


class FetchedSource(BaseModel):
    model_config = {"arbitrary_types_allowed": True}

    file_name: str
    mime_type: str | None = None
    stream: Any = None
    size: int | None = None
    sha256: str | None = None
