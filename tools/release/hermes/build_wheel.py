"""Build the Hermes wheel from a frozen source tree."""

from __future__ import annotations

import shutil
from pathlib import Path

from tools.release.subprocess_text import command_output, run_command


def build_wheel(repo: Path, dest: Path) -> Path:
    dest.mkdir(parents=True, exist_ok=True)
    # Hermes upstream blocks PEP 517 wheel builds unless HERMES_NIX_BUILD=1
    # (same escape hatch as nix/python.nix / uv2nix packaging).
    build_env = {"HERMES_NIX_BUILD": "1"}
    uv = shutil.which("uv")
    if uv:
        cmd = [uv, "build", "--wheel", "--out-dir", str(dest)]
    else:
        cmd = ["python", "-m", "build", "--wheel", "--outdir", str(dest)]
    result = run_command(cmd, cwd=repo, env=build_env)
    if result.returncode != 0:
        raise ValueError(command_output(result, "wheel build failed"))
    wheels = sorted(dest.glob("hermes_agent-*.whl")) or sorted(dest.glob("*.whl"))
    if not wheels:
        raise ValueError("hermes wheel missing after build")
    return wheels[-1]
