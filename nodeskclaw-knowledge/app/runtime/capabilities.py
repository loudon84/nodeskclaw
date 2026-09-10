"""Runtime capability snapshot — facts-driven capability shape for RuntimeBinding persistence."""

from __future__ import annotations

from typing import Any

from app.integrations.ragflow.client import RagflowClient
from app.runtime.ragflow_contract import (
    CAPABILITY_SUPPORTED,
    CAPABILITY_UNAVAILABLE,
    CAPABILITY_UNKNOWN,
    CAPABILITY_UNSUPPORTED,
    MINIMUM_SUPPORTED_RAGFLOW_VERSION,
    RagflowCompatibilityProfile,
    probe_compatibility_profile,
)

VALIDATED_RAGFLOW_VERSIONS: list[str] = []


def _project_bool(status: str, observed: bool) -> bool:
    if status in {CAPABILITY_UNKNOWN, CAPABILITY_UNAVAILABLE}:
        return True
    if status == CAPABILITY_UNSUPPORTED:
        return False
    return bool(observed)


def _combine_status(*statuses: str) -> str:
    if any(item == CAPABILITY_UNAVAILABLE for item in statuses):
        return CAPABILITY_UNAVAILABLE
    if any(item == CAPABILITY_UNSUPPORTED for item in statuses):
        return CAPABILITY_UNSUPPORTED
    if statuses and all(item == CAPABILITY_SUPPORTED for item in statuses):
        return CAPABILITY_SUPPORTED
    return CAPABILITY_UNKNOWN


def _cap_entry(
    *,
    status: str,
    build_observed: bool = False,
    retrieval_observed: bool = False,
    runtime_version: str | None,
    validated: bool = False,
    experimental: bool = False,
    requires_reparse: bool = False,
    reason: str | None = None,
) -> dict[str, Any]:
    build_supported = _project_bool(status, build_observed)
    retrieval_supported = _project_bool(status, retrieval_observed)
    return {
        "build_supported": build_supported,
        "retrieval_supported": retrieval_supported,
        "status": status,
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


def _flag_projection(status: str, observed: bool) -> bool:
    return _project_bool(status, observed)


def capabilities_from_profile(profile: RagflowCompatibilityProfile) -> dict[str, Any]:
    runtime_version = profile.runtime_version
    if not profile.reachable:
        unreachable = _cap_entry(
            status=CAPABILITY_UNAVAILABLE,
            runtime_version=runtime_version,
            reason="ragflow_unreachable",
        )
        return {
            "supports_chunk": unreachable,
            "supports_auto_questions": unreachable,
            "supports_raptor": unreachable,
            "supports_graph": unreachable,
            "supports_metadata_filter": True,
            "supports_toc_enhance": True,
            "supports_table": _cap_entry(
                status=CAPABILITY_UNAVAILABLE,
                runtime_version=runtime_version,
                reason="ragflow_unreachable",
            ),
            "supports_outline": _cap_entry(
                status=CAPABILITY_UNAVAILABLE,
                runtime_version=runtime_version,
                reason="ragflow_unreachable",
            ),
            "ragflow_version": runtime_version,
            "compat_profile": profile.to_dict(),
        }

    chunk_status = _combine_status(profile.fact("dataset_api"), profile.fact("document_api"), profile.fact("chunk_retrieval"))
    questions_status = _combine_status(profile.fact("auto_questions_build"), profile.fact("question_fields_visible"))
    raptor_status = _combine_status(profile.fact("raptor_build"), profile.fact("knowledge_compilation"))
    graph_status = _combine_status(profile.fact("dataset_graph"), profile.fact("kg_retrieval"))
    metadata_status = profile.fact("metadata_filter")
    toc_status = profile.fact("toc_enhance")

    chunk = _cap_entry(
        status=chunk_status,
        build_observed=profile.dataset_api and profile.document_api,
        retrieval_observed=profile.chunk_retrieval,
        runtime_version=runtime_version,
        validated=profile.chunk_retrieval,
    )
    questions = _cap_entry(
        status=questions_status,
        build_observed=profile.auto_questions_build,
        retrieval_observed=profile.question_fields_visible and profile.chunk_retrieval,
        runtime_version=runtime_version,
        validated=profile.question_fields_visible,
        requires_reparse=True,
        experimental=questions_status != CAPABILITY_SUPPORTED,
        reason=None if questions_status == CAPABILITY_SUPPORTED else "question_fields_not_visible",
    )
    raptor = _cap_entry(
        status=raptor_status,
        build_observed=profile.raptor_build or profile.knowledge_compilation,
        retrieval_observed=profile.knowledge_compilation,
        runtime_version=runtime_version,
        validated=profile.knowledge_compilation,
        experimental=raptor_status != CAPABILITY_SUPPORTED,
        reason=None if raptor_status == CAPABILITY_SUPPORTED else "knowledge_compilation_unavailable",
    )
    graph = _cap_entry(
        status=graph_status,
        build_observed=profile.dataset_graph,
        retrieval_observed=profile.kg_retrieval,
        runtime_version=runtime_version,
        validated=profile.kg_retrieval,
        experimental=graph_status != CAPABILITY_SUPPORTED,
        reason=None if graph_status == CAPABILITY_SUPPORTED else "kg_retrieval_unavailable",
    )
    return {
        "supports_chunk": chunk,
        "supports_auto_questions": questions,
        "supports_raptor": raptor,
        "supports_graph": graph,
        "supports_metadata_filter": _flag_projection(metadata_status, profile.metadata_filter),
        "supports_toc_enhance": _flag_projection(toc_status, profile.toc_enhance),
        "supports_table": _cap_entry(
            status=CAPABILITY_UNSUPPORTED,
            runtime_version=runtime_version,
            reason="table_index_not_implemented",
        ),
        "supports_outline": _cap_entry(
            status=CAPABILITY_UNSUPPORTED,
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
