"""API request/response schemas."""

from decimal import Decimal
from typing import Any

from pydantic import BaseModel, Field

from app.models.enums import (
    AclEffect,
    AnswerMode,
    FilePermission,
    KbPermission,
    SetPermission,
    SubjectType,
    UiRole,
    Visibility,
)


ALLOWED_ROLES = {"member", "operator", "admin"}


class KnowledgeBaseCreate(BaseModel):
    name: str = Field(min_length=1, max_length=128)
    description: str | None = None
    embedding_model: str = "bge-m3"
    chunk_method: str = "naive"
    parser_config: dict[str, Any] | None = None
    visibility: Visibility = Visibility.private
    tags: list[str] | None = None


class KnowledgeBaseUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=128)
    description: str | None = None
    tags: list[str] | None = None
    visibility: Visibility | None = None


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
    acl_version: int = 1
    visibility: str = "private"
    tags: list[str] | None = None
    last_synced_at: Any = None
    last_error: str | None = None
    metadata_schema: dict[str, Any] | None = None
    document_count: int | None = None
    chunk_count: int | None = None
    ui_role: str | None = None

    model_config = {"from_attributes": True}


class AclCreate(BaseModel):
    subject_type: SubjectType
    subject_id: str = Field(min_length=1, max_length=128)
    permission: str
    effect: AclEffect = AclEffect.allow


class KbAclCreate(AclCreate):
    permission: KbPermission


class FileAclCreate(AclCreate):
    permission: FilePermission


class SetAclCreate(AclCreate):
    permission: SetPermission


class UiRoleAclCreate(BaseModel):
    subject_type: SubjectType
    subject_id: str = Field(min_length=1, max_length=128)
    role: UiRole
    effect: AclEffect = AclEffect.allow


class AclOut(BaseModel):
    id: str
    subject_type: str
    subject_id: str
    permission: str
    effect: str
    created_by_member_id: str

    model_config = {"from_attributes": True}


class RetrievalConfig(BaseModel):
    top_k: int = 1024
    top_n: int = 8
    similarity_threshold: float = 0.2
    vector_similarity_weight: float = 0.7
    keyword: bool = False
    rerank_id: str | None = None
    highlight: bool = False
    cross_languages: list[str] = Field(default_factory=list)
    answer_model: str = ""
    failure_policy: str = "fail_closed"
    context_max_chunks: int = 8
    context_max_chars: int = 24000


class RetrievalProfileCreate(BaseModel):
    config: RetrievalConfig | None = None


class RetrievalProfileUpdate(BaseModel):
    config: RetrievalConfig


class RetrievalProfileRollback(BaseModel):
    publish: bool = False


class RetrievalProfileOut(BaseModel):
    id: str
    knowledge_set_id: str
    version: int
    config: dict[str, Any]
    status: str
    created_by_member_id: str
    activated_at: Any = None
    created_at: Any = None
    updated_at: Any = None

    model_config = {"from_attributes": True}


class KnowledgeSetCreate(BaseModel):
    name: str = Field(min_length=1, max_length=128)
    description: str | None = None
    embedding_model: str = "bge-m3"
    visibility: Visibility = Visibility.private
    retrieval_config: RetrievalConfig | None = None


class KnowledgeSetUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    status: str | None = None
    visibility: Visibility | None = None
    retrieval_config: RetrievalConfig | None = None


class KnowledgeSetOut(BaseModel):
    id: str
    org_id: str
    name: str
    description: str | None = None
    embedding_model: str
    owner_member_id: str
    status: str
    acl_version: int = 1
    visibility: str = "private"
    retrieval_config: dict[str, Any] | None = None
    usage_count: int = 0
    last_used_at: Any = None
    document_count: int | None = None
    ui_role: str | None = None
    knowledge_bases: list[dict[str, Any]] | None = None

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
    acl_version: int = 1
    last_error: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict, validation_alias="metadata_")
    metadata_revision: int = 0
    archived_at: Any = None
    parse_status: str | None = None
    chunk_count: int | None = None
    version_no: int | None = None

    model_config = {"from_attributes": True, "populate_by_name": True}


