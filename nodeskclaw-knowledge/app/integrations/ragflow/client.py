"""RAGFlow HTTP Adapter."""

from __future__ import annotations

import asyncio
import logging
from typing import Any

import httpx

from app.core.config import settings
from app.integrations.ragflow.exceptions import RagflowError
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
    ) -> Any:
        attempts = 3 if retry else 1
        last_exc: Exception | None = None
        client = await self._ensure_client()
        request_url = path if str(client.base_url) else f"{self.base_url}{path}"
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
                    raise map_ragflow_payload(int(payload.get("code", -1)), str(payload.get("message", "")))
                return payload.get("data") if isinstance(payload, dict) else payload
            except RagflowError:
                raise
            except Exception as exc:
                last_exc = exc
                logger.warning("RAGFlow request failed attempt=%s path=%s err=%s", attempt + 1, path, type(exc).__name__)
                if attempt + 1 < attempts:
                    await asyncio.sleep(0.2 * (2**attempt))
        raise map_transport_error(last_exc or RuntimeError("unknown"))

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
        )
        if isinstance(data, list) and data:
            return str(data[0].get("id"))
        if isinstance(data, dict) and data.get("id"):
            return str(data["id"])
        raise RagflowError("RAGFlow upload_document 返回异常", message_key="errors.knowledge.ragflow_error")

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
    ) -> list[RagflowDocument]:
        params: dict[str, Any] = {"page": page, "page_size": page_size}
        if id:
            params["id"] = id
        if run:
            params["run"] = run
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
        similarity_threshold: float | None = None,
        vector_similarity_weight: float | None = None,
        page: int = 1,
        page_size: int = 30,
        keyword: bool = False,
        highlight: bool = False,
        rerank_id: str | None = None,
        cross_languages: list[str] | None = None,
    ) -> RagflowRetrievalResult:
        body: dict[str, Any] = {
            "question": question,
            "dataset_ids": dataset_ids,
            "top_k": top_k,
            "page": page,
            "page_size": page_size,
            "keyword": keyword,
            "highlight": highlight,
        }
        if document_ids:
            body["document_ids"] = document_ids
        if similarity_threshold is not None:
            body["similarity_threshold"] = similarity_threshold
        if vector_similarity_weight is not None:
            body["vector_similarity_weight"] = vector_similarity_weight
        if rerank_id:
            body["rerank_id"] = rerank_id
        if cross_languages:
            body["cross_languages"] = cross_languages
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
