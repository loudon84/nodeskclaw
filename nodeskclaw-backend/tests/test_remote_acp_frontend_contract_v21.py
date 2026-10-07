from __future__ import annotations

import hashlib
import importlib.util
import shutil
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
V2_DIGEST = "22ad68dd1132a073f6df5d2bf9f219b683c73ebb7ea1fa48933c9b92a744ecd5"
VERIFY = REPO / "tools" / "contracts" / "verify_remote_expert_frontend_contract_v21.py"


def _load_verifier_module():
    spec = importlib.util.spec_from_file_location("verify_remote_acp_v21", VERIFY)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_v21_verifier_pass():
    proc = subprocess.run(
        [sys.executable, str(VERIFY), "--repo-root", str(REPO)],
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert '"ok":true' in proc.stdout.replace(" ", "").lower()


def test_v20_digest_unchanged():
    sums = REPO / "contracts" / "remote-expert-frontend" / "v2.0.0" / "SHA256SUMS"
    digest = hashlib.sha256(sums.read_bytes()).hexdigest()
    assert digest == V2_DIGEST


def test_tamper_sha256sums_fails(tmp_path):
    src = REPO / "contracts" / "remote-expert-frontend" / "v2.1.0"
    dst = tmp_path / "v2.1.0"
    shutil.copytree(src, dst)
    sums = dst / "SHA256SUMS"
    lines = sums.read_text(encoding="utf-8").splitlines()
    digest, sep, rel = lines[0].partition("  ")
    flipped = ("0" if digest[0] != "0" else "1") + digest[1:]
    lines[0] = f"{flipped}{sep}{rel}"
    sums.write_bytes(("\n".join(lines) + "\n").encode("utf-8"))

    mod = _load_verifier_module()
    try:
        mod.verify_component_checksums(dst)
        assert False, "expected mismatch"
    except SystemExit as exc:
        assert "digest mismatch" in str(exc)
