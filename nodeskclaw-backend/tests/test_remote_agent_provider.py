from types import SimpleNamespace

import pytest

from app.core.exceptions import NotFoundError
from app.models.hermes_skill.hermes_task import TaskStatus
from app.models.hermes_skill.run_dispatch_outbox import RunDispatchStatus
from app.services.hermes_skill.permission_checker import _ROLE_PERMISSIONS
from app.services.hermes_skill.run_dispatch_outbox_service import RunDispatchOutboxService
from app.services.hermes_skill.task_service import TaskService
from app.services.remote_agent_provider_service import (
    RemoteAgentProviderService,
    RemoteAgentRouteError,
    decide_before_insert,
    parse_create_body,
    public_run_body,
    request_digest,
)
from app.services.hermes_skill.public_attachment_service import PublicAttachmentContractError


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
    assert binding_error.value.symbol == "REMOTE_AGENT_CONTEXT_REJECTED"
    assert binding_error.value.code == 40004

    parsed = parse_create_body({
        "client_request_id": "req-1",
        "agent_ref": "expert",
        "prompt": "hello",
        "connector_binding_refs": [
            "22222222-2222-4222-8222-222222222222",
            "11111111-1111-4111-8111-111111111111",
            "11111111-1111-4111-8111-111111111111",
        ],
    })
    assert parsed.connector_binding_refs == [
        "11111111-1111-4111-8111-111111111111",
        "22222222-2222-4222-8222-222222222222",
    ]

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
        connector_binding_refs=[],
        session_ref="",
    )
    other = request_digest(
        agent_ref="expert",
        prompt="hello",
        knowledge_refs=["a", "b"],
        session_ref="11111111-1111-1111-1111-111111111111",
    )
    binding_order = request_digest(
        agent_ref="expert",
        prompt="hello",
        knowledge_refs=["a", "b"],
        connector_binding_refs=[
            "22222222-2222-4222-8222-222222222222",
            "11111111-1111-4111-8111-111111111111",
        ],
        session_ref="",
    )
    binding_sorted = request_digest(
        agent_ref="expert",
        prompt="hello",
        knowledge_refs=["a", "b"],
        connector_binding_refs=[
            "11111111-1111-4111-8111-111111111111",
            "22222222-2222-4222-8222-222222222222",
        ],
        session_ref="",
    )
    assert left == same
    assert left != other
    assert binding_order == binding_sorted
    assert binding_order != left


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


@pytest.mark.asyncio
async def test_digest_replay_skips_knowledge_proof(monkeypatch):
    digest = request_digest(
        agent_ref="expert",
        prompt="hello",
        knowledge_refs=[],
        session_ref=None,
    )
    existing = SimpleNamespace(routing_metadata={"request_digest": digest})

    class Tasks:
        def __init__(self, db):
            return None

        async def find_idempotent_task(self, *args, **kwargs):
            return existing

    class Boom:
        def __init__(self, db):
            raise AssertionError("later checks must not run on replay")

    monkeypatch.setattr("app.services.remote_agent_provider_service.TaskService", Tasks)
    monkeypatch.setattr("app.services.remote_agent_provider_service.ExpertCatalogService", Boom)
    monkeypatch.setattr("app.services.remote_agent_provider_service.RuntimeSkillRunService", Boom)
    task, replayed = await RemoteAgentProviderService(SimpleNamespace()).create(
        org_id="org",
        user_id="user",
        payload={"client_request_id": "req-1", "agent_ref": "expert", "prompt": "hello"},
    )
    assert replayed is True
    assert task is existing


def test_attachment_refs_are_trimmed_deduped_and_sorted():
    parsed = parse_create_body({
        "client_request_id": "req-1",
        "agent_ref": "expert",
        "prompt": "hello",
        "attachment_refs": [" att_b ", "att_a", "att_b"],
    })
    assert parsed.attachment_refs == ["att_a", "att_b"]
    left = request_digest(
        agent_ref="expert",
        prompt="hello",
        knowledge_refs=[],
        attachment_refs=["att_b", "att_a"],
        session_ref=None,
    )
    right = request_digest(
        agent_ref="expert",
        prompt="hello",
        knowledge_refs=[],
        attachment_refs=["att_a", "att_b", "att_a"],
        session_ref=None,
    )
    assert left == right
    without_session_files = request_digest(
        agent_ref="expert",
        prompt="hello",
        knowledge_refs=[],
        attachment_refs=[],
        session_ref="11111111-1111-4111-8111-111111111111",
    )
    with_session_files = request_digest(
        agent_ref="expert",
        prompt="hello",
        knowledge_refs=[],
        attachment_refs=["att_a"],
        session_ref="11111111-1111-4111-8111-111111111111",
    )
    assert without_session_files != with_session_files
    assert "attachment_refs" not in public_run_body(
        SimpleNamespace(
            id="run-1",
            status=TaskStatus.QUEUED,
            catalog_slug="expert",
            created_at=None,
            updated_at=None,
            routing_metadata={},
            tool_name="remote_agent",
        ),
        include_updated_at=False,
    )


