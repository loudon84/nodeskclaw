from pathlib import Path

import pytest

from app.core.exceptions import BadRequestError
from app.services.hermes_external import core_file_service, profile_service


def _prepare_host_data_dir(tmp_path: Path, *, model_name: str | None = None) -> Path:
    host_data_dir = tmp_path / "data" / "hermes"
    host_data_dir.mkdir(parents=True)
    env_lines = ["API_SERVER_ENABLED=true\n"]
    if model_name:
        env_lines.append(f"API_SERVER_MODEL_NAME={model_name}\n")
    (host_data_dir / ".env").write_text("".join(env_lines), encoding="utf-8")
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
    default_item = result.items[0]
    assert default_item.status == "active_runtime"
    assert result.active_profile == "default"


def test_active_runtime_when_model_matches_agent_profile(tmp_path: Path):
    host_data_dir = _prepare_host_data_dir(tmp_path, model_name="common-writer")
    result = profile_service.list_profiles_for_host_data_dir(
        host_data_dir,
        agent_profile_name="common-writer",
    )
    assert result.items[0].status == "active_runtime"
    assert result.runtime_model_name == "common-writer"


def test_create_and_delete_profile(tmp_path: Path):
    host_data_dir = _prepare_host_data_dir(tmp_path)

    created = profile_service.create_profile_for_host_data_dir(host_data_dir, "writer")
    assert created.success is True
    assert (host_data_dir / "profiles" / "writer" / "config.yaml").is_file()

    deleted = profile_service.delete_profile_for_host_data_dir(
        host_data_dir,
        "writer",
        confirm_profile="writer",
    )
    assert deleted.success is True
    assert not (host_data_dir / "profiles" / "writer").exists()
    assert deleted.backup_file is not None


def test_delete_default_forbidden(tmp_path: Path):
    host_data_dir = _prepare_host_data_dir(tmp_path)
    with pytest.raises(BadRequestError):
        profile_service.delete_profile_for_host_data_dir(
            host_data_dir,
            "default",
            confirm_profile="default",
        )


def test_delete_confirm_mismatch(tmp_path: Path):
    host_data_dir = _prepare_host_data_dir(tmp_path)
    profile_service.create_profile_for_host_data_dir(host_data_dir, "writer")
    with pytest.raises(BadRequestError):
        profile_service.delete_profile_for_host_data_dir(
            host_data_dir,
            "writer",
            confirm_profile="wrong-name",
        )


def test_validate_env_rejects_export_and_bad_keys(tmp_path: Path):
    invalid_export = core_file_service.validate_core_file("env", "export KEY=value\n")
    assert invalid_export.valid is False

    invalid_key = core_file_service.validate_core_file("env", "A B=1\n")
    assert invalid_key.valid is False
    assert "A B" in invalid_key.message

    valid = core_file_service.validate_core_file("env", "API_SERVER_ENABLED=true\nKEY=\n")
    assert valid.valid is True


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


def test_symlink_profile_marked_invalid(tmp_path: Path):
    host_data_dir = _prepare_host_data_dir(tmp_path)
    profiles_dir = host_data_dir / "profiles"
    profiles_dir.mkdir(parents=True)
    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / ".env").write_text("X=1\n", encoding="utf-8")
    symlink = profiles_dir / "evil"
    symlink.symlink_to(outside)

    result = profile_service.list_profiles_for_host_data_dir(host_data_dir)
    evil = next(item for item in result.items if item.profile == "evil")
    assert evil.status == "invalid"
