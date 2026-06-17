from pathlib import Path

import pytest

from app.services.hermes_external import core_file_service, profile_service


def _prepare_host_data_dir(tmp_path: Path) -> Path:
    host_data_dir = tmp_path / "data" / "hermes"
    host_data_dir.mkdir(parents=True)
    (host_data_dir / ".env").write_text("API_SERVER_ENABLED=true\n", encoding="utf-8")
    (host_data_dir / "config.yaml").write_text("models: {}\n", encoding="utf-8")
    (host_data_dir / "SOUL.md").write_text("You are a helpful assistant.\n", encoding="utf-8")
    return host_data_dir


def test_list_profiles_includes_default_and_extended(tmp_path: Path):
    host_data_dir = _prepare_host_data_dir(tmp_path)
    extended = host_data_dir / "profiles" / "writer"
    extended.mkdir(parents=True)
    (extended / ".env").write_text("API_SERVER_ENABLED=true\n", encoding="utf-8")

    result = profile_service.list_profiles_for_host_data_dir(host_data_dir)
    names = [item.profile for item in result.items]
    assert names == ["default", "writer"]


def test_create_and_delete_profile(tmp_path: Path):
    host_data_dir = _prepare_host_data_dir(tmp_path)

    created = profile_service.create_profile_for_host_data_dir(host_data_dir, "writer")
    assert created.success is True
    assert (host_data_dir / "profiles" / "writer" / "config.yaml").is_file()

    deleted = profile_service.delete_profile_for_host_data_dir(host_data_dir, "writer")
    assert deleted.success is True
    assert not (host_data_dir / "profiles" / "writer").exists()


def test_validate_and_save_core_file(tmp_path: Path):
    host_data_dir = _prepare_host_data_dir(tmp_path)

    invalid = core_file_service.validate_core_file("env", "BAD LINE")
    assert invalid.valid is False

    valid = core_file_service.validate_core_file("env", "API_SERVER_ENABLED=true\n")
    assert valid.valid is True

    import asyncio

    saved = asyncio.run(core_file_service.save_core_file_for_host_data_dir(
        host_data_dir,
        "default",
        "env",
        "API_SERVER_ENABLED=false\n",
    ))
    assert saved.success is True
    assert (host_data_dir / ".env").read_text(encoding="utf-8") == "API_SERVER_ENABLED=false\n"
    assert saved.backup_file is not None
