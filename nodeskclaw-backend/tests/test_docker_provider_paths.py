import pytest

from app.services.runtime.compute import docker_provider
from app.services.runtime.registries.runtime_registry import RuntimeSpec


def test_join_host_path_for_posix() -> None:
    path = docker_provider._join_host_path("/Users/tester/.nodeskclaw/docker-instances", "demo", "data")
    assert path == "/Users/tester/.nodeskclaw/docker-instances/demo/data"


def test_join_host_path_for_windows_drive() -> None:
    path = docker_provider._join_host_path(r"C:\Users\tester\.nodeskclaw\docker-instances", "demo", "data")
    assert path == r"C:\Users\tester\.nodeskclaw\docker-instances\demo\data"


def test_build_compose_yaml_uses_host_data_dir_for_bind_source(monkeypatch) -> None:
    monkeypatch.setattr(docker_provider, "DOCKER_HOST_DATA_DIR", r"C:\Users\tester\.nodeskclaw\docker-instances")

    config = docker_provider.InstanceComputeConfig(
        instance_id="instance-1",
        name="demo",
        namespace="default",
        slug="demo",
        image_version="latest",
        runtime="openclaw",
        gateway_port=3000,
        env_vars={},
        mem_limit=None,
        cpu_limit=None,
        companion=None,
    )

    compose = docker_provider._build_compose_yaml(config)
    volumes = compose["services"]["agent"]["volumes"]

    assert volumes == [{
        "type": "bind",
        "source": r"C:\Users\tester\.nodeskclaw\docker-instances\demo\data",
        "target": "/root/.openclaw",
    }]


def test_resolve_compose_path_prefers_current_container_path(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(docker_provider, "DOCKER_DATA_DIR", tmp_path)
    monkeypatch.setattr(docker_provider, "DOCKER_HOST_DATA_DIR", r"C:\Users\tester\.nodeskclaw\docker-instances")

    compose_path = tmp_path / "demo" / "docker-compose.yml"
    compose_path.parent.mkdir(parents=True)
    compose_path.write_text("services: {}\n", encoding="utf-8")

    resolved = docker_provider._resolve_compose_path(
        "demo",
        r"C:\Users\tester\.nodeskclaw\docker-instances\demo\docker-compose.yml",
    )

    assert resolved == str(compose_path)


def test_remap_legacy_compose_path_maps_host_path_to_container_path(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(docker_provider, "DOCKER_DATA_DIR", tmp_path)
    monkeypatch.setattr(docker_provider, "DOCKER_HOST_DATA_DIR", r"C:\Users\tester\.nodeskclaw\docker-instances")

    remapped = docker_provider._remap_legacy_compose_path(
        r"C:\Users\tester\.nodeskclaw\docker-instances\demo\docker-compose.yml",
    )

    assert remapped == str(tmp_path / "demo" / "docker-compose.yml")


@pytest.mark.asyncio
async def test_destroy_instance_falls_back_to_slug_cleanup(monkeypatch) -> None:
    calls = []

    class _Proc:
        def __init__(self, returncode: int = 0, stderr: bytes = b""):
            self.returncode = returncode
            self._stderr = stderr

        async def communicate(self):
            return b"", self._stderr

    async def _fake_exec(*args, **kwargs):
        calls.append(args)
        return _Proc()

    monkeypatch.setattr(docker_provider, "_resolve_compose_path", lambda slug, stored: "")
    monkeypatch.setattr(docker_provider.asyncio, "create_subprocess_exec", _fake_exec)

    handle = docker_provider.ComputeHandle(
        provider="docker",
        instance_id="instance-1",
        namespace="default",
        extra={"slug": "demo", "compose_path": "/legacy/demo/docker-compose.yml"},
    )

    await docker_provider.DockerComputeProvider().destroy_instance(handle)

    assert calls == [
        ("docker", "rm", "-f", "demo-companion"),
        ("docker", "rm", "-f", "demo"),
        ("docker", "network", "rm", "demo-net"),
    ]


@pytest.mark.asyncio
async def test_seed_template_from_image_uses_runtime_template_rel(tmp_path, monkeypatch) -> None:
    calls = []

    class _Proc:
        def __init__(self, returncode: int = 0, stdout: bytes = b"", stderr: bytes = b""):
            self.returncode = returncode
            self._stdout = stdout
            self._stderr = stderr

        async def communicate(self):
            return self._stdout, self._stderr

        async def wait(self):
            return self.returncode

    async def _fake_exec(*args, **kwargs):
        calls.append(args)
        if args[:2] == ("docker", "create"):
            return _Proc(stdout=b"cid-123\n")
        return _Proc()

    monkeypatch.setattr(docker_provider.asyncio, "create_subprocess_exec", _fake_exec)

    config = docker_provider.InstanceComputeConfig(
        instance_id="instance-1",
        name="demo",
        namespace="default",
        slug="demo",
        image_version="latest",
        runtime="openclaw",
        gateway_port=3000,
        env_vars={},
        mem_limit=None,
        cpu_limit=None,
        companion=None,
    )

    await docker_provider._seed_template_from_image(config, tmp_path)

    create_call = calls[0]
    assert calls == [
        ("docker", "create", "--platform", "linux/amd64", "--name", create_call[5], "deskclaw:latest"),
        ("docker", "cp", f"cid-123:/root/.openclaw/openclaw.json.template", str(tmp_path / "openclaw.json.template")),
        ("docker", "rm", "cid-123"),
    ]


@pytest.mark.asyncio
async def test_seed_template_from_image_skips_runtime_without_template(tmp_path, monkeypatch) -> None:
    calls = []

    async def _fake_exec(*args, **kwargs):
        calls.append(args)
        raise AssertionError("should not invoke docker when runtime has no seed template")

    monkeypatch.setattr(docker_provider.asyncio, "create_subprocess_exec", _fake_exec)

    from app.services.runtime.registries.runtime_registry import RUNTIME_REGISTRY

    monkeypatch.setattr(
        RUNTIME_REGISTRY,
        "get",
        lambda runtime_id: RuntimeSpec(
            runtime_id=runtime_id,
            data_dir_container_path="/root/.custom",
            docker_seed_template_rel=None,
        ),
    )

    config = docker_provider.InstanceComputeConfig(
        instance_id="instance-1",
        name="demo",
        namespace="default",
        slug="demo",
        image_version="latest",
        runtime="custom",
        gateway_port=3000,
        env_vars={},
        mem_limit=None,
        cpu_limit=None,
        companion=None,
    )

    await docker_provider._seed_template_from_image(config, tmp_path)

    assert calls == []
