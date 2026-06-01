from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from app.core.exceptions import BadRequestError
from app.models.deploy_record import DeployStatus
from app.models.instance import Instance, InstanceStatus
from app.services import deploy_service, instance_service
from app.services.deploy_service import _DeployContext
from app.startup import deletion_reconcile


class _Result:
    def __init__(self, value):
        self.value = value

    def scalar_one_or_none(self):
        return self.value

    def scalar_one(self):
        return self.value

    def scalar(self):
        return self.value

    def all(self):
        return self.value if isinstance(self.value, list) else []


class _FakeDb:
    def __init__(self, results):
        self.results = list(results)
        self.updated_tables: list[str] = []
        self.commit = AsyncMock()

    async def execute(self, stmt):
        if getattr(stmt, "is_update", False):
            self.updated_tables.append(stmt.table.name)
            return _Result(None)
        return _Result(self.results.pop(0))


class _SessionContext:
    def __init__(self, db):
        self.db = db

    async def __aenter__(self):
        return self.db

    async def __aexit__(self, exc_type, exc, tb):
        return False


def _make_instance(status=InstanceStatus.running, compute_provider="k8s") -> Instance:
    return Instance(
        id="instance-1",
        name="demo",
        slug="demo",
        cluster_id="cluster-1",
        namespace="ns-demo",
        image_version="v1",
        replicas=1,
        cpu_request="100m",
        cpu_limit="500m",
        mem_request="256Mi",
        mem_limit="1Gi",
        service_type="ClusterIP",
        storage_size="1Gi",
        quota_cpu="1",
        quota_mem="1Gi",
        compute_provider=compute_provider,
        runtime="openclaw",
        status=status,
        created_by="user-1",
        org_id="org-1",
    )


def _make_cluster(proxy_endpoint: str | None = None):
    return SimpleNamespace(
        id="cluster-1",
        is_k8s=True,
        credentials_encrypted="kubeconfig",
        proxy_endpoint=proxy_endpoint,
    )


def _make_context() -> _DeployContext:
    return _DeployContext(
        record_id="deploy-1",
        instance_id="instance-1",
        cluster_id="cluster-1",
        name="demo",
        namespace="ns-demo",
        image_version="v1",
        replicas=1,
        cpu_request="100m",
        cpu_limit="500m",
        mem_request="256Mi",
        mem_limit="1Gi",
        storage_class=None,
        storage_size="1Gi",
        quota_cpu="1",
        quota_mem="1Gi",
        env_vars={},
        advanced_config={},
    )


@pytest.mark.asyncio
async def test_delete_instance_rejects_delete_k8s_false():
    with pytest.raises(BadRequestError) as exc_info:
        await instance_service.delete_instance("instance-1", _FakeDb([]), delete_k8s=False)

    assert exc_info.value.status_code == 400
    assert exc_info.value.error_code == 40000
    assert exc_info.value.message_key == "errors.instance.delete_k8s_required"


@pytest.mark.asyncio
async def test_finalizer_keeps_instance_deleting_when_namespace_cleanup_fails(monkeypatch):
    instance = _make_instance(status=InstanceStatus.running)
    db = _FakeDb([instance, _make_cluster()])

    async def fail_get_k8s_client(_cluster):
        raise RuntimeError("k8s unavailable")

    monkeypatch.setattr(
        instance_service,
        "_get_k8s_client_for_cluster",
        fail_get_k8s_client,
    )

    done = await instance_service.finalize_instance_deletion_once(instance.id, db)

    assert done is False
    assert instance.status == InstanceStatus.deleting
    assert instance.deleted_at is None
    assert db.updated_tables == []


