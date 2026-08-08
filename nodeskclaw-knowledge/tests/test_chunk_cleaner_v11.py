"""Chunk cleaner v1.1 security drops."""

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.integrations.ragflow.models import RagflowChunk
from app.services.chunk_security_service import ActiveDocumentIdentity, clean_chunks


def _identity(
    document_id: str,
    *,
    source_file_id: str,
    version_id: str,
    active_version_id: str | None,
) -> ActiveDocumentIdentity:
    return ActiveDocumentIdentity(
        source_file_id=source_file_id,
        file_version_id=version_id,
        knowledge_base_id="kb1",
        org_id="o1",
        active_version_id=active_version_id,
    )


@pytest.mark.asyncio
async def test_chunk_cleaner_drops_superseded_unknown_mismatch_unauthorized():
    db = MagicMock()
    ragflow = AsyncMock()
    identity_map = {
        "d_active": _identity("d_active", source_file_id="sf_ok", version_id="v_active", active_version_id="v_active"),
        "d_old": _identity("d_old", source_file_id="sf_ok", version_id="v_old", active_version_id="v_active"),
        "d_mismatch": _identity("d_mismatch", source_file_id="sf_ok", version_id="v_real", active_version_id="v_real"),
    }
    chunks = [
        RagflowChunk(
            id="c_ok",
            content="ok",
            document_id="d_active",
            document_metadata={"nk_source_file_id": "sf_ok", "nk_file_version_id": "v_active"},
        ),
        RagflowChunk(
            id="c_superseded",
            content="old",
            document_id="d_old",
            document_metadata={"nk_source_file_id": "sf_ok", "nk_file_version_id": "v_old"},
        ),
        RagflowChunk(id="c_unknown", content="unknown", document_id="d_missing", document_metadata={}),
        RagflowChunk(
            id="c_mismatch",
            content="mismatch",
            document_id="d_mismatch",
            document_metadata={"nk_source_file_id": "sf_ok", "nk_file_version_id": "v_wrong"},
        ),
        RagflowChunk(
            id="c_denied",
            content="denied",
            document_id="d_active",
            document_metadata={"nk_source_file_id": "sf_deny", "nk_file_version_id": "v_active"},
        ),
    ]

    with patch(
        "app.services.chunk_security_service._build_active_document_map",
        new=AsyncMock(return_value=identity_map),
    ):
        safe, filtered = await clean_chunks(
            db,
            ragflow,
            chunks,
            allowed_source_file_ids={"sf_ok"},
        )

    assert [c.id for c in safe] == ["c_ok"]
    assert filtered == 4
