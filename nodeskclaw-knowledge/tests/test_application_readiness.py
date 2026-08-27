"""Application readiness and publish gate tests."""

from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest

from app.core.exceptions import ConflictError
from app.models.enums import ApplicationStatus
from app.schemas.principal import KnowledgePrincipal
from app.services import application_readiness_service, knowledge_application_service


def _member() -> KnowledgePrincipal:
    return KnowledgePrincipal(
        user_id="u1",
        member_id="m1",
        org_id="o1",
        member_role="member",
    )


@pytest.mark.asyncio
async def test_publish_application_returns_409_when_not_ready(monkeypatch):
    monkeypatch.setattr(
        "app.services.knowledge_application_service.has_application_permission",
        AsyncMock(return_value=True),
    )
    app = SimpleNamespace(
        id="app1",
        org_id="o1",
        status=ApplicationStatus.draft.value,
    )
    db = AsyncMock()
    with (
        patch(
            "app.services.knowledge_application_service.get_application",
            new=AsyncMock(return_value=app),
        ),
        patch(
            "app.services.application_readiness_service.check",
            new=AsyncMock(
                return_value=application_readiness_service.ReadinessResult(
                    ready=False,
                    blocking=[
                        application_readiness_service.ReadinessIssue(
                            code="runtime_chunk_unavailable",
                            knowledge_base_id="kb1",
                        )
                    ],
                )
            ),
        ),
    ):
        with pytest.raises(ConflictError) as exc:
            await knowledge_application_service.publish_application(db, _member(), "app1")
    assert exc.value.message_key == "errors.knowledge.application_not_ready"
    assert exc.value.details["ready"] is False
    assert exc.value.details["blocking"][0]["code"] == "runtime_chunk_unavailable"


def test_build_execution_slices_shape():
    from app.services.retrieval_trace_service import build_execution_slices

    item = SimpleNamespace(
        knowledge_base_id="kb1",
        dataset_id="ds1",
        status="success",
        latency_ms=12,
        candidate_count=3,
        safe_count=2,
        runtime_mode="semantic",
        access_scope="full",
        fallback_used=False,
        fallback_reason=None,
        error_code=None,
    )
    rows = build_execution_slices([item])
    assert rows[0]["knowledge_base_id"] == "kb1"
    assert rows[0]["runtime_mode"] == "semantic"
    assert rows[0]["params_safe_view"]["dataset_id"] == "ds1"
