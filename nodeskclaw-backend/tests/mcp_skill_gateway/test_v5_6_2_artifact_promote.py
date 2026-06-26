from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.mcp_skill_gateway.artifact_materializer import (
    extract_company_from_task,
    render_filename,
)
from app.services.mcp_skill_gateway.server_artifact_service import ServerArtifactService


def test_extract_company_from_task_prompt():
    task = SimpleNamespace(
        arguments={"prompt": "请为陕西天基通信科技有限责任公司做客户画像"},
        request_summary=None,
    )
    assert extract_company_from_task(task) == "陕西天基通信科技有限责任公司"


def test_render_filename_no_unknown_when_prompt_has_company():
    task = SimpleNamespace(
        arguments={"prompt": "请为陕西天基通信科技有限责任公司做客户画像"},
        request_summary=None,
        tool_name="hermes_xieyi__customer-profiling",
    )
    when = datetime(2026, 6, 26, 11, 8, tzinfo=timezone.utc)
    name = render_filename("{company}_客户画像_{date}.md", task, completed_at=when)
    assert "unknown" not in name
    assert "陕西天基通信科技有限责任公司" in name


def test_build_suggested_path_from_relative_path():
    assert (
        ServerArtifactService.build_suggested_path_from_relative_path(
            "exports/陕西天基通信科技有限责任公司_客户画像报告.md"
        )
        == "workspace/exports/陕西天基通信科技有限责任公司_客户画像报告.md"
    )
    assert (
        ServerArtifactService.build_suggested_path_from_relative_path(
            "workspace/exports/report.md"
        )
        == "workspace/exports/report.md"
    )


@pytest.mark.asyncio
async def test_promote_discovered_artifact_uploads_and_creates_kb_job(tmp_path):
    report = tmp_path / "陕西天基通信科技有限责任公司_客户画像报告.md"
    report.write_text("# 客户画像\n\n正文", encoding="utf-8")

    task = SimpleNamespace(
        id="task-1",
        org_id="org-1",
        skill_id="skill-1",
        agent_id="agent-1",
        workspace_id="ws-1",
        user_id="user-1",
        tool_name="hermes_xieyi__customer-profiling",
        worker_id="worker-1",
        completed_at=datetime.now(timezone.utc),
    )
    artifact = SimpleNamespace(
        id="art-disc-1",
        deleted_at=None,
        task_id="task-1",
        org_id="org-1",
        file_name=report.name,
        file_path=str(report),
        relative_path="exports/陕西天基通信科技有限责任公司_客户画像报告.md",
        content_type="text/markdown",
        storage_type="local",
        object_key=None,
        size_bytes=report.stat().st_size,
        sha256=None,
        format=None,
        artifact_type="markdown",
        kb_status="none",
        workspace_saved=False,
        suggested_workspace_dir=None,
        suggested_workspace_path=None,
        metadata_json={
            "host_workspace_root": str(tmp_path),
            "source": "hermes_api_server_workspace",
        },
        source="discovery",
    )

    db = AsyncMock()
    db.flush = AsyncMock()
    svc = ServerArtifactService(db)
    stored = SimpleNamespace(
        object_key="orgs/org-1/tasks/task-1/artifacts/art-disc-1/report.md",
        size_bytes=report.stat().st_size,
        sha256="abc123",
    )

    with (
        patch.object(svc.store, "store", new=AsyncMock(return_value=stored)),
        patch.object(svc.kb, "create_job", new_callable=AsyncMock, return_value=SimpleNamespace(id="job-1")) as create_job_mock,
        patch.object(svc.audit, "log", new=AsyncMock()),
    ):
        result = await svc.create_from_discovered_artifacts(
            task,
            [artifact],
            {
                "store_to_gateway": True,
                "kb_ingest": {"enabled": True, "mode": "pending_review"},
            },
            result_text="exports/陕西天基通信科技有限责任公司_客户画像报告.md",
        )

    assert len(result) == 1
    assert result[0]["name"] == "陕西天基通信科技有限责任公司_客户画像报告.md"
    assert artifact.storage_type == "object_store"
    assert artifact.kb_status == "pending_review"
    create_job_mock.assert_awaited_once()


@pytest.mark.asyncio
async def test_kb_dedup_syncs_artifact_status():
    from app.services.mcp_skill_gateway.kb_ingestion_service import KbIngestionService

    db = AsyncMock()
    existing_job = SimpleNamespace(id="job-existing", status="indexed")
    existing_result = MagicMock()
    existing_result.scalar_one_or_none.return_value = existing_job
    db.execute = AsyncMock(return_value=existing_result)
    db.flush = AsyncMock()

    artifact = SimpleNamespace(
        id="a1",
        org_id="org1",
        task_id="t1",
        sha256="abc",
        file_name="x.md",
        metadata_json={},
        kb_status="pending_review",
    )
    svc = KbIngestionService(db)
    with patch.object(svc.audit, "log", new=AsyncMock()):
        job = await svc.create_job(
            artifact,
            {"kb_ingest": {"enabled": True, "mode": "pending_review"}},
        )

    assert job is None
    assert artifact.kb_status == "indexed"


@pytest.mark.asyncio
async def test_promote_skips_when_no_eligible_files(tmp_path):
    task = SimpleNamespace(
        id="task-1",
        org_id="org-1",
        tool_name="tool",
        worker_id="worker-1",
        completed_at=datetime.now(timezone.utc),
    )
    artifact = SimpleNamespace(
        id="art-1",
        deleted_at=None,
        task_id="task-1",
        org_id="org-1",
        file_name="report.pdf",
        file_path=str(tmp_path / "report.pdf"),
        relative_path="exports/report.pdf",
        content_type="application/pdf",
        storage_type="local",
        object_key=None,
        metadata_json={"host_workspace_root": str(tmp_path)},
    )
    (tmp_path / "report.pdf").write_bytes(b"%PDF")

    db = AsyncMock()
    svc = ServerArtifactService(db)
    with patch.object(svc.audit, "log", new=AsyncMock()):
        result = await svc.create_from_discovered_artifacts(
            task,
            [artifact],
            {"store_to_gateway": True, "kb_ingest": {"enabled": True}},
        )
    assert result == []


@pytest.mark.asyncio
async def test_fallback_materialize_when_discovered_empty():
    task = SimpleNamespace(
        id="task-2",
        org_id="org-1",
        skill_id="s1",
        agent_id="a1",
        workspace_id="w1",
        user_id="u1",
        tool_name="tool",
        worker_id="worker-1",
        request_summary=None,
        completed_at=datetime.now(timezone.utc),
    )
    db = AsyncMock()
    db.add = MagicMock()
    db.flush = AsyncMock()
    svc = ServerArtifactService(db)
    stored = SimpleNamespace(object_key="key", size_bytes=10, sha256="sha")

    with (
        patch.object(svc.store, "store", new=AsyncMock(return_value=stored)),
        patch.object(svc.materializer, "materialize") as materialize_mock,
        patch.object(svc.kb, "create_job", new=AsyncMock(return_value=SimpleNamespace(id="j1"))),
        patch.object(svc.audit, "log", new=AsyncMock()),
    ):
        materialize_mock.return_value = SimpleNamespace(
            filename="report.md",
            content=b"body",
            mime_type="text/markdown",
            format="markdown",
            suggested_workspace_dir="drafts",
            suggested_workspace_path="workspace/drafts/report.md",
        )
        result = await svc.create_from_task_result(
            task,
            "完整报告正文",
            {"store_to_gateway": True, "kb_ingest": {"enabled": True}},
            fallback=True,
        )

    assert len(result) == 1
    assert result[0]["name"] == "report.md"
