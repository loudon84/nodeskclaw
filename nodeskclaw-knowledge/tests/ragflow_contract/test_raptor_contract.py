"""Live RAGFlow RAPTOR / summary contract."""

from __future__ import annotations

import os

import pytest

pytestmark = pytest.mark.ragflow_contract


@pytest.mark.asyncio
async def test_raptor_contract_supports_summary_shape():
    if os.environ.get("RAGFLOW_CONTRACT_TEST") != "1":
        pytest.skip("RAGFLOW_CONTRACT_TEST=1 required")
    dataset_id = os.environ.get("RAGFLOW_CONTRACT_DATASET_ID")
    from app.runtime.ragflow import RagflowRuntimeAdapter

    adapter = RagflowRuntimeAdapter()
    try:
        caps = await adapter.probe_capabilities(dataset_id=dataset_id)
        entry = caps.get("supports_summary") or caps.get("include_knowledge_compilation")
        assert entry is not None
        if isinstance(entry, dict):
            assert "build_supported" in entry or "retrieval_supported" in entry
    finally:
        await adapter.aclose()
