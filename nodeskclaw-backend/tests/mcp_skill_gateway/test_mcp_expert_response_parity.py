from app.schemas.hermes_skill.runtime_skill_run import StartRuntimeSkillRunRequest
from app.services.hermes_skill.runtime_skill_run_service import RuntimeSkillRunService


def _org_structured():
    request = StartRuntimeSkillRunRequest(
        org_id="org-1",
        user_id="user-1",
        tool_name="hermes_writer__customer-profiling",
        runtime_skill_id="customer-profiling",
        agent_profile="writer",
        hermes_agent_instance_id="binding-1",
        agent_id="inst-1",
        arguments={"prompt": "hello"},
        client_context={"source": "mcp_skill_gateway"},
        output_policy={"artifact_mode": "pull_only"},
        task_source="org_mcp",
        skill_id="customer-profiling",
        entrypoint="mcp_skill_gateway",
    )
    task = type("Task", (), {
        "id": "task-1",
        "task_no": "TASK-1",
        "status": type("S", (), {"value": "queued"})(),
        "event_url": "/api/v1/hermes/tasks/task-1/events",
        "artifact_url": "/api/v1/hermes/tasks/task-1/artifacts",
        "server_artifacts": [],
    })()
    return RuntimeSkillRunService.build_structured_content(
        task=task,
        request=request,
        event_sse_url="/api/v1/hermes/tasks/task-1/events?token=sse_test",
        output_policy={"artifact_mode": "pull_only"},
    )


def _expert_structured():
    request = StartRuntimeSkillRunRequest(
        org_id="org-1",
        user_id="user-1",
        tool_name="hermes_writer__customer-profiling",
        runtime_skill_id="customer-profiling",
        agent_profile="writer",
        hermes_agent_instance_id="binding-1",
        agent_id="inst-1",
        arguments={"prompt": "hello"},
        client_context={"source": "expert_mcp_gateway"},
        output_policy={"artifact_mode": "pull_only"},
        task_source="expert_mcp",
        skill_id="customer-profiling",
        entrypoint="expert_mcp_gateway",
        catalog_kind="expert",
        catalog_slug="call-prep",
        skill_name="customer-profiling",
        invocation_id="log-1",
    )
    task = type("Task", (), {
        "id": "task-1",
        "task_no": "TASK-1",
        "status": type("S", (), {"value": "queued"})(),
        "event_url": "/api/v1/hermes/tasks/task-1/events",
        "artifact_url": "/api/v1/hermes/tasks/task-1/artifacts",
        "server_artifacts": [],
    })()
    return RuntimeSkillRunService.build_structured_content(
        task=task,
        request=request,
        event_sse_url="/api/v1/hermes/tasks/task-1/events?token=sse_test",
        output_policy={"artifact_mode": "pull_only"},
    )


def test_org_and_expert_structured_content_core_fields_match():
    org = _org_structured()
    expert = _expert_structured()

    core_fields = {
        "task_id",
        "task_no",
        "status",
        "execution_mode",
        "event_stream",
        "event_url",
        "artifact_url",
        "result_url",
        "committed",
        "wait_strategy",
    }
    for field in core_fields:
        assert field in org
        assert field in expert

    assert org["entrypoint"] == "mcp_skill_gateway"
    assert expert["entrypoint"] == "expert_mcp_gateway"
    assert expert["invocation_id"] == "log-1"
    assert "invocation_id" not in org


def test_structured_content_has_no_camel_case_runtime_fields():
    expert = _expert_structured()
    forbidden = {"taskId", "taskNo", "eventSseUrl", "artifactUrl", "invocationId"}
    assert forbidden.isdisjoint(set(expert.keys()))
