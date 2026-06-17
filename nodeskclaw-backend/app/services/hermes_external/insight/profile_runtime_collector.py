"""Profile runtime status collector for Hermes Insight."""

from __future__ import annotations

import logging
import socket
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from app.core.exceptions import BadRequestError
from app.services.hermes_external.hermes_env_parser import parse_env_file
from app.services.hermes_external.insight.safe_path import InsightProfilePaths, resolve_insight_profile_paths
from app.services.hermes_external.insight.usage_collector import _collect_from_state_db, insight_cutoff

logger = logging.getLogger(__name__)

PROFILE_RUNTIME_STATUSES = frozenset({
    "running",
    "idle",
    "configured",
    "missing",
    "error",
    "unknown",
})


@dataclass
class ProfileRuntimeInfo:
    profile_name: str
    status: str = "unknown"
    api_server_enabled: bool = False
    api_server_port: int | None = None
    webui_port: int | None = None
    state_db_exists: bool = False
    config_exists: bool = False
    webui_index_exists: bool = False
    gateway_pid_alive: bool = False
    last_state_write_at: str | None = None
    last_session_at: str | None = None


class ProfileRuntimeCollector:
    def collect(self, host_data_dir: Path, profile_name: str) -> ProfileRuntimeInfo:
        try:
            paths = resolve_insight_profile_paths(host_data_dir, profile_name)
        except BadRequestError:
            return ProfileRuntimeInfo(profile_name=profile_name, status="missing")
        except Exception as exc:
            logger.warning("profile runtime resolve failed for %s: %s", profile_name, exc)
            return ProfileRuntimeInfo(profile_name=profile_name, status="error")

        if not paths.profile_dir.exists():
            return ProfileRuntimeInfo(profile_name=profile_name, status="missing")

        info = ProfileRuntimeInfo(profile_name=profile_name)
        info.state_db_exists = paths.state_db_path.is_file()
        info.config_exists = paths.config_path.is_file()
        info.webui_index_exists = paths.webui_index_path.is_file()
        info.last_state_write_at = _file_mtime_iso(paths.state_db_path)
        info.last_session_at = _last_session_at(paths)

        env_data = _safe_parse_env(paths.env_path)
        if env_data:
            info.api_server_enabled = bool(env_data.api_server_enabled)
            info.api_server_port = env_data.api_server_port or env_data.gateway_port
            info.webui_port = env_data.webui_port

        info.gateway_pid_alive = _gateway_pid_alive(paths.gateway_pid_path)
        port_listening = _is_port_listening(info.api_server_port)

        if port_listening or info.gateway_pid_alive:
            info.status = "running"
        elif info.state_db_exists:
            info.status = "idle"
        elif info.config_exists:
            info.status = "configured"
        elif paths.profile_dir.exists():
            info.status = "unknown"
        else:
            info.status = "missing"

        return info


def _safe_parse_env(env_path: Path):
    if not env_path.is_file():
        return None
    try:
        return parse_env_file(env_path, require_gateway_port=False)
    except BadRequestError:
        return None


def _file_mtime_iso(path: Path) -> str | None:
    if not path.is_file():
        return None
    try:
        mtime = datetime.fromtimestamp(path.stat().st_mtime, tz=UTC)
        return mtime.isoformat()
    except OSError:
        return None


def _last_session_at(paths: InsightProfilePaths) -> str | None:
    cutoff = insight_cutoff()
    records, _ = _collect_from_state_db(paths, cutoff, cutoff.isoformat())
    if not records:
        return None
    dates = [r.event_date for r in records if r.event_date]
    return max(dates) if dates else None


def _gateway_pid_alive(pid_path: Path) -> bool:
    if not pid_path.is_file():
        return False
    try:
        pid = int(pid_path.read_text(encoding="utf-8").strip())
    except (OSError, ValueError):
        return False
    try:
        import os

        os.kill(pid, 0)
        return True
    except OSError:
        return False


def _is_port_listening(port: int | None) -> bool:
    if not port:
        return False
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(0.3)
    try:
        return sock.connect_ex(("127.0.0.1", port)) == 0
    except OSError:
        return False
    finally:
        sock.close()
