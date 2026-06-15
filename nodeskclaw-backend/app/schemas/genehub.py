"""Pydantic schemas for GeneHub Hermes Skill Registry."""

import re
from datetime import datetime

from pydantic import BaseModel, Field, field_validator, model_validator

SKILL_NAME_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")
SLUG_PATTERN = re.compile(r"^[a-z0-9][a-z0-9-]{0,127}$")


class CompatibilityItem(BaseModel):
    runtime: str
    target: str
    min_version: str | None = None


class AdminGeneHubSkillCreate(BaseModel):
    name: str = Field(..., max_length=128)
    slug: str = Field(..., max_length=128)
    description: str | None = None
    short_description: str | None = Field(None, max_length=256)
    category: str | None = Field(None, max_length=32)
    tags: list[str] = []
    version: str = Field("1.0.0", max_length=32)
    skill_content: str = Field(..., min_length=1)
    scripts: dict[str, str] = {}
    compatibility: list[CompatibilityItem]
    visibility: str = "org_private"
    is_published: bool = False

    @field_validator("slug")
    @classmethod
    def validate_slug(cls, value: str) -> str:
        if not SLUG_PATTERN.match(value):
            raise ValueError("slug 格式无效")
        return value


class AdminGeneHubSkillUpdate(BaseModel):
    name: str | None = Field(None, max_length=128)
    description: str | None = None
    short_description: str | None = Field(None, max_length=256)
    category: str | None = Field(None, max_length=32)
    tags: list[str] | None = None
    version: str | None = Field(None, max_length=32)
    skill_content: str | None = None
    scripts: dict[str, str] | None = None
    compatibility: list[CompatibilityItem] | None = None
    visibility: str | None = None


class AdminGeneHubSkillReview(BaseModel):
    action: str = Field(..., pattern=r"^(approve|reject)$")
    reason: str | None = Field(None, max_length=512)


class AdminGeneHubSkillInfo(BaseModel):
    id: str
    slug: str
    version: str
    review_status: str | None = None
    is_published: bool = False
    name: str | None = None

    model_config = {"from_attributes": True}


class GeneHubEntitlementTarget(BaseModel):
    target_type: str = Field(..., pattern=r"^(organization|user|role|department)$")
    target_id: str = Field(..., max_length=64)
    permissions: list[str]
    profile_scope: str | None = Field(None, max_length=128)


class GeneHubEntitlementGrant(BaseModel):
    gene_id: str
    targets: list[GeneHubEntitlementTarget]


class AdminInstallJobAssign(BaseModel):
    gene_slug: str = Field(..., max_length=128)
    version: str = "latest"
    target_type: str = Field(..., pattern=r"^(organization|user|role|department)$")
    target_ids: list[str]
    profile_name: str | None = Field(None, max_length=128)
    job_type: str = Field("install", pattern=r"^(install|update|uninstall|rollback)$")


class AdminInstallJobInfo(BaseModel):
    id: str
    user_id: str
    status: str
    gene_slug: str
    gene_version: str
    job_type: str
    install_mode: str
    profile_id: str | None = None
    created_at: datetime | None = None

    model_config = {"from_attributes": True}


class AdminInstallJobAssignResult(BaseModel):
    created: int
    skipped: int
    jobs: list[AdminInstallJobInfo]


class DesktopDeviceRegister(BaseModel):
    device_name: str = Field(..., max_length=128)
    device_fingerprint: str = Field(..., max_length=128)
    os_type: str = Field(..., max_length=32)
    os_version: str | None = Field(None, max_length=64)
    app_version: str | None = Field(None, max_length=64)


class DesktopDeviceInfo(BaseModel):
    desktop_device_id: str
    device_id: str | None = None
    status: str


class DesktopHermesProfileRegister(BaseModel):
    desktop_device_id: str
    profile_name: str = Field(..., max_length=128)
    hermes_home: str
    runtime_version: str | None = Field(None, max_length=64)
    gateway_url: str | None = None
    gateway_port: int | None = None
    capabilities: dict | None = None


class DesktopHermesProfileInfo(BaseModel):
    profile_id: str
    status: str


class DesktopHeartbeatProfile(BaseModel):
    profile_id: str
    profile_name: str = Field(..., max_length=128)
    status: str = Field(..., max_length=32)


class DesktopHeartbeat(BaseModel):
    desktop_device_id: str
    profiles: list[DesktopHeartbeatProfile] = []


class DesktopHeartbeatResponse(BaseModel):
    sync_interval_seconds: int
    pending_jobs_interval_seconds: int = 60
    genehub_enabled: bool


class DesktopSelfServiceInstallJobCreate(BaseModel):
    profile_id: str
    gene_slug: str = Field(..., max_length=128)
    version: str = "latest"
    job_type: str = Field("install", pattern=r"^(install|update|uninstall|rollback)$")

    @model_validator(mode="before")
    @classmethod
    def accept_action_alias(cls, data):
        if isinstance(data, dict) and "job_type" not in data and "action" in data:
            data = dict(data)
            data["job_type"] = data["action"]
        return data


class DesktopInstallJobStatusUpdate(BaseModel):
    status: str = Field(
        ...,
        pattern=r"^(downloading|validating|installing|installed|failed|cancelled)$",
    )
    install_path: str | None = None
    gene_version: str | None = Field(None, max_length=32)
    message: str | None = None
    error_code: str | None = Field(None, max_length=64)
    error_message: str | None = None
    client_report: dict | None = None


