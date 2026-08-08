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


class IngestionJobStatus(str, Enum):
    pending = "pending"
    uploading = "uploading"
    ragflow_uploaded = "ragflow_uploaded"
    metadata_synced = "metadata_synced"
    parsing = "parsing"
    validating = "validating"
    active = "active"
    failed = "failed"
    cancelled = "cancelled"


class AccessPlanKind(str, Enum):
    full_access = "full_access"
    filtered_access = "filtered_access"
    no_access = "no_access"


class KnowledgeSetStatus(str, Enum):
    active = "active"
    disabled = "disabled"
