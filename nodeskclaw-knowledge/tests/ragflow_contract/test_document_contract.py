"""Live RAGFlow document contract."""

from __future__ import annotations

import os

import pytest

pytestmark = pytest.mark.ragflow_contract


@pytest.mark.asyncio
async def test_document_contract_list_requires_dataset():
    if os.environ.get("RAGFLOW_CONTRACT_TEST") != "1":
        pytest.skip("RAGFLOW_CONTRACT_TEST=1 required")
    dataset_id = os.environ.get("RAGFLOW_CONTRACT_DATASET_ID")
    if not dataset_id:
        pytest.skip("RAGFLOW_CONTRACT_DATASET_ID required")
    from app.integrations.ragflow.client import RagflowClient

    client = RagflowClient()
    try:
        docs = await client.list_documents(dataset_id, page=1, page_size=1)
        assert isinstance(docs, list)
    finally:
        await client.aclose()
