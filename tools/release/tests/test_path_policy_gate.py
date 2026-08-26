"""Unit tests for Hermes Windows installer-managed PATH static gate."""

from __future__ import annotations

from pathlib import Path

import pytest

from tools.release.hermes.path_policy_gate import (
    ALLOWED_WIX_PATH_COMPONENT_ID,
    HERMES_BIN_PATH,
    assert_hermes_path_policy,
    assert_no_persistent_path_mutations,
    assert_path_policy_metadata,
    assert_wix_path_environment_allowlist,
    path_policy_payload,
    scan_persistent_path_mutations,
)

APPROVED_WIX = f"""<?xml version="1.0" encoding="UTF-8"?>
<Wix xmlns="http://wixtoolset.org/schemas/v4/wxs">
  <Component Id="{ALLOWED_WIX_PATH_COMPONENT_ID}">
    <Environment Id="envHermesBinPath" Name="PATH" Value="{HERMES_BIN_PATH}" Permanent="no" Part="first" Action="set" System="yes" />
  </Component>
</Wix>
"""


def test_repo_production_source_has_no_persistent_path_mutations() -> None:
    assert_hermes_path_policy()
    assert scan_persistent_path_mutations() == []


def test_path_policy_metadata_requires_installer_managed() -> None:
    assert_path_policy_metadata({"environment": path_policy_payload()})
    with pytest.raises(ValueError, match="environment.path.policy"):
        assert_path_policy_metadata({})
    with pytest.raises(ValueError, match="fields invalid|installer-managed"):
        assert_path_policy_metadata({"environment": {"path": {"policy": "immutable"}}})
    with pytest.raises(ValueError, match="fields invalid"):
        assert_path_policy_metadata(
            {
                "environment": {
                    "path": {
                        "policy": "installer-managed",
                        "owner": "windows-installer",
                        "entries": [HERMES_BIN_PATH],
                        "note": "extra",
                    }
                }
            }
        )
    with pytest.raises(ValueError, match="entries"):
        assert_path_policy_metadata(
            {
                "environment": {
                    "path": {
                        "policy": "installer-managed",
                        "owner": "windows-installer",
                        "entries": [HERMES_BIN_PATH, HERMES_BIN_PATH],
                    }
                }
            }
        )
    with pytest.raises(ValueError, match="owner"):
        assert_path_policy_metadata(
            {
                "environment": {
                    "path": {
                        "policy": "installer-managed",
                        "owner": "powershell",
                        "entries": [HERMES_BIN_PATH],
                    }
                }
            }
        )


def test_scan_detects_setenvironmentvariable_path(tmp_path: Path) -> None:
    prod = tmp_path / "scripts"
    prod.mkdir()
    (prod / "bad.psm1").write_text(
        '[Environment]::SetEnvironmentVariable("PATH", $x, "Machine")\n',
        encoding="utf-8",
    )
    hits = scan_persistent_path_mutations(tmp_path)
    assert hits, "expected persistent PATH mutation hit"
    with pytest.raises(ValueError, match="PERSISTENT_PATH_MUTATION_FORBIDDEN"):
        assert_no_persistent_path_mutations(tmp_path)


def test_scan_allowlists_tests_directory(tmp_path: Path) -> None:
    tests = tmp_path / "tests"
    tests.mkdir()
    (tests / "fixture.ps1").write_text(
        '[Environment]::SetEnvironmentVariable("PATH", $x, "Machine")\n',
        encoding="utf-8",
    )
    assert scan_persistent_path_mutations(tmp_path) == []
    assert_no_persistent_path_mutations(tmp_path)


def test_wix_gate_accepts_approved_component(tmp_path: Path) -> None:
    (tmp_path / "Product.wxs").write_text(APPROVED_WIX, encoding="utf-8")
    assert_wix_path_environment_allowlist(tmp_path)


def test_wix_gate_rejects_unapproved_environment_path(tmp_path: Path) -> None:
    (tmp_path / "Product.wxs").write_text(
        '<Wix xmlns="http://wixtoolset.org/schemas/v4/wxs">'
        '<Component Id="cmpOther"><Environment Id="envBad" Name="PATH" '
        'Value="C:\\bad" Permanent="no" Part="first" Action="set" System="yes" />'
        "</Component></Wix>\n",
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="PERSISTENT_PATH_MUTATION_FORBIDDEN"):
        assert_wix_path_environment_allowlist(tmp_path)


def test_wix_gate_rejects_user_scope(tmp_path: Path) -> None:
    (tmp_path / "Product.wxs").write_text(
        f'<Wix xmlns="http://wixtoolset.org/schemas/v4/wxs">'
        f'<Component Id="{ALLOWED_WIX_PATH_COMPONENT_ID}">'
        f'<Environment Id="envHermesBinPath" Name="PATH" Value="{HERMES_BIN_PATH}" '
        f'Permanent="no" Part="first" Action="set" System="no" />'
        f"</Component></Wix>\n",
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="PERSISTENT_PATH_MUTATION_FORBIDDEN"):
        assert_wix_path_environment_allowlist(tmp_path)


def test_wix_gate_rejects_duplicate_approved_component(tmp_path: Path) -> None:
    (tmp_path / "Product.wxs").write_text(
        f"""<?xml version="1.0" encoding="UTF-8"?>
<Wix xmlns="http://wixtoolset.org/schemas/v4/wxs">
  <Component Id="{ALLOWED_WIX_PATH_COMPONENT_ID}">
    <Environment Id="envHermesBinPath" Name="PATH" Value="{HERMES_BIN_PATH}" Permanent="no" Part="first" Action="set" System="yes" />
  </Component>
  <Component Id="{ALLOWED_WIX_PATH_COMPONENT_ID}2">
    <Environment Id="envHermesBinPath" Name="PATH" Value="{HERMES_BIN_PATH}" Permanent="no" Part="first" Action="set" System="yes" />
  </Component>
</Wix>
""",
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="unapproved|exactly once"):
        assert_wix_path_environment_allowlist(tmp_path)


def test_wix_gate_rejects_missing_approved_component(tmp_path: Path) -> None:
    (tmp_path / "Product.wxs").write_text(
        '<Wix xmlns="http://wixtoolset.org/schemas/v4/wxs"><Component Id="X" /></Wix>\n',
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="exactly once"):
        assert_wix_path_environment_allowlist(tmp_path)


def test_wix_gate_rejects_setx_and_registry_writers(tmp_path: Path) -> None:
    prod = tmp_path / "scripts"
    prod.mkdir()
    (prod / "bad.cmd").write_text("setx PATH C:\\bad\n", encoding="utf-8")
    (tmp_path / "Product.wxs").write_text(APPROVED_WIX, encoding="utf-8")
    with pytest.raises(ValueError, match="PERSISTENT_PATH_MUTATION_FORBIDDEN"):
        assert_hermes_path_policy(tmp_path)
