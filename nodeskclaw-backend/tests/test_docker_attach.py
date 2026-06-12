import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.core.exceptions import BadRequestError, ConflictError, NotFoundError
from app.models.cluster import ClusterStatus
from app.models.instance import Instance, InstanceStatus
from app.schemas.docker_attach import AttachExistingInstanceRequest
from app.services import docker_attach_service, instance_service
from app.services.hermes_expert.expert_filesystem import get_hermes_host_data_dir


def _inspect_payload(status: str = "running") -> dict:
    return {
        "Name": "/hermes-writer",
        "State": {"Status": status, "Health": {"Status": "healthy"}},
        "Config": {"Image": "hermes-agent-webui:latest", "Labels": {}},
        "NetworkSettings": {
            "Ports": {"8787/tcp": [{"HostIp": "0.0.0.0", "HostPort": "8787"}]},
        },
        "Mounts": [{
            "Destination": "/data/hermes",
            "Source": "/opt/nodeskclaw/instances/writer/data/hermes",
        }],
        "Created": "2026-01-01T00:00:00.000000000Z",
    }


def _attach_request(**overrides) -> AttachExistingInstanceRequest:
    payload = {
        "cluster_id": "cluster-1",
        "runtime": "hermes-webui-expert",
        "name": "写作专家",
        "slug": "writer",
        "profile": "writer",
        "container_name": "hermes-writer",
        "host_port": 8787,
        "image": "hermes-agent-webui:latest",
        "data_dir": "/opt/nodeskclaw/instances/writer",
        "compose_path": "/opt/nodeskclaw/instances/writer/docker-compose.yml",
    }
    payload.update(overrides)
    return AttachExistingInstanceRequest(**payload)


def _make_docker_instance(status=InstanceStatus.deleting) -> Instance:
    advanced = {
        "attach_mode": "external",
        "external_lifecycle": False,
        "external_container_name": "hermes-writer",
        "paths": {
            "host_data_dir": "/opt/nodeskclaw/instances/writer/data/hermes",
            "skills_dir": "/opt/nodeskclaw/instances/writer/data/hermes/skills",
        },
    }
    return Instance(
        id="instance-1",
        name="writer",
        slug="writer",
        cluster_id="cluster-1",
        namespace="docker-writer",
        image_version="latest",
        replicas=1,
        cpu_request="100m",
        cpu_limit="500m",
        mem_request="256Mi",
        mem_limit="1Gi",
        service_type="docker",
        storage_size="20Gi",
        quota_cpu="1",
        quota_mem="1Gi",
        compute_provider="docker",
        runtime="hermes-webui-expert",
        status=status,
        advanced_config=json.dumps(advanced),
        created_by="user-1",
        org_id="org-1",
    )


class _Result:
    def __init__(self, value):
        self.value = value

    def scalar_one_or_none(self):
        return self.value

    def scalars(self):
        return self

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


@pytest.fixture(autouse=True)
def _patch_cluster_lookup(monkeypatch):
    cluster = SimpleNamespace(
        id="cluster-1",
        compute_provider="docker",
        status=ClusterStatus.connected,
        deleted_at=None,
    )
    monkeypatch.setattr(
        docker_attach_service,
        "_get_docker_cluster",
        AsyncMock(return_value=cluster),
    )


@pytest.fixture(autouse=True)
def _ensure_host_data_dir(monkeypatch):
    monkeypatch.setattr(Path, "is_dir", lambda self: True)


@pytest.mark.asyncio
async def test_attach_existing_container_success(monkeypatch):
    monkeypatch.setattr(
        docker_attach_service,
        "_docker_inspect",
        AsyncMock(return_value=_inspect_payload()),
    )
    monkeypatch.setattr(
        docker_attach_service,
        "_find_attachment_match",
        AsyncMock(return_value=None),
    )
    monkeypatch.setattr(
        docker_attach_service,
        "_probe_health",
        AsyncMock(return_value="healthy"),
    )

    db = AsyncMock()
    added: list[object] = []

    def capture_add(obj):
        added.append(obj)

    db.add = capture_add
    db.commit = AsyncMock()

    async def refresh_side_effect(obj):
        if isinstance(obj, Instance) and not obj.id:
            obj.id = "instance-new"

    db.refresh = AsyncMock(side_effect=refresh_side_effect)

    instance = await docker_attach_service.attach_existing_container(
        db,
        SimpleNamespace(id="user-1"),
        _attach_request(),
        "org-1",
    )

    assert instance.id == "instance-new"
    assert instance.slug == "writer"
    assert instance.status == InstanceStatus.running
    assert instance.ingress_domain == "localhost:8787"
    advanced = json.loads(instance.advanced_config or "{}")
    assert advanced["attach_mode"] == "external"
    assert advanced["external_lifecycle"] is False
    assert advanced["external_container_name"] == "hermes-writer"
    assert advanced["paths"]["host_data_dir"] == "/opt/nodeskclaw/instances/writer/data/hermes"
    assert advanced["webui"]["public_url"] == "http://localhost:8787"
    assert any(isinstance(item, Instance) for item in added)
    assert db.commit.await_count >= 2


