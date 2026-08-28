"""Domain enums for knowledge service."""

from enum import Enum


class KnowledgeBaseStatus(str, Enum):
    provisioning = "provisioning"
    active = "active"
    updating = "updating"
    degraded = "degraded"
    error = "error"
    deleting = "deleting"


class SourceFileStatus(str, Enum):
    pending = "pending"
    active = "active"
    updating = "updating"
    error = "error"
    deleting = "deleting"


class ParseStatus(str, Enum):
    pending = "pending"
    parsing = "parsing"
    active = "active"
    failed = "failed"
    superseded = "superseded"


class SubjectType(str, Enum):
    member = "member"
    role = "role"
    department = "department"
    organization = "organization"


class AclEffect(str, Enum):
    allow = "allow"
    deny = "deny"


class KbPermission(str, Enum):
    read = "read"
    upload = "upload"
    update = "update"
    delete = "delete"
    manage = "manage"
    manage_acl = "manage_acl"


class FilePermission(str, Enum):
    read = "read"
    download = "download"
    update = "update"
    delete = "delete"
    manage_acl = "manage_acl"


class SetPermission(str, Enum):
    read = "read"
    use = "use"
    update = "update"
    delete = "delete"
    manage = "manage"
    manage_acl = "manage_acl"


class ApplicationPermission(str, Enum):
    read = "read"
    use = "use"
    update = "update"
    delete = "delete"
    manage = "manage"
    manage_acl = "manage_acl"


class ApplicationStatus(str, Enum):
    draft = "draft"
    active = "active"
    disabled = "disabled"


class ApplicationReleaseStatus(str, Enum):
    draft = "draft"
    validating = "validating"
    validated = "validated"
    promoted = "promoted"
    superseded = "superseded"
    retired = "retired"
    failed = "failed"


class ReleaseChannelName(str, Enum):
    preview = "preview"
    stable = "stable"


class QualityGateResult(str, Enum):
    pass_ = "PASS"
    warn = "WARN"
    fail = "FAIL"


class QualitySnapshotScopeType(str, Enum):
    application = "application"
    knowledge_base = "knowledge_base"


class ApplicationRetrievalPolicyStatus(str, Enum):
    draft = "draft"
    active = "active"
    archived = "archived"


class ProfileScopeType(str, Enum):
    set = "set"
    application = "application"


class IngestionJobStatus(str, Enum):
    pending = "pending"
    uploading = "uploading"
    upload_unknown = "upload_unknown"
    ragflow_uploaded = "ragflow_uploaded"
    metadata_synced = "metadata_synced"
    parse_dispatched = "parse_dispatched"
    parsing = "parsing"
    validating = "validating"
    active = "active"
    failed = "failed"
    cancelled = "cancelled"


class AccessPlanKind(str, Enum):
    full_access = "full_access"
    filtered_access = "filtered_access"
    no_access = "no_access"


class RetrievalSliceKind(str, Enum):
    full_dataset = "full_dataset"
    filtered_documents = "filtered_documents"


class RuntimeRetrievalMode(str, Enum):
    semantic = "semantic"
    compiled_assisted = "compiled_assisted"
    graph_assisted = "graph_assisted"
    toc_enhanced = "toc_enhanced"


class KnowledgeSetStatus(str, Enum):
    active = "active"
    disabled = "disabled"


class ProfileStatus(str, Enum):
    draft = "draft"
    active = "active"
    archived = "archived"


class AnswerMode(str, Enum):
    concise = "concise"
    detailed = "detailed"
    structured = "structured"


class ChatMessageRole(str, Enum):
    user = "user"
    assistant = "assistant"
    system = "system"


class ChatMessageStatus(str, Enum):
    pending = "pending"
    streaming = "streaming"
    completed = "completed"
    failed = "failed"


class ChatSessionStatus(str, Enum):
    active = "active"
    archived = "archived"


class UiRole(str, Enum):
    owner = "owner"
    manager = "manager"
    editor = "editor"
    viewer = "viewer"


class Visibility(str, Enum):
    private = "private"
    department = "department"
    organization = "organization"


class AuditAction(str, Enum):
    kb_create = "KB_CREATE"
    kb_update = "KB_UPDATE"
    kb_delete = "KB_DELETE"
    kb_acl_add = "KB_ACL_ADD"
    kb_acl_delete = "KB_ACL_DELETE"
    file_upload = "FILE_UPLOAD"
    file_version_create = "FILE_VERSION_CREATE"
    file_version_activate = "FILE_VERSION_ACTIVATE"
    file_archive = "FILE_ARCHIVE"
    file_unarchive = "FILE_UNARCHIVE"
    file_reparse = "FILE_REPARSE"
    file_delete = "FILE_DELETE"
    file_download = "FILE_DOWNLOAD"
    file_acl_add = "FILE_ACL_ADD"
    file_acl_delete = "FILE_ACL_DELETE"
    set_create = "SET_CREATE"
    set_update = "SET_UPDATE"
    set_bind = "SET_BIND"
    set_unbind = "SET_UNBIND"
    set_delete = "SET_DELETE"
    set_acl_change = "SET_ACL_CHANGE"
    profile_create = "PROFILE_CREATE"
    profile_update = "PROFILE_UPDATE"
    profile_publish = "PROFILE_PUBLISH"
    profile_rollback = "PROFILE_ROLLBACK"
    retrieval = "RETRIEVAL"
    retrieval_denied = "RETRIEVAL_DENIED"
    chunk_security_drop = "CHUNK_SECURITY_DROP"
    metadata_mismatch = "METADATA_MISMATCH"
    metadata_repaired = "METADATA_REPAIRED"
    metadata_update = "METADATA_UPDATE"
    metadata_schema_update = "METADATA_SCHEMA_UPDATE"
    chat_create = "CHAT_CREATE"
    chat_query = "CHAT_QUERY"
    connector_create = "CONNECTOR_CREATE"
    connector_update = "CONNECTOR_UPDATE"
    connector_delete = "CONNECTOR_DELETE"
    connector_credential_update = "CONNECTOR_CREDENTIAL_UPDATE"
    connector_sync_start = "CONNECTOR_SYNC_START"
    connector_sync_complete = "CONNECTOR_SYNC_COMPLETE"
    connector_sync_failed = "CONNECTOR_SYNC_FAILED"
    source_discovered = "SOURCE_DISCOVERED"
    source_changed = "SOURCE_CHANGED"
    source_deleted = "SOURCE_DELETED"
    source_restored = "SOURCE_RESTORED"
    source_detached = "SOURCE_DETACHED"
    file_detach = "FILE_DETACH"


