from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

from app.api.runs import _public_run_event
from app.schemas.hermes_skill.runtime_skill_run import StartRuntimeSkillRunRequest
from app.services.hermes_skill.runtime_skill_run_service import RuntimeSkillRunService


def _event(event_type: str, payload: dict, seq: int = 1) -> dict:
    return {
        "event_type": event_type,
        "event_seq": seq,
        "timestamp": "2026-09-12T00:00:00Z",
        "payload": payload,
    }


def test_projection_schema_allows_tool_call_arguments_and_tool_result():
    started = _public_run_event(
        _event(
            "tool.call",
            {
                "tool_name": "search",
                "call_id": "call-1",
                "status": "started",
                "arguments": {"q": "ok"},
                "redacted": False,
                "truncated": False,
            },
        ),
        "run-1",
    )
    assert started is not None
    assert started["payload"]["arguments"] == {"q": "ok"}
    result = _public_run_event(
        _event(
            "tool.result",
            {
                "tool_name": "search",
                "call_id": "call-1",
                "status": "completed",
                "content": "3 hits",
                "artifact_ids": ["art-1"],
            },
            seq=2,
        ),
        "run-1",
        persisted_artifact_ids={"art-1"},
    )
    assert result is not None
    assert result["payload"]["call_id"] == "call-1"
    assert result["payload"]["artifact_ids"] == ["art-1"]


def test_projection_rejects_unknown_schema_fields():
    assert (
        _public_run_event(
            _event(
                "tool.call",
                {
                    "tool_name": "search",
                    "call_id": "call-1",
                    "status": "started",
                    "preview": "secret",
                },
            ),
            "run-1",
        )
        is None
    )
    assert (
        _public_run_event(
            _event(
                "tool.result",
                {
                    "tool_name": "search",
                    "call_id": "call-1",
                    "status": "completed",
                    "gateway_url": "https://example.com",
                },
            ),
            "run-1",
        )
        is None
    )


def test_sanitize_secret_path_and_thought_are_stripped():
    projected = _public_run_event(
        _event(
            "tool.call",
            {
                "tool_name": "fetch",
                "call_id": "call-2",
                "status": "started",
                "arguments": {
                    "q": "keep",
                    "token": "secret-token",
                    "path": "/home/user/.ssh/id_rsa",
                    "url": "https://example.com/a?signature=abcd&q=ok",
                    "chain_of_thought": "hidden",
                },
            },
        ),
        "run-1",
    )
    assert projected is not None
    arguments = projected["payload"]["arguments"]
    assert arguments["q"] == "keep"
    assert "token" not in arguments
    assert "chain_of_thought" not in arguments
    assert arguments["path"] == "id_rsa"
    assert "signature=" not in arguments["url"]
    assert projected["payload"]["redacted"] is True


def test_artifact_ids_same_run_only_rejects_cross_run_and_tenant():
    projected = _public_run_event(
        _event(
            "tool.result",
            {
                "tool_name": "search",
                "call_id": "call-3",
                "status": "completed",
                "artifact_ids": ["same-run", "cross_run_art", "other-tenant"],
            },
        ),
        "run-1",
        persisted_artifact_ids={"same-run"},
    )
    assert projected is not None
    assert projected["payload"]["artifact_ids"] == ["same-run"]
    assert "cross_run_art" not in projected["payload"]["artifact_ids"]
    assert "other-tenant" not in projected["payload"]["artifact_ids"]


def test_contract_version_reports_160_when_agent_enabled():
    source = Path(__file__).resolve().parents[2] / "app" / "services" / "hermes_skill" / "runtime_skill_run_service.py"
    text = source.read_text(encoding="utf-8")
    assert "SKILL_RUN_CONTRACT_VERSION_V121" not in text
    assert '"1.6.0"' in text
    task = MagicMock()
    task.id = "run-ver"
    task.status = "running"
    task.server_artifacts = []
    req = StartRuntimeSkillRunRequest(
        org_id="org-1",
        user_id="user-1",
        tool_name="test_tool",
        runtime_skill_id="test_tool",
        agent_profile="agent",
        hermes_agent_instance_id="inst-1",
        agent_id="agent-1",
        arguments={},
        client_context={},
        output_policy={"artifact_mode": "pull_only"},
        task_source="org_mcp",
        skill_id="test_tool",
    )
    with patch("app.services.hermes_skill.runtime_skill_run_service.settings.SKILL_AGENT_ENABLED", True):
        content = RuntimeSkillRunService.build_structured_content(
            task=task,
            request=req,
            event_sse_url="/events",
            output_policy={"artifact_mode": "pull_only"},
            contract_version="1.6.0",
        )
    assert content["contract_version"] == "1.6.0"
    with patch("app.services.hermes_skill.runtime_skill_run_service.settings.SKILL_AGENT_ENABLED", False):
        content_off = RuntimeSkillRunService.build_structured_content(
            task=task,
            request=req,
            event_sse_url="/events",
            output_policy={"artifact_mode": "pull_only"},
            contract_version="1.5.0",
        )
    assert content_off["contract_version"] == "1.5.0"


def test_no_second_store_or_sse_endpoint():
    source = Path(__file__).resolve().parents[2] / "app" / "api" / "runs.py"
    text = source.read_text(encoding="utf-8")
    assert text.count('@router.get("/{run_id}/events")') == 1
    assert "def stream_run_events" in text
    assert "class EventStore" not in text
    descriptor = text.split("def _public_artifact_descriptor")[1].split("def ")[0]
    assert "download_url" not in descriptor
