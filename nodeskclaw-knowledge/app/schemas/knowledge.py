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


class RuntimeIndexCapability(BaseModel):
    index_type: str
    build_supported: bool
    retrieval_supported: bool
    build_mode: str | None = None
    retrieval_mode: str | None = None
    requires_reparse: bool = False
    source_lineage_supported: bool = False
    runtime_version: str | None = None
    min_runtime_version: str | None = None
    validated: bool = False
    experimental: bool = False
    reason: str | None = None


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
    source_kind: str = "manual"
    connector_id: str | None = None
    external_object_id: str | None = None
    source_uri: str | None = None
    source_path: str | None = None
    source_revision: str | None = None
    source_etag: str | None = None
    source_modified_at: Any = None
    source_metadata: dict[str, Any] = Field(default_factory=dict)
    last_synced_at: Any = None
    sync_state: str | None = None
    archive_reason: str | None = None

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
    uploaded_by_member_id: str | None = None
    activated_at: Any = None
    superseded_at: Any = None
    created_at: Any = None
    origin_connector_id: str | None = None
    origin_external_revision: str | None = None
    origin_etag: str | None = None
    source_snapshot_at: Any = None
    created_by_actor_type: str | None = None
    created_by_actor_id: str | None = None

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


class PlaygroundRequest(BaseModel):
    knowledge_set_id: str
    query: str = Field(min_length=1)
    profile_id: str | None = None
    include_trace: bool = False
    filters: dict[str, list] | None = None


class PlaygroundPlanOut(BaseModel):
    knowledge_bases: int
    slices: int


class PlaygroundTimingOut(BaseModel):
    acl_ms: int
    ragflow_ms: int
    security_ms: int
    merge_ms: int
    total_ms: int


class PlaygroundFilterSummaryOut(BaseModel):
    candidates: int
    unauthorized: int
    superseded: int
    metadata_mismatch: int
    returned: int


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


class PlaygroundResponse(BaseModel):
    query: str
    plan: PlaygroundPlanOut
    timing: PlaygroundTimingOut
    results: list[RetrievalChunkOut]
    filter_summary: PlaygroundFilterSummaryOut


class ChatSessionCreate(BaseModel):
    knowledge_set_id: str | None = None
    application_id: str | None = None
    title: str | None = None
    answer_mode: AnswerMode = AnswerMode.detailed
    show_citations: bool = True
    answer_model: str | None = None


class ChatSessionOut(BaseModel):
    id: str
    org_id: str
    member_id: str
    knowledge_set_id: str
    application_id: str | None = None
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
    evidence_id: str
    citation_id: str
    message_id: str | None = None
    org_id: str
    issued_member_id: str
    evidence_type: str
    content: str | None = None
    source_refs: list | None = None
    origin: str
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
    source_kind: str | None = None
    connector_type: str | None = None
    connector_name: str | None = None
    source_path: str | None = None
    source_revision: str | None = None
    source_modified_at: str | None = None
    last_synced_at: str | None = None
    sync_state: str | None = None
    source_freshness: str | None = None


class EvidenceResolveOut(CitationResolveOut):
    pass


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


class EvaluationSetCreate(BaseModel):
    knowledge_set_id: str
    name: str = Field(min_length=1, max_length=128)
    description: str | None = None


class EvaluationSetUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=128)
    description: str | None = None


class EvaluationSetOut(BaseModel):
    id: str
    org_id: str
    knowledge_set_id: str
    name: str
    description: str | None = None
    created_by_member_id: str
    created_at: Any = None
    updated_at: Any = None

    model_config = {"from_attributes": True}


class EvaluationCaseCreate(BaseModel):
    query: str = Field(min_length=1)
    expected_source_file_ids: list[str] = Field(min_length=1)
    expected_keywords: list[str] | None = None
    expected_answer: str | None = None


class EvaluationCaseUpdate(BaseModel):
    query: str | None = Field(default=None, min_length=1)
    expected_source_file_ids: list[str] | None = None
    expected_keywords: list[str] | None = None
    expected_answer: str | None = None


