import os
from pathlib import Path

import pytest

from app.services.docker_instance_layout_resolver import (
    layout_to_advanced_config,
    resolve_from_inspect,
)


def _inspect(
    *,
    container_name: str = "hermes-agent-01",
    host_port: str = "8901",
    mount_source: str = "/data/copilot-docker/instances/agent-01/data/hermes",
    labels: dict | None = None,
) -> dict:
    return {
        "Name": f"/{container_name}",
        "State": {"Status": "running"},
        "Config": {
            "Image": "hermes-agent-webui:latest",
            "Labels": labels or {},
        },
        "NetworkSettings": {
            "Ports": {"8787/tcp": [{"HostIp": "0.0.0.0", "HostPort": host_port}]},
        },
        "Mounts": [{"Destination": "/data/hermes", "Source": mount_source}],
    }


def test_profile_from_container_name():
    layout = resolve_from_inspect(_inspect(container_name="hermes-agent-01"))
    assert layout.profile == "agent-01"
    assert layout.container_name == "hermes-agent-01"


def test_host_data_dir_from_mount():
    layout = resolve_from_inspect(_inspect())
    assert layout.host_data_dir == "/data/copilot-docker/instances/agent-01/data/hermes"
    assert Path(layout.instance_root).as_posix() == "/data/copilot-docker/instances/agent-01"


def test_env_file_and_compose_labels(monkeypatch, tmp_path: Path):
    compose_path = tmp_path / "docker-compose.yml"
    compose_path.write_text("services: {}\n", encoding="utf-8")
    env_dir = tmp_path / "instances" / "writer"
    env_dir.mkdir(parents=True)
    env_file = env_dir / ".env"
    env_file.write_text("HERMES_WEBUI_PORT=9001\n", encoding="utf-8")
    mount_source = env_dir / "data" / "hermes"
    mount_source.mkdir(parents=True)

    monkeypatch.setenv("DOCKER_PUBLIC_HOST", "192.168.102.247")
    monkeypatch.setenv("DOCKER_PUBLIC_SCHEME", "http")

    layout = resolve_from_inspect(
        _inspect(
            container_name="hermes-writer",
            host_port="9001",
            mount_source=str(mount_source),
            labels={
                "com.docker.compose.project": "hermes-writer",
                "com.docker.compose.project.config_files": str(compose_path),
            },
        ),
        scan_entry=env_dir,
    )

    assert layout.profile == "writer"
    assert layout.env_file == str(env_file)
    assert layout.compose_path == str(compose_path)
    assert layout.project_name == "hermes-writer"
    assert layout.public_url == "http://192.168.102.247:9001"
    assert layout.lifecycle_mode == "managed_compose"


def test_compose_missing_downgrades_lifecycle(monkeypatch, tmp_path: Path):
    env_dir = tmp_path / "instances" / "writer"
    env_dir.mkdir(parents=True)
    env_file = env_dir / ".env"
    env_file.write_text("HERMES_WEBUI_PORT=9001\n", encoding="utf-8")
    mount_source = env_dir / "data" / "hermes"
    mount_source.mkdir(parents=True)
    monkeypatch.setenv("DOCKER_COMPOSE_FILE", str(tmp_path / "missing-compose.yml"))
    monkeypatch.setattr(
        "app.services.docker_instance_layout_resolver.get_docker_compose_file_fallback",
        lambda: None,
    )

    layout = resolve_from_inspect(
        _inspect(
            container_name="hermes-writer",
            mount_source=str(mount_source),
            labels={},
        ),
        scan_entry=env_dir,
    )

    assert layout.lifecycle_mode == "managed_container"
    assert any("compose_path missing" in warning for warning in layout.warnings)


def test_missing_host_data_dir_not_attachable():
    layout = resolve_from_inspect({
        "Name": "/hermes-agent-01",
        "State": {"Status": "running"},
        "Config": {"Image": "hermes-agent-webui:latest", "Labels": {}},
        "NetworkSettings": {"Ports": {}},
        "Mounts": [],
    })
    assert layout.attachable is False
    assert any("无法识别" in warning for warning in layout.warnings)


def test_layout_to_advanced_config_structure():
    layout = resolve_from_inspect(_inspect())
    advanced = layout_to_advanced_config(layout)
    assert advanced["attach_mode"] == "external"
    assert advanced["lifecycle_mode"] == layout.lifecycle_mode
    assert advanced["paths"]["host_data_dir"] == layout.host_data_dir
    assert advanced["compose"]["project_name"] == layout.project_name
    assert advanced["webui"]["public_url"] == layout.public_url
    assert advanced["capabilities"]["allow_destroy_container"] is False
