"""Index capability catalog — product index descriptors (single-file registry)."""

from __future__ import annotations

from typing import Any

from app.models.enums import BuildTriggerPolicy, IndexType

INDEX_DESCRIPTORS: dict[str, dict[str, Any]] = {
    IndexType.chunk.value: {
        "index_type": IndexType.chunk.value,
        "provider": "ragflow",
        "cost_class": "core",
        "trigger_policy": BuildTriggerPolicy.ingestion.value,
        "runtime_requirements": {"requires_public_api": False, "capability_key": "supports_chunk"},
        "requires": {"build_capability": "chunk", "retrieval_capability": "chunk"},
        "fallback": [],
        "core": True,
        "experimental": False,
    },
    IndexType.question.value: {
        "index_type": IndexType.question.value,
        "provider": "derived",
        "cost_class": "medium",
        "trigger_policy": BuildTriggerPolicy.on_activate.value,
        "runtime_requirements": {
            "requires_public_api": True,
            "capability_key": "supports_auto_questions",
        },
        "requires": {"build_capability": "question", "retrieval_capability": "question"},
        "fallback": ["chunk"],
        "core": False,
        "experimental": False,
    },
    IndexType.outline.value: {
        "index_type": IndexType.outline.value,
        "provider": "derived",
        "cost_class": "medium",
        "trigger_policy": BuildTriggerPolicy.on_activate.value,
        "runtime_requirements": {"requires_public_api": True, "capability_key": "supports_outline"},
        "requires": {"build_capability": "outline", "retrieval_capability": "outline"},
        "fallback": ["chunk"],
        "core": False,
        "experimental": True,
    },
    IndexType.table.value: {
        "index_type": IndexType.table.value,
        "provider": "derived",
        "cost_class": "medium",
        "trigger_policy": BuildTriggerPolicy.on_activate.value,
        "runtime_requirements": {"requires_public_api": True, "capability_key": "supports_table"},
        "requires": {"build_capability": "table", "retrieval_capability": "table"},
        "fallback": ["chunk"],
        "core": False,
        "experimental": True,
    },
    IndexType.hierarchical_summary.value: {
        "index_type": IndexType.hierarchical_summary.value,
        "provider": "ragflow",
        "cost_class": "high",
        "trigger_policy": BuildTriggerPolicy.debounce.value,
        "runtime_requirements": {"requires_public_api": True, "capability_key": "supports_raptor"},
        "requires": {"build_capability": "summary", "retrieval_capability": "summary"},
        "fallback": ["chunk"],
        "core": False,
        "experimental": False,
        "debounce_seconds": 300,
    },
    IndexType.graph.value: {
        "index_type": IndexType.graph.value,
        "provider": "ragflow",
        "cost_class": "high",
        "trigger_policy": BuildTriggerPolicy.debounce.value,
        "runtime_requirements": {"requires_public_api": True, "capability_key": "supports_graph"},
        "requires": {"build_capability": "graph", "retrieval_capability": "graph"},
        "fallback": ["chunk"],
        "core": False,
        "experimental": False,
        "debounce_seconds": 600,
    },
}

SYSTEM_BUILD_PROFILES: dict[str, dict[str, Any]] = {
    "standard": {
        "name": "Standard",
        "description": "Chunk-only build for basic enterprise RAG",
        "index_types": [IndexType.chunk.value],
        "trigger_policy": {
            IndexType.chunk.value: BuildTriggerPolicy.ingestion.value,
        },
    },
    "enhanced": {
        "name": "Enhanced",
        "description": "Chunk plus Question indexes for FAQ and operational knowledge",
        "index_types": [
            IndexType.chunk.value,
            IndexType.question.value,
        ],
        "trigger_policy": {
            IndexType.chunk.value: BuildTriggerPolicy.ingestion.value,
            IndexType.question.value: BuildTriggerPolicy.on_activate.value,
        },
    },
    "reasoning": {
        "name": "Reasoning",
        "description": "Enhanced plus hierarchical summary and graph for complex knowledge",
        "index_types": [
            IndexType.chunk.value,
            IndexType.question.value,
            IndexType.hierarchical_summary.value,
            IndexType.graph.value,
        ],
        "trigger_policy": {
            IndexType.chunk.value: BuildTriggerPolicy.ingestion.value,
            IndexType.question.value: BuildTriggerPolicy.on_activate.value,
            IndexType.hierarchical_summary.value: BuildTriggerPolicy.debounce.value,
            IndexType.graph.value: BuildTriggerPolicy.debounce.value,
        },
    },
    "experimental": {
        "name": "Experimental",
        "description": "Outline and table indexes not included in standard profiles",
        "index_types": [
            IndexType.chunk.value,
            IndexType.outline.value,
            IndexType.table.value,
        ],
        "trigger_policy": {
            IndexType.chunk.value: BuildTriggerPolicy.ingestion.value,
            IndexType.outline.value: BuildTriggerPolicy.on_activate.value,
            IndexType.table.value: BuildTriggerPolicy.on_activate.value,
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
        caps = capabilities or {}
        chunk_cap = caps.get("supports_chunk")
        if chunk_cap is None:
            return True
        return _capability_flag_enabled(chunk_cap)
    req = desc.get("runtime_requirements") or {}
    if not req.get("requires_public_api"):
        return True
    key = req.get("capability_key")
    if not key:
        return False
    caps = capabilities or {}
    return _capability_flag_enabled(caps.get(key))


def is_index_retrieval_ready(index_type: str, capabilities: dict[str, Any] | None) -> bool:
    if not is_runtime_supported(index_type, capabilities):
        return False
    caps = capabilities or {}
    key = (get_descriptor(index_type) or {}).get("runtime_requirements", {}).get("capability_key")
    if not key:
        return True
    cap_value = caps.get(key)
    if isinstance(cap_value, dict):
        return bool(cap_value.get("retrieval_supported"))
    return bool(cap_value)


def _capability_flag_enabled(cap_value: Any) -> bool:
    if isinstance(cap_value, dict):
        return bool(cap_value.get("build_supported"))
    return bool(cap_value)
