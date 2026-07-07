from typing import Any

from pydantic import Field

from app.schemas.common import CamelModel


class WorkerRegisterRequest(CamelModel):
    worker_id: str = Field(serialization_alias="workerId")
    worker_type: str = Field(serialization_alias="workerType")
    device_name: str = Field(serialization_alias="deviceName")
    user_id: str | None = Field(None, serialization_alias="userId")
    app_version: str | None = Field(None, serialization_alias="appVersion")
    agent_version: str | None = Field(None, serialization_alias="agentVersion")
    os: str | None = None
    capabilities: list[str] = Field(default_factory=list)


class WorkerLeaseRequest(CamelModel):
    worker_id: str = Field(serialization_alias="workerId")
    capabilities: list[str] = Field(default_factory=list)
    limit: int = 1


class WorkerLeaseResponse(CamelModel):
    task_id: str = Field(serialization_alias="taskId")
    run_id: str = Field(serialization_alias="runId")
    lease_id: str = Field(serialization_alias="leaseId")
    workflow_binding_id: str = Field(serialization_alias="workflowBindingId")
    portal_account_id: str = Field(serialization_alias="portalAccountId")
    rpa_flow_id: str = Field(serialization_alias="rpaFlowId")
    input: dict[str, Any] = Field(default_factory=dict)


class WorkerLeaseRenewRequest(CamelModel):
    worker_id: str = Field(serialization_alias="workerId")
    lease_id: str = Field(serialization_alias="leaseId")


class RunEventCreate(CamelModel):
    worker_id: str | None = Field(None, serialization_alias="workerId")
    type: str
    level: str = "INFO"
    message: str
    payload: dict[str, Any] | None = None


class RunArtifactCreate(CamelModel):
    type: str
    name: str
    storage_key: str = Field(serialization_alias="storageKey")
    size: int = 0
    mime_type: str | None = Field(None, serialization_alias="mimeType")


class RunFinishRequest(CamelModel):
    status: str
    error_code: str | None = Field(None, serialization_alias="errorCode")
    error_message: str | None = Field(None, serialization_alias="errorMessage")
