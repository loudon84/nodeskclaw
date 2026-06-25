import logging
import os
import re
from datetime import datetime
from pathlib import Path

from app.core.exceptions import BadRequestError

logger = logging.getLogger(__name__)

MCP_ENV_KEYS = frozenset({
    "NODESKCLAW_MCP_URL",
    "NODESKCLAW_MCP_TOKEN",
    "NODESKCLAW_MCP_ENABLED",
    "NODESKCLAW_MCP_NAME",
})


def _strip_quotes(value: str) -> str:
    value = value.strip()
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
        return value[1:-1]
    return value


def read_env(env_path: Path) -> dict[str, str]:
    if not env_path.is_file():
        return {}
    raw: dict[str, str] = {}
    for line in env_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        raw[key.strip()] = _strip_quotes(value)
    return raw


def merge_env(existing: dict[str, str], updates: dict[str, str]) -> dict[str, str]:
    merged = dict(existing)
    for key, value in updates.items():
        merged[key] = value
    return merged


def format_env_content(values: dict[str, str]) -> str:
    lines: list[str] = []
    for key, value in values.items():
        if re.search(r"[\s#\"']", value):
            lines.append(f'{key}="{value}"')
        else:
            lines.append(f"{key}={value}")
    return "\n".join(lines) + "\n"


def backup_env(env_path: Path) -> Path:
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_path = env_path.parent / f".env.bak.{stamp}"
    backup_path.write_text(env_path.read_text(encoding="utf-8"), encoding="utf-8")
    return backup_path


def atomic_write_env(env_path: Path, values: dict[str, str]) -> None:
    env_path.parent.mkdir(parents=True, exist_ok=True)
    existing = read_env(env_path) if env_path.is_file() else {}
    merged = merge_env(existing, values)
    content = format_env_content(merged)

    if env_path.is_file():
        backup_env(env_path)

    tmp_path = env_path.with_suffix(".env.tmp")
    tmp_path.write_text(content, encoding="utf-8")
    os.replace(tmp_path, env_path)
    try:
        os.chmod(env_path, 0o600)
    except OSError as exc:
        logger.warning("chmod 600 failed for %s: %s", env_path, exc)


def remove_env_keys(env_path: Path, keys: frozenset[str] = MCP_ENV_KEYS) -> None:
    if not env_path.is_file():
        return
    existing = read_env(env_path)
    if not any(key in existing for key in keys):
        return
    backup_env(env_path)
    filtered = {k: v for k, v in existing.items() if k not in keys}
    content = format_env_content(filtered)
    tmp_path = env_path.with_suffix(".env.tmp")
    tmp_path.write_text(content, encoding="utf-8")
    os.replace(tmp_path, env_path)
    try:
        os.chmod(env_path, 0o600)
    except OSError as exc:
        logger.warning("chmod 600 failed for %s: %s", env_path, exc)


def resolve_env_path(env_file: str | None, instance_dir: str | None) -> Path:
    if env_file:
        return Path(env_file)
    if instance_dir:
        return Path(instance_dir) / ".env"
    raise BadRequestError("实例未配置 .env 路径", "errors.mcp_gateway.env_path_missing")


def write_mcp_env_values(env_path: Path, values: dict[str, str]) -> None:
    safe_log_keys = {k: ("***" if k == "NODESKCLAW_MCP_TOKEN" else v) for k, v in values.items()}
    logger.info("Writing MCP env keys to %s: %s", env_path, safe_log_keys)
    try:
        atomic_write_env(env_path, values)
    except OSError as exc:
        raise BadRequestError(
            f"写入 .env 失败: {exc}",
            "errors.mcp_gateway.env_write_failed",
        ) from exc
