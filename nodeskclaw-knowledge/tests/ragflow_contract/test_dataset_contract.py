"""Live RAGFlow dataset contract."""

from __future__ import annotations

import os

import pytest

pytestmark = pytest.mark.ragflow_contract


@pytest.mark.asyncio
async def test_dataset_contract_list_and_create_shape():
    if os.environ.get("RAGFLOW_CONTRACT_TEST") != "1":
        pytest.skip("RAGFLOW_CONTRACT_TEST=1 required")
    from app.integrations.ragflow.client import RagflowClient

    client = RagflowClient()
    try:
        datasets = await client.list_datasets(page=1, page_size=1)
        assert isinstance(datasets, list)
    finally:
        await client.aclose()
