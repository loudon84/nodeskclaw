"""Live RAGFlow chunk list/page/available PATCH contract (Golden Consumer evidence)."""

from __future__ import annotations

import asyncio
import os
import subprocess
from pathlib import Path

import pytest

from app.services.source_chunk_service import _normalize_chunk

pytestmark = pytest.mark.ragflow_contract

# PRD-NODESKCLAW-KNOWLEDGE-CHUNK-GATEWAY-v1.1 pinned Golden (user-provided; no blind scan)
GOLDEN_IMAGE_DATASET_ID = "956a88c8b26311f1a0c48d3842373341"
GOLDEN_IMAGE_DOCUMENT_ID = "fe656706b41311f1a0c48d3842373341"
_IMAGE_MIME_ALLOWLIST = frozenset({"image/png", "image/jpeg", "image/webp", "image/gif"})
_IMAGE_MAX_BYTES = 20 * 1024 * 1024


def _git_sha() -> str:
    try:
        return (
            subprocess.check_output(
                ["git", "rev-parse", "HEAD"],
                cwd=Path(__file__).resolve().parents[2],
                text=True,
            ).strip()
        )
    except Exception:
        return "unknown"


def _provider_image_token(raw: dict) -> str | None:
    for key in ("image_id", "img_id"):
        value = raw.get(key)
        if value is None:
            continue
        text = str(value).strip()
        if text:
            return text
    return None


@pytest.mark.asyncio
async def test_chunk_contract_list_keywords_total_and_available_toggle():
    if os.environ.get("RAGFLOW_CONTRACT_TEST") != "1":
        pytest.skip("RAGFLOW_CONTRACT_TEST=1 required")

    from app.integrations.ragflow.client import RagflowClient

    client = RagflowClient()
    evidence: dict[str, object] = {
        "nodeskclaw_commit_sha": _git_sha(),
        "ragflow_base_url": os.environ.get("RAGFLOW_BASE_URL", ""),
    }
    try:
        version = await client.get_system_version()
        evidence["ragflow_version"] = version
        assert version, "RAGFlow runtime version required for Golden Consumer"

        dataset_id = os.environ.get("RAGFLOW_CONTRACT_DATASET_ID")
        document_id = os.environ.get("RAGFLOW_CONTRACT_DOCUMENT_ID")
        chunk_id = None
        orig_available = None

        if not dataset_id or not document_id:
            found = False
            for ds in await client.list_datasets(page=1, page_size=30):
                docs = await client.list_documents(ds.id, page=1, page_size=20)
                for doc in docs:
                    page = await client.list_document_chunks_page(
                        ds.id, doc.id, page=1, page_size=10
                    )
                    if page.chunks:
                        dataset_id, document_id = ds.id, doc.id
                        chunk_id = str(page.chunks[0].get("id"))
                        orig_available = page.chunks[0].get("available")
                        evidence["total_sample"] = page.total
                        found = True
                        break
                if found:
                    break
            if not found:
                pytest.skip("no dataset/document with chunks found")
        else:
            page = await client.list_document_chunks_page(
                dataset_id, document_id, page=1, page_size=10
            )
            assert page.total >= 0
            assert isinstance(page.chunks, list)
            assert page.total >= len(page.chunks)
            if not page.chunks:
                pytest.skip("configured document has no chunks")
            chunk_id = str(page.chunks[0].get("id"))
            orig_available = page.chunks[0].get("available")
            evidence["total_sample"] = page.total

        evidence.update(
            {
                "dataset_id": dataset_id,
                "document_id": document_id,
                "chunk_id": chunk_id,
                "pre_available": orig_available,
            }
        )

        page_kw = await client.list_document_chunks_page(
            dataset_id,
            document_id,
            page=1,
            page_size=10,
            keywords="a",
        )
        assert isinstance(page_kw.total, int)
        assert isinstance(page_kw.chunks, list)

        assert isinstance(orig_available, bool), "chunk available must be bool for toggle test"
        target = not orig_available
        await client.set_document_chunk_available(dataset_id, document_id, chunk_id, target)
        after_chunk = None
        for _ in range(6):
            await asyncio.sleep(0.5)
            after = await client.list_document_chunks_page(
                dataset_id, document_id, page=1, page_size=50
            )
            after_chunk = next(
                (c for c in after.chunks if str(c.get("id")) == chunk_id),
                None,
            )
            if after_chunk is not None and after_chunk.get("available") is target:
                break
        assert after_chunk is not None
        assert after_chunk.get("available") is target
        evidence["post_available"] = after_chunk.get("available")

        await client.set_document_chunk_available(
            dataset_id, document_id, chunk_id, orig_available
        )
        restored = None
        for _ in range(6):
            await asyncio.sleep(0.5)
            restored_page = await client.list_document_chunks_page(
                dataset_id, document_id, page=1, page_size=50
            )
            restored = next(
                (c for c in restored_page.chunks if str(c.get("id")) == chunk_id),
                None,
            )
            if restored is not None and restored.get("available") is orig_available:
                break
        assert restored is not None
        assert restored.get("available") is orig_available
        evidence["restored_available"] = restored.get("available")
        evidence["cleanup"] = "ok"
    finally:
        await client.aclose()
        print("EVIDENCE", evidence)


