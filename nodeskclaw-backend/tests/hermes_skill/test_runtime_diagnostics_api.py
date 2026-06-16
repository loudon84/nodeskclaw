import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.services.hermes_skill.runtime_diagnostics_service import RuntimeDiagnosticsService


@pytest.mark.asyncio
async def test_runtime_diagnostics_shape():
    db = AsyncMock()
    count_result = MagicMock()
    count_result.scalar_one.return_value = 0
    status_rows = MagicMock()
    status_rows.all.return_value = []
    db.execute = AsyncMock(side_effect=[status_rows, count_result, count_result, MagicMock(scalars=MagicMock(return_value=MagicMock(all=MagicMock(return_value=[])))), count_result])

    svc = RuntimeDiagnosticsService(db)
    with patch.object(svc, "_artifact_stats", AsyncMock(return_value={"created_last_24h": 0, "downloaded_last_24h": 0})), \
         patch.object(svc, "_recent_failed_tasks", AsyncMock(return_value=[])), \
         patch.object(svc, "_recent_scan_failed", AsyncMock(return_value=[])):
        payload = await svc.get_runtime_diagnostics("org-1")

    assert "worker" in payload
    assert "queue" in payload
    assert "agents" in payload
    assert payload["worker"]["enabled"] is True
