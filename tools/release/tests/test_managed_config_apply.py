"""Unit tests for managed_config_apply.py (FR-216-08 / FR-216-09 / FR-216-10)."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[3]
APPLY_PATH = ROOT / "infra" / "windows" / "hermes-agent" / "scripts" / "managed_config_apply.py"


def _load_apply():
    spec = importlib.util.spec_from_file_location("managed_config_apply", APPLY_PATH)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_merge_semantics_defaults_existing_enforced(tmp_path: Path):
    apply = _load_apply()
    managed = {
        "schema": "smc.opsi.managed-config.v2",
        "profile": "smc-managed",
        "profileVersion": 2,
        "profileDigest": "d",
        "defaults": {"logging": {"level": "INFO"}, "sessions": {"retention_days": 90}},
        "enforced": {
            "security": {"allow_lazy_installs": False},
            "mcp_servers": {
                "workspace": {
                    "args": ["@modelcontextprotocol/server-filesystem", r"C:\ProgramData\SMC\Hermes\workspace"],
                    "enabled": True,
                }
            },
        },
    }
    managed_path = tmp_path / "managed.defaults.yaml"
    managed_path.write_text(yaml.safe_dump(managed, sort_keys=True), encoding="utf-8")
    config_path = tmp_path / "config.yaml"
    config_path.write_text(
        yaml.safe_dump(
            {"models": {"default": "keep-me"}, "logging": {"level": "DEBUG"}},
            sort_keys=True,
        ),
        encoding="utf-8",
    )
    result = apply.apply_config(
        config_path=config_path,
        managed_defaults_path=managed_path,
        workspace_root=r"C:\ProgramData\SMC\Hermes\workspace",
    )
    assert result["ok"] is True
    loaded = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    assert loaded["models"]["default"] == "keep-me"
    assert loaded["logging"]["level"] == "DEBUG"  # existing wins over defaults
    assert loaded["security"]["allow_lazy_installs"] is False
    assert loaded["terminal"]["cwd"] == r"C:\ProgramData\SMC\Hermes\workspace"
    assert loaded["mcp_servers"]["workspace"]["args"][0] == "@modelcontextprotocol/server-filesystem"
    assert type(loaded["mcp_servers"]["workspace"]["args"][0]) is str


def test_unchanged_still_validates(tmp_path: Path):
    apply = _load_apply()
    managed = {
        "schema": "smc.opsi.managed-config.v2",
        "profile": "smc-managed",
        "profileVersion": 2,
        "profileDigest": "d",
        "defaults": {},
        "enforced": {"security": {"allow_lazy_installs": False}},
    }
    managed_path = tmp_path / "managed.defaults.yaml"
    managed_path.write_text(yaml.safe_dump(managed, sort_keys=True), encoding="utf-8")
    # First apply
    config_path = tmp_path / "config.yaml"
    first = apply.apply_config(
        config_path=config_path,
        managed_defaults_path=managed_path,
        workspace_root=r"C:\ProgramData\SMC\Hermes\workspace",
    )
    assert first["changed"] is True
    second = apply.apply_config(
        config_path=config_path,
        managed_defaults_path=managed_path,
        workspace_root=r"C:\ProgramData\SMC\Hermes\workspace",
    )
    assert second["ok"] is True
    assert second["changed"] is False
    assert second["standardYaml"] == "PASS"


def test_invalid_yaml_does_not_overwrite(tmp_path: Path):
    apply = _load_apply()
    managed_path = tmp_path / "managed.defaults.yaml"
    managed_path.write_text("not: valid: yaml: [[\n", encoding="utf-8")
    config_path = tmp_path / "config.yaml"
    original = "models:\n  default: keep-me\n"
    config_path.write_text(original, encoding="utf-8")
    with pytest.raises(SystemExit) as exc:
        apply.apply_config(config_path=config_path, managed_defaults_path=managed_path)
    assert exc.value.code == apply.EXIT_YAML_PARSE
    assert config_path.read_text(encoding="utf-8") == original


def test_validate_only_accepts_valid_mapping(tmp_path: Path, capsys):
    apply = _load_apply()
    config_path = tmp_path / "config.yaml"
    config_path.write_text("models:\n  default: keep-me\n", encoding="utf-8")
    code = apply.main(["--validate-only", "--config", str(config_path)])
    assert code == 0
    out = json.loads(capsys.readouterr().out.strip())
    assert out["ok"] is True
    assert out["standardYaml"] == "PASS"


def test_validate_only_rejects_invalid_yaml(tmp_path: Path):
    apply = _load_apply()
    config_path = tmp_path / "config.yaml"
    config_path.write_text("not: valid: yaml: [[\n", encoding="utf-8")
    code = apply.main(["--validate-only", "--config", str(config_path)])
    assert code == apply.EXIT_YAML_PARSE


def test_cli_json_stdout(tmp_path: Path, capsys):
    apply = _load_apply()
    managed = {
        "schema": "smc.opsi.managed-config.v2",
        "profile": "smc-managed",
        "profileVersion": 2,
        "profileDigest": "d",
        "defaults": {},
        "enforced": {},
    }
    managed_path = tmp_path / "managed.defaults.yaml"
    managed_path.write_text(yaml.safe_dump(managed, sort_keys=True), encoding="utf-8")
    config_path = tmp_path / "config.yaml"
    code = apply.main(
        [
            "--config",
            str(config_path),
            "--managed-defaults",
            str(managed_path),
            "--workspace-root",
            r"C:\ProgramData\SMC\Hermes\workspace",
        ]
    )
    assert code == 0
    out = json.loads(capsys.readouterr().out.strip())
    assert out["ok"] is True
    assert out["standardYaml"] == "PASS"
