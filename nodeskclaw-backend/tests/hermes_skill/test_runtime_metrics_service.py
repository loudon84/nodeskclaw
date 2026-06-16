import pytest
from unittest.mock import AsyncMock, MagicMock

from app.services.hermes_skill.hermes_runtime_metrics_service import HermesRuntimeMetricsService


@pytest.mark.asyncio
async def test_metrics_overview_shape():
    db = AsyncMock()
    count_result = MagicMock()
    count_result.scalar_one.return_value = 0
    avg_result = MagicMock()
    avg_result.scalar_one.return_value = 0
    db.execute = AsyncMock(side_effect=[count_result, count_result, count_result, count_result, avg_result, MagicMock(all=MagicMock(return_value=[])), MagicMock(all=MagicMock(return_value=[])), count_result])
    svc = HermesRuntimeMetricsService(db)
    payload = await svc.get_metrics("org-1", "7d")
    assert "overview" in payload
    assert "success_rate" in payload["overview"]
