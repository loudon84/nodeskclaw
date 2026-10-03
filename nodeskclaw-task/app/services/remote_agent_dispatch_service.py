from __future__ import annotations

import asyncio
import logging
from datetime import UTC, datetime, timedelta
from typing import Any

import httpx
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.config import Settings, settings
from app.models.agent_automation import (
    AgentAutomation,
    AutomationInvocation,
    RemoteAgentDispatchJob,
)
from app.models.base import not_deleted

logger = logging.getLogger(__name__)

_RETRY_DELAYS_SECONDS = (5, 30, 120, 600, 1800, 3600)
_RETRYABLE_HTTP = frozenset({408, 425, 429, 500, 502, 503, 504})
_TERMINAL_REMOTE = frozenset({
    "SUCCEEDED",
    "FAILED",
    "CANCELLED",
    "COMPLETED",
    "SUCCESS",
    "CANCELED",
})
_WAITING = frozenset({"WAITING_APPROVAL", "AWAITING_APPROVAL", "PENDING_APPROVAL"})
_RUNNING = frozenset({"RUNNING", "IN_PROGRESS", "DISPATCHING", "QUEUED", "SUBMITTED"})


class DispatchError(Exception):
    def __init__(self, code: str, message: str, *, retryable: bool = False) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.retryable = retryable


def _map_remote_status(remote_status: str | None) -> str | None:
    if not remote_status:
        return None
    status = remote_status.upper()
    if status in _WAITING:
        return "WAITING_APPROVAL"
    if status in {"SUCCEEDED", "COMPLETED", "SUCCESS"}:
        return "SUCCEEDED"
    if status in {"FAILED"}:
        return "FAILED"
    if status in {"CANCELLED", "CANCELED"}:
        return "CANCELLED"
    if status in _RUNNING:
        return "RUNNING" if status != "SUBMITTED" else "SUBMITTED"
    return None


async def project_invocation_status(
    db: AsyncSession,
    *,
    invocation: AutomationInvocation,
    client: httpx.AsyncClient | None = None,
) -> AutomationInvocation:
    if not invocation.remote_agent_run_id:
        return invocation
    if invocation.status in {"SUCCEEDED", "FAILED", "CANCELLED", "MISSED", "SKIPPED_CONCURRENCY"}:
        return invocation
    automation = (
        await db.execute(
            select(AgentAutomation).where(
                AgentAutomation.id == invocation.automation_id,
                not_deleted(AgentAutomation),
            )
        )
    ).scalar_one_or_none()
    if automation is None:
        return invocation
    owns_client = client is None
    http = client or httpx.AsyncClient(timeout=30.0)
    try:
        response = await http.get(
            f"{settings.NODESKCLAW_BACKEND_URL.rstrip('/')}/api/v1/internal/v1/automation/remote-agent/runs/{invocation.remote_agent_run_id}",
            params={"org_id": automation.tenant_id, "owner_user_id": invocation.owner_user_id_snapshot},
            headers={"X-Autotask-Internal-Token": settings.AUTOTASK_INTERNAL_TOKEN},
        )
    finally:
        if owns_client:
            await http.aclose()
    if response.status_code >= 500 or response.status_code in {408, 425, 429}:
        return invocation
    if response.status_code >= 400:
        return invocation
    body = response.json()
    mapped = _map_remote_status(str(body.get("status") or ""))
    if mapped:
        invocation.status = mapped
        if mapped in {"SUCCEEDED", "FAILED", "CANCELLED"}:
            invocation.completed_at = datetime.now(UTC)
        await db.commit()
        await db.refresh(invocation)
    return invocation


