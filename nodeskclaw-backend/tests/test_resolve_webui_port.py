import json
from types import SimpleNamespace

from app.services.instance_service import _resolve_webui_port


def _inst(*, advanced: dict | None = None, env: dict | None = None):
    return SimpleNamespace(
        advanced_config=json.dumps(advanced) if advanced is not None else None,
        env_vars=json.dumps(env) if env is not None else None,
    )


# @lat: [[core-concepts#Instance]]
def test_resolve_webui_port_prefers_host_port():
    inst = _inst(
        advanced={"webui": {"host_port": 19001, "port": 19002}},
        env={"DOCKER_HOST_PORT": "19003"},
    )
    assert _resolve_webui_port(inst) == 19001


def test_resolve_webui_port_falls_back_to_port():
    inst = _inst(advanced={"webui": {"port": 19002}})
    assert _resolve_webui_port(inst) == 19002


def test_resolve_webui_port_falls_back_to_docker_host_port():
    inst = _inst(env={"DOCKER_HOST_PORT": "19003"})
    assert _resolve_webui_port(inst) == 19003


def test_resolve_webui_port_invalid_string_returns_none():
    inst = _inst(env={"DOCKER_HOST_PORT": "not-a-port"})
    assert _resolve_webui_port(inst) is None


def test_resolve_webui_port_missing_returns_none():
    assert _resolve_webui_port(_inst()) is None
