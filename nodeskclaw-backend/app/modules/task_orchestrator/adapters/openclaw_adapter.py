"""OpenClaw adapter - OpenClaw executor integration (stub)."""

from typing import Any

from app.modules.task_orchestrator.adapters.base import (
    BaseExecutorAdapter,
    ExecutorSubmitContext,
    ExecutorSubmitResult,
    ExecutorPollResult,
    ExecutorCancelResult,
)


class OpenClawExecutorAdapter(BaseExecutorAdapter):
    """Adapter for OpenClaw executor (stub implementation).

    This is a placeholder implementation for Phase 1. The full
    implementation will be added in Phase 3.
    """

    def __init__(self, base_url: str = "http://openclaw:8000", api_key: str | None = None):
        self.base_url = base_url
        self.api_key = api_key

    async def submit(self, ctx: ExecutorSubmitContext) -> ExecutorSubmitResult:
        """Submit task to OpenClaw (stub).

        Args:
            ctx: Submission context

        Returns:
            Submission result (stub)
        """
        # TODO: Implement actual OpenClaw submission
        # 1. Select available agent from projection_service
        # 2. Call OpenClaw API to create run
        # 3. Return external_run_id and callback_mode

        return ExecutorSubmitResult(
            accepted=True,
            external_run_id=f"oc_stub:{ctx.workflow_node_id}",
            callback_mode="poll",
            raw={
                "message": "OpenClaw stub - not implemented",
                "node_key": ctx.node_key,
            },
        )

    async def poll(self, external_run_id: str) -> ExecutorPollResult:
        """Poll OpenClaw run status (stub).

        Args:
            external_run_id: External run ID

        Returns:
            Poll result (stub)
        """
        # TODO: Implement actual OpenClaw polling
        # Call OpenClaw API to get run status

        return ExecutorPollResult(
            status="completed",
            result={"message": "OpenClaw stub - not implemented"},
            error={},
        )

    async def cancel(self, external_run_id: str) -> ExecutorCancelResult:
        """Cancel OpenClaw run (stub).

        Args:
            external_run_id: External run ID

        Returns:
            Cancellation result (stub)
        """
        # TODO: Implement actual OpenClaw cancellation

        return ExecutorCancelResult(
            cancelled=True,
            reason="OpenClaw stub - not implemented",
        )

    def normalize_output(self, raw: dict[str, Any]) -> dict[str, Any]:
        """Normalize OpenClaw output.

        Args:
            raw: Raw OpenClaw output

        Returns:
            Normalized output
        """
        # OpenClaw output format:
        # {
        #   "summary": "Task summary",
        #   "structured": {...},
        #   "artifacts": [...],
        # }

        return {
            "summary": raw.get("summary", ""),
            "structured": raw.get("structured", {}),
            "artifacts": raw.get("artifacts", []),
        }

    async def health_check(self) -> bool:
        """Check OpenClaw health (stub).

        Returns:
            True (stub)
        """
        # TODO: Implement actual health check
        return True
