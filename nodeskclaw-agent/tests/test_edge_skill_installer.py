from __future__ import annotations

import io
import json
import os
import stat
import zipfile

import pytest

from app.services.edge_skill_installer import EdgeSkillInstaller


def _build_zip(entries: dict[str, str]) -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as zf:
        for name, content in entries.items():
            zf.writestr(name, content)
    return buffer.getvalue()


def test_install_activates_current_and_preserves_old_on_failure(tmp_path):
    installer = EdgeSkillInstaller(base_dir=tmp_path)
    skill_id = "weather-skill"
    v1_zip = _build_zip({"index.js": "v1"})
    v2_zip = _build_zip({"index.js": "v2"})

    installer.install(skill_id=skill_id, version="1", zip_bytes=v1_zip)
    assert installer.is_installed(skill_id=skill_id, version="1")
    assert (tmp_path / skill_id / "current.json").read_text(encoding="utf-8") == json.dumps({"version": "1"})

    with pytest.raises(ValueError, match="Package checksum mismatch"):
        installer.install(
            skill_id=skill_id,
            version="2",
            zip_bytes=v2_zip,
            expected_sha256="0" * 64,
        )

    assert installer.is_installed(skill_id=skill_id, version="1")
    assert not installer.is_installed(skill_id=skill_id, version="2")

    installer.install(skill_id=skill_id, version="2", zip_bytes=v2_zip)
    assert installer.is_installed(skill_id=skill_id, version="2")
    assert (tmp_path / skill_id / "2" / "index.js").read_text(encoding="utf-8") == "v2"


def test_install_rejects_zip_slip_and_symlink(tmp_path):
    installer = EdgeSkillInstaller(base_dir=tmp_path)

    bad_slip = io.BytesIO()
    with zipfile.ZipFile(bad_slip, "w") as zf:
        zf.writestr("../evil.txt", "evil")
    with pytest.raises(ValueError, match="Zip path traversal detected"):
        installer.install(skill_id="bad", version="1", zip_bytes=bad_slip.getvalue())

    symlink_zip = io.BytesIO()
    with zipfile.ZipFile(symlink_zip, "w") as zf:
        info = zipfile.ZipInfo("link.txt")
        info.external_attr = stat.S_IFLNK << 16
        zf.writestr(info, "target")
    with pytest.raises(ValueError, match="Zip symlink entry rejected"):
        installer.install(skill_id="bad", version="1", zip_bytes=symlink_zip.getvalue())


def test_uninstall_only_removes_managed_root(tmp_path):
    installer = EdgeSkillInstaller(base_dir=tmp_path)
    zip_bytes = _build_zip({"main.py": "ok"})
    installer.install(skill_id="skill-a", version="3", zip_bytes=zip_bytes)
    outside = tmp_path / "outside.txt"
    outside.write_text("keep", encoding="utf-8")

    assert installer.uninstall(skill_id="skill-a", version="3") is True
    assert not installer.is_installed(skill_id="skill-a", version="3")
    assert outside.read_text(encoding="utf-8") == "keep"


@pytest.mark.parametrize(
    ("skill_id", "version"),
    [
        ("..", "1"),
        ("skill-a/subdir", "1"),
        ("skill-a", ".."),
        ("skill-a", "1/subdir"),
    ],
)
def test_install_rejects_non_opaque_identifiers(tmp_path, skill_id, version):
    installer = EdgeSkillInstaller(base_dir=tmp_path / "managed")

    with pytest.raises(ValueError, match="Invalid managed path identifier"):
        installer.install(
            skill_id=skill_id,
            version=version,
            zip_bytes=_build_zip({"main.py": "ok"}),
        )


def test_install_rolls_back_when_current_pointer_switch_fails(tmp_path, monkeypatch):
    installer = EdgeSkillInstaller(base_dir=tmp_path)
    installer.install(skill_id="skill-a", version="1", zip_bytes=_build_zip({"main.py": "v1"}))
    original_replace = os.replace

    def fail_current_switch(source, destination):
        if str(destination).endswith("current.json"):
            raise OSError("pointer switch failed")
        return original_replace(source, destination)

    monkeypatch.setattr("app.services.edge_skill_installer.os.replace", fail_current_switch)

    with pytest.raises(OSError, match="pointer switch failed"):
        installer.install(skill_id="skill-a", version="2", zip_bytes=_build_zip({"main.py": "v2"}))

    assert (tmp_path / "skill-a" / "current.json").read_text(encoding="utf-8") == json.dumps({"version": "1"})
    assert not (tmp_path / "skill-a" / "2").exists()


def test_uninstall_old_generation_preserves_current(tmp_path):
    installer = EdgeSkillInstaller(base_dir=tmp_path)
    installer.install(skill_id="skill-a", version="2", zip_bytes=_build_zip({"main.py": "v2"}))

    assert installer.uninstall(skill_id="skill-a", version="1") is False
    assert installer.is_installed(skill_id="skill-a", version="2")
    assert (tmp_path / "skill-a" / "current.json").read_text(encoding="utf-8") == json.dumps({"version": "2"})


def test_install_rejects_managed_skill_root_symlink(tmp_path, monkeypatch):
    managed = tmp_path / "managed"
    managed.mkdir()
    skill_root = managed / "skill-a"
    original_is_symlink = type(skill_root).is_symlink

    def fake_is_symlink(path):
        return path == skill_root or original_is_symlink(path)

    monkeypatch.setattr(type(skill_root), "is_symlink", fake_is_symlink)

    installer = EdgeSkillInstaller(base_dir=managed)
    with pytest.raises(ValueError, match="Managed skill directory"):
        installer.install(skill_id="skill-a", version="1", zip_bytes=_build_zip({"main.py": "ok"}))
