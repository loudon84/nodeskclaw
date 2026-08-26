#!/usr/bin/env python3
"""Export Runtime SSE / error JSON Schemas to contracts/runtime-events/."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
RUNTIME_SRC = ROOT / "services" / "runtime" / "src"
OUT_DIR = ROOT / "contracts" / "runtime-events"


def _sort(value: Any) -> Any:
    if isinstance(value, dict):
        return {k: _sort(value[k]) for k in sorted(value)}
    if isinstance(value, list):
        return [_sort(item) for item in value]
    return value


def _write(name: str, schema: dict[str, Any]) -> None:
    path = OUT_DIR / name
    path.write_text(
        json.dumps(_sort(schema), indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    print(f"[export_event_schemas] wrote {path.relative_to(ROOT)}")


def main() -> int:
    sys.path.insert(0, str(RUNTIME_SRC))
    from schemas.chat import (  # noqa: WPS433
        WorkspaceChatChunkEvent,
        WorkspaceChatDoneEvent,
        WorkspaceChatErrorEvent,
        WorkspaceChatToolProgressEvent,
        WorkspaceChatUsageEvent,
    )
    from schemas.chat_events import (  # noqa: WPS433
        ApprovalRequestedEvent,
        ApprovalResolvedEvent,
        ArtifactCreatedEvent,
        ClarifyRequestedEvent,
        ClarifyResolvedEvent,
        MessageCompletedEvent,
        MessageDeltaEvent,
        QueueChangedEvent,
        ReasoningCompletedEvent,
        ReasoningDeltaEvent,
        RunStartedEvent,
        SessionStartedEvent,
        ToolCompletedEvent,
        ToolFailedEvent,
        ToolProgressEvent,
        ToolStartedEvent,
        TurnCancelledEvent,
        TurnCompletedEvent,
        TurnFailedEvent,
        UsageUpdatedEvent,
    )
    from schemas.events import ErrorEnvelope, RuntimeJobSseEvent  # noqa: WPS433
    from schemas.task_events import TASK_EVENT_TYPES  # noqa: WPS433

    OUT_DIR.mkdir(parents=True, exist_ok=True)

    job_schema = RuntimeJobSseEvent.model_json_schema(mode="serialization")
    job_schema["$id"] = "https://smc-copilot.local/contracts/runtime-events/job-event.schema.json"
    job_schema["title"] = "RuntimeJobSseEvent"
    _write("job-event.schema.json", job_schema)

    chat_schema: dict[str, Any] = {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "$id": "https://smc-copilot.local/contracts/runtime-events/chat-event.schema.json",
        "title": "WorkspaceChatSseEvent",
        "oneOf": [
            {"title": "chunk", **WorkspaceChatChunkEvent.model_json_schema(mode="serialization")},
            {"title": "tool_progress", **WorkspaceChatToolProgressEvent.model_json_schema(mode="serialization")},
            {"title": "usage", **WorkspaceChatUsageEvent.model_json_schema(mode="serialization")},
            {"title": "done", **WorkspaceChatDoneEvent.model_json_schema(mode="serialization")},
            {"title": "error", **WorkspaceChatErrorEvent.model_json_schema(mode="serialization")},
        ],
    }
    _write("chat-event.schema.json", chat_schema)

    chat_run_event_classes = [
        ("run.started", RunStartedEvent),
        ("session.started", SessionStartedEvent),
        ("agent.message.delta", MessageDeltaEvent),
        ("agent.message.completed", MessageCompletedEvent),
        ("reasoning.delta", ReasoningDeltaEvent),
        ("reasoning.completed", ReasoningCompletedEvent),
        ("tool.started", ToolStartedEvent),
        ("tool.progress", ToolProgressEvent),
        ("tool.completed", ToolCompletedEvent),
        ("tool.failed", ToolFailedEvent),
        ("clarify.requested", ClarifyRequestedEvent),
        ("clarify.resolved", ClarifyResolvedEvent),
        ("approval.requested", ApprovalRequestedEvent),
        ("approval.resolved", ApprovalResolvedEvent),
        ("usage.updated", UsageUpdatedEvent),
        ("artifact.created", ArtifactCreatedEvent),
        ("turn.completed", TurnCompletedEvent),
        ("turn.failed", TurnFailedEvent),
        ("turn.cancelled", TurnCancelledEvent),
        ("queue.changed", QueueChangedEvent),
    ]
    chat_run_schema: dict[str, Any] = {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "$id": "https://smc-copilot.local/contracts/runtime-events/chat-run-event.schema.json",
        "title": "ChatRunEvent",
        "oneOf": [
            {"title": title, **cls.model_json_schema(mode="serialization")}
            for title, cls in chat_run_event_classes
        ],
    }
    _write("chat-run-event.schema.json", chat_run_schema)

    error_schema = ErrorEnvelope.model_json_schema(mode="serialization")
    error_schema["$id"] = "https://smc-copilot.local/contracts/runtime-events/error.schema.json"
    error_schema["title"] = "RuntimeErrorEnvelope"
    _write("error.schema.json", error_schema)

    # PRD v1.3 §14 — durable WorkTask events (type const per variant).
    task_event_variants: list[dict[str, Any]] = []
    for event_type in sorted(TASK_EVENT_TYPES):
        task_event_variants.append(
            {
                "title": event_type,
                "type": "object",
                "properties": {
                    "eventId": {"type": "string", "title": "Eventid"},
                    "taskId": {"type": "string", "title": "Taskid"},
                    "runId": {"type": "string", "title": "Runid"},
                    "sequence": {"type": "integer", "title": "Sequence"},
                    "type": {
                        "const": event_type,
                        "default": event_type,
                        "title": "Type",
                        "type": "string",
                    },
                    "payload": {
                        "additionalProperties": True,
                        "title": "Payload",
                        "type": "object",
                    },
                    "timestamp": {
                        "anyOf": [{"type": "string"}, {"type": "null"}],
                        "default": None,
                        "title": "Timestamp",
                    },
                },
                "required": ["eventId", "taskId", "runId", "sequence", "type"],
            }
        )
    task_event_schema: dict[str, Any] = {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "$id": "https://smc-copilot.local/contracts/runtime-events/task-event.schema.json",
        "title": "WorkTaskEvent",
        "oneOf": task_event_variants,
    }
    _write("task-event.schema.json", task_event_schema)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