class SourceFileVersionOut(BaseModel):
    id: str
    source_file_id: str
    version_no: int
    file_size: int | None = None
    sha256: str | None = None
    parse_status: str
    ragflow_run: str | None = None
    ragflow_progress: float | None = None
    ragflow_progress_msg: str | None = None
    chunk_count: int | None = None
    token_count: int | None = None
    process_duration: float | None = None
    uploaded_by_member_id: str
    activated_at: Any = None
    superseded_at: Any = None
    created_at: Any = None

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
    attempt_count: int = 0
    max_attempts: int = 5
    next_run_at: Any = None
    finished_at: Any = None
    created_by_member_id: str | None = None

    model_config = {"from_attributes": True}


class RetrievalOptions(BaseModel):
    top_n: int | None = None
    top_k: int | None = None
    similarity_threshold: float | None = None
    keyword: bool | None = None
    highlight: bool | None = None


class RetrievalRequest(BaseModel):
    knowledge_set_id: str
    query: str = Field(min_length=1)
    options: RetrievalOptions | None = None
    top_k: int | None = None
    similarity_threshold: float | None = None
    filters: dict[str, list] | None = None


class MetadataSchemaPut(BaseModel):
    fields: list[dict[str, Any]]


class SourceFileMetadataPatch(BaseModel):
    metadata: dict[str, Any]


class SourceFileMetadataOut(BaseModel):
    metadata: dict[str, Any] = Field(default_factory=dict)
    metadata_revision: int = 0


class RetrievalChunkOut(BaseModel):
    chunk_id: str
    knowledge_base_id: str | None = None
    source_file_id: str | None = None
    file_version_id: str | None = None
    document_id: str | None = None
    file_name: str | None = None
    content: str
    similarity: float = 0.0
    weighted_score: float | None = None
    page: int | None = None
    positions: list | None = None
    term_similarity: float | None = None
    vector_similarity: float | None = None
    highlight: str | None = None


class RetrievalResponse(BaseModel):
    query_id: str
    chunks: list[RetrievalChunkOut]


class ChatSessionCreate(BaseModel):
    knowledge_set_id: str
    title: str | None = None
    answer_mode: AnswerMode = AnswerMode.detailed
    show_citations: bool = True
    answer_model: str | None = None


class ChatSessionOut(BaseModel):
    id: str
    org_id: str
    member_id: str
    knowledge_set_id: str
    title: str | None = None
    answer_mode: str
    show_citations: bool
    answer_model: str | None = None
    status: str

    model_config = {"from_attributes": True}


class ChatMessageCreate(BaseModel):
    content: str = Field(min_length=1)
    stream: bool = True


class ChatMessageOut(BaseModel):
    id: str
    session_id: str
    role: str
    content: str
    status: str
    model: str | None = None
    prompt_tokens: int | None = None
    completion_tokens: int | None = None

    model_config = {"from_attributes": True}


class CitationResolveOut(BaseModel):
    citation_id: str
    message_id: str
    knowledge_base_id: str
    source_file_id: str
    file_version_id: str
    document_id: str | None = None
    chunk_id: str | None = None
    page: int | None = None
    positions: list | None = None
    score: float | None = None
    quote: str | None = None
    accessible: bool
    reason: str


class AuditLogOut(BaseModel):
    id: str
    org_id: str
    member_id: str | None = None
    action: str
    resource_type: str
    resource_id: str | None = None
    details: dict[str, Any] | None = None
    created_at: Any = None

    model_config = {"from_attributes": True}


class DashboardOut(BaseModel):
    stats: dict[str, int]
    parse_status_summary: dict[str, int]
    recent_knowledge_sets: list[KnowledgeSetOut] = Field(default_factory=list)
    recent_documents: list[SourceFileOut] = Field(default_factory=list)
