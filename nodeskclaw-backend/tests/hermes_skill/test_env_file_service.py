import sys
from pathlib import Path

import pytest

from app.services.hermes_agents.env_file_service import (
    atomic_write_env,
    format_env_content,
    merge_env,
    read_env,
    remove_env_keys,
)


def test_merge_env_preserves_existing_keys():
    merged = merge_env({"FOO": "bar"}, {"NODESKCLAW_MCP_URL": "http://example.com/mcp"})
    assert merged["FOO"] == "bar"
    assert merged["NODESKCLAW_MCP_URL"] == "http://example.com/mcp"


def test_atomic_write_env_creates_and_merges(tmp_path: Path):
    env_path = tmp_path / ".env"
    env_path.write_text("EXISTING=value\n", encoding="utf-8")

    atomic_write_env(
        env_path,
        {
            "NODESKCLAW_MCP_URL": "http://host.docker.internal:4510/api/v1/hermes/mcp",
            "NODESKCLAW_MCP_TOKEN": "ndsk_mcp_demo_abcd.secret",
            "NODESKCLAW_MCP_ENABLED": "true",
            "NODESKCLAW_MCP_NAME": "nodeskclaw-skills",
        },
    )

    content = env_path.read_text(encoding="utf-8")
    assert "EXISTING=value" in content
    assert "NODESKCLAW_MCP_URL=" in content
    assert "NODESKCLAW_MCP_TOKEN=" in content
    if sys.platform != "win32":
        assert env_path.stat().st_mode & 0o777 == 0o600


def test_atomic_write_env_creates_backup(tmp_path: Path):
    env_path = tmp_path / ".env"
    env_path.write_text("OLD=1\n", encoding="utf-8")

    atomic_write_env(env_path, {"NODESKCLAW_MCP_ENABLED": "true"})

    backups = list(tmp_path.glob(".env.bak.*"))
    assert len(backups) == 1
    assert "OLD=1" in backups[0].read_text(encoding="utf-8")


def test_remove_env_keys(tmp_path: Path):
    env_path = tmp_path / ".env"
    env_path.write_text(
        "KEEP=yes\nNODESKCLAW_MCP_TOKEN=secret\nNODESKCLAW_MCP_URL=http://x\n",
        encoding="utf-8",
    )

    remove_env_keys(env_path)

    data = read_env(env_path)
    assert data["KEEP"] == "yes"
    assert "NODESKCLAW_MCP_TOKEN" not in data
    assert "NODESKCLAW_MCP_URL" not in data


def test_format_env_content_quotes_special_values():
    content = format_env_content({"KEY": "value with spaces"})
    assert 'KEY="value with spaces"' in content
