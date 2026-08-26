"""Build a production node/hermes-agent workspace from the Hermes source freeze.

Uses the pinned embedded npm (from the same Node runtime archive) to run
``npm ci --omit=dev --workspaces=false``, producing a deterministic
``node_modules`` tree that includes ``agent-browser`` but excludes Chromium.
"""

from __future__ import annotations

import json
import os
import shutil
from pathlib import Path

from tools.release.subprocess_text import command_output, run_command

CHROMIUM_FORBIDDEN_PATTERNS = (
    "chromium",
    ".local-chromium",
    "chrome-win",
    "playwright",
    "puppeteer",
)

REQUIRED_PACKAGES = ("agent-browser",)


def build_hermes_node_workspace(
    hermes_source: Path,
    node_root: Path,
    dest: Path,
    *,
    env_overrides: dict[str, str] | None = None,
) -> Path:
    """Build production workspace from Hermes source manifests using embedded npm.

    Args:
        hermes_source: Hermes git checkout root (contains package.json, package-lock.json).
        node_root: Extracted Node runtime directory (contains node.exe, npm.cmd).
        dest: Output directory for the workspace (becomes node/hermes-agent).
        env_overrides: Extra environment variables for the npm ci subprocess.

    Returns:
        Path to the completed workspace directory.
    """
    pkg_json = hermes_source / "package.json"
    pkg_lock = hermes_source / "package-lock.json"
    if not pkg_json.is_file():
        raise ValueError(f"package.json missing from hermes source: {hermes_source}")
    if not pkg_lock.is_file():
        raise ValueError(f"package-lock.json missing from hermes source: {hermes_source}")

    npm_cmd = node_root / "npm.cmd"
    if not npm_cmd.is_file():
        raise ValueError(f"npm.cmd missing from node root: {node_root}")

    if dest.exists():
        shutil.rmtree(dest)
    dest.mkdir(parents=True)

    shutil.copy2(pkg_json, dest / "package.json")
    shutil.copy2(pkg_lock, dest / "package-lock.json")

    env = os.environ.copy()
    env["PATH"] = str(node_root) + os.pathsep + env.get("PATH", "")
    env["PLAYWRIGHT_SKIP_BROWSER_DOWNLOAD"] = "1"
    env["PUPPETEER_SKIP_DOWNLOAD"] = "true"
    if env_overrides:
        env.update(env_overrides)

    result = run_command(
        [
            str(npm_cmd),
            "ci",
            "--omit=dev",
            "--workspaces=false",
            "--ignore-scripts",
        ],
        cwd=dest,
        env=env,
    )
    if result.returncode != 0:
        raise ValueError(command_output(result, "npm ci failed"))

    _verify_workspace(dest)
    return dest


def _verify_workspace(workspace: Path) -> None:
    node_modules = workspace / "node_modules"
    if not node_modules.is_dir():
        raise ValueError("npm ci produced no node_modules")

    for required in REQUIRED_PACKAGES:
        if not (node_modules / required).is_dir():
            raise ValueError(f"required package missing after npm ci: {required}")

    _scan_chromium(workspace)


def _scan_chromium(workspace: Path) -> None:
    for path in workspace.rglob("*"):
        if not path.is_dir():
            continue
        name_lower = path.name.lower()
        for pattern in CHROMIUM_FORBIDDEN_PATTERNS:
            if pattern in name_lower:
                raise ValueError(
                    f"Chromium/browser binary forbidden in workspace: "
                    f"{path.relative_to(workspace)}"
                )

    pkg_json = workspace / "package.json"
    if pkg_json.is_file():
        pkg = json.loads(pkg_json.read_text(encoding="utf-8"))
        deps = pkg.get("dependencies", {})
        deps.update(pkg.get("devDependencies", {}))
        for name in deps:
            if any(p in name.lower() for p in ("playwright", "puppeteer")):
                raise ValueError(
                    f"Chromium browser automation in production dependencies: {name}"
                )
