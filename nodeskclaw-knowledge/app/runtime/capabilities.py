"""Runtime capability snapshot — facts-driven capability shape for RuntimeBinding persistence."""

from __future__ import annotations

from typing import Any

from app.integrations.ragflow.client import RagflowClient
from app.runtime.ragflow_contract import (
    MINIMUM_SUPPORTED_RAGFLOW_VERSION,
    RagflowCompatibilityProfile,
    probe_compatibility_profile,
)

VALIDATED_RAGFLOW_VERSIONS: list[str] = []


def _cap_entry(
    *,
    build_supported: bool,
    retrieval_supported: bool,
    runtime_version: str | None,
    validated: bool = False,
    experimental: bool = False,
    requires_reparse: bool = False,
    reason: str | None = None,
) -> dict[str, Any]:
    return {
        "build_supported": build_supported,
        "retrieval_supported": retrieval_supported,
        "build_mode": "native" if build_supported else None,
        "retrieval_mode": "native" if retrieval_supported else None,
        "requires_reparse": requires_reparse,
        "source_lineage_supported": build_supported,
        "runtime_version": runtime_version,
        "min_runtime_version": MINIMUM_SUPPORTED_RAGFLOW_VERSION,
        "validated": validated,
        "experimental": experimental,
        "reason": reason,
    }


def capabilities_from_profile(profile: RagflowCompatibilityProfile) -> dict[str, Any]:
    runtime_version = profile.runtime_version
    if not profile.reachable:
        unreachable = _cap_entry(
            build_supported=False,
            retrieval_supported=False,
            runtime_version=runtime_version,
            reason="ragflow_unreachable",
        )
        return {
            "supports_chunk": unreachable,
            "supports_auto_questions": unreachable,
            "supports_raptor": unreachable,
            "supports_graph": unreachable,
            "supports_metadata_filter": False,
            "supports_table": _cap_entry(
                build_supported=False,
                retrieval_supported=False,
                runtime_version=runtime_version,
                reason="ragflow_unreachable",
            ),
            "supports_outline": _cap_entry(
                build_supported=False,
                retrieval_supported=False,
                runtime_version=runtime_version,
                reason="ragflow_unreachable",
            ),
            "ragflow_version": runtime_version,
            "compat_profile": profile.to_dict(),
        }

    chunk = _cap_entry(
        build_supported=profile.dataset_api and profile.document_api,
        retrieval_supported=profile.chunk_retrieval,
        runtime_version=runtime_version,
        validated=profile.chunk_retrieval,
    )
    questions = _cap_entry(
        build_supported=profile.auto_questions_build,
        retrieval_supported=profile.question_fields_visible and profile.chunk_retrieval,
        runtime_version=runtime_version,
        validated=profile.question_fields_visible,
        requires_reparse=True,
        experimental=not profile.question_fields_visible,
        reason=None if profile.question_fields_visible else "question_fields_not_visible",
    )
    raptor = _cap_entry(
        build_supported=profile.raptor_build or profile.knowledge_compilation,
        retrieval_supported=profile.knowledge_compilation,
        runtime_version=runtime_version,
        validated=profile.knowledge_compilation,
        experimental=not profile.knowledge_compilation,
        reason=None if profile.knowledge_compilation else "knowledge_compilation_unavailable",
    )
    graph = _cap_entry(
        build_supported=profile.dataset_graph,
        retrieval_supported=profile.kg_retrieval,
        runtime_version=runtime_version,
        validated=profile.kg_retrieval,
        experimental=not profile.kg_retrieval,
        reason=None if profile.kg_retrieval else "kg_retrieval_unavailable",
    )
    return {
        "supports_chunk": chunk,
        "supports_auto_questions": questions,
        "supports_raptor": raptor,
        "supports_graph": graph,
        "supports_metadata_filter": profile.metadata_filter,
        "supports_toc_enhance": profile.toc_enhance,
        "supports_table": _cap_entry(
            build_supported=False,
            retrieval_supported=False,
            runtime_version=runtime_version,
            reason="table_index_not_implemented",
        ),
        "supports_outline": _cap_entry(
            build_supported=False,
            retrieval_supported=False,
            runtime_version=runtime_version,
            reason="outline_index_not_implemented",
        ),
        "ragflow_version": runtime_version,
        "compat_profile": profile.to_dict(),
    }


async def probe_runtime_version(client: RagflowClient) -> str | None:
    return await client.get_system_version()


async def probe_index_capabilities(
    client: RagflowClient,
    *,
    reachable: bool,
    runtime_version: str | None,
    profile: RagflowCompatibilityProfile | None = None,
) -> dict[str, Any]:
    if profile is not None:
        return capabilities_from_profile(profile)
    if not reachable:
        return capabilities_from_profile(RagflowCompatibilityProfile(reachable=False, runtime_version=runtime_version))
    discovered = await probe_compatibility_profile(client)
    return capabilities_from_profile(discovered)


async def probe_runtime(
    client: RagflowClient,
    *,
    dataset_id: str | None = None,
    document_id: str | None = None,
) -> tuple[bool, str | None, dict[str, Any]]:
    profile = await probe_compatibility_profile(client, dataset_id=dataset_id, document_id=document_id)
    capabilities = capabilities_from_profile(profile)
    return profile.reachable, profile.runtime_version, capabilities