class DesktopInstalledSkillItem(BaseModel):
    skill_name: str = Field(..., max_length=128)
    gene_slug: str = Field(..., max_length=128)
    gene_version: str = Field(..., max_length=32)
    install_path: str | None = None
    status: str = Field(..., max_length=32)


class DesktopInstalledSkillSync(BaseModel):
    profile_id: str
    device_id: str | None = None
    skills: list[DesktopInstalledSkillItem] = []


class DesktopSkillInfo(BaseModel):
    gene_id: str
    slug: str
    gene_slug: str
    name: str
    display_name: str
    description: str | None = None
    short_description: str | None = None
    version: str
    gene_version: str
    skill_name: str
    category: str | None = None
    tags: list[str] = []
    permissions: list[str] = []
    installed_status: str
    installed: bool = False
    update_available: bool = False


class DesktopPendingJobInfo(BaseModel):
    job_id: str
    source: str | None = None
    requested_by: str | None = None
    profile_id: str | None = None
    profile_name: str | None = None
    gene_slug: str
    gene_version: str
    skill_name: str
    job_type: str
    action: str
    status: str
    created_at: datetime | None = None
    assigned_at: datetime | None = None
    claimed_at: datetime | None = None
    updated_at: datetime | None = None
    error_code: str | None = None
    error_message: str | None = None
    client_report: dict | None = None


class DesktopInstallJobInfo(BaseModel):
    job_id: str
    status: str


class DesktopInstallJobDetail(BaseModel):
    job_id: str
    source: str | None = None
    requested_by: str | None = None
    profile_id: str | None = None
    profile_name: str | None = None
    gene_slug: str
    gene_version: str
    skill_name: str
    job_type: str | None = None
    action: str
    status: str
    desktop_confirmation_required: bool = False
    created_at: datetime | None = None
    assigned_at: datetime | None = None
    claimed_at: datetime | None = None
    updated_at: datetime | None = None
    finished_at: datetime | None = None
    error_code: str | None = None
    error_message: str | None = None
    client_report: dict | None = None


class DesktopIgnoreInstallJobRequest(BaseModel):
    reason: str | None = Field(None, max_length=128)
    client_report: dict | None = None


class BundlePreviewFile(BaseModel):
    relative_path: str
    size: int | None = None
    sha256: str | None = None
    kind: str = "file"


class BundlePreviewScript(BaseModel):
    relative_path: str
    size: int | None = None
    sha256: str | None = None
    entry: bool | None = None
    risk_level: str | None = None


class BundleValidationPreview(BaseModel):
    has_skill: bool = False
    has_scripts: bool = False
    requires_signature: bool = True
    signature_present: bool = False
    path_warnings: list[str] = []
    compatibility_warnings: list[str] = []


class DesktopBundlePreviewInfo(BaseModel):
    job_id: str
    gene_slug: str
    gene_version: str
    skill_name: str
    action: str
    manifest_hash: str
    bundle_hash: str
    compatibility: list | dict = []
    files: list[BundlePreviewFile] = []
    scripts: list[BundlePreviewScript] = []
    validation_preview: BundleValidationPreview


class GeneHubSkillPermissions(BaseModel):
    can_install: bool = False
    can_update: bool = False
    can_uninstall: bool = False


class GeneHubManifestPreview(BaseModel):
    has_skill: bool = False
    file_count: int = 0
    has_scripts: bool = False
    requires_signature: bool = True


class McpGeneHubSkillItem(BaseModel):
    gene_slug: str
    gene_version: str
    skill_name: str
    display_name: str
    description: str | None = None
    category: str | None = None
    tags: list[str] = []
    installed: bool = False
    installed_version: str | None = None
    update_available: bool = False
    permissions: GeneHubSkillPermissions


class McpGeneHubSkillDetail(BaseModel):
    gene_slug: str
    gene_version: str
    skill_name: str
    display_name: str
    description: str | None = None
    category: str | None = None
    tags: list[str] = []
    installed: bool = False
    installed_version: str | None = None
    update_available: bool = False
    installable: bool = False
    permissions: GeneHubSkillPermissions
    manifest_preview: GeneHubManifestPreview


class McpRegistrationJobResult(BaseModel):
    job_id: str | None = None
    status: str
    source: str | None = None
    gene_slug: str
    gene_version: str
    skill_name: str
    profile_id: str
    profile_name: str | None = None
    action: str
    desktop_confirmation_required: bool = False
    message: str


class McpRegistrationInfo(BaseModel):
    job_id: str | None = None
    source: str | None = None
    gene_slug: str
    gene_version: str | None = None
    skill_name: str | None = None
    profile_id: str | None = None
    profile_name: str | None = None
    action: str | None = None
    status: str
    error_code: str | None = None
    error_message: str | None = None
    assigned_at: datetime | None = None
    claimed_at: datetime | None = None
    updated_at: datetime | None = None
    finished_at: datetime | None = None


class DesktopBundleFile(BaseModel):
    relative_path: str
    content: str
    encoding: str = "utf-8"


class DesktopBundleInfo(BaseModel):
    schema_version: str
    manifest: dict
    files: list[DesktopBundleFile]
    scripts: list[DesktopBundleFile] = []
    hashes: dict[str, str]
    signature: dict | None = None
