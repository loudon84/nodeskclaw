import json
from datetime import datetime
from typing import Any

from pydantic import Field, field_validator

from app.schemas.common import CamelModel


class PortalAccountCreate(CamelModel):
    entity_type: str = Field(serialization_alias="entityType")
    erp_entity_code: str = Field(serialization_alias="erpEntityCode")
    erp_entity_name: str = Field(serialization_alias="erpEntityName")
    portal_name: str = Field(serialization_alias="portalName")
    portal_url: str = Field(serialization_alias="portalUrl")
    login_account: str = Field(serialization_alias="loginAccount")
    credential_ref: str | None = Field(None, serialization_alias="credentialRef")
    client_open_mode: str = Field("webcontents", serialization_alias="clientOpenMode")
    client_session_partition: str = Field("", serialization_alias="clientSessionPartition")
    rpa_profile_id: str | None = Field(None, serialization_alias="rpaProfileId")
    status: str = "ENABLED"
    owner_dept_id: str | None = Field(None, serialization_alias="ownerDeptId")


class PortalAccountUpdate(CamelModel):
    entity_type: str | None = Field(None, serialization_alias="entityType")
    erp_entity_code: str | None = Field(None, serialization_alias="erpEntityCode")
    erp_entity_name: str | None = Field(None, serialization_alias="erpEntityName")
    portal_name: str | None = Field(None, serialization_alias="portalName")
    portal_url: str | None = Field(None, serialization_alias="portalUrl")
    login_account: str | None = Field(None, serialization_alias="loginAccount")
    credential_ref: str | None = Field(None, serialization_alias="credentialRef")
    client_open_mode: str | None = Field(None, serialization_alias="clientOpenMode")
    client_session_partition: str | None = Field(None, serialization_alias="clientSessionPartition")
    rpa_profile_id: str | None = Field(None, serialization_alias="rpaProfileId")
    status: str | None = None
    owner_dept_id: str | None = Field(None, serialization_alias="ownerDeptId")


class PortalAccountResponse(CamelModel):
    id: str
    tenant_id: str = Field(serialization_alias="tenantId")
    entity_type: str = Field(serialization_alias="entityType")
    erp_entity_code: str = Field(serialization_alias="erpEntityCode")
    erp_entity_name: str = Field(serialization_alias="erpEntityName")
    portal_name: str = Field(serialization_alias="portalName")
    portal_url: str = Field(serialization_alias="portalUrl")
    login_account: str = Field(serialization_alias="loginAccount")
    credential_ref: str | None = Field(None, serialization_alias="credentialRef")
    client_open_mode: str = Field(serialization_alias="clientOpenMode")
    client_session_partition: str = Field(serialization_alias="clientSessionPartition")
    rpa_profile_id: str | None = Field(None, serialization_alias="rpaProfileId")
    status: str
    owner_dept_id: str | None = Field(None, serialization_alias="ownerDeptId")
    created_by: str = Field(serialization_alias="createdBy")
    created_at: datetime = Field(serialization_alias="createdAt")
    updated_at: datetime = Field(serialization_alias="updatedAt")


class PortalAccessGrantCreate(CamelModel):
    subject_type: str = Field(serialization_alias="subjectType")
    subject_id: str = Field(serialization_alias="subjectId")
    permissions: list[str]


class PortalAccessGrantResponse(CamelModel):
    id: str
    portal_account_id: str = Field(serialization_alias="portalAccountId")
    subject_type: str = Field(serialization_alias="subjectType")
    subject_id: str = Field(serialization_alias="subjectId")
    permissions: list[str]
    granted_by: str = Field(serialization_alias="grantedBy")
    granted_at: str = Field(serialization_alias="grantedAt")

    @field_validator("permissions", mode="before")
    @classmethod
    def parse_permissions(cls, value: Any) -> list[str]:
        if isinstance(value, str):
            return json.loads(value or "[]")
        return value or []


class PortalTestOpenResponse(CamelModel):
    portal_account_id: str = Field(serialization_alias="portalAccountId")
    portal_url: str = Field(serialization_alias="portalUrl")
    client_open_mode: str = Field(serialization_alias="clientOpenMode")
    client_session_partition: str = Field(serialization_alias="clientSessionPartition")
    can_open: bool = Field(serialization_alias="canOpen")
