from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", default=str(ROOT / "dist" / "windows-amd64"))
    args = parser.parse_args()
    output = Path(args.output)
    output.mkdir(parents=True, exist_ok=True)
    try:
        import PyInstaller  # noqa: F401
    except ImportError:
        print("PyInstaller is required to build nodeskclaw-acp.exe", file=sys.stderr)
        return 1
    cmd = [
        sys.executable,
        "-m",
        "PyInstaller",
        "--noconfirm",
        "--clean",
        "--onefile",
        "--name",
        "nodeskclaw-acp",
        "--distpath",
        str(output),
        str(ROOT / "app" / "cli.py"),
    ]
    return subprocess.call(cmd)


if __name__ == "__main__":
    raise SystemExit(main())
