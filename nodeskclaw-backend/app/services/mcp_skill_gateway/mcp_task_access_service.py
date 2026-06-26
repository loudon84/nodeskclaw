from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ArtifactNotFoundError, ForbiddenError, NotFoundError
from app.models.hermes_skill.hermes_artifact import HermesArtifact
from app.models.hermes_skill.hermes_task import HermesTask
from app.services.hermes_skill.artifact_service import ArtifactService
from app.services.hermes_skill.permission_checker import PermissionChecker
from app.services.hermes_skill.task_service import TaskService
from app.services.mcp_skill_gateway.auth import McpAuthContext


class McpTaskAccessService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def assert_can_access_task(
        self,
        task_id: str,
        auth_ctx: McpAuthContext,
    ) -> HermesTask:
        org_id = auth_ctx.org.id
        try:
            task = await TaskService(self.db).get_task(task_id, org_id)
        except NotFoundError:
            raise NotFoundError("任务不存在", "errors.task.not_found")

        if auth_ctx.auth_type == "user_jwt":
            await PermissionChecker.require_permission(
                self.db,
                auth_ctx.user.id,
                org_id,
                "hermes_task:view",
            )
            return task

        if auth_ctx.auth_type != "mcp_client_token":
            raise ForbiddenError("无权访问该任务", "errors.task.forbidden")

        if auth_ctx.allowed_skills:
            allowed = set(auth_ctx.allowed_skills)
            if task.tool_name and task.tool_name not in allowed:
                raise ForbiddenError("无权访问该任务", "errors.task.forbidden")

        if not self._mcp_token_can_access_task(task, auth_ctx):
            raise ForbiddenError("无权访问该任务", "errors.task.forbidden")

        return task

    async def assert_can_access_artifact(
        self,
        artifact_id: str,
        auth_ctx: McpAuthContext,
    ) -> HermesArtifact:
        org_id = auth_ctx.org.id
        try:
            artifact = await ArtifactService(self.db).get_artifact(artifact_id, org_id)
        except ArtifactNotFoundError:
            raise NotFoundError("产物不存在", "errors.artifact.not_found")

        if artifact.task_id:
            await self.assert_can_access_task(artifact.task_id, auth_ctx)

        return artifact

    @staticmethod
    def _mcp_token_can_access_task(task: HermesTask, auth_ctx: McpAuthContext) -> bool:
        ctx = task.client_context or {}
        token_id = auth_ctx.mcp_client_token_id
        if token_id and ctx.get("mcp_client_token_id") == token_id:
            return True

        if auth_ctx.user.id and task.user_id == auth_ctx.user.id:
            return True

        if auth_ctx.hermes_agent_id and ctx.get("hermes_agent_id") == auth_ctx.hermes_agent_id:
            return True

        if auth_ctx.profile and task.profile_id == auth_ctx.profile:
            return True

        if auth_ctx.profile and ctx.get("mcp_profile") == auth_ctx.profile:
            return True

        return False
