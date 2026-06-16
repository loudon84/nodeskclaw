from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.hermes_external.docker_container_inspect_service import DockerInspectResult
from app.services.hermes_external.hermes_docker_binding_service import HermesDockerBindingService
from app.services.hermes_external.hermes_gateway_probe_service import GatewayProbeResult


def _inspect_running(*, gateway_mapped: bool = True) -> DockerInspectResult:
    return DockerInspectResult(
        docker_status="running",
        docker_health="healthy",
        container_id="cid-1",
        image="hermes-agent:latest",
        inspect_data={
            "Config": {"Labels": {"com.docker.compose.project": "hermes-common-writer"}},
        },
        gateway_port_mapped=gateway_mapped,
        webui_port_mapped=True,
    )

@pytest.mark.asyncio
async def test_scan_existing_upserts_instance(tmp_path, monkeypatch):
    instance_dir = tmp_path / "common-writer"
    instance_dir.mkdir()
    (instance_dir / ".env").write_text(
        "HERMES_WEBUI_PORT=8900\nHERMES_GATEWAY_PORT=18900\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(
        "app.services.docker_constants.settings.DOCKER_PUBLIC_HOST",
        "127.0.0.1",
    )

    probe_result = GatewayProbeResult(
        gateway_status="online",
        probe_path="/health",
        status_code=200,
        last_error=None,
        last_probe_at=datetime.now(timezone.utc),
    )

    db = MagicMock()
    db.add = MagicMock()
    db.flush = AsyncMock()
    query_result = MagicMock()
    query_result.scalar_one_or_none.return_value = None
    db.execute = AsyncMock(return_value=query_result)
    service = HermesDockerBindingService(db)
    with patch.object(service._inspect, "inspect", AsyncMock(return_value=_inspect_running())):
        with patch.object(service._probe, "probe_url", AsyncMock(return_value=probe_result)):
            result = await service.scan_existing(
                "org-1",
                instances_root=str(tmp_path),
                probe_after_scan=True,
            )

    assert result.scanned == 1
    assert result.bound == 1
    assert result.failed == 0
    assert result.items[0].profile_name == "common-writer"
    assert result.items[0].gateway_status == "online"
    assert result.items[0].runtime_status == "ready"
    db.add.assert_called_once()
    db.flush.assert_awaited()


@pytest.mark.asyncio
async def test_upsert_from_env_unconfigured_without_gateway_port(tmp_path, monkeypatch):
    instance_dir = tmp_path / "writer"
    instance_dir.mkdir()
    env_file = instance_dir / ".env"
    env_file.write_text("HERMES_WEBUI_PORT=8900\n", encoding="utf-8")
    monkeypatch.setattr(
        "app.services.docker_constants.settings.DOCKER_PUBLIC_HOST",
        "127.0.0.1",
    )

    db = MagicMock()
    db.add = MagicMock()
    db.flush = AsyncMock()
    query_result = MagicMock()
    query_result.scalar_one_or_none.return_value = None
    db.execute = AsyncMock(return_value=query_result)
    service = HermesDockerBindingService(db)
    with patch.object(service._inspect, "inspect", AsyncMock(return_value=_inspect_running(gateway_mapped=False))):
        record = await service.upsert_from_env("org-1", env_file, probe=False)

    assert record.gateway_port is None
    assert record.gateway_status == "unconfigured"
    assert record.gateway_runtime_status == "unconfigured"
    assert record.mcp_status == "unconfigured"
    assert record.last_error is not None
    assert "HERMES_GATEWAY_PORT" in record.last_error
