"""RAGFlow Runtime Adapter — product↔runtime mapping; HTTP stays on RagflowClient."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.integrations.ragflow.client import RagflowClient
from app.integrations.ragflow.exceptions import RagflowError
from app.integrations.ragflow.models import RagflowRetrievalResult
from app.models.enums import RuntimeBindingStatus
from app.models.knowledge_base import KnowledgeBase
from app.runtime import capabilities as runtime_capabilities
from app.runtime.ragflow_contract import RagflowCompatibilityProfile, probe_compatibility_profile
from app.services import runtime_binding_service

MINIMUM_SUPPORTED_RAGFLOW_VERSION = runtime_capabilities.MINIMUM_SUPPORTED_RAGFLOW_VERSION


@dataclass
class RuntimeBindingResult:
    resource_id: str
    status: str
    capabilities: dict[str, Any] = field(default_factory=dict)
    runtime_version: str | None = None


@dataclass
class RuntimeHealth:
    reachable: bool
    version: str | None = None
    chunk_retrieval_ok: bool = False
    capabilities: dict[str, Any] = field(default_factory=dict)
    degraded_reasons: list[str] = field(default_factory=list)


class RagflowRuntimeAdapter:
    runtime_type = "ragflow"

    def __init__(self, client: RagflowClient | None = None):
        self.client = client or RagflowClient()
        self._last_probe_snapshot: dict[str, Any] | None = None
        self._last_probe_version: str | None = None
        self._last_probe_reachable: bool = False
        self._last_compat_profile: RagflowCompatibilityProfile | None = None

    async def aclose(self) -> None:
        await self.client.aclose()

    async def get_runtime_version(self) -> str | None:
        return await runtime_capabilities.probe_runtime_version(self.client)

    async def probe_capabilities(
        self,
        *,
        dataset_id: str | None = None,
        document_id: str | None = None,
    ) -> dict[str, Any]:
        profile = await probe_compatibility_profile(
            self.client,
            dataset_id=dataset_id,
            document_id=document_id,
        )
        caps = runtime_capabilities.capabilities_from_profile(profile)
        self._last_probe_reachable = profile.reachable
        self._last_probe_version = profile.runtime_version
        self._last_probe_snapshot = caps
        self._last_compat_profile = profile
        return caps

    async def discover_capabilities(self) -> dict[str, Any]:
        return await self.probe_capabilities()

    async def check_health(self) -> RuntimeHealth:
        caps = await self.probe_capabilities()
        reachable = self._last_probe_reachable
        version = self._last_probe_version
        degraded: list[str] = []
        if not reachable:
            degraded.append("ragflow_unreachable")
        chunk_entry = caps.get("supports_chunk")
        chunk_ok = reachable and _capability_enabled(chunk_entry)
        return RuntimeHealth(
            reachable=reachable,
            version=version,
            chunk_retrieval_ok=chunk_ok,
            capabilities=caps,
            degraded_reasons=degraded,
        )

    def get_probe_snapshot(self) -> tuple[dict[str, Any] | None, str | None]:
        return self._last_probe_snapshot, self._last_probe_version

    def get_compat_profile(self) -> RagflowCompatibilityProfile | None:
        return self._last_compat_profile

    async def get_dataset_runtime_config(self, dataset_id: str) -> dict[str, Any] | None:
        return await self.client.get_dataset(dataset_id)

    async def configure_index(
        self,
        dataset_id: str,
        *,
        parser_config: dict[str, Any],
    ) -> dict[str, Any] | None:
        return await self.client.update_dataset_parser_config(dataset_id, parser_config=parser_config)

    async def trigger_index_build(self, dataset_id: str, document_ids: list[str] | None = None) -> None:
        if document_ids:
            await self.client.parse_documents(dataset_id, document_ids)
            return
        docs = await self.client.list_documents(dataset_id, page=1, page_size=1)
        if docs:
            await self.client.parse_documents(dataset_id, [docs[0].id])

    async def get_index_build_status(self, dataset_id: str, document_id: str) -> dict[str, Any] | None:
        docs = await self.client.list_documents(dataset_id, id=document_id, page=1, page_size=1)
        if not docs:
            return None
        doc = docs[0]
        return {
            "document_id": doc.id,
            "run": doc.run,
            "progress": doc.progress,
            "chunk_count": doc.chunk_count,
        }

    async def feature_retrieve(
        self,
        *,
        dataset_ids: list[str],
        question: str,
        document_ids: list[str] | None = None,
        top_k: int = 8,
        knn_top_k: int | None = None,
        knn_num_candidates: int | None = None,
        rerank_candidates_count: int | None = None,
        use_kg: bool | None = None,
        toc_enhance: bool | None = None,
        include_knowledge_compilation: bool | None = None,
        metadata_condition: dict[str, Any] | None = None,
    ) -> RagflowRetrievalResult:
        return await self.client.retrieve(
            question=question,
            dataset_ids=dataset_ids,
            document_ids=document_ids,
            top_k=top_k,
            knn_top_k=knn_top_k,
            knn_num_candidates=knn_num_candidates,
            rerank_candidates_count=rerank_candidates_count,
            use_kg=use_kg,
            toc_enhance=toc_enhance,
            include_knowledge_compilation=include_knowledge_compilation,
            metadata_condition=metadata_condition,
        )

    async def search_dataset(
        self,
        dataset_id: str,
        *,
        question: str,
        top_k: int = 8,
        document_ids: list[str] | None = None,
    ) -> dict[str, Any]:
        return await self.client.search_dataset(
            dataset_id,
            question=question,
            top_k=top_k,
            document_ids=document_ids,
        )

    async def get_dataset_graph(self, dataset_id: str) -> dict[str, Any]:
        return await self.client.get_dataset_graph(dataset_id)

    async def read_document_chunks(
        self,
        dataset_id: str,
        document_id: str,
        *,
        page: int = 1,
        page_size: int = 30,
    ) -> list[dict[str, Any]]:
        return await self.client.list_document_chunks(
            dataset_id,
            document_id,
            page=page,
            page_size=page_size,
        )

    async def retrieve_index(
        self,
        *,
        dataset_ids: list[str],
        question: str,
        top_k: int = 8,
        document_ids: list[str] | None = None,
    ):
        return await self.feature_retrieve(
            dataset_ids=dataset_ids,
            question=question,
            top_k=top_k,
            document_ids=document_ids,
        )

    async def validate_index_retrieval(
        self,
        *,
        dataset_id: str,
        question: str = "health check",
    ) -> bool:
        try:
            result = await self.retrieve_index(dataset_ids=[dataset_id], question=question, top_k=1)
            return result is not None
        except Exception:
            return False

    async def provision_binding(
        self,
        db: AsyncSession,
        *,
        kb: KnowledgeBase,
        embedding_model: str,
        chunk_method: str,
        parser_config: dict | None,
        description: str | None,
        name: str,
        org_id: str,
    ) -> RuntimeBindingResult:
        if not settings.KNOWLEDGE_V2_RUNTIME_BINDING_ENABLED:
            dataset_id = await self.client.create_dataset(
                name=name,
                embedding_model=embedding_model,
                chunk_method=chunk_method,
                parser_config=parser_config,
                permission="me",
                description=description,
            )
            kb.ragflow_dataset_id = dataset_id
            return RuntimeBindingResult(resource_id=dataset_id, status=RuntimeBindingStatus.ready.value)

        dataset_id = await runtime_binding_service.create_dataset_idempotent(
            db,
            self,
            kb=kb,
            org_id=org_id,
            embedding_model=embedding_model,
            chunk_method=chunk_method,
            parser_config=parser_config,
            description=description,
        )
        probe_result = await runtime_binding_service.probe_and_persist_binding_capabilities(
            db,
            knowledge_base_id=kb.id,
            adapter=self,
        )
        binding = await runtime_binding_service.upsert_ragflow_dataset_binding(
            db,
            org_id=org_id,
            knowledge_base_id=kb.id,
            resource_id=dataset_id,
            status=RuntimeBindingStatus.ready.value,
            runtime_version=probe_result.runtime_version,
            capabilities=probe_result.capabilities,
            runtime_config={
                "embedding_model": embedding_model,
                "chunk_method": chunk_method,
                "parser_config": parser_config,
            },
            from_probe=True,
        )
        await runtime_binding_service.compile_and_persist_desired_config(db, kb, binding, compat_profile=probe_result.capabilities)
        await runtime_binding_service.mirror_dataset_id_to_kb(db, kb, dataset_id)
        return RuntimeBindingResult(
            resource_id=binding.resource_id,
            status=binding.status,
            capabilities=binding.capabilities or {},
            runtime_version=binding.runtime_version,
        )

    async def delete_binding(self, db: AsyncSession, kb: KnowledgeBase) -> None:
        dataset_id = await runtime_binding_service.get_dataset_id(db, kb)
        if not dataset_id:
            return
        try:
            await self.client.delete_dataset(dataset_id)
        except RagflowError:
            raise
        binding = await runtime_binding_service.get_binding(db, kb.id)
        if binding is not None:
            binding.status = RuntimeBindingStatus.deleting.value
            binding.soft_delete()


def _capability_enabled(cap_value: Any) -> bool:
    if isinstance(cap_value, dict):
        return bool(cap_value.get("build_supported") or cap_value.get("retrieval_supported"))
    return bool(cap_value)
