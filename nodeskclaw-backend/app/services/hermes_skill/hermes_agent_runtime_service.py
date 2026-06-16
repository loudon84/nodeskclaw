import logging
import uuid
from datetime import datetime, timezone
from pathlib import Path

import httpx
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.exceptions import NotFoundError
from app.models.base import not_deleted
from app.models.hermes_skill.hermes_agent_runtime_state import AgentRuntimeStatus, HermesAgentRuntimeState
from app.models.hermes_skill.hermes_task import HermesTask, TaskStatus
from app.models.hermes_skill.skill_installation import HermesSkillInstallation
from app.services.hermes_skill.hermes_agent_adapter import HermesAgentAdapter, _is_hermes_agent_instance

logger = logging.getLogger(__name__)

_NON_ACCEPTING_STATUSES = frozenset({
    AgentRuntimeStatus.DISABLED.value,
    AgentRuntimeStatus.MAINTENANCE.value,
    AgentRuntimeStatus.DRAINING.value,
    AgentRuntimeStatus.UNHEALTHY.value,
    AgentRuntimeStatus.DELETED.value,
})


class HermesAgentRuntimeService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def list_runtime_states(self, org_id: str) -> list[dict]:
        agent_ids = await self._discover_agent_ids(org_id)
        items = []
        for agent_id in agent_ids:
            state = await self.get_or_create_state(org_id, agent_id)
            items.append(await self._to_dict(org_id, agent_id, state))
        return items

    async def get_runtime_state(self, org_id: str, agent_id: str) -> dict:
        state = await self.get_or_create_state(org_id, agent_id)
        return await self._to_dict(org_id, agent_id, state)

    async def get_or_create_state(self, org_id: str, agent_id: str) -> HermesAgentRuntimeState:
        result = await self.db.execute(
            select(HermesAgentRuntimeState).where(
                not_deleted(HermesAgentRuntimeState),
                HermesAgentRuntimeState.org_id == org_id,
                HermesAgentRuntimeState.agent_id == agent_id,
            )
        )
        state = result.scalar_one_or_none()
        if state:
            state.current_running_tasks = await self.count_running_tasks(org_id, agent_id)
            return state

        state = HermesAgentRuntimeState(
            id=str(uuid.uuid4()),
            org_id=org_id,
            agent_id=agent_id,
            runtime_status=AgentRuntimeStatus.ENABLED.value,
            accepting_tasks=True,
            max_concurrent_tasks=settings.HERMES_QUEUE_AGENT_MAX_RUNNING,
            current_running_tasks=0,
        )
        self.db.add(state)
        await self.db.flush()
        return state

    async def is_agent_accepting_tasks(self, org_id: str, agent_id: str) -> bool:
        if not await self.is_agent_routable(org_id, agent_id):
            return False
        running = await self.count_running_tasks(org_id, agent_id)
        state = await self.get_or_create_state(org_id, agent_id)
        return running < state.max_concurrent_tasks

    async def is_agent_routable(self, org_id: str, agent_id: str) -> bool:
        state = await self.get_or_create_state(org_id, agent_id)
        if not state.accepting_tasks:
            return False
        if state.runtime_status in _NON_ACCEPTING_STATUSES:
            return False
        return True

    async def count_running_tasks(self, org_id: str, agent_id: str) -> int:
        result = await self.db.execute(
            select(func.count()).where(
                not_deleted(HermesTask),
                HermesTask.org_id == org_id,
                HermesTask.agent_id == agent_id,
                HermesTask.status == TaskStatus.RUNNING,
            )
        )
        return result.scalar_one()

    async def count_queued_tasks(self, org_id: str, agent_id: str) -> int:
        result = await self.db.execute(
            select(func.count()).where(
                not_deleted(HermesTask),
                HermesTask.org_id == org_id,
                HermesTask.agent_id == agent_id,
                HermesTask.status.in_([TaskStatus.QUEUED, TaskStatus.ACCEPTED]),
            )
        )
        return result.scalar_one()

    async def health_check(self, org_id: str, agent_id: str, actor_id: str | None = None) -> dict:
        state = await self.get_or_create_state(org_id, agent_id)
        checks: dict[str, object] = {"agent_id": agent_id, "ok": True, "details": {}}

        try:
            instance = await HermesAgentAdapter(self.db)._get_instance(agent_id, org_id)
        except NotFoundError as exc:
            state.last_health_status = "unhealthy"
            state.last_health_checked_at = datetime.now(timezone.utc)
            state.last_error = str(exc.message)
            state.runtime_status = AgentRuntimeStatus.UNHEALTHY.value
            await self.db.flush()
            return {"ok": False, "status": "unhealthy", "error": exc.message_key, "checks": checks}

        if not _is_hermes_agent_instance(instance):
            state.last_health_status = "unhealthy"
            state.last_error = "not_hermes_agent"
            await self.db.flush()
            return {"ok": False, "status": "unhealthy", "error": "errors.task.agent_not_hermes", "checks": checks}

        base_url = HermesAgentAdapter._get_base_url(instance)
        checks["details"]["base_url"] = base_url
        http_ok = False
        if base_url:
            http_ok = await self._probe_health(base_url)
        checks["details"]["http_health"] = http_ok

        installation = await self._get_primary_installation(org_id, agent_id)
        profile_exists = self._path_exists(installation.profile_root_path if installation else None)
        workspace_exists = self._path_exists(installation.installed_path if installation else None)
        checks["details"]["profile_root_path_exists"] = profile_exists
        checks["details"]["workspace_root_path_exists"] = workspace_exists

        running = await self.count_running_tasks(org_id, agent_id)
        over_limit = running >= state.max_concurrent_tasks
        checks["details"]["running_tasks"] = running
        checks["details"]["over_concurrency_limit"] = over_limit

        ok = bool(base_url and http_ok and profile_exists and workspace_exists and not over_limit)
        state.last_health_checked_at = datetime.now(timezone.utc)
        state.last_health_status = "ok" if ok else "degraded"
        if not ok:
            state.last_error = "health_check_degraded"
            if not http_ok:
                state.runtime_status = AgentRuntimeStatus.UNHEALTHY.value
        state.current_running_tasks = running
        state.updated_by = actor_id
        await self.db.flush()
        return {"ok": ok, "status": state.last_health_status, "checks": checks}

    async def set_status(
        self,
        org_id: str,
        agent_id: str,
        runtime_status: str,
        *,
        accepting_tasks: bool | None = None,
        maintenance_reason: str | None = None,
        actor_id: str | None = None,
    ) -> HermesAgentRuntimeState:
        state = await self.get_or_create_state(org_id, agent_id)
        previous = state.runtime_status
        state.runtime_status = runtime_status
        if accepting_tasks is not None:
            state.accepting_tasks = accepting_tasks
        elif runtime_status == AgentRuntimeStatus.ENABLED.value:
            state.accepting_tasks = True
        elif runtime_status in _NON_ACCEPTING_STATUSES:
            state.accepting_tasks = False
        if maintenance_reason is not None:
            state.maintenance_reason = maintenance_reason
        state.updated_by = actor_id
        await self.db.flush()
        return state, previous

    async def enable(self, org_id: str, agent_id: str, actor_id: str | None = None):
        return await self.set_status(
            org_id, agent_id, AgentRuntimeStatus.ENABLED.value,
            accepting_tasks=True, actor_id=actor_id,
        )

    async def disable(self, org_id: str, agent_id: str, actor_id: str | None = None):
        return await self.set_status(
            org_id, agent_id, AgentRuntimeStatus.DISABLED.value,
            accepting_tasks=False, actor_id=actor_id,
        )

    async def maintenance(self, org_id: str, agent_id: str, reason: str | None, actor_id: str | None = None):
        return await self.set_status(
            org_id, agent_id, AgentRuntimeStatus.MAINTENANCE.value,
            accepting_tasks=False, maintenance_reason=reason, actor_id=actor_id,
        )

    async def drain(self, org_id: str, agent_id: str, actor_id: str | None = None):
        return await self.set_status(
            org_id, agent_id, AgentRuntimeStatus.DRAINING.value,
            accepting_tasks=False, actor_id=actor_id,
        )

    async def resume(self, org_id: str, agent_id: str, actor_id: str | None = None):
        return await self.enable(org_id, agent_id, actor_id=actor_id)

    async def _to_dict(self, org_id: str, agent_id: str, state: HermesAgentRuntimeState) -> dict:
        installation = await self._get_primary_installation(org_id, agent_id)
        base_url = None
        name = agent_id
        try:
            instance = await HermesAgentAdapter(self.db)._get_instance(agent_id, org_id)
            name = instance.name or agent_id
            base_url = HermesAgentAdapter._get_base_url(instance)
        except NotFoundError:
            pass
        running = await self.count_running_tasks(org_id, agent_id)
        queued = await self.count_queued_tasks(org_id, agent_id)
        return {
            "agent_id": agent_id,
            "name": name,
            "base_url": base_url,
            "health": state.last_health_status or ("ok" if state.runtime_status == AgentRuntimeStatus.ENABLED.value else "degraded"),
            "runtime_status": state.runtime_status,
            "accepting_tasks": state.accepting_tasks,
            "max_concurrent_tasks": state.max_concurrent_tasks,
            "current_running_tasks": running,
            "queued_tasks": queued,
            "last_health_status": state.last_health_status,
            "last_health_checked_at": state.last_health_checked_at.isoformat() if state.last_health_checked_at else None,
            "last_error": state.last_error,
            "maintenance_reason": state.maintenance_reason,
            "profile_root_path": installation.profile_root_path if installation else None,
            "profile_root_path_exists": self._path_exists(installation.profile_root_path if installation else None),
            "workspace_root_path": installation.installed_path if installation else None,
            "workspace_root_path_exists": self._path_exists(installation.installed_path if installation else None),
        }

    async def _discover_agent_ids(self, org_id: str) -> list[str]:
        result = await self.db.execute(
            select(HermesSkillInstallation.agent_id).where(
                not_deleted(HermesSkillInstallation),
                HermesSkillInstallation.org_id == org_id,
                HermesSkillInstallation.status == "installed",
            ).distinct()
        )
        return [row[0] for row in result.all() if row[0]]

    async def _get_primary_installation(self, org_id: str, agent_id: str) -> HermesSkillInstallation | None:
        result = await self.db.execute(
            select(HermesSkillInstallation).where(
                not_deleted(HermesSkillInstallation),
                HermesSkillInstallation.org_id == org_id,
                HermesSkillInstallation.agent_id == agent_id,
                HermesSkillInstallation.status == "installed",
            ).limit(1)
        )
        return result.scalar_one_or_none()

    @staticmethod
    async def _probe_health(base_url: str) -> bool:
        timeout = httpx.Timeout(connect=5.0, read=5.0, write=5.0, pool=5.0)
        paths = ("/health", "/v1/health")
        async with httpx.AsyncClient(timeout=timeout) as client:
            for path in paths:
                try:
                    resp = await client.get(f"{base_url.rstrip('/')}{path}")
                    if resp.status_code < 400:
                        return True
                except httpx.HTTPError:
                    continue
        return False

    @staticmethod
    def _path_exists(path_str: str | None) -> bool:
        if not path_str:
            return False
        try:
            return Path(path_str).exists()
        except OSError:
            return False
