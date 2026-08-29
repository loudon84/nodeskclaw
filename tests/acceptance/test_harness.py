from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from tools.acceptance.harness import check_docker_available, validate_topology


def test_harness_validate_topology_structure(tmp_path):
    compose_file = tmp_path / "docker-compose.yml"
    compose_file.write_text(
        """
services:
  postgres:
    platform: linux/amd64
  nodeskclaw-backend:
    platform: linux/amd64
  nodeskclaw-agent:
    platform: linux/amd64
  nodeskclaw-agent-b:
    platform: linux/amd64
  nodeskclaw-agent-edge:
    platform: linux/amd64
    environment:
      SKILL_AGENT_INTERNAL_TOKEN: ${SKILL_AGENT_INTERNAL_TOKEN:-postman-acceptance-agent-token-secure-32b}
volumes:
  artifact_data:
"""
    )
    res = validate_topology(compose_file)
    assert res["valid"] is True
    assert res["checks"]["has_postgres"] is True
    assert res["checks"]["has_agent_b"] is True
    assert res["checks"]["uses_amd64_platform"] is True


def test_harness_validate_topology_missing_service(tmp_path):
    compose_file = tmp_path / "docker-compose.yml"
    compose_file.write_text(
        """
services:
  postgres:
    platform: linux/amd64
"""
    )
    res = validate_topology(compose_file)
    assert res["valid"] is False
    assert res["checks"]["has_backend"] is False


def test_harness_docker_unavailable_graceful():
    with patch("tools.acceptance.harness.shutil.which", return_value=None):
        assert check_docker_available() is False
