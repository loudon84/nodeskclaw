"""Domain enums for knowledge service."""

from enum import Enum


class KnowledgeBaseStatus(str, Enum):
    provisioning = "provisioning"
    active = "active"
    updating = "updating"
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


class IngestionJobStatus(str, Enum):
    pending = "pending"
    uploading = "uploading"
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


class RetrievalOrigin(str, Enum):
    direct_retrieval = "direct_retrieval"
    chat = "chat"
    agent = "agent"
    evaluation = "evaluation"


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
}
