from types import SimpleNamespace

import pytest

from app.core.exceptions import NotFoundError
from app.models.hermes_skill.hermes_task import TaskStatus
from app.models.hermes_skill.run_dispatch_outbox import RunDispatchStatus
from app.services.hermes_skill.permission_checker import _ROLE_PERMISSIONS
from app.services.hermes_skill.run_dispatch_outbox_service import RunDispatchOutboxService
from app.services.hermes_skill.task_service import TaskService
from app.services.remote_agent_provider_service import (
    RemoteAgentRouteError,
    decide_before_insert,
    parse_create_body,
    public_run_body,
    request_digest,
)


def test_expert_invoke_matches_existing_invoke_roles():
    for role in ("admin", "operator", "workspace_manager", "member"):
        assert "expert:invoke" in _ROLE_PERMISSIONS[role]
    assert "expert:invoke" not in _ROLE_PERMISSIONS["viewer"]


def test_parse_create_rejects_prompt_binding_and_context():
    with pytest.raises(RemoteAgentRouteError) as prompt_error:
        parse_create_body({"client_request_id": "req-1", "agent_ref": "expert", "prompt": "  "})
    assert prompt_error.value.symbol == "REMOTE_AGENT_PROMPT_REQUIRED"
    assert prompt_error.value.code == 40001

    with pytest.raises(RemoteAgentRouteError) as binding_error:
        parse_create_body({
            "client_request_id": "req-1",
            "agent_ref": "expert",
            "prompt": "hello",
            "connector_binding_refs": ["binding"],
        })
    assert binding_error.value.symbol == "REMOTE_AGENT_BINDING_UNSUPPORTED"

    with pytest.raises(RemoteAgentRouteError) as context_error:
        parse_create_body({
            "client_request_id": "req-1",
            "agent_ref": "expert",
            "prompt": "hello",
            "execution_context": {"context_version": 1},
        })
    assert context_error.value.symbol == "REMOTE_AGENT_CONTEXT_REJECTED"


def test_request_digest_changes_with_sorted_refs_and_session():
    left = request_digest(
        agent_ref="expert",
        prompt="  hello ",
        knowledge_refs=["b", "a"],
        session_ref=None,
    )
    same = request_digest(
        agent_ref="expert",
        prompt="hello",
        knowledge_refs=["a", "b"],
        session_ref="",
    )
    other = request_digest(
        agent_ref="expert",
        prompt="hello",
        knowledge_refs=["a", "b"],
        session_ref="11111111-1111-1111-1111-111111111111",
    )
    assert left == same
    assert left != other


def test_idempotency_replay_wins_before_session_busy():
    assert decide_before_insert(
        existing_task=True,
        digest_matches=True,
        other_user=False,
        slug_mismatch=False,
        session_busy=True,
    ) == "replay"
    assert decide_before_insert(
        existing_task=True,
        digest_matches=False,
        other_user=False,
        slug_mismatch=False,
        session_busy=True,
    ) == "conflict"
    assert decide_before_insert(
        existing_task=False,
        digest_matches=False,
        other_user=True,
        slug_mismatch=True,
        session_busy=True,
    ) == "forbidden"
    assert decide_before_insert(
        existing_task=False,
        digest_matches=False,
        other_user=False,
        slug_mismatch=True,
        session_busy=True,
    ) == "mismatch"
    assert decide_before_insert(
        existing_task=False,
        digest_matches=False,
        other_user=False,
        slug_mismatch=False,
        session_busy=True,
    ) == "busy"


def test_public_body_hides_tool_name():
    task = SimpleNamespace(
        id="run-1",
        status=TaskStatus.QUEUED,
        catalog_slug="expert",
        created_at=None,
        updated_at=None,
        routing_metadata={"session_ref": "11111111-1111-1111-1111-111111111111", "agent_ref": "expert"},
        tool_name="remote_agent",
    )
    body = public_run_body(task, include_updated_at=True)
    assert body["run_id"] == "run-1"
    assert body["agent_ref"] == "expert"
    assert "tool_name" not in body
    assert body["session_ref"].startswith("11111111")


@pytest.mark.asyncio
async def test_legacy_get_task_hides_remote_agent():
    class FakeDB:
        async def get(self, model, task_id):
            return SimpleNamespace(
                deleted_at=None,
                org_id="org",
                tool_name="remote_agent",
            )

    with pytest.raises(NotFoundError):
        await TaskService(FakeDB()).get_task("run-1", "org")


@pytest.mark.asyncio
async def test_dead_letter_marks_only_remote_agent_task_failed():
    remote_entry = SimpleNamespace(
        status=RunDispatchStatus.DEAD_LETTER.value,
        tool_name="remote_agent",
        run_id="run-1",
        last_error="gateway rejected",
    )
    remote_task = SimpleNamespace(
        tool_name="remote_agent",
        status=TaskStatus.QUEUED,
        error_code=None,
        error_message=None,
    )

    class FakeDB:
        async def get(self, model, task_id):
            return remote_task

    await RunDispatchOutboxService(FakeDB())._fail_remote_agent_task_on_dead_letter(remote_entry)
    assert remote_task.status == TaskStatus.FAILED

    skill_task = SimpleNamespace(tool_name="installed_skill", status=TaskStatus.QUEUED)
    skill_entry = SimpleNamespace(
        status=RunDispatchStatus.DEAD_LETTER.value,
        tool_name="installed_skill",
        run_id="run-2",
        last_error="boom",
    )

    class SkillDB:
        async def get(self, model, task_id):
            return skill_task

    await RunDispatchOutboxService(SkillDB())._fail_remote_agent_task_on_dead_letter(skill_entry)
    assert skill_task.status == TaskStatus.QUEUED