def test_attachment_extra_field_and_bad_format_use_distinct_codes():
    with pytest.raises(RemoteAgentRouteError) as extra:
        parse_create_body({
            "client_request_id": "req-1",
            "agent_ref": "expert",
            "prompt": "hello",
            "file_path": "/tmp/secret",
        })
    assert extra.value.code == 40004
    parsed = parse_create_body({
        "client_request_id": "req-1",
        "agent_ref": "expert",
        "prompt": "hello",
        "session_ref": "11111111-1111-4111-8111-111111111111",
        "attachment_refs": ["not-an-attachment", "att_ok"],
    })
    assert parsed.attachment_refs == ["att_ok", "not-an-attachment"]
    assert parsed.session_ref == "11111111-1111-4111-8111-111111111111"


@pytest.mark.asyncio
async def test_first_sorted_attachment_failure_creates_nothing(monkeypatch):
    seen = []

    async def prove(db, *, org_id, user_id, attachment_ref):
        seen.append(attachment_ref)
        if attachment_ref != "not-an-attachment":
            return SimpleNamespace(attachment_ref=attachment_ref)
        raise PublicAttachmentContractError(
            400,
            "ATTACHMENT_REF_INVALID",
            "errors.run.attachment_ref_invalid",
            "附件引用格式无效",
        )

    class Tasks:
        def __init__(self, db):
            return None

        async def find_idempotent_task(self, *args, **kwargs):
            return None

    class Catalog:
        def __init__(self, db):
            return None

        async def get_by_slug(self, org_id, slug):
            return SimpleNamespace(id="ex-1", published=True, enabled=True, expert_slug=slug, hermes_agent_id="h1")

        async def runtime_ready(self, org_id, expert):
            return True

        async def resolve_agent_profile(self, org_id, expert):
            return "profile"

    class DB:
        def add(self, obj):
            raise AssertionError("failure must not create a task")

    monkeypatch.setattr("app.services.remote_agent_provider_service.TaskService", Tasks)
    monkeypatch.setattr("app.services.remote_agent_provider_service.ExpertCatalogService", Catalog)
    monkeypatch.setattr("app.services.remote_agent_provider_service.prove_org_user_attachment", prove)
    with pytest.raises(RemoteAgentRouteError) as exc:
        await RemoteAgentProviderService(DB()).create(
            org_id="org",
            user_id="user",
            payload={
                "client_request_id": "req-1",
                "agent_ref": "expert",
                "prompt": "hello",
                "knowledge_refs": ["kb-1"],
                "attachment_refs": ["att_ok", "not-an-attachment"],
            },
        )
    assert seen == ["att_ok", "not-an-attachment"]
    assert exc.value.code == 40005
    assert exc.value.symbol == "ATTACHMENT_REF_INVALID"


@pytest.mark.asyncio
async def test_matching_attachment_digest_skips_proof(monkeypatch):
    digest = request_digest(
        agent_ref="expert",
        prompt="hello",
        knowledge_refs=[],
        attachment_refs=["att_a", "att_b"],
        session_ref=None,
    )
    existing = SimpleNamespace(routing_metadata={"request_digest": digest})

    class Tasks:
        def __init__(self, db):
            return None

        async def find_idempotent_task(self, *args, **kwargs):
            return existing

    class Boom:
        def __init__(self, db):
            raise AssertionError("replay must not prove attachments")

    async def prove(*args, **kwargs):
        raise AssertionError("replay must not prove attachments")

    monkeypatch.setattr("app.services.remote_agent_provider_service.TaskService", Tasks)
    monkeypatch.setattr("app.services.remote_agent_provider_service.ExpertCatalogService", Boom)
    monkeypatch.setattr("app.services.remote_agent_provider_service.RuntimeSkillRunService", Boom)
    monkeypatch.setattr("app.services.remote_agent_provider_service.prove_org_user_attachment", prove)
    task, replayed = await RemoteAgentProviderService(SimpleNamespace()).create(
        org_id="org",
        user_id="user",
        payload={
            "client_request_id": "req-1",
            "agent_ref": "expert",
            "prompt": "hello",
            "attachment_refs": ["att_b", "att_a"],
        },
    )
    assert replayed is True
    assert task is existing

