from typing import Any

from pydantic import BaseModel, Field

from app.schemas.common import ApiResponse
from app.schemas.hermes_skill.artifact import ArtifactRead
from app.schemas.hermes_skill.artifact_schema import ArtifactPreviewResponse
from app.schemas.hermes_skill.sse_events import TaskEventEnvelope
from app.schemas.hermes_skill.task import TaskRead
from app.schemas.hermes_skill.task_result_contract import (
    TaskResultResponse,
    TaskSnapshotResponse,
)
from app.schemas.work_expert.mcp_jsonrpc import JsonRpcErrorResponse, JsonRpcSuccessResponse


class ApiErrorBody(BaseModel):
    code: int
    error_code: int
    message_key: str
    message: str
    data: None = None
    message_params: dict[str, str] | None = None
    details: dict[str, Any] | None = None


class EventsTokenData(BaseModel):
    event_url: str
    expires_in: int
    expires_at: str


class TaskArtifactListItem(ArtifactRead):
    preview_url: str | None = None
    download_url: str | None = None


class TaskArtifactsHttpData(BaseModel):
    code: int = 0
    message: str = "success"
    data: list[TaskArtifactListItem] = Field(default_factory=list)
    server_artifacts: list[dict[str, Any]] = Field(default_factory=list)
    artifact_mode: str = "pull_only"


class ArtifactPreviewData(ArtifactPreviewResponse):
    org_id: str | None = None
    task_id: str | None = None
    created_by: str | None = None
    sha256: str | None = None
    preview_url: str | None = None
    download_url: str | None = None


JsonRpcHttpResponse = JsonRpcSuccessResponse | JsonRpcErrorResponse
TaskGetResponse = ApiResponse[TaskRead]
TaskSnapshotHttpResponse = ApiResponse[TaskSnapshotResponse]
TaskResultHttpResponse = ApiResponse[TaskResultResponse]
EventsTokenResponse = ApiResponse[EventsTokenData]
ArtifactPreviewHttpResponse = ApiResponse[ArtifactPreviewData]
TaskCancelResponse = ApiResponse[TaskRead]
TaskRetryResponse = ApiResponse[TaskRead]


def contract_error_responses() -> dict[int, dict[str, Any]]:
    return {
        400: {
            "model": ApiErrorBody,
            "description": "Bad request or invalid task state, e.g. errors.task.cannot_cancel / errors.task.cannot_retry",
        },
        401: {"model": ApiErrorBody, "description": "Unauthenticated"},
        403: {
            "model": ApiErrorBody,
            "description": "Forbidden. Task owner policy uses message_key errors.task.owner_forbidden",
        },
        404: {"model": ApiErrorBody, "description": "Not found"},
        422: {"model": ApiErrorBody, "description": "Request validation error"},
    }


def sse_event_responses() -> dict[int | str, dict[str, Any]]:
    return {
        200: {
            "description": "text/event-stream of TaskEventEnvelope frames; id={task_id}-{event_seq}",
            "content": {
                "text/event-stream": {
                    "schema": TaskEventEnvelope.model_json_schema(mode="serialization"),
                }
            },
        },
        **contract_error_responses(),
    }


def artifact_download_responses() -> dict[int | str, dict[str, Any]]:
    return {
        200: {
            "description": "Artifact file bytes",
            "content": {
                "application/octet-stream": {
                    "schema": {
                        "type": "string",
                        "format": "binary",
                        "title": "ArtifactBinary",
                    }
                }
            },
        },
        **contract_error_responses(),
    }


def artifact_list_item_from_record(artifact) -> dict[str, Any]:
    payload = ArtifactRead.model_validate(artifact).model_dump()
    payload["preview_url"] = f"/api/v1/hermes/artifacts/{artifact.id}/preview"
    payload["download_url"] = f"/api/v1/hermes/artifacts/{artifact.id}/download"
    return payload
