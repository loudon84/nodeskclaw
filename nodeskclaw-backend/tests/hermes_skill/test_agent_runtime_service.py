import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.models.hermes_skill.hermes_agent_runtime_state import AgentRuntimeStatus
from app.services.hermes_skill.hermes_agent_runtime_service import HermesAgentRuntimeService


@pytest.mark.asyncio
async def test_discover_agent_ids_bound_only_uses_scope():
    db = AsyncMock()
    svc = HermesAgentRuntimeService(db)
    with patch.object(svc, "_discover_bound_agent_ids", AsyncMock(return_value=["inst-1"])):
        ids = await svc._discover_agent_ids("org-1", bound_only=True)
    assert ids == ["inst-1"]


@pytest.mark.asyncio
async def test_is_agent_routable_disabled():
    db = AsyncMock()
    svc = HermesAgentRuntimeService(db)
    state = MagicMock()
    state.accepting_tasks = False
    state.runtime_status = AgentRuntimeStatus.DISABLED.value
    with patch.object(svc, "get_or_create_state", AsyncMock(return_value=state)):
        assert await svc.is_agent_routable("org-1", "agent-1") is False


@pytest.mark.asyncio
async def test_is_agent_accepting_tasks_concurrency():
    db = AsyncMock()
    svc = HermesAgentRuntimeService(db)
    state = MagicMock()
    state.accepting_tasks = True
    state.runtime_status = AgentRuntimeStatus.ENABLED.value
    state.max_concurrent_tasks = 2
    with patch.object(svc, "get_or_create_state", AsyncMock(return_value=state)), \
         patch.object(svc, "is_agent_routable", AsyncMock(return_value=True)), \
         patch.object(svc, "count_running_tasks", AsyncMock(return_value=2)):
        assert await svc.is_agent_accepting_tasks("org-1", "agent-1") is False