class EvaluationCaseOut(BaseModel):
    id: str
    evaluation_set_id: str
    query: str
    expected_source_file_ids: list[Any] = Field(default_factory=list)
    expected_keywords: list[Any] | None = None
    expected_answer: str | None = None
    created_at: Any = None
    updated_at: Any = None

    model_config = {"from_attributes": True}


class EvaluationRunCreate(BaseModel):
    evaluation_set_id: str
    retrieval_profile_id: str


class EvaluationRunOut(BaseModel):
    id: str
    evaluation_set_id: str
    retrieval_profile_id: str
    status: str
    metrics: dict[str, Any] | None = None
    principal_snapshot: dict[str, Any] | None = None
    created_by_member_id: str
    attempt_count: int = 0
    max_attempts: int = 5
    next_run_at: Any = None
    last_error: str | None = None
    finished_at: Any = None
    created_at: Any = None
    updated_at: Any = None

    model_config = {"from_attributes": True}


class EvaluationResultOut(BaseModel):
    id: str
    run_id: str
    case_id: str
    hit_at_k: float
    recall_at_k: float
    mrr: float
    latency_ms: int
    returned_source_file_ids: list[Any] = Field(default_factory=list)
    unauthorized_hit: bool = False
    details: dict[str, Any] | None = None
    created_at: Any = None

    model_config = {"from_attributes": True}


class EvaluationCompareRequest(BaseModel):
    evaluation_set_id: str
    profile_a_id: str | None = None
    profile_b_id: str | None = None
    run_a_id: str | None = None
    run_b_id: str | None = None


class EvaluationCompareMetricsOut(BaseModel):
    hit_at_8: float = 0.0
    mrr: float = 0.0
    avg_latency_ms: float = 0.0
    empty_rate: float = 0.0
    degraded_rate: float = 0.0


class EvaluationCompareSideOut(BaseModel):
    run_id: str
    retrieval_profile_id: str
    metrics: EvaluationCompareMetricsOut


class EvaluationCompareOut(BaseModel):
    evaluation_set_id: str
    profile_a: EvaluationCompareSideOut
    profile_b: EvaluationCompareSideOut
    delta: EvaluationCompareMetricsOut


class KnowledgeBaseV2Out(BaseModel):
    id: str
    org_id: str
    name: str
    description: str | None = None
    embedding_model: str
    chunk_method: str
    status: str
    owner_member_id: str
    acl_version: int = 1
    visibility: str = "private"
    tags: list[str] | None = None
    active_build_profile_id: str | None = None
    knowledge_model_id: str | None = None
    build_version: int = 0

    model_config = {"from_attributes": True}


class KnowledgeSetV2Create(BaseModel):
    name: str = Field(min_length=1, max_length=128)
    description: str | None = None
    visibility: Visibility = Visibility.private
    retrieval_config: RetrievalConfig | None = None


class KnowledgeSetV2Update(BaseModel):
    name: str | None = None
    description: str | None = None
    status: str | None = None
    visibility: Visibility | None = None


class KnowledgeSetV2Out(BaseModel):
    id: str
    org_id: str
    name: str
    description: str | None = None
    owner_member_id: str
    status: str
    acl_version: int = 1
    visibility: str = "private"
    retrieval_config: dict[str, Any] | None = None
    usage_count: int = 0
    last_used_at: Any = None
    knowledge_bases: list[dict[str, Any]] | None = None

    model_config = {"from_attributes": True}


class KnowledgeApplicationCreate(BaseModel):
    name: str = Field(min_length=1, max_length=128)
    description: str | None = None
    answer_model: str | None = None
    knowledge_set_ids: list[str] | None = None


class KnowledgeApplicationUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=128)
    description: str | None = None
    answer_model: str | None = None
    status: str | None = None


class KnowledgeApplicationOut(BaseModel):
    id: str
    org_id: str
    name: str
    description: str | None = None
    owner_member_id: str
    status: str
    answer_model: str | None = None
    active_profile_id: str | None = None
    acl_version: int = 1
    visibility: str = "private"
    knowledge_set_ids: list[str] = Field(default_factory=list)

    model_config = {"from_attributes": True}


class KnowledgeApplicationBindSet(BaseModel):
    knowledge_set_id: str
    sort_order: int = 0
