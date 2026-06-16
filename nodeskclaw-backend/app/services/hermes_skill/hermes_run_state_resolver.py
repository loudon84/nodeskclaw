from dataclasses import dataclass, field

from app.models.hermes_skill.hermes_task import EventType, TaskStatus

_TERMINAL_SUCCESS = frozenset({"completed", "success"})
_TERMINAL_FAILED = frozenset({"failed", "error"})
_TERMINAL_CANCELLED = frozenset({"cancelled", "canceled"})
_TERMINAL_TIMEOUT = frozenset({"timeout"})
_RUNNING = frozenset({"created", "queued", "running", "in_progress", "unknown"})


@dataclass
class RunStateTracker:
    seen_completed: bool = False
    seen_failed: bool = False
    seen_cancelled: bool = False
    last_error: str | None = None

    def observe_event_type(self, event_type: EventType, payload: dict | None = None) -> None:
        payload = payload or {}
        if event_type in (
            EventType.HERMES_RUN_FAILED,
            EventType.TASK_FAILED,
        ):
            self.seen_failed = True
            self.last_error = payload.get("error_message") or payload.get("message")
        elif event_type in (
            EventType.HERMES_RUN_COMPLETED,
            EventType.TASK_COMPLETED,
        ):
            status = payload.get("status", "completed")
            if status in _TERMINAL_FAILED or status == "failed":
                self.seen_failed = True
            else:
                self.seen_completed = True
        elif event_type == EventType.TASK_CANCELLED:
            self.seen_cancelled = True

    def map_hermes_run_status(self, status: str) -> TaskStatus | None:
        normalized = (status or "unknown").lower()
        if normalized in _TERMINAL_SUCCESS:
            return TaskStatus.COMPLETED
        if normalized in _TERMINAL_FAILED:
            return TaskStatus.FAILED
        if normalized in _TERMINAL_CANCELLED:
            return TaskStatus.CANCELLED
        if normalized in _TERMINAL_TIMEOUT:
            return TaskStatus.TIMEOUT
        if normalized in _RUNNING:
            return TaskStatus.RUNNING
        return None

    def resolve_after_stream(
        self,
        stream_interrupted: bool,
        run_status: str | None = None,
    ) -> TaskStatus | None:
        if self.seen_failed:
            return TaskStatus.FAILED
        if self.seen_cancelled:
            return TaskStatus.CANCELLED
        if self.seen_completed:
            return TaskStatus.COMPLETED

        if run_status:
            mapped = self.map_hermes_run_status(run_status)
            if mapped == TaskStatus.RUNNING:
                return TaskStatus.RUNNING
            if mapped:
                return mapped
            if stream_interrupted:
                return None

        if not stream_interrupted:
            return None

        return None


class HermesRunStateResolver:
    @staticmethod
    def convert_hermes_event(event: dict) -> dict | None:
        hermes_type = event.get("event_type", "")
        event_seq = event.get("event_seq")
        payload = event.get("payload", {}) or {}

        mapping = {
            "hermes.run.created": EventType.HERMES_RUN_CREATED,
            "hermes.run.started": EventType.HERMES_RUN_STARTED,
            "hermes.run.delta": EventType.HERMES_RUN_DELTA,
            "hermes.run.completed": EventType.HERMES_RUN_COMPLETED,
            "hermes.run.failed": EventType.HERMES_RUN_FAILED,
            "run.created": EventType.HERMES_RUN_CREATED,
            "run.started": EventType.HERMES_RUN_STARTED,
            "run.delta": EventType.HERMES_RUN_DELTA,
            "run.completed": EventType.HERMES_RUN_COMPLETED,
            "run.failed": EventType.HERMES_RUN_FAILED,
            "tool.started": EventType.HERMES_RUN_DELTA,
            "tool.completed": EventType.HERMES_RUN_DELTA,
            "artifact.created": EventType.ARTIFACT_CREATED,
        }

        task_event_type = mapping.get(hermes_type)
        if not task_event_type:
            return None

        if hermes_type in ("hermes.run.completed", "run.completed"):
            status = payload.get("status", "completed")
            if status == "failed":
                task_event_type = EventType.TASK_FAILED

        return {
            "event_type": task_event_type,
            "source_event_seq": event_seq,
            "payload": payload,
        }

    @staticmethod
    def convert_events(hermes_events: list[dict]) -> list[dict]:
        converted = []
        for event in hermes_events:
            item = HermesRunStateResolver.convert_hermes_event(event)
            if item:
                converted.append(item)
        return converted
