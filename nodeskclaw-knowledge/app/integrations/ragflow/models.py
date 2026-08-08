"""RAGFlow DTO models."""

from typing import Any

from pydantic import BaseModel, Field


class RagflowDataset(BaseModel):
    id: str
    name: str = ""
    embedding_model: str | None = None
    chunk_method: str | None = None
    permission: str | None = None


class RagflowDocument(BaseModel):
    id: str
    name: str = ""
    dataset_id: str | None = None
    run: str | None = None
    size: int | None = None
    meta_fields: dict[str, Any] = Field(default_factory=dict)


class RagflowChunk(BaseModel):
    id: str
    content: str = ""
    document_id: str = ""
    dataset_id: str | None = None
    similarity: float = 0.0
    document_keyword: str | None = None
    document_metadata: dict[str, Any] = Field(default_factory=dict)
    kb_id: str | None = None


class RagflowRetrievalResult(BaseModel):
    chunks: list[RagflowChunk] = Field(default_factory=list)
    total: int = 0
