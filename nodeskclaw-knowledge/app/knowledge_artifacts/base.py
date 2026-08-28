"""Artifact Provider SPI — protocol types and build context."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol


@dataclass
class SourceRef:
    source_file_id: str
    file_version_id: str
    page_start: int | None = None
    page_end: int | None = None
    chunk_id: str | None = None


@dataclass
class ArtifactCapability:
    artifact_type: str
    provider: str
    scope: str
    build_supported: bool = False
    retrieval_supported: bool = False
    incremental_supported: bool = False


@dataclass
class ArtifactBuildContext:
    org_id: str
    knowledge_base_id: str
    dataset_id: str
    adapter: Any
    manifest_hash: str
    manifest_summary: dict[str, Any]
    source_file_id: str | None = None
    file_version_id: str | None = None
    ragflow_document_id: str | None = None
    capabilities: dict[str, Any] = field(default_factory=dict)


@dataclass
class ArtifactBuildResult:
    status: str
    artifact_uri: str | None = None
    provider_payload: dict[str, Any] | None = None
    validation_payload: dict[str, Any] | None = None
    coverage_payload: dict[str, Any] | None = None
    error_code: str | None = None
    error_message: str | None = None


@dataclass
class ArtifactValidationResult:
    ready: bool
    validation_payload: dict[str, Any] = field(default_factory=dict)
    coverage_payload: dict[str, Any] = field(default_factory=dict)


@dataclass
class ArtifactEvidenceCandidate:
    artifact_type: str
    title: str
    content: str
    source_refs: list[SourceRef] = field(default_factory=list)
    citable: bool = False
    provider_payload: dict[str, Any] = field(default_factory=dict)


@dataclass
class ArtifactDelta:
    added: list[str] = field(default_factory=list)
    changed: list[str] = field(default_factory=list)
    removed: list[str] = field(default_factory=list)


class KnowledgeArtifactProvider(Protocol):
    artifact_type: str

    def capabilities(self) -> ArtifactCapability: ...

    async def build(self, context: ArtifactBuildContext) -> ArtifactBuildResult: ...

    async def validate(self, context: ArtifactBuildContext) -> ArtifactValidationResult: ...

    async def retrieve(
        self,
        query: str,
        context: ArtifactBuildContext,
    ) -> list[ArtifactEvidenceCandidate]: ...

    async def resolve_lineage(self, item: dict[str, Any]) -> list[SourceRef]: ...

    async def diff(self, context: ArtifactBuildContext) -> ArtifactDelta: ...
