from enum import Enum


class SourceType(str, Enum):
    SYSTEM_BUILTIN = "system_builtin"
    CENTRAL = "central"
    MARKETPLACE = "marketplace"
    GITHUB = "github"
    GIT = "git"
    LOCAL_UPLOAD = "local_upload"
    USER_CREATED = "user_created"
    AGENT_SCANNED = "agent_scanned"


class InstallMode(str, Enum):
    COPY = "copy"
    SYMLINK = "symlink"
    DOCKER_MOUNT = "docker_mount"
    REGISTRY_BIND = "registry_bind"
    API_DEPLOY = "api_deploy"


class InstallStatus(str, Enum):
    PENDING = "pending"
    INSTALLED = "installed"
    FAILED = "failed"
    OUTDATED = "outdated"
    REMOVED = "removed"


class ConflictType(str, Enum):
    SAME_SKILL_ID = "same_skill_id"
    SAME_TOOL_NAME = "same_tool_name"
    SAME_INSTALL_PATH = "same_install_path"
    VERSION_DOWNGRADE = "version_downgrade"
    READ_ONLY_OVERRIDE = "read_only_override"
    AGENT_TYPE_MISMATCH = "agent_type_mismatch"


class ConflictStrategy(str, Enum):
    SKIP = "skip"
    OVERWRITE = "overwrite"
    RENAME = "rename"
    INSTALL_AS_NEW_VERSION = "install_as_new_version"
    ABORT = "abort"


class AuthMode(str, Enum):
    NONE = "none"
    TOKEN = "token"
    SSH_KEY = "ssh_key"


class SyncStatus(str, Enum):
    NEVER = "never"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"
    DISABLED = "disabled"


class ImportStatus(str, Enum):
    PREVIEW = "preview"
    IMPORTING = "importing"
    COMPLETED = "completed"
    FAILED = "failed"


class SkillAuditAction(str, Enum):
    SCANNED = "hermes.skill.scanned"
    CREATED = "hermes.skill.created"
    UPDATED = "hermes.skill.updated"
    DELETED = "hermes.skill.deleted"
    ENABLED = "hermes.skill.enabled"
    DISABLED = "hermes.skill.disabled"
    IMPORTED = "hermes.skill.imported"
    REGISTRY_SYNCED = "hermes.skill.registry.synced"
    INSTALLED = "hermes.skill.installed"
    UNINSTALLED = "hermes.skill.uninstalled"
    COLLECTION_CREATED = "hermes.skill.collection.created"
    COLLECTION_INSTALLED = "hermes.skill.collection.installed"
    CONFLICT_DETECTED = "hermes.skill.conflict.detected"
    CONFLICT_RESOLVED = "hermes.skill.conflict.resolved"
    INVOKED = "hermes.skill.invoked"


READ_ONLY_SOURCE_TYPES = frozenset({
    SourceType.SYSTEM_BUILTIN,
    SourceType.MARKETPLACE,
    SourceType.GITHUB,
    SourceType.GIT,
    SourceType.AGENT_SCANNED,
})

DEFAULT_CONFLICT_STRATEGIES = {
    SourceType.SYSTEM_BUILTIN: ConflictStrategy.ABORT,
    SourceType.MARKETPLACE: ConflictStrategy.INSTALL_AS_NEW_VERSION,
    SourceType.GITHUB: ConflictStrategy.INSTALL_AS_NEW_VERSION,
    SourceType.GIT: ConflictStrategy.INSTALL_AS_NEW_VERSION,
    SourceType.USER_CREATED: ConflictStrategy.RENAME,
    SourceType.AGENT_SCANNED: ConflictStrategy.SKIP,
    SourceType.CENTRAL: ConflictStrategy.INSTALL_AS_NEW_VERSION,
    SourceType.LOCAL_UPLOAD: ConflictStrategy.INSTALL_AS_NEW_VERSION,
}
