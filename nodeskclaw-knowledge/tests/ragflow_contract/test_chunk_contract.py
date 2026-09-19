"""Live RAGFlow chunk list/page/available PATCH contract (Golden Consumer evidence)."""

from __future__ import annotations

import asyncio
import os
import subprocess
from pathlib import Path

import pytest

pytestmark = pytest.mark.ragflow_contract


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
        await asyncio.sleep(0.5)
        after = await client.list_document_chunks_page(
            dataset_id, document_id, page=1, page_size=50
        )
        after_chunk = next(c for c in after.chunks if str(c.get("id")) == chunk_id)
        assert after_chunk.get("available") is target
        evidence["post_available"] = after_chunk.get("available")

        await client.set_document_chunk_available(
            dataset_id, document_id, chunk_id, orig_available
        )
        await asyncio.sleep(0.5)
        restored_page = await client.list_document_chunks_page(
            dataset_id, document_id, page=1, page_size=50
        )
        restored = next(c for c in restored_page.chunks if str(c.get("id")) == chunk_id)
        assert restored.get("available") is orig_available
        evidence["restored_available"] = restored.get("available")
        evidence["cleanup"] = "ok"
    finally:
        await client.aclose()
        print("EVIDENCE", evidence)
