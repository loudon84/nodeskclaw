"""Routing service - Executor routing and resolution."""

from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.task_orchestrator.enums import ExecutorType
from app.modules.task_orchestrator.models import WorkflowNode


class RoutingService:
    """Service for resolving executor for workflow nodes."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def resolve_executor(
        self,
        node: WorkflowNode,
        org_id: str,
        workspace_id: str | None = None,
    ) -> tuple[str, str | None, dict[str, Any]]:
        """Resolve executor for a workflow node.

        Resolution order:
        1. Template explicit executor_type
        2. Role code default binding
        3. Capability matching
        4. Fallback to human_review

        Args:
            node: Workflow node
            org_id: Organization ID
            workspace_id: Workspace ID (optional)

        Returns:
            Tuple of (executor_type, assigned_agent_id, executor_config)
        """
        # 1. Check if executor is explicitly specified
        if node.executor_type and node.executor_type != "system":
            return node.executor_type, node.assigned_agent_id, {}

        # 2. Check role code binding
        if node.role_code:
            executor_type, agent_id = await self._resolve_by_role(
                node.role_code, org_id, workspace_id
            )
            if executor_type:
                return executor_type, agent_id, {}

        # 3. Check capability matching
        # TODO: Implement capability-based matching
        # This would query available agents and match capabilities

        # 4. Fallback to human_review
        return ExecutorType.HUMAN_REVIEW.value, None, {}

    async def _resolve_by_role(
        self,
        role_code: str,
        org_id: str,
        workspace_id: str | None = None,
    ) -> tuple[str | None, str | None]:
        """Resolve executor by role code.

        Args:
            role_code: Role code
            org_id: Organization ID
            workspace_id: Workspace ID (optional)

        Returns:
            Tuple of (executor_type, agent_id) if found, (None, None) otherwise
        """
        # TODO: Implement role-based executor binding
        # This would query a role-executor mapping table

        # For now, return None to trigger fallback
        return None, None

    async def get_adapter_config(
        self,
        executor_type: str,
        org_id: str,
    ) -> dict[str, Any]:
        """Get adapter configuration for an executor type.

        Args:
            executor_type: Executor type
            org_id: Organization ID

        Returns:
            Adapter configuration
        """
        # TODO: Load from configuration or database

        configs = {
            ExecutorType.OPENCLAW.value: {
                "base_url": "http://openclaw:8000",
                "timeout_sec": 1800,
            },
            ExecutorType.DIFY.value: {
                "base_url": "http://dify:8000",
                "timeout_sec": 1800,
            },
            ExecutorType.DEERFLOW.value: {
                "gateway_url": "http://deerflow-gateway:8000",
                "timeout_sec": 1800,
            },
            ExecutorType.HUMAN_REVIEW.value: {
                "timeout_hours": 24,
            },
        }

        return configs.get(executor_type, {})
