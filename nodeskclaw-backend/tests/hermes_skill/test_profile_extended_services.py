from pathlib import Path

import pytest

from app.core.exceptions import BadRequestError
from app.services.hermes_external import (
    profile_backup_service,
    profile_file_service,
    profile_package_service,
    profile_runtime_service,
    profile_service,
    profile_skill_service,
)


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


def test_profile_skills_isolated_between_profiles(tmp_path: Path):
    host_data_dir = _prepare_host_data_dir(tmp_path)
    default_skills = host_data_dir / "skills" / "obsidian"
    default_skills.mkdir(parents=True)
    (default_skills / "SKILL.md").write_text("# obsidian\n", encoding="utf-8")

    extended = host_data_dir / "profiles" / "writer"
    extended.mkdir(parents=True)
    (extended / ".env").write_text("X=1\n", encoding="utf-8")
    writer_skills = extended / "skills" / "writer-skill"
    writer_skills.mkdir(parents=True)
    (writer_skills / "SKILL.md").write_text("# writer\n", encoding="utf-8")

    default_list = profile_skill_service.list_profile_skills(host_data_dir, "default")
    writer_list = profile_skill_service.list_profile_skills(host_data_dir, "writer")
    assert {i.slug for i in default_list.items} == {"obsidian"}
    assert {i.slug for i in writer_list.items} == {"writer-skill"}


def test_profile_file_path_escape_rejected(tmp_path: Path):
    host_data_dir = _prepare_host_data_dir(tmp_path)
    with pytest.raises(BadRequestError):
        profile_file_service.list_profile_files(host_data_dir, "default", scope="workspace", path="../.env")


def test_profile_file_write_protected_core_file(tmp_path: Path):
    host_data_dir = _prepare_host_data_dir(tmp_path)
    with pytest.raises(BadRequestError):
        profile_file_service.write_profile_file(host_data_dir, "default", scope="system", path=".env", content="X=1\n")


def test_backup_create_and_restore(tmp_path: Path):
    host_data_dir = _prepare_host_data_dir(tmp_path)
    profile_service.create_profile_for_host_data_dir(host_data_dir, "writer")
    writer_env = host_data_dir / "profiles" / "writer" / ".env"
    writer_env.write_text("API_SERVER_ENABLED=true\nWRITER=1\n", encoding="utf-8")

    created = profile_backup_service.create_profile_backup(host_data_dir, "writer")
    import zipfile
    with zipfile.ZipFile(created.file_path, "r") as zf:
        assert ".env" in zf.namelist(), zf.namelist()
        assert b"WRITER=1" in zf.read(".env")
    writer_env.write_text("API_SERVER_ENABLED=false\n", encoding="utf-8")

    import asyncio
    restored = asyncio.run(profile_backup_service.restore_profile_backup_async(
        host_data_dir, "writer", created.backup_id,
    ))
    assert restored.success is True
    assert "WRITER=1" in writer_env.read_text(encoding="utf-8")


def test_clone_export_import_roundtrip(tmp_path: Path):
    host_data_dir = _prepare_host_data_dir(tmp_path)
    profile_service.create_profile_for_host_data_dir(host_data_dir, "writer")
    writer_dir = host_data_dir / "profiles" / "writer"
    (writer_dir / "skills" / "s1").mkdir(parents=True)
    (writer_dir / "skills" / "s1" / "SKILL.md").write_text("# s1\n", encoding="utf-8")

    cloned = profile_package_service.clone_profile(host_data_dir, "writer", target_profile="researcher")
    assert cloned.success is True
    assert (host_data_dir / "profiles" / "researcher" / "skills" / "s1" / "SKILL.md").is_file()

    exported = profile_package_service.export_profile(host_data_dir, "writer", include_skills=True)
    import zipfile
    with zipfile.ZipFile(exported.file_path, "r") as zf:
        names = zf.namelist()
    assert "manifest.json" in names

    imported = profile_package_service.import_profile(
        host_data_dir,
        Path(exported.file_path).read_bytes(),
        target_profile="writer-copy",
    )
    assert imported.success is True
    assert (host_data_dir / "profiles" / "writer-copy" / "config.yaml").is_file()


