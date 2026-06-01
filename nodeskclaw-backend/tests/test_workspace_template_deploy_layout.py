from types import SimpleNamespace
from uuid import uuid4

import pytest
from sqlalchemy import func, select

from app.api import templates as templates_api
from app.models.cluster import Cluster
from app.models.organization import Organization
from app.models.user import User
from app.models.workspace import Workspace
from app.models.workspace_deploy import WorkspaceDeploy
from app.models.workspace_template import WorkspaceTemplate
from app.services import workspace_template_deploy_service
from app.services.workspace_template_deploy_service import (
    _build_agent_specs_with_layout,
    _filter_topology_by_exclusions,
    _mark_agent_add_workspace_failed,
    _run_deploy_pipeline_inner,
    _workspace_deploy_final_counts,
    prepare_template_deploy_layout,
    start_workspace_template_deploy,
)
from tests.conftest import TestSessionLocal


def _template(agent_specs: list[dict], *, topology: dict | None = None, humans: list[dict] | None = None):
    return WorkspaceTemplate(
        id=f"template-layout-{uuid4().hex[:8]}",
        name="Layout Template",
        description="",
        org_id="org-layout",
        visibility="org_private",
        created_by="user-layout",
        topology_snapshot=topology or {"nodes": [], "edges": []},
        blackboard_snapshot={},
        gene_assignments=[],
        agent_specs=agent_specs,
        human_specs=humans or [],
    )


def test_layout_check_reports_missing_position():
    result = prepare_template_deploy_layout(
        _template([{"display_name": "A", "runtime": "openclaw", "compute_provider": "k8s"}])
    )

    assert result["can_deploy"] is False
    assert result["issues"][0]["code"] == "missing_position"
    assert result["agent_positions"] == []


def test_layout_check_reports_blackboard_conflict():
    result = prepare_template_deploy_layout(
        _template([{"display_name": "A", "hex_q": 0, "hex_r": 0}])
    )

    assert result["can_deploy"] is False
    assert result["issues"][0]["code"] == "blackboard_conflict"


def test_layout_check_reports_duplicate_agent_position():
    result = prepare_template_deploy_layout(
        _template([
            {"display_name": "A", "hex_q": 1, "hex_r": 0},
            {"display_name": "B", "hex_q": 1, "hex_r": 0},
        ])
    )

    assert result["can_deploy"] is False
    assert any(issue["code"] == "duplicate_position" for issue in result["issues"])


def test_layout_check_accepts_override_to_empty_hex():
    result = prepare_template_deploy_layout(
        _template([{"display_name": "A"}]),
        agent_positions=[{"agent_index": 0, "hex_q": 2, "hex_r": -1}],
    )

    assert result["can_deploy"] is True
    assert result["agent_positions"] == [{"agent_index": 0, "hex_q": 2, "hex_r": -1}]


def test_deploy_layout_requires_explicit_confirmed_positions():
    result = prepare_template_deploy_layout(
        _template([{"display_name": "A", "hex_q": 1, "hex_r": 0}]),
        require_explicit_agent_positions=True,
    )

    assert result["can_deploy"] is False
    assert result["issues"][0]["code"] == "missing_position"


@pytest.mark.asyncio
async def test_layout_check_endpoint_requires_explicit_positions(monkeypatch):
    template = _template([{"display_name": "A", "hex_q": 1, "hex_r": 0}])

    async def fake_get_template_with_access(template_id, org_id, db):
        assert template_id == template.id
        assert org_id == template.org_id
        assert db is not None
        return template

    monkeypatch.setattr(templates_api, "_get_template_with_access", fake_get_template_with_access)

    response = await templates_api.check_template_deploy_layout(
        template.id,
        templates_api.TemplateDeployLayoutCheckRequest(),
        org_ctx=(None, SimpleNamespace(id=template.org_id)),
        db=SimpleNamespace(),
    )

    assert response["data"]["can_deploy"] is False
    assert response["data"]["issues"][0]["code"] == "missing_position"


@pytest.mark.asyncio
async def test_layout_check_endpoint_accepts_confirmed_positions(monkeypatch):
    template = _template([{"display_name": "A", "hex_q": 1, "hex_r": 0}])

    async def fake_get_template_with_access(*_args):
        return template

    monkeypatch.setattr(templates_api, "_get_template_with_access", fake_get_template_with_access)

    response = await templates_api.check_template_deploy_layout(
        template.id,
        templates_api.TemplateDeployLayoutCheckRequest(
            agent_positions=[{"agent_index": 0, "hex_q": 2, "hex_r": -1}],
        ),
        org_ctx=(None, SimpleNamespace(id=template.org_id)),
        db=SimpleNamespace(),
    )

    assert response["data"]["can_deploy"] is True
    assert response["data"]["agent_positions"] == [{"agent_index": 0, "hex_q": 2, "hex_r": -1}]


