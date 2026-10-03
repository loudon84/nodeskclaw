from types import SimpleNamespace
from datetime import datetime, timezone

import pytest

from app.core.exceptions import NotFoundError
from app.models.hermes_skill.hermes_task import TaskStatus
from app.services.remote_agent_provider_service import RemoteAgentRouteError
from app.services.remote_agent_session_proof import derive_session_proof, public_proof_body, selectors_match
from app.services.remote_expert_catalog_service import CATALOG_CAPABILITIES, public_catalog_item
from app.services.hermes_skill.permission_checker import _ROLE_PERMISSIONS


def test_catalog_item_uses_slug_and_hides_runtime_ids():
    expert = SimpleNamespace(
        expert_slug="sales-expert",
        display_name="Sales Expert",
        description="desc",
        category="sales",
        tags=["crm"],
        avatar=None,
        hermes_agent_id="should-not-leak",
        id="pk",
    )
    item = public_catalog_item(expert, ready=False)
    assert item["agent_ref"] == "sales-expert"
    assert item["status"] == "unavailable"
    assert item["capabilities"] == CATALOG_CAPABILITIES
    assert "hermes_agent_id" not in item
    assert "id" not in item
    assert "skillName" not in item


def test_invoke_roles_still_include_member():
    assert "expert:invoke" in _ROLE_PERMISSIONS["member"]
    assert "expert:invoke" not in _ROLE_PERMISSIONS["viewer"]


def _task(**kwargs):
    now = datetime.now(timezone.utc)
    defaults = {
        "id": "run-1",
        "idempotency_key": "acp:11111111-1111-1111-1111-111111111111:1",
        "status": TaskStatus.COMPLETED,
        "catalog_slug": "sales-expert",
        "routing_metadata": {"session_ref": "11111111-1111-1111-1111-111111111111", "agent_ref": "sales-expert"},
        "request_snapshot": {
            "knowledge_refs": ["kb-1"],
            "connector_binding_refs": [],
            "integration_account_refs": [],
        },
        "created_at": now,
        "updated_at": now,
    }
    defaults.update(kwargs)
    return SimpleNamespace(**defaults)


def test_proof_next_seq_and_busy():
    session = "11111111-1111-1111-1111-111111111111"
    proof = derive_session_proof(
        session,
        [
            _task(id="r1", idempotency_key=f"acp:{session}:1", status=TaskStatus.COMPLETED),
            _task(id="r2", idempotency_key=f"acp:{session}:2", status=TaskStatus.RUNNING),
        ],
    )
    body = public_proof_body(proof)
    assert set(body) == {"session_ref", "agent_ref", "status", "last_run_id", "next_turn_seq"}
    assert body["status"] == "busy"
    assert body["last_run_id"] == "r2"
    assert body["next_turn_seq"] == 3
    assert proof.has_acp_turn is True


def test_proof_dual_busy_fails():
    session = "11111111-1111-1111-1111-111111111111"
    with pytest.raises(RemoteAgentRouteError) as exc:
        derive_session_proof(
            session,
            [
                _task(id="r1", status=TaskStatus.RUNNING, idempotency_key=f"acp:{session}:1"),
                _task(id="r2", status=TaskStatus.QUEUED, idempotency_key=f"acp:{session}:2"),
            ],
        )
    assert exc.value.symbol == "REMOTE_AGENT_SESSION_AMBIGUOUS"
    assert exc.value.data["non_terminal_run_ids"] == ["r1", "r2"]


def test_proof_malformed_acp_key_fails():
    session = "11111111-1111-1111-1111-111111111111"
    with pytest.raises(RemoteAgentRouteError) as exc:
        derive_session_proof(session, [_task(idempotency_key=f"acp:{session}:x")])
    assert exc.value.symbol == "REMOTE_AGENT_SESSION_SEQ_AMBIGUOUS"


def test_proof_empty_is_not_found():
    with pytest.raises(RemoteAgentRouteError) as exc:
        derive_session_proof("s", [])
    assert exc.value.http_status == 404


def test_selector_match():
    frozen = {
        "agent_ref": "sales-expert",
        "knowledge_refs": ["a"],
        "connector_binding_refs": [],
        "integration_account_refs": ["acc"],
    }
    assert selectors_match(frozen, frozen)
    assert not selectors_match(frozen, {**frozen, "knowledge_refs": ["b"]})
