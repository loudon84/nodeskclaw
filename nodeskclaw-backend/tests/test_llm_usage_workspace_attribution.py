from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from uuid import uuid4

import pytest
from sqlalchemy import text

from app.api import organizations, workspaces
from app.models.cluster import Cluster
from app.models.instance import Instance
from app.models.llm_usage_log import LlmUsageLog
from app.models.organization import Organization
from app.models.user import User
from app.models.workspace import Workspace
from app.models.workspace_agent import WorkspaceAgent
from app.models.workspace_task import WorkspaceTask
from tests.conftest import TestSessionLocal


async def _session_or_skip():
    db = TestSessionLocal()
    try:
        result = await db.execute(text("SELECT 1"))
        result.close()
        await db.rollback()
        return db
    except Exception as exc:
        await db.close()
        pytest.skip(f"test database unavailable: {exc}")


async def _seed_case(db):
    suffix = uuid4().hex[:12]
    org = Organization(id=f"org-{suffix}", name="Org", slug=f"org-{suffix}")
    user = User(id=f"user-{suffix}", name="User", username=f"user-{suffix}", current_org_id=org.id)
    cluster = Cluster(id=f"cluster-{suffix}", name=f"cluster-{suffix}", created_by=user.id, org_id=org.id)
    instance = Instance(
        id=f"inst-{suffix}",
        name="Agent",
        slug=f"agent-{suffix}",
        cluster_id=cluster.id,
        namespace=f"ns-{suffix}",
        image_version="test",
        created_by=user.id,
        org_id=org.id,
        wp_api_key=f"wp-{suffix}",
    )
    ws_a = Workspace(id=f"wsa-{suffix}", org_id=org.id, name="A", created_by=user.id)
    ws_b = Workspace(id=f"wsb-{suffix}", org_id=org.id, name="B", created_by=user.id)
    for model in (org, user, cluster, instance, ws_a, ws_b):
        db.add(model)
        await db.flush()

    db.add_all([
        WorkspaceAgent(workspace_id=ws_a.id, instance_id=instance.id),
        WorkspaceAgent(workspace_id=ws_b.id, instance_id=instance.id),
        LlmUsageLog(
            user_id=user.id,
            instance_id=instance.id,
            workspace_id=ws_a.id,
            attribution_source="session_key",
            provider="openai",
            model="gpt-test",
            prompt_tokens=40,
            completion_tokens=60,
            total_tokens=100,
            org_id=org.id,
        ),
        LlmUsageLog(
            user_id=user.id,
            instance_id=instance.id,
            workspace_id=None,
            attribution_source="unattributed",
            provider="openai",
            model="gpt-test",
            prompt_tokens=400,
            completion_tokens=600,
            total_tokens=1000,
            org_id=org.id,
        ),
    ])
    await db.commit()
    return SimpleNamespace(org=org, user=user, instance=instance, ws_a=ws_a, ws_b=ws_b)


@pytest.mark.asyncio
async def test_workspace_token_usage_uses_event_workspace(monkeypatch):
    async def allow_member(*_args, **_kwargs):
        return None

    monkeypatch.setattr(workspaces.wm_service, "check_workspace_member", allow_member)
    async with await _session_or_skip() as db:
        case = await _seed_case(db)

        usage_a = await workspaces.get_workspace_token_usage(case.ws_a.id, db=db, user=case.user)
        usage_b = await workspaces.get_workspace_token_usage(case.ws_b.id, db=db, user=case.user)

        assert usage_a["data"]["total_tokens"] == 100
        assert usage_b["data"]["total_tokens"] == 0


@pytest.mark.asyncio
async def test_org_akr_summary_does_not_duplicate_multi_workspace_instance():
    async with await _session_or_skip() as db:
        case = await _seed_case(db)

        response = await organizations.org_akr_summary(case.org.id, db=db, _org_ctx=object())
        totals = {
            item["workspace_id"]: item["total_tokens"]
            for item in response.data["workspaces"]
        }

        assert totals[case.ws_a.id] == 100
        assert totals[case.ws_b.id] == 0


@pytest.mark.asyncio
async def test_attribute_tokens_stays_within_workspace(monkeypatch):
    async def allow_access(*_args, **_kwargs):
        return None

    monkeypatch.setattr(workspaces.wm_service, "check_workspace_access", allow_access)
    async with await _session_or_skip() as db:
        case = await _seed_case(db)
        now = datetime.now(timezone.utc)
        task = WorkspaceTask(
            workspace_id=case.ws_b.id,
            title="Task B",
            status="done",
            assignee_instance_id=case.instance.id,
            created_at=now - timedelta(hours=1),
            completed_at=now + timedelta(hours=1),
        )
        db.add(task)
        await db.commit()

        result = await workspaces.attribute_tokens_to_tasks(case.ws_b.id, db=db, user=case.user)
        await db.refresh(task)

        assert result["data"]["updated_tasks"] == 0
        assert task.token_cost is None
