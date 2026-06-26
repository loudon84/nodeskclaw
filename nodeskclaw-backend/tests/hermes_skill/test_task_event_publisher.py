from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.models.hermes_skill.hermes_task import EventType
from app.services.hermes_skill.task_event_publisher import TaskEventPublisher


def _event(event_type: EventType, payload: dict | None = None):
    return SimpleNamespace(
        id="evt-1",
        task_id="task-1",
        org_id="org-1",
        event_type=event_type,
        event_seq=1,
        payload=payload or {},
        created_at=datetime.now(timezone.utc),
    )


@pytest.mark.asyncio
async def test_publish_progress_writes_delta_event():
    db = AsyncMock()
    publisher = TaskEventPublisher(db)
    written = _event(EventType.HERMES_RUN_DELTA, {"mcp_event": "task.progress", "stage": "芯片推断"})
    publisher._events = MagicMock()
    publisher._events.write_event = AsyncMock(return_value=written)

    result = await publisher.publish_progress(
        "task-1",
        "org-1",
        stage="芯片推断",
        progress=0.5,
        message="分析产品结构",
    )

    publisher._events.write_event.assert_awaited_once()
    assert result.event_type == EventType.HERMES_RUN_DELTA


@pytest.mark.asyncio
async def test_publish_completed_with_result_embeds_summary():
    db = AsyncMock()
    publisher = TaskEventPublisher(db)
    publisher._events = MagicMock()
    publisher._events.write_event = AsyncMock(
        return_value=_event(EventType.TASK_COMPLETED, {"mcp_event": "task.completed"})
    )

    with patch(
        "app.services.hermes_skill.task_event_publisher.TaskResultService.get_result",
        new=AsyncMock(return_value={
            "result_summary": "完成",
            "server_artifacts": [{"artifact_id": "a1", "name": "report.md"}],
            "artifact_mode": "pull_only",
            "kb_status": "pending_review",
        }),
    ):
        await publisher.publish_completed_with_result("task-1", "org-1")

    call_kwargs = publisher._events.write_event.await_args.kwargs
    assert call_kwargs["payload"]["result"]["summary"] == "完成"
    assert call_kwargs["payload"]["result"]["artifacts"][0]["artifact_id"] == "a1"


def test_extract_progress_from_delta_payload():
    payload = {"stage": "公司验证", "progress": 0.2, "message": "校验工商信息"}
    extracted = TaskEventPublisher.extract_progress_from_delta(payload)
    assert extracted["stage"] == "公司验证"
    assert extracted["progress"] == 0.2
