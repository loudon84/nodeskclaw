"""Outline / PageIndex artifact provider."""

from __future__ import annotations

import json
from typing import Any

from app.knowledge_artifacts.base import (
    ArtifactBuildContext,
    ArtifactBuildResult,
    ArtifactCapability,
    ArtifactDelta,
    ArtifactEvidenceCandidate,
    ArtifactValidationResult,
    SourceRef,
)
from app.services import artifact_store


def _normalize_node(raw: dict[str, Any]) -> dict[str, Any]:
    source_refs = raw.get("source_refs") or raw.get("sources") or []
    normalized_refs: list[dict[str, Any]] = []
    if isinstance(source_refs, list):
        for ref in source_refs:
            if not isinstance(ref, dict):
                continue
            source_file_id = ref.get("source_file_id")
            file_version_id = ref.get("file_version_id")
            if source_file_id and file_version_id:
                normalized_refs.append(
                    {
                        "source_file_id": str(source_file_id),
                        "file_version_id": str(file_version_id),
                        "page_start": ref.get("page_start"),
                        "page_end": ref.get("page_end"),
                        "chunk_id": ref.get("chunk_id"),
                    }
                )
    return {
        "id": str(raw.get("id") or raw.get("node_id") or ""),
        "title": str(raw.get("title") or raw.get("name") or ""),
        "level": int(raw.get("level") or 1),
        "page_start": raw.get("page_start"),
        "page_end": raw.get("page_end"),
        "source_refs": normalized_refs,
        "citable": len(normalized_refs) > 0,
    }


def _structure_from_payload(payload: dict[str, Any]) -> dict[str, Any]:
    nodes_raw = payload.get("nodes") or (payload.get("data") or {}).get("nodes") or []
    nodes = [_normalize_node(node) for node in nodes_raw if isinstance(node, dict)]
    return {
        "title": str(payload.get("title") or ""),
        "nodes": nodes,
    }


class OutlineArtifactProvider:
    artifact_type = "outline"

    def capabilities(self) -> ArtifactCapability:
        return ArtifactCapability(
            artifact_type=self.artifact_type,
            provider="ragflow_native",
            scope="file",
            build_supported=True,
            retrieval_supported=True,
            incremental_supported=True,
        )

    async def build(self, context: ArtifactBuildContext) -> ArtifactBuildResult:
        params: dict[str, Any] = {}
        if context.ragflow_document_id:
            params["document_id"] = context.ragflow_document_id
        structure_payload = await context.adapter.get_artifact_structure(context.dataset_id, **params)
        structure = _structure_from_payload(structure_payload if isinstance(structure_payload, dict) else {})
        if not structure["nodes"]:
            topics = await context.adapter.get_artifact_topics(context.dataset_id, **params)
            structure = _structure_from_payload(topics if isinstance(topics, dict) else {"nodes": topics})
        if not structure["nodes"]:
            return ArtifactBuildResult(
                status="failed",
                error_code="outline_unavailable",
                error_message="no outline structure available from runtime",
            )
        relative_path = (
            f"{context.org_id}/{context.knowledge_base_id}/outline/"
            f"{context.source_file_id or 'kb'}/{context.manifest_hash}.json"
        )
        artifact_uri = artifact_store.write_bytes(
            relative_path,
            json.dumps(structure, ensure_ascii=False).encode("utf-8"),
        )
        citable_nodes = sum(1 for node in structure["nodes"] if node.get("citable"))
        return ArtifactBuildResult(
            status="succeeded",
            artifact_uri=artifact_uri,
            provider_payload={"node_count": len(structure["nodes"]), "citable_nodes": citable_nodes},
            validation_payload={"ready": True, "citable_nodes": citable_nodes},
            coverage_payload={"node_count": len(structure["nodes"])},
        )

    async def validate(self, context: ArtifactBuildContext) -> ArtifactValidationResult:
        params: dict[str, Any] = {}
        if context.ragflow_document_id:
            params["document_id"] = context.ragflow_document_id
        structure_payload = await context.adapter.get_artifact_structure(context.dataset_id, **params)
        structure = _structure_from_payload(structure_payload if isinstance(structure_payload, dict) else {})
        citable_nodes = sum(1 for node in structure["nodes"] if node.get("citable"))
        ready = len(structure["nodes"]) > 0
        return ArtifactValidationResult(
            ready=ready,
            validation_payload={
                "artifact_type": self.artifact_type,
                "node_count": len(structure["nodes"]),
                "citable_nodes": citable_nodes,
            },
            coverage_payload={"citable_ratio": (citable_nodes / len(structure["nodes"])) if structure["nodes"] else 0.0},
        )

    async def retrieve(
        self,
        query: str,
        context: ArtifactBuildContext,
    ) -> list[ArtifactEvidenceCandidate]:
        params: dict[str, Any] = {"query": query}
        if context.ragflow_document_id:
            params["document_id"] = context.ragflow_document_id
        structure_payload = await context.adapter.get_artifact_structure(context.dataset_id, **params)
        structure = _structure_from_payload(structure_payload if isinstance(structure_payload, dict) else {})
        needle = query.strip().lower()
        candidates: list[ArtifactEvidenceCandidate] = []
        for node in structure["nodes"]:
            title = str(node.get("title") or "")
            if needle and needle not in title.lower():
                continue
            refs = await self.resolve_lineage(node)
            candidates.append(
                ArtifactEvidenceCandidate(
                    artifact_type=self.artifact_type,
                    title=title,
                    content=title,
                    source_refs=refs,
                    citable=bool(refs),
                    provider_payload={"node_id": node.get("id"), "level": node.get("level")},
                )
            )
        return candidates

    async def resolve_lineage(self, item: dict[str, Any]) -> list[SourceRef]:
        refs: list[SourceRef] = []
        for raw in item.get("source_refs") or []:
            if not isinstance(raw, dict):
                continue
            source_file_id = raw.get("source_file_id")
            file_version_id = raw.get("file_version_id")
            if source_file_id and file_version_id:
                refs.append(
                    SourceRef(
                        source_file_id=str(source_file_id),
                        file_version_id=str(file_version_id),
                        page_start=raw.get("page_start"),
                        page_end=raw.get("page_end"),
                        chunk_id=str(raw["chunk_id"]) if raw.get("chunk_id") else None,
                    )
                )
        return refs

    async def diff(self, context: ArtifactBuildContext) -> ArtifactDelta:
        alteration = await context.adapter.get_artifact_alteration(context.dataset_id)
        return ArtifactDelta(
            added=[str(x) for x in (alteration.get("newly_uploaded") or [])],
            changed=[str(x) for x in (alteration.get("changed") or [])],
            removed=[str(x) for x in (alteration.get("removed") or [])],
        )
