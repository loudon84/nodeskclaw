from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from app.core.exceptions import BadRequestError

ENV_WHITELIST_KEYS = frozenset({
    "PROFILE_NAME",
    "CONTAINER_NAME",
    "HERMES_WEBUI_PORT",
    "HERMES_GATEWAY_PORT",
    "HERMES_GATEWAY_INTERNAL_PORT",
    "HERMES_INSTANCE_DIR",
    "HERMES_DATA_DIR",
})


@dataclass
class HermesEnvData:
    profile_name: str | None = None
    container_name: str | None = None
    webui_port: int | None = None
    gateway_port: int | None = None
    gateway_internal_port: int = 8642
    instance_dir: str | None = None
    data_dir: str | None = None
    raw: dict[str, str] = field(default_factory=dict)
    errors: list[str] = field(default_factory=list)


def _strip_quotes(value: str) -> str:
    value = value.strip()
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
        return value[1:-1]
    return value


def parse_env_file(env_path: Path, *, require_gateway_port: bool = False) -> HermesEnvData:
    if not env_path.is_file():
        raise BadRequestError(
            "实例目录缺少 .env，无法绑定 Hermes Runtime。",
            "errors.hermes.env_not_found",
        )

    raw: dict[str, str] = {}
    try:
        for line in env_path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, value = line.partition("=")
            key = key.strip()
            if key in ENV_WHITELIST_KEYS:
                raw[key] = _strip_quotes(value)
    except OSError as exc:
        raise BadRequestError(
            f"读取 .env 失败: {exc}",
            "errors.hermes.env_read_failed",
        ) from exc

    data = HermesEnvData(raw=raw)
    instance_root = str(env_path.parent)

    profile = raw.get("PROFILE_NAME") or Path(instance_root).name
    data.profile_name = profile
    data.instance_dir = raw.get("HERMES_INSTANCE_DIR") or instance_root
    data.data_dir = raw.get("HERMES_DATA_DIR") or str(Path(instance_root) / "data" / "hermes")
    data.container_name = raw.get("CONTAINER_NAME") or f"hermes-{profile}"

    if "HERMES_WEBUI_PORT" in raw:
        try:
            data.webui_port = int(raw["HERMES_WEBUI_PORT"])
        except ValueError:
            data.errors.append("HERMES_WEBUI_PORT is invalid")

    if "HERMES_GATEWAY_PORT" in raw:
        try:
            data.gateway_port = int(raw["HERMES_GATEWAY_PORT"])
        except ValueError:
            data.errors.append("HERMES_GATEWAY_PORT is invalid")
    elif require_gateway_port:
        raise BadRequestError(
            "实例 .env 缺少 HERMES_GATEWAY_PORT，无法监听 Hermes Agent Runtime。",
            "errors.hermes.gateway_port_missing",
        )

    internal_raw = raw.get("HERMES_GATEWAY_INTERNAL_PORT")
    if internal_raw:
        try:
            data.gateway_internal_port = int(internal_raw)
        except ValueError:
            data.errors.append("HERMES_GATEWAY_INTERNAL_PORT is invalid")

    return data
