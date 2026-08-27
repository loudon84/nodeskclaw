"""Runtime capability probe — facts-driven capability snapshot for RuntimeBinding."""

from __future__ import annotations

from typing import Any

from app.integrations.ragflow.client import RagflowClient

MINIMUM_SUPPORTED_RAGFLOW_VERSION = "0.17.0"
VALIDATED_RAGFLOW_VERSIONS = ["0.17.0", "0.24.0", "0.27.0"]


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


def _version_validated(version: str | None) -> bool:
    if not version:
        return False
    normalized = version.lstrip("v").split("-", 1)[0]
    return normalized in VALIDATED_RAGFLOW_VERSIONS


async def probe_runtime_version(client: RagflowClient) -> str | None:
    return await client.get_system_version()


async def probe_index_capabilities(
    client: RagflowClient,
    *,
    reachable: bool,
    runtime_version: str | None,
) -> dict[str, Any]:
    validated = _version_validated(runtime_version)
    if not reachable:
        return {
            "supports_chunk": _cap_entry(
                build_supported=False,
                retrieval_supported=False,
                runtime_version=runtime_version,
                reason="ragflow_unreachable",
            ),
            "supports_auto_questions": _cap_entry(
                build_supported=False,
                retrieval_supported=False,
                runtime_version=runtime_version,
                reason="ragflow_unreachable",
            ),
            "supports_raptor": _cap_entry(
                build_supported=False,
                retrieval_supported=False,
                runtime_version=runtime_version,
                reason="ragflow_unreachable",
            ),
            "supports_graph": _cap_entry(
                build_supported=False,
                retrieval_supported=False,
                runtime_version=runtime_version,
                reason="ragflow_unreachable",
            ),
            "supports_metadata_filter": True,
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
        }

    chunk = _cap_entry(
        build_supported=True,
        retrieval_supported=True,
        runtime_version=runtime_version,
        validated=validated,
    )
    questions = _cap_entry(
        build_supported=True,
        retrieval_supported=True,
        runtime_version=runtime_version,
        validated=validated,
        requires_reparse=True,
        experimental=not validated,
        reason=None if validated else "runtime_version_not_validated",
    )
    raptor = _cap_entry(
        build_supported=True,
        retrieval_supported=True,
        runtime_version=runtime_version,
        validated=validated,
        experimental=not validated,
        reason=None if validated else "runtime_version_not_validated",
    )
    graph = _cap_entry(
        build_supported=True,
        retrieval_supported=False,
        runtime_version=runtime_version,
        validated=validated,
        experimental=True,
        reason="graph_query_unsupported",
    )
    return {
        "supports_chunk": chunk,
        "supports_auto_questions": questions,
        "supports_raptor": raptor,
        "supports_graph": graph,
        "supports_metadata_filter": True,
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
    }


async def probe_runtime(client: RagflowClient) -> tuple[bool, str | None, dict[str, Any]]:
    try:
        reachable = await client.system_health()
    except Exception:
        reachable = False
    version = await probe_runtime_version(client) if reachable else None
    capabilities = await probe_index_capabilities(
        client,
        reachable=reachable,
        runtime_version=version,
    )
    return reachable, version, capabilities
