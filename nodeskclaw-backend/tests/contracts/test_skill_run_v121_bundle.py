from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest

from scripts import contracts as contracts_module


BACKEND_ROOT = Path(__file__).resolve().parents[2]
V121_ROOT = BACKEND_ROOT / "contracts/skill-run/v1.2.1"
FROZEN_ROOTS = (
    BACKEND_ROOT / "contracts/skill-run/v1.0.0",
    BACKEND_ROOT / "contracts/skill-run/v1.1.0",
    BACKEND_ROOT / "contracts/skill-run/v1.2.0",
)


def test_v121_bundle_exists_with_public_surface():
    assert V121_ROOT.exists()
    relative_paths = {path.relative_to(V121_ROOT).as_posix() for path in contracts_module._public_artifact_files(V121_ROOT)}
    assert "manifest.json" in {path.name for path in V121_ROOT.iterdir()}
    assert "runs/public-run.schema.json" in relative_paths
    assert "http/endpoint-matrix.json" in relative_paths
    assert "fixtures/run-event-assistant-message.json" in relative_paths
    assert "mcp/skill-tool-annotations.schema.json" in relative_paths


def test_v121_has_no_internal_southbound_paths():
    for relative in contracts_module._bundle_files_excluding_checksum(V121_ROOT):
        assert not relative.startswith("edge/")
        assert not relative.startswith("installations/")
        assert relative != "runs/execution-snapshot.schema.json"


def test_v121_manifest_is_listed_in_sha256sums():
    listed = contracts_module._parse_sha256sums(V121_ROOT / "SHA256SUMS")
    assert "manifest.json" in listed
    assert "SHA256SUMS" not in listed
    assert "consumer-lock.json" not in listed


def test_v121_exact_checksum_closure_passes():
    contracts_module._validate_skill_run_checksums_exact(V121_ROOT)


def test_v121_sha256sums_is_lf_only():
    raw_bytes = (V121_ROOT / "SHA256SUMS").read_bytes()
    assert b"\r" not in raw_bytes
    assert raw_bytes.endswith(b"\n")


def test_v121_check_command_passes():
    result = subprocess.run(
        ["uv", "run", "python", "scripts/contracts.py", "check", "--family", "skill-run", "--version", "1.2.1"],
        cwd=BACKEND_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr or result.stdout


def test_v121_missing_file_fails_closure(tmp_path: Path):
    bundle = tmp_path / "bundle"
    shutil.copytree(V121_ROOT, bundle)
    (bundle / "fixtures" / "run-cancelled.json").unlink()
    with pytest.raises(SystemExit, match="closure mismatch"):
        contracts_module._validate_skill_run_checksums_exact(bundle)


def test_v121_extra_file_fails_closure(tmp_path: Path):
    bundle = tmp_path / "bundle"
    shutil.copytree(V121_ROOT, bundle)
    (bundle / "fixtures" / "extra-file.json").write_text("{}\n", encoding="utf-8")
    with pytest.raises(SystemExit, match="closure mismatch"):
        contracts_module._validate_skill_run_checksums_exact(bundle)


def test_v121_tampered_manifest_fails(tmp_path: Path):
    bundle = tmp_path / "bundle"
    shutil.copytree(V121_ROOT, bundle)
    manifest_path = bundle / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["contractVersion"] = "9.9.9"
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    with pytest.raises(SystemExit, match="SHA256 mismatch"):
        contracts_module._validate_skill_run_checksums_exact(bundle)


def test_v121_internal_path_fails_boundary(tmp_path: Path):
    bundle = tmp_path / "bundle"
    shutil.copytree(V121_ROOT, bundle)
    edge_dir = bundle / "edge"
    edge_dir.mkdir()
    (edge_dir / "lease-renew.schema.json").write_text("{}\n", encoding="utf-8")
    with pytest.raises(SystemExit, match="Internal Southbound"):
        contracts_module._validate_skill_run_public_boundary(bundle)


def test_v121_crlf_sha256sums_fails(tmp_path: Path):
    bundle = tmp_path / "bundle"
    shutil.copytree(V121_ROOT, bundle)
    checksum_path = bundle / "SHA256SUMS"
    checksum_path.write_bytes(checksum_path.read_bytes().replace(b"\n", b"\r\n"))
    with pytest.raises(SystemExit, match="LF-only"):
        contracts_module._validate_skill_run_checksums_exact(bundle)


def test_frozen_skill_run_versions_unchanged_by_v121_generate():
    before = {
        root: {path.relative_to(root): path.read_bytes() for path in root.rglob("*") if path.is_file()}
        for root in FROZEN_ROOTS
    }
    result = subprocess.run(
        ["uv", "run", "python", "scripts/contracts.py", "generate", "--family", "skill-run", "--version", "1.2.1"],
        cwd=BACKEND_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr or result.stdout
    after = {
        root: {path.relative_to(root): path.read_bytes() for path in root.rglob("*") if path.is_file()}
        for root in FROZEN_ROOTS
    }
    assert before == after
