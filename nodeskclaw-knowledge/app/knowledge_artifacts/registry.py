"""Artifact Provider registry."""

from __future__ import annotations

from app.knowledge_artifacts.base import KnowledgeArtifactProvider

_PROVIDERS: dict[str, KnowledgeArtifactProvider] = {}


def register_provider(provider: KnowledgeArtifactProvider) -> None:
    _PROVIDERS[provider.artifact_type] = provider


def get_provider(artifact_type: str) -> KnowledgeArtifactProvider | None:
    return _PROVIDERS.get(artifact_type)


def list_providers() -> list[KnowledgeArtifactProvider]:
    return list(_PROVIDERS.values())


def ensure_default_providers() -> None:
    if _PROVIDERS:
        return
    from app.knowledge_artifacts.outline import OutlineArtifactProvider
    from app.knowledge_artifacts.ragflow_compilation import RagflowCompilationArtifactProvider
    from app.knowledge_artifacts.table import TableArtifactProvider

    register_provider(RagflowCompilationArtifactProvider())
    register_provider(OutlineArtifactProvider())
    register_provider(TableArtifactProvider())
