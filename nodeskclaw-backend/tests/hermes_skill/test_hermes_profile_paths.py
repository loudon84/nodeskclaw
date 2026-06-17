from pathlib import Path

import pytest

from app.core.exceptions import BadRequestError
from app.services.hermes_external.path_resolver import (
    HermesExternalPathResolver,
    validate_profile_name,
)


def test_validate_profile_name_accepts_valid_names():
    assert validate_profile_name("default") == "default"
    assert validate_profile_name("writer") == "writer"
    assert validate_profile_name("zhang-zhen") == "zhang-zhen"


def test_validate_profile_name_rejects_invalid_names():
    with pytest.raises(BadRequestError):
        validate_profile_name("../writer")
    with pytest.raises(BadRequestError):
        validate_profile_name("bad/name")


def test_resolve_profile_default_and_extended(tmp_path: Path):
    host_data_dir = tmp_path / "data" / "hermes"
    host_data_dir.mkdir(parents=True)
    extended = host_data_dir / "profiles" / "writer"
    extended.mkdir(parents=True)
    (extended / ".env").write_text("API_SERVER_ENABLED=true\n", encoding="utf-8")

    resolver = HermesExternalPathResolver()
    default_paths = resolver.resolve_profile_from_host_data_dir(host_data_dir, "default")
    writer_paths = resolver.resolve_profile_from_host_data_dir(host_data_dir, "writer")

    assert default_paths.profile_type == "default"
    assert default_paths.env_file == host_data_dir / ".env"
    assert writer_paths.profile_type == "extended"
    assert writer_paths.env_file == extended / ".env"
    assert writer_paths.core_file_backup_dir == extended / "backups" / "core-files"
