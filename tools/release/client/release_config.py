"""Load and validate smc.client-release.config.v1."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from tools.release.simple_yaml import load_yaml

SCHEMA = "smc.client-release.config.v1"


def load_release_config(path: Path) -> dict[str, Any]:
    data = load_yaml(path)
    if not isinstance(data, dict) or data.get("schema") != SCHEMA:
        raise ValueError(f"invalid client release config: {path}")
    for key in ("release", "clientRuntime", "work", "hermes", "opsi", "external"):
        if key not in data:
            raise ValueError(f"client release config missing {key}")
    if data["opsi"].get("buildMode") != "native":
        raise ValueError("opsi.buildMode must be native")
    if str(data["release"].get("version")) == str(data["hermes"].get("version")) and data["hermes"].get("version") not in {"auto", ""}:
        # versions may coincide by accident; product vs hermes is the forbidden bind
        pass
    if data["opsi"].get("productVersion") and data["hermes"].get("version") not in {"auto", None}:
        if str(data["opsi"]["productVersion"]) == str(data["hermes"]["version"]):
            raise ValueError("OPSI Product Version must not equal Hermes Version")
    return data
