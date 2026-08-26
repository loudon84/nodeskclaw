"""RAGFlow Runtime Adapter — product↔runtime mapping; HTTP stays on RagflowClient."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.integrations.ragflow.client import RagflowClient
from app.integrations.ragflow.exceptions import RagflowError
from app.models.enums import RuntimeBindingStatus
from app.models.knowledge_base import KnowledgeBase
from app.services import runtime_binding_service

MINIMUM_SUPPORTED_RAGFLOW_VERSION = "0.17.0"
VALIDATED_RAGFLOW_VERSIONS = ["0.17.0", "0.24.0", "0.27.0"]


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

    async def aclose(self) -> None:
        await self.client.aclose()

    async def discover_capabilities(self) -> dict[str, Any]:
        health = await self.check_health()
        return health.capabilities

    async def check_health(self) -> RuntimeHealth:
        reachable = False
        version: str | None = None
        try:
            reachable = await self.client.system_health()
        except Exception:
            reachable = False
        capabilities = {
            "supports_chunk": reachable,
            "supports_auto_questions": False,
            "supports_raptor": False,
            "supports_graph": False,
            "supports_metadata_filter": True,
            "supports_table": False,
            "ragflow_version": version,
        }
        degraded: list[str] = []
        if not reachable:
            degraded.append("ragflow_unreachable")
        chunk_ok = bool(reachable)
        return RuntimeHealth(
            reachable=reachable,
            version=version,
            chunk_retrieval_ok=chunk_ok,
            capabilities=capabilities,
            degraded_reasons=degraded,
        )

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

        dataset_id = await self.client.create_dataset(
            name=name,
            embedding_model=embedding_model,
            chunk_method=chunk_method,
            parser_config=parser_config,
            permission="me",
            description=description,
        )
        health = await self.check_health()
        binding = await runtime_binding_service.upsert_ragflow_dataset_binding(
            db,
            org_id=org_id,
            knowledge_base_id=kb.id,
            resource_id=dataset_id,
            status=RuntimeBindingStatus.ready.value,
            runtime_version=health.version,
            capabilities=health.capabilities,
            runtime_config={
                "embedding_model": embedding_model,
                "chunk_method": chunk_method,
                "parser_config": parser_config,
            },
        )
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