class RetrievalOrigin(str, Enum):
    direct_retrieval = "direct_retrieval"
    chat = "chat"
    agent = "agent"
    evaluation = "evaluation"


class EvaluationRunStatus(str, Enum):
    pending = "pending"
    running = "running"
    completed = "completed"
    failed = "failed"


class SourceKind(str, Enum):
    manual = "manual"
    connector = "connector"


class SourceSyncState(str, Enum):
    in_sync = "in_sync"
    stale = "stale"
    error = "error"
    detached = "detached"


class KnowledgeActorType(str, Enum):
    member = "member"
    connector = "connector"
    system = "system"


class ArchiveReason(str, Enum):
    user = "user"
    source_deleted = "source_deleted"
    connector_deleted = "connector_deleted"
    detached = "detached"


class ConnectorStatus(str, Enum):
    provisioning = "provisioning"
    active = "active"
    paused = "paused"
    auth_error = "auth_error"
    error = "error"
    deleting = "deleting"


class ConnectorSyncMode(str, Enum):
    manual = "manual"
    interval = "interval"


class ConnectorSyncRunStatus(str, Enum):
    pending = "pending"
    discovering = "discovering"
    applying = "applying"
    waiting_ingestion = "waiting_ingestion"
    completed = "completed"
    partial = "partial"
    failed = "failed"
    cancelled = "cancelled"


class ConnectorSyncTrigger(str, Enum):
    manual = "manual"
    interval = "interval"


class ConnectorSyncItemAction(str, Enum):
    create = "create"
    update_content = "update_content"
    update_metadata = "update_metadata"
    archive = "archive"
    restore = "restore"


class ConnectorSyncItemStatus(str, Enum):
    pending = "pending"
    fetching = "fetching"
    ingestion_dispatched = "ingestion_dispatched"
    waiting_parse = "waiting_parse"
    applied = "applied"
    failed = "failed"


class ConnectorSourceObjectState(str, Enum):
    active = "active"
    missing = "missing"
    deleted = "deleted"
    error = "error"
    detached = "detached"


class RuntimeBindingStatus(str, Enum):
    provisioning = "provisioning"
    ready = "ready"
    syncing = "syncing"
    error = "error"
    deleting = "deleting"


class BindingDriftStatus(str, Enum):
    unknown = "unknown"
    in_sync = "in_sync"
    drifted = "drifted"
    reconciling = "reconciling"
    error = "error"


class RuntimeType(str, Enum):
    ragflow = "ragflow"


class RuntimeResourceType(str, Enum):
    dataset = "dataset"


class IndexType(str, Enum):
    chunk = "chunk"
    question = "question"
    hierarchical_summary = "hierarchical_summary"
    table = "table"
    outline = "outline"
    graph = "graph"


class IndexStateStatus(str, Enum):
    not_built = "not_built"
    building = "building"
    ready = "ready"
    stale = "stale"
    failed = "failed"
    unsupported = "unsupported"


class IndexRetrievalStatus(str, Enum):
    unavailable = "unavailable"
    ready = "ready"
    degraded = "degraded"
    unsupported = "unsupported"


class BuildJobStatus(str, Enum):
    queued = "queued"
    running = "running"
    completed = "completed"
    partial = "partial"
    failed = "failed"
    cancelled = "cancelled"


class BuildTriggerPolicy(str, Enum):
    ingestion = "ingestion"
    on_activate = "on_activate"
    debounce = "debounce"
    manual = "manual"


DEFAULT_RETRIEVAL_CONFIG = {
    "top_k": 1024,
    "top_n": 8,
    "similarity_threshold": 0.2,
    "vector_similarity_weight": 0.7,
    "keyword": False,
    "rerank_id": None,
    "highlight": False,
    "cross_languages": [],
    "answer_model": "",
    "failure_policy": "fail_closed",
    "context_max_chunks": 8,
    "context_max_chars": 24000,
    "retrieval_mode": "adaptive",
    "allow_question_enrichment": True,
    "allow_summary": True,
    "allow_graph": True,
    "allow_toc_enhance": True,
    "fallback_policy": "chunk",
    "candidate_budget": 1024,
    "rerank_candidates": 64,
}
