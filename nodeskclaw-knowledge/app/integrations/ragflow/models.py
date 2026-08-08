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
    progress: float | None = None
    progress_msg: str | None = None
    chunk_count: int | None = None
    token_count: int | None = None
    process_duration: float | None = None
    size: int | None = None
    enabled: bool | None = None
    meta_fields: dict[str, Any] = Field(default_factory=dict)


class RagflowChunk(BaseModel):
    id: str
    content: str = ""
    document_id: str = ""
    dataset_id: str | None = None
    similarity: float = 0.0
    document_keyword: str | None = None
    document_name: str | None = None
    document_metadata: dict[str, Any] = Field(default_factory=dict)
    kb_id: str | None = None
    positions: list | None = None
    term_similarity: float | None = None
    vector_similarity: float | None = None
    highlight: str | None = None


class RagflowRetrievalResult(BaseModel):
    chunks: list[RagflowChunk] = Field(default_factory=list)
    total: int = 0
