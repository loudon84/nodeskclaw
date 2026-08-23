from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from app.services.hermes_skill.task_event_publisher import TaskEventPublisher


@pytest.mark.asyncio
async def test_publish_progress_uses_contract_stage_values():
    db = AsyncMock()
    publisher = TaskEventPublisher(db)
    publisher.publish = AsyncMock(return_value=SimpleNamespace(id="evt-1"))

    await publisher.publish_progress("task-1", "org-1", stage="preparing", message="start")
    payload = publisher.publish.await_args.args[3]
    assert payload["stage"] == "preparing"
    assert payload["mcp_event"] == "task.progress"

    await publisher.publish_progress("task-1", "org-1", stage="finalizing", message="finish")
    payload = publisher.publish.await_args.args[3]
    assert payload["stage"] == "finalizing"
