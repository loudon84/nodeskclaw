"""RAGFlow native knowledge compilation artifact provider."""

from __future__ import annotations

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


class RagflowCompilationArtifactProvider:
    artifact_type = "graph"

    def capabilities(self) -> ArtifactCapability:
        return ArtifactCapability(
            artifact_type=self.artifact_type,
            provider="ragflow_native",
            scope="knowledge_base",
            build_supported=True,
            retrieval_supported=True,
            incremental_supported=False,
        )

    async def build(self, context: ArtifactBuildContext) -> ArtifactBuildResult:
        graph = await context.adapter.get_artifact_graph(context.dataset_id)
        entities = graph.get("entities") or (graph.get("data") or {}).get("entities") or []
        ready = bool(entities)
        return ArtifactBuildResult(
            status="succeeded" if ready else "failed",
            provider_payload={"entity_count": len(entities) if isinstance(entities, list) else 0},
            validation_payload={"ready": ready},
            error_code=None if ready else "artifact_build_empty",
            error_message=None if ready else "graph artifact empty",
        )

    async def validate(self, context: ArtifactBuildContext) -> ArtifactValidationResult:
        graph = await context.adapter.get_artifact_graph(context.dataset_id)
        entities = graph.get("entities") or (graph.get("data") or {}).get("entities") or []
        ready = bool(entities)
        return ArtifactValidationResult(
            ready=ready,
            validation_payload={"artifact_type": self.artifact_type, "entity_count": len(entities)},
        )

    async def retrieve(
        self,
        query: str,
        context: ArtifactBuildContext,
    ) -> list[ArtifactEvidenceCandidate]:
        graph = await context.adapter.get_artifact_graph(context.dataset_id)
        entities = graph.get("entities") or (graph.get("data") or {}).get("entities") or []
        candidates: list[ArtifactEvidenceCandidate] = []
        if not isinstance(entities, list):
            return candidates
        for entity in entities[:5]:
            if not isinstance(entity, dict):
                continue
            refs = await self.resolve_lineage(entity)
            name = str(entity.get("name") or entity.get("title") or "entity")
            candidates.append(
                ArtifactEvidenceCandidate(
                    artifact_type=self.artifact_type,
                    title=name,
                    content=name,
                    source_refs=refs,
                    citable=bool(refs),
                    provider_payload={"entity": name},
                )
            )
        return candidates

    async def resolve_lineage(self, item: dict[str, Any]) -> list[SourceRef]:
        refs: list[SourceRef] = []
        source_file_id = item.get("source_file_id")
        file_version_id = item.get("file_version_id")
        if source_file_id and file_version_id:
            refs.append(
                SourceRef(
                    source_file_id=str(source_file_id),
                    file_version_id=str(file_version_id),
                    chunk_id=str(item["chunk_id"]) if item.get("chunk_id") else None,
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