def test_activate_profile_writes_marker_and_syncs_core_files(tmp_path: Path):
    host_data_dir = _prepare_host_data_dir(tmp_path)
    profile_service.create_profile_for_host_data_dir(host_data_dir, "writer")
    writer_env = host_data_dir / "profiles" / "writer" / ".env"
    writer_env.write_text("API_SERVER_ENABLED=true\nPROFILE=writer\n", encoding="utf-8")
    (host_data_dir / "profiles" / "writer" / "config.yaml").write_text("models: {writer: true}\n", encoding="utf-8")
    (host_data_dir / "profiles" / "writer" / "SOUL.md").write_text("Writer soul\n", encoding="utf-8")

    import asyncio
    result = asyncio.run(profile_runtime_service.activate_profile(
        host_data_dir, "writer", restart_after_activate=False,
    ))
    assert result.success is True
    assert result.active_profile == "writer"
    marker = host_data_dir / ".active_profile"
    assert marker.is_file()
    assert marker.read_text(encoding="utf-8").strip() == "writer"
    assert "PROFILE=writer" in (host_data_dir / ".env").read_text(encoding="utf-8")

    listed = profile_service.list_profiles_for_host_data_dir(host_data_dir)
    writer_item = next(i for i in listed.items if i.profile == "writer")
    assert writer_item.status == "active_runtime"


def test_activate_missing_files_rejected(tmp_path: Path):
    host_data_dir = _prepare_host_data_dir(tmp_path)
    incomplete = host_data_dir / "profiles" / "bad"
    incomplete.mkdir(parents=True)
    (incomplete / ".env").write_text("X=1\n", encoding="utf-8")

    import asyncio
    with pytest.raises(BadRequestError):
        asyncio.run(profile_runtime_service.activate_profile(host_data_dir, "bad", restart_after_activate=False))


def test_active_profile_from_marker_file(tmp_path: Path):
    host_data_dir = _prepare_host_data_dir(tmp_path)
    profile_service.create_profile_for_host_data_dir(host_data_dir, "writer")
    (host_data_dir / "profiles" / "writer" / "config.yaml").write_text("models: {}\n", encoding="utf-8")
    (host_data_dir / "profiles" / "writer" / "SOUL.md").write_text("soul\n", encoding="utf-8")
    (host_data_dir / ".active_profile").write_text("writer\n", encoding="utf-8")

    result = profile_service.list_profiles_for_host_data_dir(host_data_dir)
    assert result.active_profile == "writer"
    writer_item = next(i for i in result.items if i.profile == "writer")
    assert writer_item.status == "active_runtime"


def test_upload_skill_zip_slip_rejected(tmp_path: Path):
    import io
    import zipfile

    host_data_dir = _prepare_host_data_dir(tmp_path)
    profile_service.create_profile_for_host_data_dir(host_data_dir, "writer")
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("../../evil/SKILL.md", "# evil\n")
    with pytest.raises(BadRequestError):
        profile_skill_service.upload_skill_zip(host_data_dir, "writer", buf.getvalue())


def test_delete_active_runtime_forbidden(tmp_path: Path):
    host_data_dir = _prepare_host_data_dir(tmp_path)
    profile_service.create_profile_for_host_data_dir(host_data_dir, "writer")
    writer_dir = host_data_dir / "profiles" / "writer"
    (writer_dir / ".env").write_text("API_SERVER_ENABLED=true\n", encoding="utf-8")
    (writer_dir / "config.yaml").write_text("models: {}\n", encoding="utf-8")
    (writer_dir / "SOUL.md").write_text("soul\n", encoding="utf-8")

    import asyncio
    asyncio.run(profile_runtime_service.activate_profile(host_data_dir, "writer", restart_after_activate=False))

    with pytest.raises(BadRequestError):
        profile_service.delete_profile_for_host_data_dir(host_data_dir, "writer", confirm_profile="writer")
