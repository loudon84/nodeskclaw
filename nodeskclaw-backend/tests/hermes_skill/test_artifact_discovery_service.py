import hashlib
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.core.exceptions import ForbiddenError
from app.models.hermes_skill.hermes_task import TaskStatus, EventType
from app.services.hermes_skill.artifact_discovery_service import (
    ArtifactDiscoveryService,
    CONTAINER_WORKSPACE_PATH_RE,
)


def test_extract_markdown_code_path():
    text = "报告已保存到 `/data/hermes/workspace/reports/sale/客户画像.md`"
    paths = ArtifactDiscoveryService._extract_container_paths(
        text,
        Path("/data/hermes/workspace"),
    )
    assert paths == ["/data/hermes/workspace/reports/sale/客户画像.md"]


def test_extract_plain_workspace_path():
    text = "保存到 /data/hermes/workspace/reports/sale/a.md 完成"
    paths = ArtifactDiscoveryService._extract_container_paths(
        text,
        Path("/data/hermes/workspace"),
    )
    assert paths == ["/data/hermes/workspace/reports/sale/a.md"]


def test_extract_quoted_workspace_path():
    text = '路径为 "/data/hermes/workspace/out/report.pdf"'
    paths = ArtifactDiscoveryService._extract_container_paths(
        text,
        Path("/data/hermes/workspace"),
    )
    assert paths == ["/data/hermes/workspace/out/report.pdf"]


def test_ignore_non_workspace_path():
    text = "读取 /etc/passwd 和 /data/hermes/config.yaml"
    paths = ArtifactDiscoveryService._extract_container_paths(
        text,
        Path("/data/hermes/workspace"),
    )
    assert paths == []


def test_map_container_path_to_host_path(tmp_path):
    host_root = tmp_path / "data" / "hermes" / "workspace"
    host_root.mkdir(parents=True)
    rel, host_path = ArtifactDiscoveryService._map_to_host_path(
        "/data/hermes/workspace/reports/sale/a.md",
        Path("/data/hermes/workspace"),
        host_root,
    )
    assert rel == "reports/sale/a.md"
    assert host_path == host_root / "reports" / "sale" / "a.md"


def test_reject_path_traversal():
    with pytest.raises((ValueError, ForbiddenError)):
        ArtifactDiscoveryService._map_to_host_path(
            "/data/hermes/workspace/../../.env",
            Path("/data/hermes/workspace"),
            Path("/tmp/host/workspace"),
        )


@pytest.mark.asyncio
async def test_register_markdown_artifact(tmp_path):
    host_root = tmp_path / "workspace"
    host_root.mkdir()
    file_path = host_root / "reports" / "sale" / "test.md"
    file_path.parent.mkdir(parents=True)
    file_path.write_text("# Title\n\ncontent", encoding="utf-8")

    db = AsyncMock()
    task = MagicMock()
    task.id = "task-1"
    task.org_id = "org-1"
    task.skill_id = "skill-1"
    task.agent_id = "agent-1"
    task.workspace_id = "ws-1"
    task.user_id = "user-1"
    task.hermes_run_id = None
    task.result_summary = None
    task.arguments = {}
    task.routing_metadata = {
        "route_snapshot": {
            "route_type": "hermes_api_server",
            "hermes_agent_instance_id": "inst-1",
            "hermes_instance_name": "common-writer",
            "runtime_skill_id": "customer-profiling",
        },
    }
    task.installation_id = None

    instance = MagicMock()
    instance.id = "inst-1"
    instance.org_id = "org-1"
    instance.deleted_at = None
    instance.data_dir = str(tmp_path)

    db.get = AsyncMock(return_value=instance)

    existing_result = MagicMock()
    existing_result.scalar_one_or_none.return_value = None
    upsert_result = MagicMock()
    upsert_result.scalar_one_or_none.return_value = None
    db.execute = AsyncMock(side_effect=[existing_result, upsert_result])

    service = ArtifactDiscoveryService(db)
    result_text = f"保存到 /data/hermes/workspace/reports/sale/test.md"

    with patch("app.services.hermes_skill.artifact_discovery_service.TaskEventService") as mock_event_cls:
        mock_event_cls.return_value.write_event = AsyncMock()
        artifacts = await service.discover_and_register_for_task(
            task=task,
            result_text=result_text,
        )

    assert len(artifacts) == 1
    assert artifacts[0].file_name == "test.md"
    assert artifacts[0].relative_path == "reports/sale/test.md"
    assert artifacts[0].file_path == str(file_path)
    assert artifacts[0].metadata_json["source"] == "hermes_api_server_workspace"


