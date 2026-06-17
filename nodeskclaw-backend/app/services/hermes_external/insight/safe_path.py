"""Safe path resolution for Hermes Insight collectors."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from app.services.hermes_external.path_resolver import HermesExternalPathResolver


@dataclass(frozen=True)
class InsightProfilePaths:
    profile_name: str
    profile_dir: Path
    state_db_path: Path
    config_path: Path
    webui_index_path: Path
    env_path: Path
    gateway_pid_path: Path


_resolver = HermesExternalPathResolver()


def resolve_insight_profile_paths(host_data_dir: Path, profile_name: str) -> InsightProfilePaths:
    pp = _resolver.resolve_profile_from_host_data_dir(host_data_dir, profile_name)
    profile_dir = pp.profile_dir
    _resolver.validate_profile_path(profile_dir, profile_dir / "state.db")
    _resolver.validate_profile_path(profile_dir, profile_dir / "webui" / "sessions" / "_index.json")
    return InsightProfilePaths(
        profile_name=pp.profile,
        profile_dir=profile_dir,
        state_db_path=profile_dir / "state.db",
        config_path=pp.config_file,
        webui_index_path=profile_dir / "webui" / "sessions" / "_index.json",
        env_path=pp.env_file,
        gateway_pid_path=profile_dir / "gateway.pid",
    )