async def cancel_invocation(
    db: AsyncSession,
    *,
    tenant_id: str,
    invocation_id: str,
    requested_by: str,
) -> AutomationInvocation:
    invocation = (
        await db.execute(
            select(AutomationInvocation)
            .join(AgentAutomation, AgentAutomation.id == AutomationInvocation.automation_id)
            .where(
                AutomationInvocation.id == invocation_id,
                AgentAutomation.tenant_id == tenant_id,
                not_deleted(AutomationInvocation),
                not_deleted(AgentAutomation),
            )
            .with_for_update()
        )
    ).scalar_one_or_none()
    if invocation is None:
        raise DispatchError("INVOCATION_NOT_FOUND", "调用不存在")
    invocation.cancel_requested_by = requested_by
    invocation.cancel_requested_at = datetime.now(UTC)
    if invocation.status in {"PENDING", "RETRYING", "DISPATCHING", "RECEIVED"}:
        invocation.status = "CANCELLED"
        invocation.cancel_outcome = "LOCAL_CANCELLED"
        invocation.completed_at = datetime.now(UTC)
        job = (
            await db.execute(
                select(RemoteAgentDispatchJob).where(
                    RemoteAgentDispatchJob.invocation_id == invocation.id,
                    not_deleted(RemoteAgentDispatchJob),
                )
            )
        ).scalar_one_or_none()
        if job is not None and job.status in {"PENDING", "RETRYING", "PROCESSING"}:
            job.status = "CANCELLED"
        await db.commit()
        await db.refresh(invocation)
        return invocation
    if invocation.status in {"SUBMITTED", "RUNNING", "WAITING_APPROVAL"} and invocation.remote_agent_run_id:
        automation = (
            await db.execute(
                select(AgentAutomation).where(AgentAutomation.id == invocation.automation_id)
            )
        ).scalar_one()
        async with httpx.AsyncClient(timeout=30.0) as http:
            response = await http.post(
                f"{settings.NODESKCLAW_BACKEND_URL.rstrip('/')}/api/v1/internal/v1/automation/remote-agent/runs/{invocation.remote_agent_run_id}/cancel",
                headers={"X-Autotask-Internal-Token": settings.AUTOTASK_INTERNAL_TOKEN},
                json={
                    "org_id": automation.tenant_id,
                    "owner_user_id": invocation.owner_user_id_snapshot,
                },
            )
        if response.status_code in _RETRYABLE_HTTP or response.status_code >= 500:
            invocation.cancel_outcome = "CANCEL_RETRYING"
            await db.commit()
            await db.refresh(invocation)
            return invocation
        if response.status_code < 400:
            invocation.cancel_outcome = "REMOTE_CANCEL_ACCEPTED"
            await db.commit()
            await db.refresh(invocation)
            return invocation
        invocation.cancel_outcome = "CANCEL_REJECTED"
        await db.commit()
        await db.refresh(invocation)
        return invocation
    await db.commit()
    await db.refresh(invocation)
    return invocation


