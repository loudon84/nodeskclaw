from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest
from pydantic import ValidationError

from app.schemas import validate_semantic_event_payload

BACKEND_MCP = (
    Path(__file__).resolve().parents[2]
    / "nodeskclaw-backend"
    / "app"
    / "schemas"
    / "skill_run"
    / "mcp_jsonrpc.py"
)


def _load_backend_models():
    spec = importlib.util.spec_from_file_location("rm20_skill_run_mcp_jsonrpc", BACKEND_MCP)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_tool_call_started_allows_arguments_object_or_null():
    assert (
        validate_semantic_event_payload(
            "tool.call",
            {"tool_name": "search", "call_id": "c1", "status": "started", "arguments": {"q": "ok"}},
        )
        is None
    )
    assert (
        validate_semantic_event_payload(
            "tool.call",
            {"tool_name": "search", "call_id": "c1", "status": "started", "arguments": None},
        )
        is None
    )
    assert (
        validate_semantic_event_payload(
            "tool.call",
            {"tool_name": "search", "call_id": "c1", "status": "started"},
        )
        is None
    )


def test_tool_call_terminal_may_omit_arguments():
    for status in ("completed", "failed"):
        assert (
            validate_semantic_event_payload(
                "tool.call",
                {"tool_name": "search", "call_id": "c1", "status": status},
            )
            is None
        )


def test_tool_call_rejects_non_object_arguments_and_unknown_keys():
    assert (
        validate_semantic_event_payload(
            "tool.call",
            {"tool_name": "search", "call_id": "c1", "status": "started", "arguments": ["q"]},
        )
        == "invalid_tool_arguments"
    )
    assert (
        validate_semantic_event_payload(
            "tool.call",
            {"tool_name": "search", "call_id": "c1", "status": "started", "preview": "secret"},
        )
        == "unexpected_semantic_payload_field"
    )


def test_raw_arguments_remain_forbidden():
    assert (
        validate_semantic_event_payload(
            "tool.call",
            {
                "tool_name": "search",
                "call_id": "c1",
                "status": "started",
                "raw_arguments": {"token": "secret"},
            },
        )
        == "forbidden_semantic_payload_field"
    )
    assert (
        validate_semantic_event_payload(
            "assistant.message",
            {"message_id": "m1", "text": "hi", "arguments": {"q": "x"}},
        )
        == "unexpected_semantic_payload_field"
    )


def test_tool_result_allowlist_and_failed_requires_error_code():
    assert (
        validate_semantic_event_payload(
            "tool.result",
            {
                "tool_name": "search",
                "call_id": "c1",
                "status": "completed",
                "content": "3 results",
                "structured_content": {"n": 3},
                "artifact_ids": ["art-1"],
                "redacted": False,
                "truncated": False,
            },
        )
        is None
    )
    assert (
        validate_semantic_event_payload(
            "tool.result",
            {"tool_name": "search", "call_id": "c1", "status": "started"},
        )
        == "invalid_tool_result_status"
    )
    assert (
        validate_semantic_event_payload(
            "tool.result",
            {"tool_name": "search", "call_id": "c1", "status": "failed"},
        )
        == "missing_tool_result_error_code"
    )
    assert (
        validate_semantic_event_payload(
            "tool.result",
            {
                "tool_name": "search",
                "call_id": "c1",
                "status": "failed",
                "error_code": "TOOL_FAILED",
            },
        )
        is None
    )
    assert (
        validate_semantic_event_payload(
            "tool.result",
            {
                "tool_name": "search",
                "call_id": "c1",
                "status": "completed",
                "gateway_token": "secret",
            },
        )
        == "forbidden_semantic_payload_field"
    )
    assert (
        validate_semantic_event_payload(
            "tool.result",
            {
                "tool_name": "search",
                "call_id": "c1",
                "status": "completed",
                "preview": "secret",
            },
        )
        == "unexpected_semantic_payload_field"
    )


def test_v16_models_exist_without_rewriting_v15_union():
    models = _load_backend_models()
    assert "arguments" not in models.ToolCallPayload.model_fields
    assert set(models.ToolCallPayload.model_fields) == {"tool_name", "call_id", "status"}
    assert models.RunEventToolCallV12 in models.RUN_EVENT_V15_MODELS
    assert models.RunEventToolCallV16 not in models.RUN_EVENT_V15_MODELS
    assert models.RunEventToolResultV16 not in models.RUN_EVENT_V15_MODELS
    assert models.RunEventToolCallV16 in models.RUN_EVENT_V16_MODELS
    assert models.RunEventToolResultV16 in models.RUN_EVENT_V16_MODELS
    payload = models.ToolCallPayloadV16(
        tool_name="search",
        call_id="c1",
        status="started",
        arguments={"q": "ok"},
        redacted=False,
        truncated=False,
    )
    assert payload.arguments == {"q": "ok"}
    with pytest.raises(ValidationError):
        models.ToolCallPayloadV16(
            tool_name="search",
            call_id="c1",
            status="started",
            preview="secret",
        )
    with pytest.raises(ValidationError):
        models.ToolResultPayloadV16(tool_name="search", call_id="c1", status="failed")
    failed = models.ToolResultPayloadV16(
        tool_name="search",
        call_id="c1",
        status="failed",
        error_code="TOOL_FAILED",
    )
    assert failed.status == "failed"
    assert failed.error_code == "TOOL_FAILED"
