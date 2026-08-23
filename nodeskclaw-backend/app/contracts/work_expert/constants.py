WORK_EXPERT_CONTRACT_NAME = "WORK-EXPERT-CONTRACT"
WORK_EXPERT_CONTRACT_VERSION = "1.0.0"
WORK_EXPERT_CONTRACT_PATH = "/contracts/work-expert/v1.0.0/"

WORK_EXPERT_CAPABILITIES = {
    "asyncEvent": True,
    "sseResume": True,
    "runtimeProgress": False,
    "artifactMode": "pull_only",
    "idempotency": True,
    "taskOwnerPolicy": True,
    "retryContract": True,
    "cancelSafe": True,
    "loadGate": "unmet",
}

WORK_EXPERT_OPENAPI_PATHS = [
    "/api/v1/expert/health",
    "/api/v1/expert/mcp",
    "/api/v1/expert/mcp/{slug}",
    "/api/v1/hermes/tasks/{task_id}",
    "/api/v1/hermes/tasks/{task_id}/snapshot",
    "/api/v1/hermes/tasks/{task_id}/events",
    "/api/v1/hermes/tasks/{task_id}/events-token",
    "/api/v1/hermes/tasks/{task_id}/result",
    "/api/v1/hermes/tasks/{task_id}/artifacts",
    "/api/v1/hermes/tasks/{task_id}/cancel",
    "/api/v1/hermes/tasks/{task_id}/retry",
    "/api/v1/hermes/artifacts/{artifact_id}/preview",
    "/api/v1/hermes/artifacts/{artifact_id}/download",
]

PROGRESS_STAGE_VALUES = (
    "preparing",
    "analyzing",
    "retrieving",
    "tool_calling",
    "processing",
    "generating",
    "artifact_building",
    "finalizing",
)
