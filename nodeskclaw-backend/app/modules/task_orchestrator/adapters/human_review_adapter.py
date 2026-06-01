"""Human review adapter - Human-in-the-loop executor."""

from typing import Any

from app.modules.task_orchestrator.adapters.base import (
    BaseExecutorAdapter,
    ExecutorSubmitContext,
    ExecutorSubmitResult,
    ExecutorPollResult,
    ExecutorCancelResult,
)


class HumanReviewAdapter(BaseExecutorAdapter):
    """Adapter for human-in-the-loop review tasks.

    This adapter uses LangGraph's interrupt/resume mechanism for
    human intervention. It doesn't actually execute anything,
    just signals that human input is required.
    """

    async def submit(self, ctx: ExecutorSubmitContext) -> ExecutorSubmitResult:
        """Submit a human review task.

        This doesn't actually submit anything - it just returns
        an interrupt callback mode to signal that the workflow
        should pause for human input.

        Args:
            ctx: Submission context

        Returns:
            Submission result with interrupt callback mode
        """
        return ExecutorSubmitResult(
            accepted=True,
            external_run_id=f"human:{ctx.workflow_node_id}",
            callback_mode="interrupt",  # Signal to use LangGraph interrupt
            raw={
                "message": "Human review required",
                "node_key": ctx.node_key,
                "input_payload": ctx.input_payload,
            },
        )

    async def poll(self, external_run_id: str) -> ExecutorPollResult:
        """Poll human review status.

        Since human reviews use interrupt/resume, polling always
        returns waiting_human status.

        Args:
            external_run_id: External run ID

        Returns:
            Poll result with waiting_human status
        """
        return ExecutorPollResult(
            status="running",  # Will be interrupted, so technically running
            result={},
            error={},
        )

    async def cancel(self, external_run_id: str) -> ExecutorCancelResult:
        """Cancel human review.

        Args:
            external_run_id: External run ID

        Returns:
            Cancellation result
        """
        # Human reviews can be cancelled
        return ExecutorCancelResult(
            cancelled=True,
            reason="Human review cancelled",
        )

    def normalize_output(self, raw: dict[str, Any]) -> dict[str, Any]:
        """Normalize human review output.

        Args:
            raw: Raw human input

        Returns:
            Normalized output (pass-through for human input)
        """
        return raw

    async def create_intervention_request(
        self,
        ctx: ExecutorSubmitContext,
        intervention_type: str = "approval",
    ) -> dict[str, Any]:
        """Create intervention request for human review.

        Args:
            ctx: Submission context
            intervention_type: Type of intervention

        Returns:
            Intervention request payload
        """
        return {
            "workflow_instance_id": ctx.workflow_instance_id,
            "workflow_node_id": ctx.workflow_node_id,
            "node_key": ctx.node_key,
            "intervention_type": intervention_type,
            "request_payload": ctx.input_payload,
            "created_at": __import__("datetime").datetime.utcnow().isoformat(),
        }