class RemoteAgentDispatchProcessor:
    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        app_settings: Settings | None = None,
    ) -> None:
        self._session_factory = session_factory
        self._settings = app_settings or settings
        self._poll_interval = self._settings.DISPATCH_JOB_POLL_INTERVAL_SECONDS
        self._batch_size = self._settings.DISPATCH_JOB_BATCH_SIZE
        self._stop_event = asyncio.Event()
        self._task: asyncio.Task[None] | None = None

    async def start(self) -> None:
        if self._task is not None and not self._task.done():
            return
        self._stop_event.clear()
        self._task = asyncio.create_task(self._run(), name="remote-agent-dispatch-processor")

    async def stop(self) -> None:
        self._stop_event.set()
        if self._task is not None:
            await self._task
        self._task = None

    async def _run(self) -> None:
        while not self._stop_event.is_set():
            try:
                await self.process_once()
            except Exception:
                logger.exception("Remote Agent dispatch 轮询失败")
            try:
                await asyncio.wait_for(self._stop_event.wait(), timeout=self._poll_interval)
            except TimeoutError:
                continue

    async def process_once(self) -> int:
        now = datetime.now(UTC)
        async with self._session_factory() as db:
            jobs = list(
                (
                    await db.execute(
                        select(RemoteAgentDispatchJob)
                        .where(
                            RemoteAgentDispatchJob.status.in_(["PENDING", "RETRYING"]),
                            or_(
                                RemoteAgentDispatchJob.next_attempt_at.is_(None),
                                RemoteAgentDispatchJob.next_attempt_at <= now,
                            ),
                            not_deleted(RemoteAgentDispatchJob),
                        )
                        .order_by(RemoteAgentDispatchJob.created_at.asc())
                        .limit(self._batch_size)
                        .with_for_update(skip_locked=True)
                    )
                )
                .scalars()
                .all()
            )
            for job in jobs:
                await self._process_job(db, job, now=now)
            return len(jobs)

    async def _process_job(
        self,
        db: AsyncSession,
        job: RemoteAgentDispatchJob,
        *,
        now: datetime,
    ) -> None:
        job.status = "PROCESSING"
        job.attempt_count += 1
        await db.flush()
        invocation = (
            await db.execute(
                select(AutomationInvocation).where(
                    AutomationInvocation.id == job.invocation_id,
                    not_deleted(AutomationInvocation),
                )
            )
        ).scalar_one_or_none()
        automation = (
            await db.execute(
                select(AgentAutomation).where(
                    AgentAutomation.id == job.automation_id,
                    not_deleted(AgentAutomation),
                )
            )
        ).scalar_one_or_none()
        if invocation is None or automation is None:
            job.status = "FAILED"
            job.last_error_code = "INVOCATION_NOT_FOUND"
            await db.commit()
            return
        if invocation.status == "CANCELLED":
            job.status = "CANCELLED"
            await db.commit()
            return
        invocation.status = "DISPATCHING"
        invocation.started_at = invocation.started_at or now
        await db.commit()
        try:
            result = await self._dispatch_http(automation, invocation, job)
            run_id = str(result.get("id") or result.get("run_id") or "")
            if not run_id:
                raise DispatchError("DISPATCH_RESPONSE_INVALID", "内部派发响应缺少 run id", retryable=True)
            job.remote_agent_run_id = run_id
            job.status = "SUCCEEDED"
            job.next_attempt_at = None
            job.last_error_code = None
            job.last_error_message = None
            invocation.remote_agent_run_id = run_id
            mapped = _map_remote_status(str(result.get("status") or "SUBMITTED")) or "SUBMITTED"
            invocation.status = mapped
            await db.commit()
        except DispatchError as exc:
            self._record_failure(job, invocation, exc, now=now)
            await db.commit()
        except httpx.HTTPError as exc:
            self._record_failure(
                job,
                invocation,
                DispatchError("DISPATCH_NETWORK", str(exc), retryable=True),
                now=now,
            )
            await db.commit()

    def _record_failure(
        self,
        job: RemoteAgentDispatchJob,
        invocation: AutomationInvocation,
        error: DispatchError,
        *,
        now: datetime,
    ) -> None:
        job.last_error_code = error.code
        job.last_error_message = error.message
        invocation.remote_error_code = error.code
        if error.retryable and job.attempt_count < job.max_attempts:
            delay_index = min(job.attempt_count - 1, len(_RETRY_DELAYS_SECONDS) - 1)
            job.status = "RETRYING"
            invocation.status = "RETRYING"
            job.next_attempt_at = now + timedelta(seconds=_RETRY_DELAYS_SECONDS[delay_index])
        else:
            job.status = "FAILED"
            invocation.status = "FAILED"
            invocation.error_code = error.code
            invocation.completed_at = now
            job.next_attempt_at = None

    async def _dispatch_http(
        self,
        automation: AgentAutomation,
        invocation: AutomationInvocation,
        job: RemoteAgentDispatchJob,
    ) -> dict[str, Any]:
        payload = {
            "dispatch_id": job.id,
            "invocation_id": invocation.id,
            "org_id": automation.tenant_id,
            "owner_user_id": invocation.owner_user_id_snapshot,
            "client_request_id": f"autotask:{invocation.id}",
            "agent_ref": automation.agent_ref,
            "prompt": invocation.rendered_prompt,
            "knowledge_refs": list(automation.knowledge_refs or []),
            "connector_binding_refs": list(automation.connector_binding_refs or []),
            "integration_account_refs": list(automation.integration_account_refs or []),
            "automation_context": {
                "automation_id": automation.id,
                "automation_generation": invocation.automation_generation,
                "trigger_type": invocation.trigger_type,
            },
        }
        async with httpx.AsyncClient(timeout=30.0) as http:
            response = await http.post(
                f"{self._settings.NODESKCLAW_BACKEND_URL.rstrip('/')}/api/v1/internal/v1/automation/remote-agent/runs",
                headers={"X-Autotask-Internal-Token": self._settings.AUTOTASK_INTERNAL_TOKEN},
                json=payload,
            )
        if response.status_code == 409:
            body = response.json()
            run_id = str(body.get("id") or body.get("run_id") or "")
            if run_id:
                return body
            raise DispatchError("DISPATCH_CONFLICT", "冲突且无法定位同一 Run", retryable=False)
        if response.status_code in _RETRYABLE_HTTP or response.status_code >= 500:
            raise DispatchError(
                "DISPATCH_RETRYABLE",
                f"可重试 HTTP {response.status_code}",
                retryable=True,
            )
        if response.status_code >= 400:
            body = {}
            try:
                body = response.json()
            except Exception:
                body = {}
            raise DispatchError(
                str(body.get("error_code") or "DISPATCH_REJECTED"),
                str(body.get("message") or f"业务拒绝 HTTP {response.status_code}"),
                retryable=False,
            )
        return response.json()


class CronFireProcessor:
    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        app_settings: Settings | None = None,
    ) -> None:
        self._session_factory = session_factory
        self._settings = app_settings or settings
        self._poll_interval = self._settings.CRON_POLL_INTERVAL_SECONDS
        self._stop_event = asyncio.Event()
        self._task: asyncio.Task[None] | None = None

    async def start(self) -> None:
        if self._task is not None and not self._task.done():
            return
        self._stop_event.clear()
        self._task = asyncio.create_task(self._run(), name="agent-automation-cron-processor")

    async def stop(self) -> None:
        self._stop_event.set()
        if self._task is not None:
            await self._task
        self._task = None

    async def _run(self) -> None:
        from app.services.agent_automation_service import fire_due_cron_triggers

        while not self._stop_event.is_set():
            try:
                async with self._session_factory() as db:
                    await fire_due_cron_triggers(db)
            except Exception:
                logger.exception("Agent Automation cron 轮询失败")
            try:
                await asyncio.wait_for(self._stop_event.wait(), timeout=self._poll_interval)
            except TimeoutError:
                continue
