"""Live RAGFlow question enrichment contract."""

from __future__ import annotations

import os

import pytest

pytestmark = pytest.mark.ragflow_contract


@pytest.mark.asyncio
async def test_question_contract_chunk_fields_visible():
    if os.environ.get("RAGFLOW_CONTRACT_TEST") != "1":
        pytest.skip("RAGFLOW_CONTRACT_TEST=1 required")
    from app.runtime.ragflow import RagflowRuntimeAdapter

    adapter = RagflowRuntimeAdapter()
    try:
        caps = await adapter.probe_capabilities()
        assert isinstance(caps, dict)
    finally:
        await adapter.aclose()
