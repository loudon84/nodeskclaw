"""RuntimeConfigCompiler — sole authority for desired RAGFlow dataset config generation."""

# @lat: [[knowledge-objects#Runtime Binding]]
from __future__ import annotations

import copy
from typing import Any

from app.models.build_profile import BuildProfile
from app.models.enums import IndexType
from app.models.knowledge_base import KnowledgeBase
from app.models.knowledge_model import KnowledgeModel
from app.runtime.ragflow_contract import RagflowCompatibilityProfile


def _capability_enabled(caps: dict[str, Any] | None, key: str) -> bool:
    if not caps:
        return False
    entry = caps.get(key)
    if isinstance(entry, dict):
        return bool(entry.get("build_supported"))
    return bool(entry)


def compile_desired_config(
    kb: KnowledgeBase,
    build_profile: BuildProfile,
    knowledge_model: KnowledgeModel | None,
    compat_profile: RagflowCompatibilityProfile | dict[str, Any] | None,
) -> dict[str, Any]:
    caps: dict[str, Any] = {}
    if isinstance(compat_profile, RagflowCompatibilityProfile):
        caps = {
            "supports_auto_questions": compat_profile.auto_questions_build,
            "supports_raptor": compat_profile.raptor_build,
            "supports_graph": compat_profile.dataset_graph,
        }
    elif isinstance(compat_profile, dict):
        caps = compat_profile

    parser_config = copy.deepcopy(kb.parser_config or {})
    index_types = set(build_profile.index_types or [])

    if IndexType.question.value in index_types and _capability_enabled(caps, "supports_auto_questions"):
        parser_config.setdefault("auto_questions", 5)
    if IndexType.hierarchical_summary.value in index_types and _capability_enabled(caps, "supports_raptor"):
        raptor = dict(parser_config.get("raptor") or {})
        raptor.setdefault("use_raptor", True)
        raptor.setdefault("scope", "file")
        parser_config["raptor"] = raptor
    if IndexType.graph.value in index_types and _capability_enabled(caps, "supports_graph"):
        graphrag = dict(parser_config.get("graphrag") or {})
        graphrag.setdefault("use_graphrag", True)
        parser_config["graphrag"] = graphrag

    if knowledge_model is not None and knowledge_model.extraction_policy:
        policy = knowledge_model.extraction_policy or {}
        if policy.get("graph_entities") and IndexType.graph.value in index_types:
            graphrag = dict(parser_config.get("graphrag") or {})
            graphrag.setdefault("use_graphrag", True)
            parser_config["graphrag"] = graphrag

    return {
        "embedding_model": kb.embedding_model,
        "chunk_method": kb.chunk_method,
        "parser_config": parser_config,
        "description": kb.description,
    }
