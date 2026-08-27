"""Live RAGFlow graph contract."""

from __future__ import annotations

import os

import pytest

pytestmark = pytest.mark.ragflow_contract


@pytest.mark.asyncio
async def test_graph_contract_dataset_graph_endpoint():
    if os.environ.get("RAGFLOW_CONTRACT_TEST") != "1":
        pytest.skip("RAGFLOW_CONTRACT_TEST=1 required")
    dataset_id = os.environ.get("RAGFLOW_CONTRACT_DATASET_ID")
    if not dataset_id:
        pytest.skip("RAGFLOW_CONTRACT_DATASET_ID required")
    from app.runtime.ragflow import RagflowRuntimeAdapter

    adapter = RagflowRuntimeAdapter()
    try:
        graph = await adapter.get_dataset_graph(dataset_id)
        assert graph is not None
    finally:
        await adapter.aclose()
