"""Live RAGFlow retrieval contract."""

from __future__ import annotations

import os

import pytest

pytestmark = pytest.mark.ragflow_contract


@pytest.mark.asyncio
async def test_retrieval_contract_minimal_query():
    if os.environ.get("RAGFLOW_CONTRACT_TEST") != "1":
        pytest.skip("RAGFLOW_CONTRACT_TEST=1 required")
    dataset_id = os.environ.get("RAGFLOW_CONTRACT_DATASET_ID")
    if not dataset_id:
        pytest.skip("RAGFLOW_CONTRACT_DATASET_ID required")
    from app.integrations.ragflow.client import RagflowClient

    client = RagflowClient()
    try:
        result = await client.retrieve(
            question="contract probe",
            dataset_ids=[dataset_id],
            top_k=1,
        )
        assert result is not None
    finally:
        await client.aclose()