def test_layout_rewrites_topology_edges_after_agent_move():
    template = _template(
        [{"display_name": "A", "hex_q": 1, "hex_r": 0}],
        topology={
            "nodes": [{"node_type": "corridor", "hex_q": 2, "hex_r": 0}],
            "edges": [{"a_q": 1, "a_r": 0, "b_q": 2, "b_r": 0, "direction": "both"}],
        },
    )
    layout = prepare_template_deploy_layout(
        template,
        agent_positions=[{"agent_index": 0, "hex_q": 3, "hex_r": -1}],
    )
    agent_specs, rewrites = _build_agent_specs_with_layout(
        list(template.agent_specs or []),
        layout["selected_agent_indices"],
        layout["agent_positions"],
    )
    topology = _filter_topology_by_exclusions(
        template.topology_snapshot,
        list(template.agent_specs or []),
        layout["selected_agent_indices"],
        layout["excluded_corridor_coords"],
        rewrites,
    )

    assert agent_specs[0]["hex_q"] == 3
    assert topology["edges"][0]["a_q"] == 3
    assert topology["edges"][0]["a_r"] == -1


def test_add_workspace_failure_counts_as_failed_agent():
    agents_progress = [
        {
            "display_name": "A",
            "instance_id": "instance-a",
            "status": "success",
            "step": "deploy",
            "error": None,
            "retry_count": 0,
        }
    ]

    _mark_agent_add_workspace_failed(agents_progress, 0, "加入办公室失败")
    success_n, fail_n, final_status = _workspace_deploy_final_counts(1, set())

    assert agents_progress[0]["status"] == "add_workspace_failed"
    assert agents_progress[0]["step"] == "add_workspace"
    assert agents_progress[0]["error"] == "加入办公室失败"
    assert success_n == 0
    assert fail_n == 1
    assert final_status == "partial_success"


@pytest.mark.asyncio
async def test_deploy_rejects_invalid_layout_before_creating_resources():
    suffix = uuid4().hex[:8]
    org = Organization(id=f"org-layout-{suffix}", name="Layout Org", slug=f"layout-org-{suffix}")
    user = User(
        id=f"user-layout-{suffix}",
        name="Layout User",
        email=f"layout-{suffix}@example.com",
        username=f"layout-{suffix}",
        password_hash="x",
        current_org_id=org.id,
    )
    cluster = Cluster(
        id=f"cluster-layout-{suffix}",
        name=f"Cluster {suffix}",
        compute_provider="k8s",
        created_by=user.id,
        org_id=org.id,
    )
    template = WorkspaceTemplate(
        id=f"template-layout-{suffix}",
        name="Layout Template",
        description="",
        org_id=org.id,
        visibility="org_private",
        created_by=user.id,
        topology_snapshot={"nodes": [], "edges": []},
        blackboard_snapshot={},
        gene_assignments=[],
        agent_specs=[{"display_name": "A", "runtime": "openclaw", "compute_provider": "k8s"}],
        human_specs=[],
    )

    try:
        async with TestSessionLocal() as db:
            db.add_all([org, user, cluster, template])
            await db.commit()

            with pytest.raises(ValueError, match="模板部署布局未通过校验"):
                await start_workspace_template_deploy(
                    db,
                    template=template,
                    workspace_name="Layout Workspace",
                    cluster_id=cluster.id,
                    user=user,
                    org_id=org.id,
                )

            workspace_count = (
                await db.execute(select(func.count()).select_from(Workspace))
            ).scalar_one()
            deploy_count = (
                await db.execute(select(func.count()).select_from(WorkspaceDeploy))
            ).scalar_one()
    except Exception:
        pytest.skip("test database unavailable")

    assert workspace_count == 0
    assert deploy_count == 0