@pytest.mark.asyncio
async def test_finalizer_soft_deletes_records_after_k8s_and_proxy_are_absent(monkeypatch):
    instance = _make_instance(status=InstanceStatus.deleting)
    cluster = _make_cluster(proxy_endpoint="https://gateway.example.com")
    db = _FakeDb([instance, cluster, []])
    k8s = SimpleNamespace(name="workload")
    gateway_k8s = SimpleNamespace(name="gateway")
    namespace_calls: list[tuple[object, str]] = []
    proxy_calls: list[tuple[object, str]] = []

    async def get_k8s_client(_cluster):
        return k8s

    async def get_gateway_k8s_client():
        return gateway_k8s

    async def namespace_absent(client, namespace):
        namespace_calls.append((client, namespace))
        return True

    async def proxy_absent(client, proxy_name):
        proxy_calls.append((client, proxy_name))
        return True

    def close_background_coro(coro):
        coro.close()
        return None

    monkeypatch.setattr(instance_service, "_get_k8s_client_for_cluster", get_k8s_client)
    monkeypatch.setattr(instance_service, "_get_gateway_k8s_client", get_gateway_k8s_client)
    monkeypatch.setattr(
        instance_service,
        "_delete_namespace_and_check_absent",
        namespace_absent,
    )
    monkeypatch.setattr(
        instance_service,
        "_delete_proxy_ingress_and_check_absent",
        proxy_absent,
    )
    monkeypatch.setattr(instance_service, "_fire_task", close_background_coro)

    done = await instance_service.finalize_instance_deletion_once(instance.id, db)

    assert done is True
    assert instance.deleted_at is not None
    assert namespace_calls == [(k8s, "ns-demo")]
    assert proxy_calls == [(gateway_k8s, "proxy-demo")]
    assert db.updated_tables == [
        "deploy_records",
        "instance_backups",
        "instance_members",
    ]


@pytest.mark.asyncio
async def test_resume_deleting_instances_reschedules_finalizer(monkeypatch):
    db = _FakeDb([[("instance-1", "demo"), ("instance-2", "demo-2")]])
    scheduled: list[str] = []

    monkeypatch.setattr(
        deletion_reconcile,
        "schedule_instance_deletion_finalizer",
        scheduled.append,
    )

    count = await deletion_reconcile.resume_deleting_instances(
        lambda: _SessionContext(db),
    )

    assert count == 2
    assert scheduled == ["instance-1", "instance-2"]


@pytest.mark.asyncio
async def test_mark_deploy_failed_uses_finalizer_without_soft_delete(monkeypatch):
    import app.core.deps as deps

    record = SimpleNamespace(
        status=DeployStatus.running,
        message=None,
        finished_at=None,
    )
    instance = _make_instance(status=InstanceStatus.deploying)
    db = _FakeDb([record, instance])
    scheduled: list[str] = []

    monkeypatch.setattr(deps, "async_session_factory", lambda: _SessionContext(db))
    monkeypatch.setattr(
        instance_service,
        "schedule_instance_deletion_finalizer",
        scheduled.append,
    )

    await deploy_service._mark_deploy_failed(_make_context(), "boom")

    assert record.status == DeployStatus.failed
    assert record.message == "boom"
    assert record.finished_at is not None
    assert instance.status == InstanceStatus.deleting
    assert instance.deleted_at is None
    assert db.updated_tables == []
    assert scheduled == ["instance-1"]


@pytest.mark.asyncio
async def test_cancel_deploy_uses_finalizer_without_soft_delete(monkeypatch):
    import app.core.deps as deps

    record = SimpleNamespace(
        id="deploy-1",
        instance_id="instance-1",
        status=DeployStatus.running,
        message=None,
        finished_at=None,
    )
    instance = _make_instance(status=InstanceStatus.deploying)
    db = _FakeDb([record, instance])
    scheduled: list[str] = []
    events: list[tuple] = []

    monkeypatch.setattr(deps, "async_session_factory", lambda: _SessionContext(db))
    monkeypatch.setattr(deploy_service, "_running_tasks", {})
    monkeypatch.setattr(
        instance_service,
        "schedule_instance_deletion_finalizer",
        scheduled.append,
    )
    monkeypatch.setattr(deploy_service.event_bus, "publish", lambda *args: events.append(args))

    result = await deploy_service.cancel_deploy("deploy-1")

    assert result == "已取消，资源清理已开始"
    assert record.status == DeployStatus.failed
    assert record.message == "用户手动取消部署"
    assert record.finished_at is not None
    assert instance.status == InstanceStatus.deleting
    assert instance.deleted_at is None
    assert db.updated_tables == []
    assert scheduled == ["instance-1"]
    assert events
