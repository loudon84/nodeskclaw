import json
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from app.models.deploy_record import DeployStatus
from app.models.instance import InstanceStatus
from app.services import deploy_service
from app.services.deploy_service import _DeployContext


class _Result:
    def __init__(self, value):
        self.value = value

    def scalar_one(self):
        return self.value

    def scalar_one_or_none(self):
        return self.value


class _SessionFactory:
    def __init__(self, db):
        self.db = db

    async def __aenter__(self):
        return self.db

    async def __aexit__(self, exc_type, exc, tb):
        return False


class _FakeDb:
    def __init__(self, results):
        self.results = list(results)
        self.commit = AsyncMock()

    async def execute(self, _stmt):
        return _Result(self.results.pop(0))


class _FakeK8s:
    def __init__(self):
        self.core = SimpleNamespace(
            create_namespaced_resource_quota=AsyncMock(),
            create_namespaced_config_map=AsyncMock(),
            create_namespaced_persistent_volume_claim=AsyncMock(),
            create_namespaced_secret=AsyncMock(),
            create_namespaced_service=AsyncMock(),
        )
        self.apps = SimpleNamespace(
            create_namespaced_deployment=AsyncMock(),
            patch_namespaced_deployment=AsyncMock(),
        )
        self.networking = SimpleNamespace(
            create_namespaced_ingress=AsyncMock(),
            delete_namespaced_network_policy=AsyncMock(),
            create_namespaced_network_policy=AsyncMock(),
            patch_namespaced_network_policy=AsyncMock(),
        )
        self.ensure_namespace = AsyncMock()
        self.created = []
        self.applied = []

    async def create_or_skip(self, create_fn, *args, **kwargs):
        assert callable(create_fn)
        self.created.append((create_fn, args, kwargs))

    async def apply(self, create_fn, patch_fn, namespace, name, body):
        assert callable(create_fn)
        assert callable(patch_fn)
        self.applied.append((namespace, name, body))

    async def get_deployment_status(self, namespace, name):
        return {"ready": True, "available_replicas": 1}


def _ctx() -> _DeployContext:
    return _DeployContext(
        record_id="deploy-1",
        instance_id="instance-1",
        cluster_id="cluster-1",
        name="hermes-1",
        namespace="ns-hermes",
        image_version="v1",
        replicas=1,
        cpu_request="100m",
        cpu_limit="500m",
        mem_request="256Mi",
        mem_limit="1Gi",
        storage_class="fast-storage",
        storage_size="20Gi",
        quota_cpu="1",
        quota_mem="1Gi",
        env_vars={"GATEWAY_TOKEN": "token"},
        advanced_config={},
        runtime="hermes",
        pvc_access_mode="ReadWriteMany",
    )


@pytest.mark.asyncio
async def test_execute_rebuild_pipeline_uses_current_k8s_builder_signatures(monkeypatch) -> None:
    fake_k8s = _FakeK8s()
    record = SimpleNamespace(status=DeployStatus.running, message=None, finished_at=None, config_snapshot=None)
    instance = SimpleNamespace(
        status=InstanceStatus.rebuilding,
        available_replicas=0,
    )
    db = _FakeDb([
        record,
        SimpleNamespace(id="cluster-1", ingress_class="nginx"),
        record,
        instance,
    ])

    async def fake_get_config(key, _db):
        values = {
            "registry_username": "user",
            "registry_password": "pass",
            "ingress_base_domain": None,
            "ingress_subdomain_suffix": None,
            "tls_secret_name": None,
            "network_policy_ingress_enabled": "false",
            "network_policy_egress_enabled": "false",
        }
        return values.get(key)

    async def fake_resolve_image_registry(_db, _runtime):
        return "registry.example.com/deskclaw-hermes"

    published: list[dict] = []

    monkeypatch.setattr(deploy_service.asyncio, "sleep", AsyncMock())
    monkeypatch.setattr(deploy_service.event_bus, "publish", lambda _topic, payload: published.append(payload))
    monkeypatch.setattr(
        deploy_service,
        "get_deploy_adapter",
        lambda: SimpleNamespace(
            get_namespace_labels=lambda org_id: {"nodeskclaw.io/org-id": org_id or "org-1"},
            get_tls_secret=lambda tls_secret, has_proxy: tls_secret,
            get_network_policy_org_id=lambda org_id: org_id,
            setup_proxy=AsyncMock(),
        ),
    )

    import app.core.deps as deps
    import app.services.config_service as config_service
    import app.services.registry_service as registry_service
    import app.services.runtime.registries.compute_registry as compute_registry

    monkeypatch.setattr(deps, "async_session_factory", lambda: _SessionFactory(db))
    monkeypatch.setattr(config_service, "get_config", fake_get_config)
    monkeypatch.setattr(registry_service, "resolve_image_registry", fake_resolve_image_registry)
    monkeypatch.setattr(compute_registry, "require_k8s_client", AsyncMock(return_value=fake_k8s))

    await deploy_service.execute_rebuild_pipeline(_ctx())

    fake_k8s.ensure_namespace.assert_awaited_once_with(
        "ns-hermes",
        extra_labels={"nodeskclaw.io/org-id": "org-1"},
    )

    created_by_fn = {call[0]: call[1] for call in fake_k8s.created}
    pvc = created_by_fn[fake_k8s.core.create_namespaced_persistent_volume_claim][1]
    assert pvc.metadata.name == "hermes-1-root-data"
    assert pvc.metadata.namespace == "ns-hermes"
    assert pvc.spec.storage_class_name == "fast-storage"
    assert pvc.spec.resources.requests["storage"] == "20Gi"
    assert pvc.spec.access_modes == ["ReadWriteMany"]

    deployment = fake_k8s.applied[0][2]
    assert fake_k8s.applied[0][:2] == ("ns-hermes", "hermes-1")
    assert deployment.metadata.name == "hermes-1"
    assert deployment.spec.template.spec.image_pull_secrets[0].name == "nodeskclaw-registry"
    assert record.status == DeployStatus.success
    assert json.loads(record.config_snapshot)[deploy_service.PROGRESS_STEP_NAMES_KEY] == deploy_service.REBUILD_STEPS
    assert instance.status == InstanceStatus.running
    assert published
    assert all(item["step_names"] == deploy_service.REBUILD_STEPS for item in published)