@pytest.mark.asyncio
async def test_attach_existing_container_allows_exited_container(monkeypatch):
    monkeypatch.setattr(
        docker_attach_service,
        "_docker_inspect",
        AsyncMock(return_value=_inspect_payload(status="exited")),
    )
    monkeypatch.setattr(
        docker_attach_service,
        "_find_attachment_match",
        AsyncMock(return_value=None),
    )
    monkeypatch.setattr(
        docker_attach_service,
        "_probe_health",
        AsyncMock(return_value="unhealthy"),
    )

    db = AsyncMock()
    db.add = lambda obj: None
    db.commit = AsyncMock()

    async def refresh_side_effect(obj):
        if isinstance(obj, Instance) and not obj.id:
            obj.id = "instance-new"

    db.refresh = AsyncMock(side_effect=refresh_side_effect)

    instance = await docker_attach_service.attach_existing_container(
        db,
        SimpleNamespace(id="user-1"),
        _attach_request(),
        "org-1",
    )

    assert instance.status == "stopped"


@pytest.mark.asyncio
async def test_attach_existing_container_rejects_duplicate(monkeypatch):
    monkeypatch.setattr(
        docker_attach_service,
        "_docker_inspect",
        AsyncMock(return_value=_inspect_payload()),
    )
    monkeypatch.setattr(
        docker_attach_service,
        "_find_attachment_match",
        AsyncMock(return_value=SimpleNamespace(id="existing-instance")),
    )

    with pytest.raises(ConflictError) as exc_info:
        await docker_attach_service.attach_existing_container(
            AsyncMock(),
            SimpleNamespace(id="user-1"),
            _attach_request(),
            "org-1",
        )

    assert exc_info.value.message_key == "errors.docker_attach.already_attached"


@pytest.mark.asyncio
async def test_attach_existing_container_rejects_missing_container(monkeypatch):
    monkeypatch.setattr(
        docker_attach_service,
        "_docker_inspect",
        AsyncMock(return_value=None),
    )
    monkeypatch.setattr(
        docker_attach_service,
        "_find_attachment_match",
        AsyncMock(return_value=None),
    )

    with pytest.raises(NotFoundError) as exc_info:
        await docker_attach_service.attach_existing_container(
            AsyncMock(),
            SimpleNamespace(id="user-1"),
            _attach_request(),
            "org-1",
        )

    assert exc_info.value.message_key == "errors.docker_attach.container_not_found"


@pytest.mark.asyncio
async def test_list_attachable_containers_marks_already_attached(monkeypatch):
    monkeypatch.setattr(
        docker_attach_service,
        "_docker_ps_hermes_containers",
        AsyncMock(return_value=["hermes-writer"]),
    )
    monkeypatch.setattr(
        docker_attach_service,
        "_docker_inspect",
        AsyncMock(return_value=_inspect_payload()),
    )
    monkeypatch.setattr(
        docker_attach_service,
        "_find_attachment_match",
        AsyncMock(return_value=SimpleNamespace(id="inst-bound")),
    )

    items = await docker_attach_service.list_attachable_containers(
        AsyncMock(),
        cluster_id="cluster-1",
        org_id="org-1",
        runtime="hermes-webui-expert",
    )

    assert len(items) == 1
    assert items[0].profile == "writer"
    assert items[0].already_attached is True
    assert items[0].matched_instance_id == "inst-bound"
    assert items[0].public_url == "http://localhost:8787"


@pytest.mark.asyncio
async def test_finalizer_skips_destroy_for_external_attach_instance(monkeypatch):
    instance = _make_docker_instance(status=InstanceStatus.deleting)
    db = _FakeDb([instance, []])
    destroy = AsyncMock(return_value=True)
    monkeypatch.setattr(instance_service, "_destroy_non_k8s_instance", destroy)

    def close_background_coro(coro):
        coro.close()
        return None

    monkeypatch.setattr(instance_service, "_fire_task", close_background_coro)

    done = await instance_service.finalize_instance_deletion_once(instance.id, db)

    assert done is True
    assert instance.deleted_at is not None
    destroy.assert_not_awaited()
    assert db.updated_tables == [
        "deploy_records",
        "instance_backups",
        "instance_members",
    ]


def test_is_external_attach_instance():
    instance = _make_docker_instance(status=InstanceStatus.running)
    assert instance_service._is_external_attach_instance(instance) is True

    instance.advanced_config = json.dumps({"attach_mode": "external", "external_lifecycle": True})
    assert instance_service._is_external_attach_instance(instance) is False


def test_get_hermes_host_data_dir_prefers_advanced_config():
    instance = _make_docker_instance(status=InstanceStatus.running)
    path = get_hermes_host_data_dir(instance)
    assert path == Path("/opt/nodeskclaw/instances/writer/data/hermes")
