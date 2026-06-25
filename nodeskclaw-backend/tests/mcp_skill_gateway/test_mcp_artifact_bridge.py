from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest

from app.services.mcp_skill_gateway.artifact_materializer import (
    ArtifactMaterializer,
    build_suggested_workspace_path,
    render_filename,
)
from app.services.mcp_skill_gateway.output_policy_service import OutputPolicyService, tool_short_name


def test_tool_short_name_strips_prefix():
    assert tool_short_name("hermes_xieyi__semiconductor-marketing-copy") == "semiconductor-marketing-copy"


def test_output_policy_priority_installation_over_skill():
    skill = SimpleNamespace(output_policy={"format": "json", "suggested_workspace_dir": "drafts/a"})
    installation = SimpleNamespace(routing_metadata={"output_policy": {"format": "markdown", "suggested_workspace_dir": "drafts/b"}})
    policy = OutputPolicyService.resolve(skill=skill, installation=installation, tool_name="hermes_xieyi__customer-profiling")
    assert policy["format"] == "markdown"
    assert policy["artifact_mode"] == "pull_only"


def test_output_policy_default_for_semiconductor_marketing_copy():
    policy = OutputPolicyService.resolve(skill=None, installation=None, tool_name="hermes_xieyi__semiconductor-marketing-copy")
    assert policy["suggested_workspace_dir"] == "drafts/sale"
    assert policy["kb_ingest"]["enabled"] is True


def test_render_filename_replaces_topic_and_date():
    task = SimpleNamespace(
        arguments={"topic": "TI 音频芯片"},
        request_summary=None,
        tool_name="hermes_xieyi__semiconductor-marketing-copy",
    )
    when = datetime(2026, 6, 25, 18, 30, tzinfo=timezone.utc)
    name = render_filename("{topic}_推广文案_{date}.md", task, completed_at=when)
    assert name.endswith("_1830.md")
    assert "TI" in name


def test_build_suggested_workspace_path():
    path = build_suggested_workspace_path("drafts/sale", "report.md")
    assert path == "workspace/drafts/sale/report.md"


def test_materialize_markdown_frontmatter_no_token():
    task = SimpleNamespace(
        id="task-1",
        tool_name="hermes_xieyi__semiconductor-marketing-copy",
        request_summary="推广文案",
        arguments={"topic": "TI"},
    )
    policy = OutputPolicyService.resolve(skill=None, installation=None, tool_name=task.tool_name)
    content = ArtifactMaterializer.materialize(
        task,
        "正文内容\nBearer ndsk_mcp_secret_token",
        policy,
        artifact_id="art-1",
    )
    text = content.content.decode("utf-8")
    assert "source: nodeskclaw-mcp-skill-gateway" in text
    assert "Bearer" not in text
    assert "ndsk_mcp_" not in text
    assert "[REDACTED]" in text
    assert content.suggested_workspace_path.startswith("workspace/drafts/sale/")


def test_artifact_store_builds_object_key():
    from app.services.mcp_skill_gateway.artifact_store_service import ArtifactStoreService

    key = ArtifactStoreService.build_object_key("org1", "task1", "art1", "report.md")
    assert key == "orgs/org1/tasks/task1/artifacts/art1/report.md"


@pytest.mark.asyncio
async def test_kb_ingestion_sha256_dedup():
    from app.services.mcp_skill_gateway.kb_ingestion_service import KbIngestionService

    db = AsyncMock()
    existing_result = AsyncMock()
    existing_result.scalar_one_or_none.return_value = SimpleNamespace(id="existing")
    db.execute = AsyncMock(return_value=existing_result)
    db.add = AsyncMock()
    db.flush = AsyncMock()

    svc = KbIngestionService(db)
    artifact = SimpleNamespace(
        id="a1",
        org_id="org1",
        task_id="t1",
        sha256="abc",
        file_name="x.md",
        metadata_json={},
    )
    policy = {"kb_ingest": {"enabled": True, "mode": "pending_review", "knowledge_base": "general", "tags": []}}
    with patch.object(svc.audit, "log", new=AsyncMock()):
        job = await svc.create_job(artifact, policy)
    assert job is None
