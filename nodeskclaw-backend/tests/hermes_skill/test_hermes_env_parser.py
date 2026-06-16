from pathlib import Path

import pytest

from app.core.exceptions import BadRequestError
from app.services.hermes_external.hermes_env_parser import parse_env_file


def test_parse_env_file_reads_gateway_and_webui_ports(tmp_path: Path):
    env_file = tmp_path / ".env"
    env_file.write_text(
        'PROFILE_NAME=common-writer\n'
        'HERMES_WEBUI_PORT=8900\n'
        'HERMES_GATEWAY_PORT=18900\n'
        '# comment\n'
        'HERMES_GATEWAY_INTERNAL_PORT=8642\n',
        encoding="utf-8",
    )
    data = parse_env_file(env_file)
    assert data.profile_name == "common-writer"
    assert data.webui_port == 8900
    assert data.gateway_port == 18900
    assert data.gateway_internal_port == 8642
    assert data.container_name == "hermes-common-writer"


def test_parse_env_file_strips_quotes(tmp_path: Path):
    env_file = tmp_path / ".env"
    env_file.write_text('HERMES_GATEWAY_PORT="18900"\n', encoding="utf-8")
    data = parse_env_file(env_file)
    assert data.gateway_port == 18900


def test_parse_env_file_missing_file_raises():
    with pytest.raises(BadRequestError) as exc:
        parse_env_file(Path("/nonexistent/.env"))
    assert exc.value.message_key == "errors.hermes.env_not_found"


def test_parse_env_file_require_gateway_port(tmp_path: Path):
    env_file = tmp_path / ".env"
    env_file.write_text("HERMES_WEBUI_PORT=8900\n", encoding="utf-8")
    with pytest.raises(BadRequestError) as exc:
        parse_env_file(env_file, require_gateway_port=True)
    assert exc.value.message_key == "errors.hermes.gateway_port_missing"
