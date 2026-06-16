import pytest
from unittest.mock import AsyncMock, patch

from app.services.hermes_skill.hermes_runtime_control_service import HermesRuntimeControlService


@pytest.mark.asyncio
async def test_get_controls_default_false():
    db = AsyncMock()
    svc = HermesRuntimeControlService(db)
    with patch.object(svc, "_get_control", AsyncMock(return_value=None)):
        controls = await svc.get_controls("org-1")
    assert controls["worker"]["paused"] is False
    assert controls["queue"]["paused"] is False
