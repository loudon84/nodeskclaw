from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

FORBIDDEN = ("BEGIN PRIVATE", "API_KEY=", "JWT_SECRET")


def main() -> int:
    if len(sys.argv) < 2:
        print("usage: verify_desktop_bundle.py <bundle-dir>", file=sys.stderr)
        return 2
    root = Path(sys.argv[1])
    exe = root / "nodeskclaw-acp.exe"
    manifest_path = root / "manifest.json"
    sums_path = root / "SHA256SUMS"
    if not exe.is_file() or not manifest_path.is_file() or not sums_path.is_file():
        print("missing exe, manifest.json or SHA256SUMS", file=sys.stderr)
        return 1
    digest = hashlib.sha256(exe.read_bytes()).hexdigest()
    listed = {}
    for line in sums_path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        value, _, name = line.partition("  ")
        listed[name] = value
    if listed.get("nodeskclaw-acp.exe") != digest:
        print("SHA256 mismatch for nodeskclaw-acp.exe", file=sys.stderr)
        return 1
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest.get("sha256") != digest:
        print("manifest sha256 mismatch", file=sys.stderr)
        return 1
    blob = exe.read_bytes()
    for token in FORBIDDEN:
        if token.encode("ascii") in blob:
            print("possible secret in binary", file=sys.stderr)
            return 1
    print(json.dumps({"ok": True, "sha256": digest}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
