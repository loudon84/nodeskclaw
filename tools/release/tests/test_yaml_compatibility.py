"""YAML compatibility / independent PyYAML oracle (PRD-OPSI-v2.1.6 FR-216-16/17/21)."""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from tools.release.hermes.managed_config import (
    assert_managed_defaults_roundtrip,
    compile_managed_defaults,
    dump_managed_yaml,
    render_managed_defaults_yaml,
)
from tools.release.hermes.runtime_profile import load_profiles, resolve_profile
from tools.release.simple_yaml import (
    _format_scalar,
    _needs_quotes,
    _needs_quotes_pre_v216,
    dump_yaml,
)

ROOT = Path(__file__).resolve().parents[3]
CORPUS_PATH = Path(__file__).resolve().parent / "fixtures" / "yaml_q_corpus.yaml"
PROFILES = ROOT / "release" / "hermes-runtime-profiles.yaml"


def _load_corpus() -> dict:
    data = yaml.safe_load(CORPUS_PATH.read_text(encoding="utf-8"))
    assert isinstance(data, dict)
    return data


def test_corpus_file_parses_with_standard_parser():
    data = _load_corpus()
    assert data["schema"] == "smc.opsi.yaml-q-corpus.v1"
    assert data["strings"]["scoped_npm"] == "@modelcontextprotocol/server-filesystem"


@pytest.mark.parametrize(
    "key",
    [
        "scoped_npm",
        "at_user",
        "backtick",
        "windows_path",
        "url",
        "hash",
        "colon",
        "bool_string",
        "null_string",
        "number_string",
        "leading_space",
        "trailing_space",
        "unicode",
        "env",
        "quote",
        "apostrophe",
        "ampersand",
        "asterisk",
        "bang",
        "pipe",
        "fold",
        "percent",
        "question",
    ],
)
def test_yaml_q_corpus_production_roundtrip(key: str):
    """YAML-Q01–Q15+: dump → yaml.safe_load → value/type equality."""
    original = _load_corpus()["strings"][key]
    payload = {"value": original}
    dumped = dump_managed_yaml(payload)
    loaded = yaml.safe_load(dumped)
    assert loaded == payload
    assert type(loaded["value"]) is str
    assert loaded["value"] == original


def test_legacy_needs_quotes_covers_forbidden_prefixes():
    for sample in (
        "@modelcontextprotocol/server-filesystem",
        "@foo",
        "`command",
        "#value",
        "&ref",
        "*star",
        "!tag",
        "|pipe",
        ">fold",
        "%x",
        "?query",
        "true",
        "null",
        "123",
        " value",
        "value ",
        "${API_SERVER_KEY}",
    ):
        assert _needs_quotes(sample), sample


def test_reg_yaml_001_scoped_npm_legacy_hotfix_roundtrip():
    """Legacy dump_yaml with fixed _needs_quotes must quote scoped npm packages."""
    value = "@modelcontextprotocol/server-filesystem"
    text = dump_yaml({"args": [value]})
    loaded = yaml.safe_load(text)
    assert loaded == {"args": [value]}
    assert '"' in text or "'" in text


def test_reg_yaml_001_old_implementation_red():
    """Prove pre-v2.1.6 quoting fails independent PyYAML parse (FR-216-17)."""
    value = "@modelcontextprotocol/server-filesystem"
    assert _needs_quotes_pre_v216(value) is False
    # Simulate old _format_scalar using pre-v216 quoting.
    if _needs_quotes_pre_v216(value):
        pytest.fail("pre-v216 must NOT quote @scoped npm")
    bare = f"- {value}\n"
    with pytest.raises(yaml.YAMLError):
        yaml.safe_load(bare)
    # Document that current hotfix quotes it.
    assert _needs_quotes(value) is True
    fixed = f"- {_format_scalar(value)}\n"
    assert yaml.safe_load(fixed) == [value]


def test_nested_corpus_roundtrip():
    nested = _load_corpus()["nested"]
    dumped = dump_managed_yaml({"nested": nested})
    loaded = yaml.safe_load(dumped)
    assert loaded["nested"] == nested
    assert loaded["nested"]["empty_list"] == []
    assert loaded["nested"]["empty_map"] == {}


def test_unexpected_nested_indent_fails_standard_parser():
    """REG-YAML-003: unexpected nested indent → standard parser FAIL."""
    bad = "root:\n  child: value\n   sibling: bad\n"
    with pytest.raises(yaml.YAMLError):
        yaml.safe_load(bad)


def test_managed_defaults_production_profile_semantic_gate():
    profile = resolve_profile(load_profiles(PROFILES), "smc-managed")
    payload = compile_managed_defaults(profile, profile_name="smc-managed")
    text = render_managed_defaults_yaml(profile, profile_name="smc-managed")
    assert_managed_defaults_roundtrip(text, payload)
    loaded = yaml.safe_load(text)
    args = loaded["enforced"]["mcp_servers"]["workspace"]["args"]
    assert args[0] == "@modelcontextprotocol/server-filesystem"
    assert type(args[0]) is str
    # Must appear quoted in serialized form (not bare @ plain scalar).
    assert '@modelcontextprotocol/server-filesystem"' in text or (
        "'@modelcontextprotocol/server-filesystem'" in text
    )


def test_production_serializer_is_pyyaml_not_simple_yaml_oracle():
    """Production path must not rely on simple_yaml._parse_block as validity oracle."""
    profile = resolve_profile(load_profiles(PROFILES), "smc-managed")
    text = render_managed_defaults_yaml(profile, profile_name="smc-managed")
    # Independent oracle only.
    loaded = yaml.safe_load(text)
    assert loaded["schema"] == "smc.opsi.managed-config.v2"
    assert isinstance(loaded["defaults"], dict)
    assert isinstance(loaded["enforced"], dict)
