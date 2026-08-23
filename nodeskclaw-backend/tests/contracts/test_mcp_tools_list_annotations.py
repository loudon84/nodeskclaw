import jsonschema
import pytest
from pydantic import ValidationError

from app.schemas.work_expert.mcp_jsonrpc import ToolsListResult


def _schema() -> dict:
    return ToolsListResult.model_json_schema(mode="serialization")


def _tool_item_schema(schema: dict) -> dict:
    items = schema["properties"]["tools"]["items"]
    ref = items.get("$ref")
    if isinstance(ref, str) and ref.startswith("#/$defs/"):
        return schema["$defs"][ref.rsplit("/", 1)[-1]]
    return items


def test_tools_list_schema_is_not_open_object_only():
    # @lat: [[work-expert-contract#MCP Tools List Annotations]]
    schema = _schema()
    items = _tool_item_schema(schema)
    assert items.get("additionalProperties") is not True or "properties" in items
    assert "name" in (items.get("properties") or {})
    assert "inputSchema" in (items.get("properties") or {})
    assert "annotations" in (items.get("properties") or {})
    annotations = items["properties"]["annotations"]
    variants = annotations.get("anyOf") or annotations.get("oneOf") or [annotations]
    assert len(variants) >= 2


def test_catalog_chinese_display_name_validates():
    payload = {
        "tools": [
            {
                "name": "call-prep",
                "description": "客户调研专家",
                "inputSchema": {"type": "object", "properties": {}},
                "annotations": {
                    "kind": "expert",
                    "slug": "call-prep",
                    "displayName": "客户调研专家",
                    "status": "ready",
                    "publicSkillCount": 3,
                    "callableSkillCount": 2,
                },
            }
        ]
    }
    ToolsListResult.model_validate(payload)
    jsonschema.validate(payload, _schema())


def test_skill_annotations_validate():
    payload = {
        "tools": [
            {
                "name": "customer-profiling",
                "description": "Profile a customer",
                "inputSchema": {
                    "type": "object",
                    "properties": {"prompt": {"type": "string"}},
                },
                "annotations": {
                    "displayName": "客户画像",
                    "status": "ready",
                    "callEnabled": True,
                    "riskLevel": "low",
                    "approvalMode": "none",
                },
            }
        ]
    }
    ToolsListResult.model_validate(payload)
    jsonschema.validate(payload, _schema())


def test_missing_optional_display_name_validates():
    payload = {
        "tools": [
            {
                "name": "call-prep",
                "inputSchema": {"type": "object", "properties": {}},
                "annotations": {
                    "kind": "expert",
                    "slug": "call-prep",
                    "status": "offline",
                    "publicSkillCount": 1,
                    "callableSkillCount": 0,
                },
            }
        ]
    }
    result = ToolsListResult.model_validate(payload)
    assert result.tools[0].annotations.displayName is None
    jsonschema.validate(payload, _schema())


def test_call_enabled_false_skill_validates():
    payload = {
        "tools": [
            {
                "name": "restricted-skill",
                "inputSchema": {"type": "object", "properties": {}},
                "annotations": {
                    "status": "ready",
                    "callEnabled": False,
                    "riskLevel": "high",
                    "approvalMode": "approval_required",
                },
            }
        ]
    }
    result = ToolsListResult.model_validate(payload)
    assert result.tools[0].annotations.callEnabled is False
    jsonschema.validate(payload, _schema())


def test_invalid_catalog_counts_rejected():
    payload = {
        "tools": [
            {
                "name": "call-prep",
                "inputSchema": {"type": "object", "properties": {}},
                "annotations": {
                    "kind": "expert",
                    "slug": "call-prep",
                    "status": "ready",
                    "publicSkillCount": -1,
                    "callableSkillCount": 0,
                },
            }
        ]
    }
    with pytest.raises(ValidationError):
        ToolsListResult.model_validate(payload)


def test_catalog_missing_slug_rejected():
    payload = {
        "tools": [
            {
                "name": "call-prep",
                "inputSchema": {"type": "object", "properties": {}},
                "annotations": {
                    "kind": "expert",
                    "status": "ready",
                    "publicSkillCount": 1,
                    "callableSkillCount": 1,
                },
            }
        ]
    }
    with pytest.raises(ValidationError):
        ToolsListResult.model_validate(payload)
