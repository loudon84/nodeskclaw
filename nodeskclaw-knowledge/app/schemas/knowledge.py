"""API request/response schemas."""

from decimal import Decimal
from typing import Any

from pydantic import BaseModel, Field


class KnowledgeBaseCreate(BaseModel):
    name: str = Field(min_length=1, max_length=128)
    description: str | None = None
    embedding_model: str = "bge-m3"
    chunk_method: str = "naive"
    parser_config: dict[str, Any] | None = None


class KnowledgeBaseUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=128)
    description: str | None = None


class KnowledgeBaseOut(BaseModel):
    id: str
    org_id: str
    name: str
    description: str | None = None
    ragflow_dataset_id: str | None = None
    embedding_model: str
    chunk_method: str
    status: str
    owner_member_id: str

    model_config = {"from_attributes": True}


class AclCreate(BaseModel):
    subject_type: str
    subject_id: str
    permission: str
    effect: str = "allow"


class AclOut(BaseModel):
    id: str
    subject_type: str
    subject_id: str
    permission: str
    effect: str
    created_by_member_id: str

    model_config = {"from_attributes": True}


class KnowledgeSetCreate(BaseModel):
    name: str = Field(min_length=1, max_length=128)
    description: str | None = None
    embedding_model: str = "bge-m3"


class KnowledgeSetUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    status: str | None = None


class KnowledgeSetOut(BaseModel):
    id: str
    org_id: str
    name: str
    description: str | None = None
    embedding_model: str
    owner_member_id: str
    status: str

    model_config = {"from_attributes": True}


class KnowledgeSetBind(BaseModel):
    knowledge_base_id: str
    weight: Decimal = Decimal("1.0")
    sort_order: int = 0


class SourceFileOut(BaseModel):
    id: str
    org_id: str
    knowledge_base_id: str
    file_name: str
    mime_type: str | None = None
    owner_member_id: str
    active_version_id: str | None = None
    status: str

    model_config = {"from_attributes": True}


class IngestionJobOut(BaseModel):
    id: str
    source_file_id: str
    file_version_id: str
    ragflow_document_id: str | None = None
    status: str
    progress: int
    error_code: str | None = None
    error_message: str | None = None

    model_config = {"from_attributes": True}


class RetrievalRequest(BaseModel):
    knowledge_set_id: str
    query: str = Field(min_length=1)
    top_k: int = 20
    similarity_threshold: float | None = 0.2


class RetrievalChunkOut(BaseModel):
    chunk_id: str
    knowledge_base_id: str | None = None
    source_file_id: str | None = None
    file_version_id: str | None = None
    document_id: str | None = None
    file_name: str | None = None
    content: str
    similarity: float = 0.0


class RetrievalResponse(BaseModel):
    query_id: str
    chunks: list[RetrievalChunkOut]