@pytest.mark.asyncio
async def test_chunk_contract_multipage_and_pinned_image_golden():
    if os.environ.get("RAGFLOW_CONTRACT_TEST") != "1":
        pytest.skip("RAGFLOW_CONTRACT_TEST=1 required")

    from app.integrations.ragflow.client import RagflowClient

    client = RagflowClient()
    evidence: dict[str, object] = {
        "nodeskclaw_commit_sha": _git_sha(),
        "acceptance": "A-PAGE-004+A-IMG-002",
        "golden_dataset_id": GOLDEN_IMAGE_DATASET_ID,
        "golden_document_id": GOLDEN_IMAGE_DOCUMENT_ID,
    }
    try:
        version = await client.get_system_version()
        evidence["ragflow_version"] = version
        assert version, "RAGFlow runtime version required for Golden Consumer"

        dataset_id = os.environ.get("RAGFLOW_CONTRACT_IMAGE_DATASET_ID", GOLDEN_IMAGE_DATASET_ID)
        document_id = os.environ.get("RAGFLOW_CONTRACT_IMAGE_DOCUMENT_ID", GOLDEN_IMAGE_DOCUMENT_ID)
        evidence["dataset_id"] = dataset_id
        evidence["document_id"] = document_id

        page1 = await client.list_document_chunks_page(
            dataset_id, document_id, page=1, page_size=10
        )
        assert page1.page == 1
        assert page1.page_size == 10
        evidence["page1_total"] = page1.total
        evidence["page1_count"] = len(page1.chunks)

        if page1.total < 11:
            pytest.fail(
                f"Release Gate BLOCKED: golden document total={page1.total} < 11 "
                "(A-PAGE-004 multi-page requires >=11 matching chunks)"
            )
        assert len(page1.chunks) == 10

        page2 = await client.list_document_chunks_page(
            dataset_id, document_id, page=2, page_size=10
        )
        assert page2.page == 2
        assert page2.page_size == 10
        assert len(page2.chunks) >= 1
        ids1 = {str(c.get("id")) for c in page1.chunks}
        ids2 = {str(c.get("id")) for c in page2.chunks}
        assert ids1.isdisjoint(ids2), "stable data: page1 and page2 chunk ids must not overlap"
        evidence["page2_count"] = len(page2.chunks)

        page_kw = await client.list_document_chunks_page(
            dataset_id, document_id, page=1, page_size=10, keywords="a"
        )
        assert isinstance(page_kw.total, int)
        evidence["filtered_total"] = page_kw.total

        image_chunk = None
        image_token = None
        scan_page = 1
        while scan_page <= max(1, (page1.total + 9) // 10):
            page = await client.list_document_chunks_page(
                dataset_id, document_id, page=scan_page, page_size=10
            )
            for raw in page.chunks:
                token = _provider_image_token(raw)
                if token:
                    image_chunk = raw
                    image_token = token
                    break
            if image_token:
                break
            if not page.chunks:
                break
            scan_page += 1

        if image_chunk is None or image_token is None:
            pytest.fail(
                "Release Gate BLOCKED: pinned golden document has no chunk with "
                "image_id/img_id (A-IMG-002); do not substitute another document"
            )

        public = _normalize_chunk(image_chunk)
        assert public.has_image is True
        dumped = public.model_dump()
        assert "image_id" not in dumped
        assert "img_id" not in dumped
        evidence["image_chunk_id"] = public.id

        by_id = await client.list_document_chunks_page(
            dataset_id, document_id, page=1, page_size=1, id=public.id
        )
        assert by_id.total >= 1
        assert any(str(c.get("id")) == public.id for c in by_id.chunks)

        image = await client.get_document_image(image_token)
        assert image.content_type in _IMAGE_MIME_ALLOWLIST
        assert 0 < len(image.content) <= _IMAGE_MAX_BYTES
        evidence["image_mime"] = image.content_type
        evidence["image_bytes"] = len(image.content)
        evidence["status"] = "PASS"
    finally:
        await client.aclose()
        print("EVIDENCE", evidence)
