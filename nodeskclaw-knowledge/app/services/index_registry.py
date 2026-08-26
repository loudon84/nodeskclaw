"""Index capability catalog — product index descriptors (single-file registry)."""

from __future__ import annotations

from typing import Any

from app.models.enums import BuildTriggerPolicy, IndexType

INDEX_DESCRIPTORS: dict[str, dict[str, Any]] = {
    IndexType.chunk.value: {
        "index_type": IndexType.chunk.value,
        "cost_class": "core",
        "trigger_policy": BuildTriggerPolicy.ingestion.value,
        "runtime_requirements": {"requires_public_api": False, "capability_key": "supports_chunk"},
        "core": True,
    },
    IndexType.question.value: {
        "index_type": IndexType.question.value,
        "cost_class": "medium",
        "trigger_policy": BuildTriggerPolicy.on_activate.value,
        "runtime_requirements": {
            "requires_public_api": True,
            "capability_key": "supports_auto_questions",
        },
        "core": False,
    },
    IndexType.outline.value: {
        "index_type": IndexType.outline.value,
        "cost_class": "medium",
        "trigger_policy": BuildTriggerPolicy.on_activate.value,
        "runtime_requirements": {"requires_public_api": True, "capability_key": "supports_outline"},
        "core": False,
    },
    IndexType.table.value: {
        "index_type": IndexType.table.value,
        "cost_class": "medium",
        "trigger_policy": BuildTriggerPolicy.on_activate.value,
        "runtime_requirements": {"requires_public_api": True, "capability_key": "supports_table"},
        "core": False,
    },
    IndexType.hierarchical_summary.value: {
        "index_type": IndexType.hierarchical_summary.value,
        "cost_class": "high",
        "trigger_policy": BuildTriggerPolicy.debounce.value,
        "runtime_requirements": {"requires_public_api": True, "capability_key": "supports_raptor"},
        "core": False,
        "debounce_seconds": 300,
    },
    IndexType.graph.value: {
        "index_type": IndexType.graph.value,
        "cost_class": "high",
        "trigger_policy": BuildTriggerPolicy.debounce.value,
        "runtime_requirements": {"requires_public_api": True, "capability_key": "supports_graph"},
        "core": False,
        "debounce_seconds": 600,
    },
}

SYSTEM_BUILD_PROFILES: dict[str, dict[str, Any]] = {
    "standard": {
        "name": "Standard",
        "description": "Chunk-only build; Graph excluded",
        "index_types": [IndexType.chunk.value],
        "trigger_policy": {
            IndexType.chunk.value: BuildTriggerPolicy.ingestion.value,
        },
    },
    "enhanced": {
        "name": "Enhanced",
        "description": "Chunk plus on-activate secondary indexes when runtime supports them",
        "index_types": [
            IndexType.chunk.value,
            IndexType.question.value,
            IndexType.outline.value,
            IndexType.table.value,
        ],
        "trigger_policy": {
            IndexType.chunk.value: BuildTriggerPolicy.ingestion.value,
            IndexType.question.value: BuildTriggerPolicy.on_activate.value,
            IndexType.outline.value: BuildTriggerPolicy.on_activate.value,
            IndexType.table.value: BuildTriggerPolicy.on_activate.value,
        },
    },
    "reasoning": {
        "name": "Reasoning",
        "description": "Enhanced plus summary/graph with debounce (no per-file full rebuild)",
        "index_types": [
            IndexType.chunk.value,
            IndexType.question.value,
            IndexType.outline.value,
            IndexType.table.value,
            IndexType.hierarchical_summary.value,
            IndexType.graph.value,
        ],
        "trigger_policy": {
            IndexType.chunk.value: BuildTriggerPolicy.ingestion.value,
            IndexType.question.value: BuildTriggerPolicy.on_activate.value,
            IndexType.outline.value: BuildTriggerPolicy.on_activate.value,
            IndexType.table.value: BuildTriggerPolicy.on_activate.value,
            IndexType.hierarchical_summary.value: BuildTriggerPolicy.debounce.value,
            IndexType.graph.value: BuildTriggerPolicy.debounce.value,
        },
    },
}


def get_descriptor(index_type: str) -> dict[str, Any] | None:
    return INDEX_DESCRIPTORS.get(index_type)


def list_index_types() -> list[str]:
    return list(INDEX_DESCRIPTORS.keys())


def is_runtime_supported(index_type: str, capabilities: dict[str, Any] | None) -> bool:
    desc = get_descriptor(index_type)
    if desc is None:
        return False
    if index_type == IndexType.chunk.value:
        return True
    req = desc.get("runtime_requirements") or {}
    if not req.get("requires_public_api"):
        return True
    key = req.get("capability_key")
    if not key:
        return False
    caps = capabilities or {}
    return bool(caps.get(key))
