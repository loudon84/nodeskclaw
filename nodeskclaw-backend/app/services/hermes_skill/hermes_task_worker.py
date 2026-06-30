import asyncio
import logging
import uuid
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.deps import async_session_factory
from app.models.hermes_skill.hermes_task import HermesTask, TaskStatus, EventType
from app.models.base import not_deleted
from app.services.hermes_external.hermes_docker_binding_service import HermesDockerBindingService
from app.services.hermes_external.hermes_runtime_skill_executor import execute_runtime_skill_via_api_server
from app.services.hermes_skill.hermes_agent_adapter import HermesAgentAdapter
from app.services.hermes_skill.hermes_run_state_resolver import HermesRunStateResolver, RunStateTracker
from app.services.hermes_skill.hermes_queue_policy_service import HermesQueuePolicyService
from app.services.hermes_skill.hermes_runtime_control_service import HermesRuntimeControlService
from app.services.hermes_skill.task_event_service import TaskEventService
from app.services.hermes_skill.task_event_publisher import TaskEventPublisher
from app.services.hermes_skill.task_service import TaskService
from app.services.hermes_skill.skill_audit_logger import SkillAuditLogger

logger = logging.getLogger(__name__)


class HermesTaskWorker:
    def __init__(self):
        self._running = False
        self._worker_id = uuid.uuid4().hex[:12]

    async def start(self):
        self._running = True
        logger.info("HermesTaskWorker started, worker_id=%s", self._worker_id)
        while self._running:
            try:
                await self._poll_once()
            except Exception as exc:
                logger.error("Worker poll error: %s", exc)
            await asyncio.sleep(settings.HERMES_TASK_WORKER_INTERVAL_SECONDS)

    def stop(self):
        self._running = False
        logger.info("HermesTaskWorker stopped")

    async def _poll_once(self):
        async with async_session_factory() as db:
            tasks = await self._fetch_and_lock(db)
            if not tasks:
                await self._check_timeouts(db)
                await db.commit()
                return

            for task in tasks:
                try:
                    await self._execute_task(db, task)
                except Exception as exc:
                    logger.error("Execute task %s error: %s", task.id, exc)
                    task_service = TaskService(db)
                    await task_service.mark_failed(
                        task,
                        error_code="TASK_EXECUTION_ERROR",
                        error_message=str(exc)[:1024],
                    )
                    await self._maybe_auto_retry(db, task, task_service)

                    audit_logger = SkillAuditLogger(db)
                    await audit_logger.log(
                        action="hermes.task.failed",
                        target_id=task.id,
                        org_id=task.org_id,
                        actor_type="system",
                        actor_id=self._worker_id,
                        details={"task_no": task.task_no, "error": str(exc)[:512]},
                    )

                    task.worker_id = None
                    task.locked_at = None
                    task.dispatch_status = "failed"
                    await db.commit()

            await self._check_timeouts(db)
            await db.commit()

    async def _fetch_and_lock(self, db: AsyncSession) -> list[HermesTask]:
        from datetime import timedelta
        from sqlalchemy import nullsfirst

        lock_cutoff = datetime.now(timezone.utc) - timedelta(seconds=settings.HERMES_TASK_LOCK_TIMEOUT_SECONDS)
        control = HermesRuntimeControlService(db)
        policy = HermesQueuePolicyService(db)

        stmt = (
            select(HermesTask)
            .where(
                not_deleted(HermesTask),
                HermesTask.status == TaskStatus.QUEUED,
                (HermesTask.locked_at.is_(None)) | (HermesTask.locked_at < lock_cutoff),
            )
            .order_by(
                HermesTask.priority.desc(),
                nullsfirst(HermesTask.scheduled_at.asc()),
                HermesTask.created_at.asc(),
            )
            .limit(settings.HERMES_TASK_WORKER_BATCH_SIZE * 3)
            .with_for_update(skip_locked=True)
        )
        result = await db.execute(stmt)
        candidates = list(result.scalars().all())

        now = datetime.now(timezone.utc)
        task_service = TaskService(db)
        accepted: list[HermesTask] = []
        for task in candidates:
            if len(accepted) >= settings.HERMES_TASK_WORKER_BATCH_SIZE:
                break
            if await control.is_worker_paused(task.org_id):
                continue
            if task.not_before and task.not_before > now:
                continue
            can_dispatch, _ = await policy.can_dispatch(task)
            if not can_dispatch:
                continue

            task.worker_id = self._worker_id
            task.locked_at = now
            task.dispatch_status = "accepted"
            task.dispatch_attempts = (task.dispatch_attempts or 0) + 1
            task.run_dispatched_at = now
            await task_service.mark_accepted(
                task,
                payload={
                    "worker_id": self._worker_id,
                    "dispatch_attempts": task.dispatch_attempts,
                    "status": TaskStatus.ACCEPTED.value,
                },
            )
            accepted.append(task)

        await db.flush()
        return accepted

    async def _execute_task(self, db: AsyncSession, task: HermesTask):
        now = datetime.now(timezone.utc)
        event_service = TaskEventService(db)
        task_service = TaskService(db)
        audit_logger = SkillAuditLogger(db)

        try:
            task.status = TaskStatus.RUNNING
            task.run_started_at = now
            task.dispatch_status = "running"

            await task_service.mark_running(task)

            await audit_logger.log(
                action="hermes.task.started",
                target_id=task.id,
                org_id=task.org_id,
                actor_type="system",
                actor_id=self._worker_id,
                details={"task_no": task.task_no, "skill_id": task.skill_id, "tool_name": task.tool_name},
            )
            await db.flush()

            if await event_service.has_event(task.id, EventType.TASK_CANCEL_REQUESTED):
                await task_service.mark_failed(
                    task,
                    error_code="TASK_CANCELLED",
                    error_message="任务已请求取消",
                )
                task.status = TaskStatus.CANCELLED
                await db.flush()
                return

            route_snapshot = self._get_route_snapshot(task)

            metadata = task.routing_metadata or {}
            contract = metadata.get("execution_contract") or {}
            route_type = route_snapshot.get("route_type")

            if contract.get("runtime_invocation") == "chat_completions" and route_type != "hermes_api_server":
                logger.error(
                    "worker.dispatch.route_contract_violation trace_id=%s task_id=%s task_no=%s "
                    "tool=%s expected=hermes_api_server actual=%s blocked=/v1/runs",
                    getattr(task, "request_trace_id", None),
                    task.id, task.task_no, task.tool_name,
                    route_type or "<empty>",
                )
                await task_service.mark_failed(
                    task,
                    error_code="RUNTIME_ROUTE_CONTRACT_VIOLATION",
                    error_message=(
                        "Runtime Skill 执行契约要求 chat_completions，"
                        f"但 route_snapshot.route_type={route_type or '<empty>'}，已阻止进入 /v1/runs"
                    ),
                )
                await event_service.write_event(
                    task_id=task.id,
                    org_id=task.org_id,
                    event_type="task.failed",
                    payload={
                        "error_code": "RUNTIME_ROUTE_CONTRACT_VIOLATION",
                        "route_type": route_type,
                        "expected_route_type": "hermes_api_server",
                        "request_trace_id": getattr(task, "request_trace_id", None),
                    },
                    source="worker",
                )
                await db.flush()
                return

            logger.info(
                "worker.dispatch.begin trace_id=%s task_id=%s task_no=%s tool=%s route_type=%s "
                "runtime_invocation=%s execution_mode=%s",
                getattr(task, "request_trace_id", None),
                task.id, task.task_no, task.tool_name,
                route_type, contract.get("runtime_invocation"),
                contract.get("mode"),
            )

            if route_type == "hermes_api_server":
                await self._execute_api_server_task(
                    db,
                    task,
                    route_snapshot,
                    task_service,
                    event_service,
                    audit_logger,
                )
                return

            is_expert_stream = route_type == "expert_agent_event_stream"
            logger.warning(
                "worker.dispatch.legacy_run_stream_entered trace_id=%s task_id=%s task_no=%s "
                "tool=%s route_type=%s source=%s contract=%s",
                getattr(task, "request_trace_id", None),
                task.id, task.task_no, task.tool_name,
                route_type,
                (task.client_context or {}).get("source"),
                contract or None,
            )
            await self._execute_agent_run_stream(
                db,
                task,
                route_snapshot,
                task_service,
                event_service,
                audit_logger,
                enrich_expert_metadata=is_expert_stream,
            )
            if is_expert_stream:
                await self._sync_expert_invocation_log(db, task.id)
        finally:
            task.worker_id = None
            task.locked_at = None
            if task.status in (TaskStatus.COMPLETED, TaskStatus.FAILED, TaskStatus.TIMEOUT, TaskStatus.CANCELLED):
                task.dispatch_status = "finished"
            await db.flush()

    async def _execute_agent_run_stream(
        self,
        db: AsyncSession,
        task: HermesTask,
        route_snapshot: dict,
        task_service: TaskService,
        event_service: TaskEventService,
        audit_logger: SkillAuditLogger,
        *,
        enrich_expert_metadata: bool = False,
    ) -> None:
        if enrich_expert_metadata:
            await event_service.write_event(
                task_id=task.id,
                org_id=task.org_id,
                event_type=EventType.HERMES_RUN_STARTED,
                payload=self._enrich_expert_event_payload({}, route_snapshot),
                source="worker",
            )
            await db.flush()

        adapter = HermesAgentAdapter(db)
        try:
            await adapter.submit_run(task, task.arguments or {})
        except Exception as exc:
            await task_service.mark_failed(
                task,
                error_code="AGENT_UNREACHABLE",
                error_message=str(exc)[:1024],
            )
            task.worker_id = None
            task.locked_at = None
            task.dispatch_status = "failed"
            await db.flush()
            return

        created_payload: dict = {"hermes_run_id": task.hermes_run_id}
        if enrich_expert_metadata:
            created_payload = self._enrich_expert_event_payload(created_payload, route_snapshot)
        if not await event_service.has_event(task.id, EventType.HERMES_RUN_CREATED):
            await event_service.write_event(
                task_id=task.id,
                org_id=task.org_id,
                event_type=EventType.HERMES_RUN_CREATED,
                payload=created_payload,
            )
        await db.flush()

        stream_interrupted = False
        state_tracker = RunStateTracker()
        try:
            async for event_data in adapter.read_run_events(task):
                try:
                    converted = HermesRunStateResolver.convert_hermes_event(event_data)
                except Exception as exc:
                    logger.warning("convert_events failed for task %s: %s", task.id, exc)
                    continue
                if not converted:
                    continue
                payload = converted.get("payload")
                if enrich_expert_metadata and isinstance(payload, dict):
                    payload = self._enrich_expert_event_payload(payload, route_snapshot)
                    converted["payload"] = payload
                state_tracker.observe_event_type(
                    converted["event_type"],
                    payload,
                )
                try:
                    await event_service.write_event(
                        task_id=task.id,
                        org_id=task.org_id,
                        event_type=converted["event_type"],
                        payload=payload,
                        source="hermes",
                        source_event_seq=converted.get("source_event_seq"),
                    )
                    if converted["event_type"] == EventType.HERMES_RUN_DELTA:
                        progress = TaskEventPublisher.extract_progress_from_delta(payload)
                        if progress:
                            metadata = (
                                self._enrich_expert_event_payload({}, route_snapshot)
                                if enrich_expert_metadata
                                else None
                            )
                            await TaskEventPublisher(db).publish_progress(
                                task.id,
                                task.org_id,
                                stage=progress["stage"],
                                progress=progress.get("progress"),
                                message=progress.get("message"),
                                metadata=metadata,
                            )
                except Exception as exc:
                    logger.warning("write_event failed for task %s: %s", task.id, exc)
                await db.flush()
        except Exception as exc:
            logger.warning("read_run_events stream error for task %s: %s", task.id, exc)
            stream_interrupted = True

        await db.refresh(task)

        if task.status == TaskStatus.RUNNING:
            run_status_value: str | None = None
            resolved = state_tracker.resolve_after_stream(
                stream_interrupted=stream_interrupted,
                run_status=None,
            )

            if resolved is None:
                try:
                    run_status = await adapter.get_run_status(task)
                    run_status_value = run_status.get("status", "unknown")
                except Exception as exc:
                    logger.error("get_run_status failed for task %s: %s", task.id, exc)
                    run_status_value = "unknown"

                resolved = state_tracker.resolve_after_stream(
                    stream_interrupted=stream_interrupted,
                    run_status=run_status_value,
                )
                if resolved is None and run_status_value:
                    resolved = state_tracker.map_hermes_run_status(run_status_value)

            if resolved is None and (
                run_status_value in (None, "unknown", "running", "in_progress", "created", "queued")
                or state_tracker.map_hermes_run_status(str(run_status_value or "unknown")) == TaskStatus.RUNNING
            ):
                task.worker_id = None
                task.locked_at = None
                task.dispatch_status = "running"
                await db.flush()
                return

            if resolved == TaskStatus.FAILED:
                await task_service.mark_failed(
                    task,
                    error_code="RUN_FAILED",
                    error_message=state_tracker.last_error or "Run failed",
                )
            elif resolved == TaskStatus.CANCELLED:
                task.status = TaskStatus.CANCELLED
                task.run_finished_at = datetime.now(timezone.utc)
                await task_service.update_status(task.id, task.org_id, TaskStatus.CANCELLED)
            elif resolved == TaskStatus.COMPLETED:
                task.status = TaskStatus.COMPLETED
                task.run_finished_at = datetime.now(timezone.utc)
                task.completed_at = datetime.now(timezone.utc)
            elif resolved == TaskStatus.TIMEOUT:
                await task_service.mark_timeout(
                    task,
                    (datetime.now(timezone.utc) - task.run_started_at).total_seconds()
                    if task.run_started_at else 0,
                )
            elif resolved is None:
                await task_service.mark_failed(
                    task,
                    error_code="RUN_STATUS_UNKNOWN",
                    error_message=f"Unknown run status: {run_status_value}",
                )

            if task.status == TaskStatus.COMPLETED:
                await task_service.mark_completed(task)
                await audit_logger.log(
                    action="hermes.task.completed",
                    target_id=task.id,
                    org_id=task.org_id,
                    actor_type="system",
                    actor_id=self._worker_id,
                    details={
                        "task_no": task.task_no,
                        "skill_id": task.skill_id,
                        "hermes_run_id": task.hermes_run_id,
                    },
                )
                await db.flush()
                await self._scan_artifacts(db, task)
                try:
                    await TaskEventPublisher(db).publish_completed_with_result(
                        task.id, task.org_id,
                    )
                except Exception as exc:
                    logger.warning(
                        "publish_completed_with_result failed for task %s: %s",
                        task.id,
                        exc,
                    )

            elif task.status == TaskStatus.FAILED:
                await audit_logger.log(
                    action="hermes.task.failed",
                    target_id=task.id,
                    org_id=task.org_id,
                    actor_type="system",
                    actor_id=self._worker_id,
                    details={
                        "task_no": task.task_no,
                        "error_code": task.error_code,
                        "error_message": task.error_message,
                    },
                )

    @staticmethod
    def _enrich_expert_event_payload(payload: dict, route_snapshot: dict) -> dict:
        enriched = dict(payload or {})
        expert = route_snapshot.get("expert")
        if isinstance(expert, dict):
            enriched["expert"] = expert
        team = route_snapshot.get("team")
        if isinstance(team, dict):
            enriched["team"] = team
        enriched["agent"] = {
            "agent_profile": route_snapshot.get("agent_profile"),
            "hermes_agent_instance_id": route_snapshot.get("hermes_agent_instance_id"),
        }
        if enriched.get("stage") or enriched.get("message") or enriched.get("progress") is not None:
            enriched.setdefault("mcp_event", "task.progress")
        return enriched

    async def _sync_expert_invocation_log(self, db: AsyncSession, task_id: str) -> None:
        from app.services.expert_gateway.expert_invocation_log_service import ExpertInvocationLogService

        try:
            await ExpertInvocationLogService(db).sync_from_task(task_id)
        except Exception as exc:
            logger.warning("sync expert invocation log failed for task %s: %s", task_id, exc)

    async def _maybe_auto_retry(
        self,
        db: AsyncSession,
        task: HermesTask,
        task_service: TaskService,
    ) -> None:
        if task.status != TaskStatus.FAILED:
            return
        if task.retry_count >= task.max_retry:
            return
        policy = HermesQueuePolicyService(db)
        task.status = TaskStatus.QUEUED
        task.retry_count += 1
        task.not_before = policy.compute_retry_not_before(task.retry_count)
        task.worker_id = None
        task.locked_at = None
        task.queue_entered_at = datetime.now(timezone.utc)
        task.error_code = None
        task.error_message = None
        await task_service._append_status_event(
            task,
            EventType.TASK_RETRYING,
            {
                "status": TaskStatus.QUEUED.value,
                "retry_count": task.retry_count,
                "not_before": task.not_before.isoformat() if task.not_before else None,
            },
        )
        await db.flush()

    @staticmethod
    def _get_route_snapshot(task: HermesTask) -> dict:
        metadata = task.routing_metadata or {}
        snapshot = metadata.get("route_snapshot")
        if isinstance(snapshot, dict):
            return snapshot
        return metadata

    async def _execute_api_server_task(
        self,
        db: AsyncSession,
        task: HermesTask,
        route_snapshot: dict,
        task_service: TaskService,
        event_service: TaskEventService,
        audit_logger: SkillAuditLogger,
    ) -> None:
        agent_profile = str(route_snapshot.get("agent_profile") or task.agent_id or "")
        hermes_agent_instance_id = str(route_snapshot.get("hermes_agent_instance_id") or "")
        runtime_skill_id = str(route_snapshot.get("runtime_skill_id") or "")
        hermes_instance_name = str(route_snapshot.get("hermes_instance_name") or agent_profile)
        timeout_seconds = route_snapshot.get("timeout_seconds")

        instance_detail = {
            "hermes_instance_name": hermes_instance_name,
            "hermes_agent_instance_id": hermes_agent_instance_id,
            "runtime_skill_id": runtime_skill_id,
            "agent_profile": agent_profile,
        }

        binding = HermesDockerBindingService(db)
        record = await binding.get_by_profile(task.org_id, agent_profile)
        if not record or record.id != hermes_agent_instance_id:
            await event_service.write_event(
                task_id=task.id,
                org_id=task.org_id,
                event_type=EventType.HERMES_RUN_FAILED,
                payload={
                    **instance_detail,
                    "error_code": "hermes_instance_unavailable",
                    "error_message": "指定 Hermes 实例绑定记录不存在或已变更",
                },
                source="worker",
            )
            await task_service.mark_failed(
                task,
                error_code="hermes_instance_unavailable",
                error_message="指定 Hermes 实例绑定记录不存在或已变更",
            )
            task.worker_id = None
            task.locked_at = None
            task.dispatch_status = "failed"
            await db.flush()
            return

        from app.services.hermes_external.hermes_bound_agent_scope_service import HermesBoundAgentScopeService

        try:
            if task.agent_id:
                await HermesBoundAgentScopeService(db).assert_dispatchable_instance(
                    task.org_id, task.agent_id,
                )
        except Exception as exc:
            await event_service.write_event(
                task_id=task.id,
                org_id=task.org_id,
                event_type=EventType.HERMES_RUN_FAILED,
                payload={**instance_detail, "error": str(exc)[:512]},
                source="worker",
            )
            await task_service.mark_failed(
                task,
                error_code="hermes_instance_unavailable",
                error_message=str(exc)[:1024],
            )
            task.worker_id = None
            task.locked_at = None
            task.dispatch_status = "failed"
            await db.flush()
            return

        arguments = task.arguments or {}
        prompt = str(arguments.get("prompt") or "").strip()
        context = arguments.get("context") if isinstance(arguments.get("context"), dict) else None

        await event_service.write_event(
            task_id=task.id,
            org_id=task.org_id,
            event_type=EventType.HERMES_RUN_STARTED,
            payload=instance_detail,
            source="worker",
        )
        await audit_logger.log(
            action="hermes.task.assigned_to_hermes_instance",
            target_id=task.id,
            org_id=task.org_id,
            actor_type="system",
            actor_id=self._worker_id,
            details={**instance_detail, "task_no": task.task_no},
        )
        await db.flush()

        try:
            content_text = await execute_runtime_skill_via_api_server(
                gateway_url=record.gateway_url,
                env_file=record.env_file,
                agent_profile=agent_profile,
                runtime_skill_id=runtime_skill_id,
                prompt=prompt,
                context=context,
                timeout_seconds=int(timeout_seconds) if timeout_seconds else None,
            )
        except Exception as exc:
            await event_service.write_event(
                task_id=task.id,
                org_id=task.org_id,
                event_type=EventType.HERMES_RUN_FAILED,
                payload={**instance_detail, "error": str(exc)[:512]},
                source="worker",
            )
            await task_service.mark_failed(
                task,
                error_code="HERMES_API_SERVER_CALL_FAILED",
                error_message=str(exc)[:1024],
            )
            await audit_logger.log(
                action="hermes.instance.execution_failed",
                target_id=task.id,
                org_id=task.org_id,
                actor_type="system",
                actor_id=self._worker_id,
                details={**instance_detail, "error": str(exc)[:512]},
            )
            task.worker_id = None
            task.locked_at = None
            task.dispatch_status = "failed"
            await db.flush()
            return

        await event_service.write_event(
            task_id=task.id,
            org_id=task.org_id,
            event_type=EventType.HERMES_RUN_COMPLETED,
            payload={**instance_detail, "result_preview": content_text[:500]},
            source="worker",
        )
        task.run_finished_at = datetime.now(timezone.utc)
        await task_service.mark_completed(task, result_summary=content_text[:500])

        output_policy = None
        if task.routing_metadata and isinstance(task.routing_metadata, dict):
            output_policy = task.routing_metadata.get("output_policy")

        discovered_artifacts: list = []
        if settings.HERMES_ARTIFACT_DISCOVERY_ENABLED:
            try:
                from app.services.hermes_skill.artifact_discovery_service import ArtifactDiscoveryService
                discovered_artifacts = await ArtifactDiscoveryService(db).discover_and_register_for_task(
                    task=task,
                    result_text=content_text,
                    force_rescan=False,
                )
            except Exception as exc:
                logger.error(
                    "Artifact discovery failed for task %s: %s",
                    task.id,
                    exc,
                    exc_info=True,
                )
                await event_service.write_event(
                    task_id=task.id,
                    org_id=task.org_id,
                    event_type=EventType.ARTIFACT_SCAN_FAILED,
                    payload={"status": "failed", "error": str(exc)[:1024]},
                    source="worker",
                )

        server_artifacts: list = []
        if output_policy:
            from app.services.mcp_skill_gateway.server_artifact_service import ServerArtifactService
            from app.services.hermes_skill.skill_audit_logger import SkillAuditLogger

            server_svc = ServerArtifactService(db)
            if (
                settings.HERMES_ARTIFACT_PROMOTE_DISCOVERED_ENABLED
                and discovered_artifacts
            ):
                try:
                    server_artifacts = await server_svc.create_from_discovered_artifacts(
                        task=task,
                        artifacts=discovered_artifacts,
                        output_policy=output_policy,
                        result_text=content_text,
                    )
                except Exception as exc:
                    logger.error(
                        "Promote discovered artifacts failed for task %s: %s",
                        task.id,
                        exc,
                        exc_info=True,
                    )

            if not server_artifacts and settings.HERMES_ARTIFACT_MATERIALIZE_FALLBACK_ENABLED:
                try:
                    server_artifacts = await server_svc.create_from_task_result(
                        task=task,
                        full_result_text=content_text,
                        output_policy=output_policy,
                        fallback=bool(discovered_artifacts),
                    )
                except Exception as exc:
                    logger.error(
                        "Server artifact materialization failed for task %s: %s",
                        task.id,
                        exc,
                        exc_info=True,
                    )
                    audit_logger = SkillAuditLogger(db)
                    await audit_logger.log(
                        action="mcp_artifact.materialize.failed",
                        target_id=task.id,
                        org_id=task.org_id,
                        actor_type="system",
                        actor_id=self._worker_id,
                        details={"error": str(exc)[:512], "tool_name": task.tool_name},
                    )
            elif not server_artifacts and discovered_artifacts:
                await SkillAuditLogger(db).log(
                    action="mcp_artifact.materialize.fallback.skipped",
                    target_id=task.id,
                    org_id=task.org_id,
                    actor_type="system",
                    actor_id=self._worker_id,
                    details={"tool_name": task.tool_name, "reason": "fallback_disabled"},
                )

            if server_artifacts:
                task.server_artifacts = server_artifacts
                task.artifact_status = "stored"
                task.kb_status = server_svc.resolve_task_kb_status(server_artifacts)
                task.result_summary = server_svc.append_artifact_links(
                    task.result_summary or content_text[:500],
                    server_artifacts,
                )
                await db.flush()
                publisher = TaskEventPublisher(db)
                for artifact in server_artifacts:
                    try:
                        await publisher.publish_artifact_ready(task.id, task.org_id, artifact)
                    except Exception as exc:
                        logger.warning(
                            "publish_artifact_ready failed for task %s: %s",
                            task.id,
                            exc,
                        )

        await audit_logger.log(
            action="hermes.task.completed",
            target_id=task.id,
            org_id=task.org_id,
            actor_type="system",
            actor_id=self._worker_id,
            details={
                "task_no": task.task_no,
                "skill_id": task.skill_id,
                "tool_name": task.tool_name,
                **instance_detail,
            },
        )
        task.worker_id = None
        task.locked_at = None
        task.dispatch_status = "finished"
        await db.flush()
        try:
            await TaskEventPublisher(db).publish_completed_with_result(task.id, task.org_id)
        except Exception as exc:
            logger.warning(
                "publish_completed_with_result failed for task %s: %s",
                task.id,
                exc,
            )

    async def _scan_artifacts(self, db: AsyncSession, task: HermesTask) -> None:
        try:
            from app.services.hermes_skill.artifact_service import ArtifactService
            artifact_service = ArtifactService(db)
            await artifact_service.scan_and_register(task.id, task.org_id)
        except Exception as exc:
            logger.error("Artifact scan failed for task %s: %s", task.id, exc)

    async def _check_timeouts(self, db: AsyncSession):
        now = datetime.now(timezone.utc)
        stmt = select(HermesTask).where(
            not_deleted(HermesTask),
            HermesTask.status == TaskStatus.RUNNING,
            HermesTask.run_started_at.isnot(None),
        )
        result = await db.execute(stmt)
        event_service = TaskEventService(db)
        task_service = TaskService(db)
        for task in result.scalars().all():
            elapsed = (now - task.run_started_at).total_seconds() if task.run_started_at else 0
            if elapsed > task.timeout_seconds:
                await task_service.mark_timeout(task, elapsed)
                task.worker_id = None
                task.locked_at = None

                audit_logger = SkillAuditLogger(db)
                await audit_logger.log(
                    action="hermes.task.timeout",
                    target_id=task.id,
                    org_id=task.org_id,
                    actor_type="system",
                    actor_id=self._worker_id,
                    details={"task_no": task.task_no, "elapsed_seconds": elapsed},
                )
                await db.flush()
