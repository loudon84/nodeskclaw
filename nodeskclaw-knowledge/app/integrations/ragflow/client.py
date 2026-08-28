"""RAGFlow HTTP Adapter."""

from __future__ import annotations

import asyncio
import logging
from typing import Any

import httpx

from app.core.config import settings
from app.integrations.ragflow.exceptions import RagflowError, RagflowUploadUnknownError
from app.integrations.ragflow.mapper import map_ragflow_payload, map_transport_error
from app.integrations.ragflow.models import (
    RagflowChunk,
    RagflowDataset,
    RagflowDocument,
    RagflowRetrievalResult,
)

logger = logging.getLogger(__name__)


# @lat: [[knowledge#Isolation From Ragflow]]
class RagflowClient:
    def __init__(
        self,
        base_url: str | None = None,
        api_key: str | None = None,
        timeout: float | None = None,
        upload_timeout: float | None = None,
        http_client: httpx.AsyncClient | None = None,
    ):
        self.base_url = (base_url or settings.RAGFLOW_BASE_URL).rstrip("/")
        self.api_key = api_key if api_key is not None else settings.RAGFLOW_API_KEY
        self.timeout = timeout if timeout is not None else settings.RAGFLOW_TIMEOUT_SECONDS
        self.upload_timeout = (
            upload_timeout if upload_timeout is not None else settings.RAGFLOW_UPLOAD_TIMEOUT_SECONDS
        )
        self._http_client = http_client
        self._owns_client = http_client is None

    def _headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self.api_key}"}

    async def aclose(self) -> None:
        if self._owns_client and self._http_client is not None:
            await self._http_client.aclose()
            self._http_client = None

    async def _ensure_client(self) -> httpx.AsyncClient:
        if self._http_client is None:
            self._http_client = httpx.AsyncClient(
                base_url=self.base_url,
                timeout=self.timeout,
                headers=self._headers(),
            )
            self._owns_client = True
        return self._http_client

    async def _request(
        self,
        method: str,
        path: str,
        *,
        json: dict | None = None,
        params: dict | None = None,
        files: Any = None,
        data: Any = None,
        retry: bool = False,
        timeout: float | None = None,
        upload: bool = False,
        upload_token: str | None = None,
    ) -> Any:
        import time

        import httpx

        from app.services import metrics_service

        attempts = 3 if retry else 1
        last_exc: Exception | None = None
        client = await self._ensure_client()
        request_url = path if str(client.base_url) else f"{self.base_url}{path}"
        started = time.perf_counter()
        for attempt in range(attempts):
            try:
                resp = await client.request(
                    method,
                    request_url,
                    headers=self._headers(),
                    json=json,
                    params=params,
                    files=files,
                    data=data,
                    timeout=timeout or self.timeout,
                )
                payload = resp.json() if resp.content else {"code": resp.status_code, "message": resp.text}
                if isinstance(payload, dict) and payload.get("code", 0) != 0:
                    metrics_service.observe_ragflow_request(
                        method=method,
                        path=path,
                        status="error",
                        duration_seconds=time.perf_counter() - started,
                    )
                    raise map_ragflow_payload(int(payload.get("code", -1)), str(payload.get("message", "")))
                metrics_service.observe_ragflow_request(
                    method=method,
                    path=path,
                    status="ok",
                    duration_seconds=time.perf_counter() - started,
                )
                return payload.get("data") if isinstance(payload, dict) else payload
            except RagflowError:
                raise
            except (httpx.TimeoutException, TimeoutError) as exc:
                last_exc = exc
                if upload:
                    metrics_service.observe_ragflow_request(
                        method=method,
                        path=path,
                        status="unknown",
                        duration_seconds=time.perf_counter() - started,
                    )
                    raise map_transport_error(exc, upload=True, upload_token=upload_token) from exc
                logger.warning("RAGFlow request failed attempt=%s path=%s err=%s", attempt + 1, path, type(exc).__name__)
                if attempt + 1 < attempts:
                    await asyncio.sleep(0.2 * (2**attempt))
            except Exception as exc:
                last_exc = exc
                logger.warning("RAGFlow request failed attempt=%s path=%s err=%s", attempt + 1, path, type(exc).__name__)
                if attempt + 1 < attempts:
                    await asyncio.sleep(0.2 * (2**attempt))
        metrics_service.observe_ragflow_request(
            method=method,
            path=path,
            status="error",
            duration_seconds=time.perf_counter() - started,
        )
        raise map_transport_error(last_exc or RuntimeError("unknown"), upload=upload, upload_token=upload_token)

    async def create_dataset(
        self,
        name: str,
        embedding_model: str,
        chunk_method: str = "naive",
        parser_config: dict | None = None,
        permission: str = "me",
        description: str | None = None,
    ) -> str:
        body: dict[str, Any] = {
            "name": name,
            "embedding_model": embedding_model,
            "chunk_method": chunk_method,
            "permission": permission,
        }
        if parser_config is not None:
            body["parser_config"] = parser_config
        if description:
            body["description"] = description
        data = await self._request("POST", "/api/v1/datasets", json=body)
        if isinstance(data, dict):
            return str(data.get("id"))
        raise RagflowError("RAGFlow create_dataset 返回异常", message_key="errors.knowledge.ragflow_error")

    async def update_dataset(self, dataset_id: str, **fields: Any) -> None:
        await self._request("PUT", f"/api/v1/datasets/{dataset_id}", json=fields, retry=True)

    async def delete_dataset(self, dataset_id: str) -> None:
        await self._request("DELETE", "/api/v1/datasets", json={"ids": [dataset_id]}, retry=True)

    async def list_datasets(self, page: int = 1, page_size: int = 30) -> list[RagflowDataset]:
        data = await self._request(
            "GET",
            "/api/v1/datasets",
            params={"page": page, "page_size": page_size},
            retry=True,
        )
        items = data if isinstance(data, list) else (data or {}).get("data") or []
        return [RagflowDataset.model_validate(item) for item in items]

    async def upload_document(
        self,
        dataset_id: str,
        file_bytes: bytes | None = None,
        filename: str = "file",
        mime: str | None = None,
        *,
        file_obj: Any = None,
        upload_token: str | None = None,
    ) -> str:
        if file_obj is not None:
            files = {"file": (filename, file_obj, mime or "application/octet-stream")}
        else:
            files = {"file": (filename, file_bytes or b"", mime or "application/octet-stream")}
        data = await self._request(
            "POST",
            f"/api/v1/datasets/{dataset_id}/documents",
            files=files,
            timeout=self.upload_timeout,
            upload=True,
            upload_token=upload_token,
        )
        if isinstance(data, list) and data:
            return str(data[0].get("id"))
        if isinstance(data, dict) and data.get("id"):
            return str(data["id"])
        raise RagflowError("RAGFlow upload_document 返回异常", message_key="errors.knowledge.ragflow_error")

    async def find_documents_by_upload_token(
        self,
        dataset_id: str,
        upload_token: str,
        *,
        page_size: int = 100,
        max_pages: int = 20,
    ) -> list[RagflowDocument]:
        """List documents whose name contains the deterministic upload token (never blind re-POST)."""
        if not upload_token:
            return []
        matches: list[RagflowDocument] = []
        for page in range(1, max_pages + 1):
            docs = await self.list_documents(
                dataset_id,
                page=page,
                page_size=page_size,
                keywords=upload_token,
            )
            for doc in docs:
                if upload_token in (doc.name or ""):
                    matches.append(doc)
            if len(docs) < page_size:
                break
            if not docs and page > 1:
                break
        if matches:
            return matches
        # Fallback: scan without keywords filter when API ignores keywords
        for page in range(1, max_pages + 1):
            docs = await self.list_documents(dataset_id, page=page, page_size=page_size)
            for doc in docs:
                if upload_token in (doc.name or ""):
                    matches.append(doc)
            if len(docs) < page_size:
                break
        return matches

    async def recover_uploaded_document(
        self,
        dataset_id: str,
        upload_token: str,
    ) -> str | None:
        docs = await self.find_documents_by_upload_token(dataset_id, upload_token)
        if not docs:
            return None
        docs_sorted = sorted(docs, key=lambda d: d.id)
        return docs_sorted[0].id

    async def update_document(self, dataset_id: str, document_id: str, **fields: Any) -> None:
        await self._request(
            "PUT",
            f"/api/v1/datasets/{dataset_id}/documents/{document_id}",
            json=fields,
            retry=True,
        )

    async def update_document_metadata(self, dataset_id: str, document_id: str, meta_fields: dict[str, Any]) -> None:
        await self.update_document(dataset_id, document_id, meta_fields=meta_fields)

    async def set_document_enabled(self, dataset_id: str, document_id: str, enabled: bool) -> None:
        await self.update_document(dataset_id, document_id, enabled=1 if enabled else 0)

    async def delete_documents(self, dataset_id: str, document_ids: list[str]) -> None:
        await self._request(
            "DELETE",
            f"/api/v1/datasets/{dataset_id}/documents",
            json={"ids": document_ids},
            retry=True,
        )

    async def download_document(self, dataset_id: str, document_id: str) -> bytes:
        path = f"/api/v1/datasets/{dataset_id}/documents/{document_id}"
        try:
            client = await self._ensure_client()
            resp = await client.get(path, headers=self._headers(), timeout=self.timeout)
            if resp.status_code >= 400:
                raise RagflowError(
                    "RAGFlow 下载失败",
                    message_key="errors.knowledge.ragflow_error",
                )
            return resp.content
        except RagflowError:
            raise
        except Exception as exc:
            raise map_transport_error(exc) from exc

    async def list_documents(
        self,
        dataset_id: str,
        *,
        id: str | None = None,
        page: int = 1,
        page_size: int = 100,
        run: str | None = None,
        keywords: str | None = None,
        name: str | None = None,
    ) -> list[RagflowDocument]:
        params: dict[str, Any] = {"page": page, "page_size": page_size}
        if id:
            params["id"] = id
        if run:
            params["run"] = run
        if keywords:
            params["keywords"] = keywords
        if name:
            params["name"] = name
        data = await self._request(
            "GET",
            f"/api/v1/datasets/{dataset_id}/documents",
            params=params,
            retry=True,
        )
        items = data if isinstance(data, list) else (data or {}).get("docs") or (data or {}).get("data") or []
        return [RagflowDocument.model_validate(item) for item in items]

    async def parse_documents(self, dataset_id: str, document_ids: list[str]) -> None:
        await self._request(
            "POST",
            f"/api/v1/datasets/{dataset_id}/chunks",
            json={"document_ids": document_ids},
        )

    async def stop_parsing(self, dataset_id: str, document_ids: list[str]) -> None:
        await self._request(
            "DELETE",
            f"/api/v1/datasets/{dataset_id}/chunks",
            json={"document_ids": document_ids},
            retry=True,
        )

    async def retrieve(
        self,
        *,
        question: str,
        dataset_ids: list[str],
        document_ids: list[str] | None = None,
        top_k: int = 20,
        knn_top_k: int | None = None,
        knn_num_candidates: int | None = None,
        rerank_candidates_count: int | None = None,
        use_kg: bool | None = None,
        toc_enhance: bool | None = None,
        include_knowledge_compilation: bool | None = None,
        similarity_threshold: float | None = None,
        vector_similarity_weight: float | None = None,
        page: int = 1,
        page_size: int = 30,
        keyword: bool = False,
        highlight: bool = False,
        rerank_id: str | None = None,
        cross_languages: list[str] | None = None,
        metadata_condition: dict[str, Any] | None = None,
    ) -> RagflowRetrievalResult:
        effective_knn_top_k = knn_top_k if knn_top_k is not None else top_k
        body: dict[str, Any] = {
            "question": question,
            "dataset_ids": dataset_ids,
            "top_k": top_k,
            "knn_top_k": effective_knn_top_k,
            "page": page,
            "page_size": page_size,
            "keyword": keyword,
            "highlight": highlight,
        }
        if document_ids:
            body["document_ids"] = document_ids
        if knn_num_candidates is not None:
            body["knn_num_candidates"] = knn_num_candidates
        if rerank_candidates_count is not None:
            body["rerank_candidates_count"] = rerank_candidates_count
        if use_kg is not None:
            body["use_kg"] = use_kg
        if toc_enhance is not None:
            body["toc_enhance"] = toc_enhance
        if include_knowledge_compilation is not None:
            body["include_knowledge_compilation"] = include_knowledge_compilation
        if similarity_threshold is not None:
            body["similarity_threshold"] = similarity_threshold
        if vector_similarity_weight is not None:
            body["vector_similarity_weight"] = vector_similarity_weight
        if rerank_id:
            body["rerank_id"] = rerank_id
        if cross_languages:
            body["cross_languages"] = cross_languages
        if metadata_condition:
            body["metadata_condition"] = metadata_condition
        data = await self._request("POST", "/api/v1/retrieval", json=body)
        chunks_raw = (data or {}).get("chunks") or []
        chunks: list[RagflowChunk] = []
        for item in chunks_raw:
            meta = item.get("document_metadata") or item.get("meta_fields") or {}
            chunks.append(
                RagflowChunk(
                    id=str(item.get("id", "")),
                    content=str(item.get("content", "")),
                    document_id=str(item.get("document_id", "")),
                    dataset_id=item.get("dataset_id") or item.get("kb_id"),
                    similarity=float(item.get("similarity") or 0),
                    document_keyword=item.get("document_keyword") or item.get("document_name"),
                    document_name=item.get("document_name") or item.get("document_keyword"),
                    document_metadata=meta if isinstance(meta, dict) else {},
                    kb_id=item.get("kb_id"),
                    positions=item.get("positions"),
                    term_similarity=item.get("term_similarity"),
                    vector_similarity=item.get("vector_similarity"),
                    highlight=item.get("highlight"),
                )
            )
        return RagflowRetrievalResult(chunks=chunks, total=int((data or {}).get("total") or len(chunks)))

    async def system_health(self) -> bool:
        try:
            client = await self._ensure_client()
            resp = await client.get("/v1/system/healthz", headers=self._headers(), timeout=5.0)
            if resp.status_code < 400:
                return True
            resp2 = await client.get("/api/v1/system/healthz", headers=self._headers(), timeout=5.0)
            return resp2.status_code < 400
        except Exception:
            return False

    async def get_system_version(self) -> str | None:
        for path in ("/api/v1/system/version", "/v1/system/version"):
            try:
                client = await self._ensure_client()
                resp = await client.get(path, headers=self._headers(), timeout=5.0)
                if resp.status_code >= 400:
                    continue
                payload = resp.json() if resp.content else {}
                if isinstance(payload, dict):
                    data = payload.get("data") if payload.get("code", 0) == 0 else payload
                    if isinstance(data, dict):
                        for key in ("version", "ragflow_version", "release"):
                            value = data.get(key)
                            if value:
                                return str(value)
                    elif data:
                        return str(data)
            except Exception:
                continue
        return None

    async def get_dataset(self, dataset_id: str) -> dict[str, Any] | None:
        data = await self._request("GET", f"/api/v1/datasets/{dataset_id}")
        return data if isinstance(data, dict) else None

    async def update_dataset_parser_config(
        self,
        dataset_id: str,
        *,
        parser_config: dict[str, Any],
    ) -> dict[str, Any] | None:
        data = await self._request(
            "PUT",
            f"/api/v1/datasets/{dataset_id}",
            json={"parser_config": parser_config},
        )
        return data if isinstance(data, dict) else None

    async def search_dataset(
        self,
        dataset_id: str,
        *,
        question: str,
        top_k: int = 1,
        document_ids: list[str] | None = None,
    ) -> dict[str, Any]:
        body: dict[str, Any] = {"question": question, "top_k": top_k}
        if document_ids:
            body["document_ids"] = document_ids
        data = await self._request(
            "POST",
            f"/api/v1/datasets/{dataset_id}/search",
            json=body,
        )
        return data if isinstance(data, dict) else {"data": data}

    async def get_dataset_graph(self, dataset_id: str) -> dict[str, Any]:
        data = await self._request("GET", f"/api/v1/datasets/{dataset_id}/graph")
        return data if isinstance(data, dict) else {"data": data}

    async def list_dataset_artifacts(self, dataset_id: str) -> list[dict[str, Any]]:
        data = await self._request("GET", f"/api/v1/datasets/{dataset_id}/artifacts")
        if isinstance(data, list):
            return [item for item in data if isinstance(item, dict)]
        if isinstance(data, dict):
            items = data.get("artifacts") or data.get("data") or []
            return [item for item in items if isinstance(item, dict)] if isinstance(items, list) else []
        return []

    async def get_dataset_artifact_topics(
        self,
        dataset_id: str,
        **params: Any,
    ) -> dict[str, Any]:
        data = await self._request(
            "GET",
            f"/api/v1/datasets/{dataset_id}/artifacts/topics",
            params=params or None,
        )
        return data if isinstance(data, dict) else {"data": data}

    async def get_dataset_artifact_graph(
        self,
        dataset_id: str,
        **params: Any,
    ) -> dict[str, Any]:
        data = await self._request(
            "GET",
            f"/api/v1/datasets/{dataset_id}/artifacts/graph",
            params=params or None,
        )
        return data if isinstance(data, dict) else {"data": data}

    async def get_dataset_artifact_structure(
        self,
        dataset_id: str,
        **params: Any,
    ) -> dict[str, Any]:
        data = await self._request(
            "GET",
            f"/api/v1/datasets/{dataset_id}/artifacts/structure",
            params=params or None,
        )
        return data if isinstance(data, dict) else {"data": data}

    async def get_dataset_artifact_alteration(
        self,
        dataset_id: str,
        **params: Any,
    ) -> dict[str, Any]:
        data = await self._request(
            "GET",
            f"/api/v1/datasets/{dataset_id}/artifacts/alteration",
            params=params or None,
        )
        return data if isinstance(data, dict) else {"data": data}

    async def list_document_chunks(
        self,
        dataset_id: str,
        document_id: str,
        *,
        page: int = 1,
        page_size: int = 30,
    ) -> list[dict[str, Any]]:
        data = await self._request(
            "GET",
            f"/api/v1/datasets/{dataset_id}/documents/{document_id}/chunks",
            params={"page": page, "page_size": page_size},
        )
        if isinstance(data, list):
            return data
        if isinstance(data, dict):
            items = data.get("chunks") or data.get("data") or []
            return items if isinstance(items, list) else []
        return []

    async def probe_retrieval_endpoint(self) -> bool:
        try:
            await self._request(
                "POST",
                "/api/v1/retrieval",
                json={"question": "probe", "dataset_ids": [], "top_k": 1, "page": 1, "page_size": 1},
            )
            return True
        except RagflowError as exc:
            message = str(exc).lower()
            if "dataset" in message or "empty" in message or "required" in message:
                return True
            return False
        except Exception:
            return False

    async def probe_dataset_search(self, dataset_id: str) -> bool:
        try:
            await self.search_dataset(dataset_id, question="probe", top_k=1)
            return True
        except RagflowError:
            return False
        except Exception:
            return False

    async def probe_dataset_graph(self, dataset_id: str) -> bool:
        try:
            data = await self.get_dataset_graph(dataset_id)
            return isinstance(data, dict)
        except RagflowError:
            return False
        except Exception:
            return False

    async def probe_document_chunks(self, dataset_id: str, document_id: str) -> dict[str, Any]:
        result = {
            "chunk_retrieval": False,
            "question_fields_visible": False,
            "knowledge_compilation": False,
            "raptor_source_lineage": False,
        }
        try:
            chunks = await self.list_document_chunks(dataset_id, document_id, page=1, page_size=5)
        except Exception:
            return result
        if not chunks:
            return result
        result["chunk_retrieval"] = True
        for item in chunks:
            if not isinstance(item, dict):
                continue
            questions = item.get("questions") or item.get("question_kwd")
            if questions:
                result["question_fields_visible"] = True
            if item.get("important_kwd") or item.get("raptor") or item.get("compiled"):
                result["knowledge_compilation"] = True
            meta = item.get("document_metadata") or item.get("meta_fields") or {}
            if isinstance(meta, dict) and (meta.get("source_chunk_ids") or meta.get("nk_source_chunk_ids")):
                result["raptor_source_lineage"] = True
        return result

    @staticmethod
    def _feature_probe_state(
        *,
        transport: bool = False,
        supported: bool = False,
        operational: bool = False,
        artifact_present: bool = False,
    ) -> dict[str, bool]:
        return {
            "transport": transport,
            "supported": supported,
            "operational": operational,
            "artifact_present": artifact_present,
        }

    @staticmethod
    def _unsupported_param_error(message: str) -> bool:
        lowered = message.lower()
        return any(token in lowered for token in ("unsupported", "unknown parameter", "invalid parameter", "invalid field"))

    async def probe_retrieval_features(self, dataset_id: str) -> dict[str, dict[str, bool]]:
        feature_names = (
            "kg_retrieval",
            "toc_enhance",
            "metadata_filter",
            "knn_top_k",
            "knn_num_candidates",
            "rerank_candidates_count",
            "knowledge_compilation",
        )
        features: dict[str, dict[str, bool]] = {
            name: self._feature_probe_state() for name in feature_names
        }
        probes = [
            ("kg_retrieval", {"use_kg": True}, False),
            ("toc_enhance", {"toc_enhance": True}, False),
            ("knowledge_compilation", {"include_knowledge_compilation": True}, True),
            ("knn_top_k", {"knn_top_k": 1}, False),
            ("knn_num_candidates", {"knn_num_candidates": 1}, False),
            ("rerank_candidates_count", {"rerank_candidates_count": 1}, False),
            (
                "metadata_filter",
                {
                    "metadata_condition": {
                        "logic": "and",
                        "conditions": [{"name": "nk_probe", "comparison_operator": "is", "value": "probe"}],
                    }
                },
                False,
            ),
        ]
        for name, extra, marks_artifact in probes:
            try:
                await self.retrieve(
                    question="probe",
                    dataset_ids=[dataset_id],
                    top_k=1,
                    page=1,
                    page_size=1,
                    **extra,
                )
                features[name] = self._feature_probe_state(
                    transport=True,
                    supported=True,
                    operational=True,
                    artifact_present=marks_artifact,
                )
            except RagflowError as exc:
                message = str(exc)
                if self._unsupported_param_error(message):
                    features[name] = self._feature_probe_state(transport=True, supported=False, operational=False)
                else:
                    features[name] = self._feature_probe_state(
                        transport=True,
                        supported=False,
                        operational=False,
                    )
            except Exception:
                features[name] = self._feature_probe_state()
        return features