@pytest.mark.asyncio
async def test_upsert_artifact_idempotent(tmp_path):
    host_root = tmp_path / "workspace"
    host_root.mkdir()
    file_path = host_root / "a.md"
    file_path.write_text("hello", encoding="utf-8")

    db = AsyncMock()
    task = MagicMock()
    task.id = "task-1"
    task.org_id = "org-1"
    task.skill_id = None
    task.agent_id = None
    task.workspace_id = None
    task.user_id = None
    task.hermes_run_id = None
    task.routing_metadata = {
        "route_snapshot": {
            "route_type": "hermes_api_server",
            "hermes_agent_instance_id": "inst-1",
            "hermes_instance_name": "writer",
            "runtime_skill_id": "skill-a",
        },
    }
    task.installation_id = None

    instance = MagicMock()
    instance.id = "inst-1"
    instance.org_id = "org-1"
    instance.deleted_at = None
    instance.data_dir = str(tmp_path)
    db.get = AsyncMock(return_value=instance)

    existing_artifact = MagicMock()
    existing_artifact.id = "artifact-existing"
    existing_result = MagicMock()
    existing_result.scalar_one_or_none.return_value = existing_artifact
    db.execute = AsyncMock(return_value=existing_result)

    service = ArtifactDiscoveryService(db)
    with patch("app.services.hermes_skill.artifact_discovery_service.TaskEventService") as mock_event_cls:
        mock_event_cls.return_value.write_event = AsyncMock()
        artifacts = await service.discover_and_register_for_task(
            task=task,
            result_text="/data/hermes/workspace/a.md",
            force_rescan=False,
        )

    assert len(artifacts) == 1
    assert artifacts[0].id == "artifact-existing"
    db.add.assert_not_called()


@pytest.mark.asyncio
async def test_no_artifact_path_returns_empty():
    db = AsyncMock()
    task = MagicMock()
    task.id = "task-1"
    task.org_id = "org-1"
    task.routing_metadata = {
        "route_snapshot": {"route_type": "hermes_api_server", "hermes_agent_instance_id": "inst-1"},
    }
    task.installation_id = None
    task.result_summary = "no paths here"
    task.arguments = {}

    instance = MagicMock()
    instance.id = "inst-1"
    instance.org_id = "org-1"
    instance.deleted_at = None
    instance.data_dir = "/tmp/data/hermes"
    db.get = AsyncMock(return_value=instance)

    service = ArtifactDiscoveryService(db)
    with patch("app.services.hermes_skill.artifact_discovery_service.TaskEventService") as mock_event_cls:
        mock_event_cls.return_value.write_event = AsyncMock()
        artifacts = await service.discover_and_register_for_task(task=task)

    assert artifacts == []