@pytest.mark.asyncio
async def test_template_deploy_marks_add_workspace_failure_as_partial(monkeypatch):
    suffix = uuid4().hex[:8]
    org = Organization(id=f"org-add-{suffix}", name="Add Org", slug=f"add-org-{suffix}")
    user = User(
        id=f"user-add-{suffix}",
        name="Add User",
        email=f"add-{suffix}@example.com",
        username=f"add-{suffix}",
        password_hash="x",
        current_org_id=org.id,
    )
    cluster = Cluster(
        id=f"cluster-add-{suffix}",
        name=f"Cluster {suffix}",
        compute_provider="k8s",
        created_by=user.id,
        org_id=org.id,
    )
    template = WorkspaceTemplate(
        id=f"template-add-{suffix}",
        name="Add Template",
        description="",
        org_id=org.id,
        visibility="org_private",
        created_by=user.id,
        topology_snapshot={"nodes": [], "edges": []},
        blackboard_snapshot={},
        gene_assignments=[],
        agent_specs=[
            {
                "display_name": "A",
                "runtime": "openclaw",
                "compute_provider": "k8s",
                "hex_q": 1,
                "hex_r": 0,
            }
        ],
        human_specs=[],
    )
    workspace = Workspace(
        id=f"workspace-add-{suffix}",
        org_id=org.id,
        name="Add Workspace",
        description="",
        created_by=user.id,
        cluster_id=cluster.id,
    )
    workspace_deploy = WorkspaceDeploy(
        id=f"deploy-add-{suffix}",
        workspace_id=workspace.id,
        template_id=template.id,
        status="pending",
        total_agents=1,
        completed_agents=0,
        failed_agents=0,
        progress_detail={
            "agents": [
                {
                    "display_name": "A",
                    "instance_id": None,
                    "status": "pending",
                    "step": None,
                    "error": None,
                    "retry_count": 0,
                }
            ],
            "current_phase": "pending",
            "phases_completed": [],
        },
        config_snapshot={
            "cluster_id": cluster.id,
            "selected_agent_indices": [0],
            "excluded_corridor_coords": [],
            "agent_positions": [{"agent_index": 0, "hex_q": 1, "hex_r": 0}],
        },
        created_by=user.id,
        org_id=org.id,
    )

    try:
        async with TestSessionLocal() as db:
            db.add_all([org, user, cluster, template, workspace, workspace_deploy])
            await db.commit()
    except Exception:
        pytest.skip("test database unavailable")

    async def fake_deploy_instance(_req, _deploy_user, _db, *, org_id):
        assert org_id == org.id
        return f"deploy-record-{suffix}", SimpleNamespace(instance_id=f"instance-{suffix}")

    async def fake_execute_deploy_pipeline(_ctx):
        return None

    async def fake_wait_deploy_finished(_deploy_id):
        return True, "部署成功"

    async def fake_resolve_image_version(_db, _runtime):
        return "test-version"

    async def fake_add_agent(*_args, **_kwargs):
        raise ValueError("加入办公室失败")

    events: list[tuple[str, dict]] = []

    def fake_publish(_deploy_id, event, data):
        events.append((event, data))

    monkeypatch.setattr(workspace_template_deploy_service, "async_session_factory", TestSessionLocal)
    monkeypatch.setattr(workspace_template_deploy_service.deploy_service, "deploy_instance", fake_deploy_instance)
    monkeypatch.setattr(
        workspace_template_deploy_service.deploy_service,
        "execute_deploy_pipeline",
        fake_execute_deploy_pipeline,
    )
    monkeypatch.setattr(
        workspace_template_deploy_service.deploy_service,
        "register_deploy_task",
        lambda *_args, **_kwargs: None,
    )
    monkeypatch.setattr(
        workspace_template_deploy_service,
        "_wait_deploy_finished",
        fake_wait_deploy_finished,
    )
    monkeypatch.setattr(
        workspace_template_deploy_service,
        "_resolve_image_version",
        fake_resolve_image_version,
    )
    monkeypatch.setattr(workspace_template_deploy_service.workspace_service, "add_agent", fake_add_agent)
    monkeypatch.setattr(workspace_template_deploy_service, "_publish", fake_publish)

    await _run_deploy_pipeline_inner(workspace_deploy.id)

    async with TestSessionLocal() as db:
        refreshed = await db.get(WorkspaceDeploy, workspace_deploy.id)

    assert refreshed.status == "partial_success"
    assert refreshed.completed_agents == 0
    assert refreshed.failed_agents == 1
    assert refreshed.progress_detail["agents"][0]["status"] == "add_workspace_failed"
    assert refreshed.progress_detail["agents"][0]["error"] == "加入办公室失败"
    assert events[-1] == (
        "complete",
        {"status": "partial_success", "success_count": 0, "failed_count": 1},
    )
