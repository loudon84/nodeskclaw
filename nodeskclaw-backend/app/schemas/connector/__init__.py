from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field


class ConnectorDefinitionCreate(BaseModel):
    name: str = Field(min_length=1, max_length=128)
    kind: Literal["mcp", "rest", "db"]
    title: str | None = None
    description: str | None = None


class ConnectorDefinitionUpdate(BaseModel):
    title: str | None = None
    description: str | None = None


class ConnectorDefinitionRead(BaseModel):
    model_config = {"from_attributes": True}

    id: str
    org_id: str
    name: str
    kind: str
    title: str | None = None
    description: str | None = None
    created_by: str | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None
    instance_count: int = 0
    public_tool_count: int = 0


class SecretRefCreate(BaseModel):
    name: str = Field(min_length=1, max_length=128)
    edge_node_id: str | None = None
    description: str | None = None


class SecretRefRead(BaseModel):
    model_config = {"from_attributes": True}

    id: str
    org_id: str
    name: str
    edge_node_id: str | None = None
    description: str | None = None
    created_by: str | None = None
    created_at: datetime | None = None


class EdgeNodeCreate(BaseModel):
    name: str = Field(min_length=1, max_length=128)


class EdgeNodeRead(BaseModel):
    model_config = {"from_attributes": True}

    id: str
    org_id: str
    name: str
    status: str
    last_heartbeat_at: datetime | None = None
    created_by: str | None = None
    created_at: datetime | None = None


class EdgeNodeCreateResult(BaseModel):
    node: EdgeNodeRead
    bootstrap: str
    expires_at: datetime


class ConnectorInstanceCreate(BaseModel):
    name: str = Field(min_length=1, max_length=128)
    placement: Literal["central", "edge"] = "central"
    edge_node_id: str | None = None
    secret_ref_id: str | None = None
    config: dict[str, Any] | None = None
    is_active: bool = True


class ConnectorInstanceUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=128)
    placement: Literal["central", "edge"] | None = None
    edge_node_id: str | None = None
    secret_ref_id: str | None = None
    config: dict[str, Any] | None = None
    is_active: bool | None = None


class ConnectorInstanceRead(BaseModel):
    model_config = {"from_attributes": True}

    id: str
    org_id: str
    definition_id: str
    name: str
    placement: str
    edge_node_id: str | None = None
    secret_ref_id: str | None = None
    config: dict[str, Any] | None = None
    is_active: bool
    created_by: str | None = None
    created_at: datetime | None = None
    secret_ref_name: str | None = None


class ConnectorToolCreate(BaseModel):
    tool_name: str = Field(min_length=1, max_length=255)
    title: str | None = None
    description: str | None = None
    input_schema: dict[str, Any] | None = None
    is_public: bool = False
    extra_metadata: dict[str, Any] | None = None


class ConnectorToolUpdate(BaseModel):
    title: str | None = None
    description: str | None = None
    input_schema: dict[str, Any] | None = None
    is_public: bool | None = None
    extra_metadata: dict[str, Any] | None = None


class ConnectorToolRead(BaseModel):
    model_config = {"from_attributes": True}

    id: str
    org_id: str
    instance_id: str
    tool_name: str
    title: str | None = None
    description: str | None = None
    input_schema: dict[str, Any] | None = None
    is_public: bool
    extra_metadata: dict[str, Any] | None = None
    created_at: datetime | None = None


class SkillConnectorBindingCreate(BaseModel):
    skill_release_id: str
    connector_instance_id: str
    role: str | None = None


class SkillConnectorBindingRead(BaseModel):
    model_config = {"from_attributes": True}

    id: str
    org_id: str
    skill_release_id: str
    connector_instance_id: str
    role: str | None = None