@pytest.mark.asyncio
async def test_missing_host_file_writes_failed_event(tmp_path):
    host_root = tmp_path / "workspace"
    host_root.mkdir()

    db = AsyncMock()
    task = MagicMock()
    task.id = "task-1"
    task.org_id = "org-1"
    task.skill_id = None
    task.agent_id = None
    task.workspace_id = None
    task.user_id = None
    task.hermes_run_id = None
    task.routing_metadata = {
        "route_snapshot": {
            "route_type": "hermes_api_server",
            "hermes_agent_instance_id": "inst-1",
            "hermes_instance_name": "writer",
            "runtime_skill_id": "skill-a",
        },
    }
    task.installation_id = None
    task.result_summary = None
    task.arguments = {}

    instance = MagicMock()
    instance.id = "inst-1"
    instance.org_id = "org-1"
    instance.deleted_at = None
    instance.data_dir = str(tmp_path)
    db.get = AsyncMock(return_value=instance)

    existing_result = MagicMock()
    existing_result.scalar_one_or_none.return_value = None
    db.execute = AsyncMock(return_value=existing_result)

    service = ArtifactDiscoveryService(db)
    with patch("app.services.hermes_skill.artifact_discovery_service.TaskEventService") as mock_event_cls:
        mock_event = AsyncMock()
        mock_event_cls.return_value = mock_event
        artifacts = await service.discover_and_register_for_task(
            task=task,
            result_text="/data/hermes/workspace/missing.md",
        )

    assert artifacts == []
    failed_calls = [
        c for c in mock_event.write_event.await_args_list
        if c.kwargs.get("event_type") == EventType.ARTIFACT_SCAN_FAILED
    ]
    assert failed_calls


@pytest.mark.asyncio
async def test_scan_failure_does_not_fail_task():
    worker = __import__(
        "app.services.hermes_skill.hermes_task_worker",
        fromlist=["HermesTaskWorker"],
    ).HermesTaskWorker()
    db = AsyncMock()
    task = MagicMock()
    task.id = "task-1"
    task.org_id = "org-1"
    task.task_no = "TASK-001"
    task.skill_id = "skill-1"
    task.tool_name = "tool-1"
    task.agent_id = "inst-1"
    task.arguments = {"prompt": "test"}
    task.routing_metadata = {
        "route_snapshot": {
            "route_type": "hermes_api_server",
            "agent_profile": "common-writer",
            "hermes_agent_instance_id": "hermes-rec-1",
            "runtime_skill_id": "customer-profiling",
            "hermes_instance_name": "common-writer",
        },
    }
    task.worker_id = worker._worker_id
    task.locked_at = datetime.now(timezone.utc)

    task_service = AsyncMock()
    event_service = AsyncMock()
    audit_logger = AsyncMock()

    binding_record = MagicMock()
    binding_record.id = "hermes-rec-1"
    binding_record.gateway_url = "http://127.0.0.1:18789"
    binding_record.env_file = "/tmp/.env"

    with patch(
        "app.services.hermes_skill.hermes_task_worker.HermesDockerBindingService",
    ) as mock_binding_cls, patch(
        "app.services.hermes_external.hermes_bound_agent_scope_service.HermesBoundAgentScopeService",
    ) as mock_scope_cls, patch(
        "app.services.hermes_skill.hermes_task_worker.execute_runtime_skill_via_api_server",
        AsyncMock(return_value="saved to /data/hermes/workspace/a.md"),
    ), patch(
        "app.services.hermes_skill.artifact_discovery_service.ArtifactDiscoveryService.discover_and_register_for_task",
        AsyncMock(side_effect=RuntimeError("discovery boom")),
    ):
        mock_binding_cls.return_value.get_by_profile = AsyncMock(return_value=binding_record)
        mock_scope_cls.return_value.assert_dispatchable_instance = AsyncMock()

        await worker._execute_api_server_task(
            db,
            task,
            task.routing_metadata["route_snapshot"],
            task_service,
            event_service,
            audit_logger,
        )

    task_service.mark_completed.assert_awaited_once()
    task_service.mark_failed.assert_not_called()
    assert task.dispatch_status == "finished"


def test_container_workspace_path_re_matches():
    assert CONTAINER_WORKSPACE_PATH_RE.search(
        "/data/hermes/workspace/reports/a.md"
    )
