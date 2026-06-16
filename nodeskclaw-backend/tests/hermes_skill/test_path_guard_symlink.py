import sys

import pytest

from app.core.exceptions import ForbiddenError
from app.services.hermes_skill.path_guard import PathGuard


def test_validate_zip_entry_rejects_empty_name():
    with pytest.raises(ForbiddenError):
        PathGuard.validate_zip_entry_name("")


def test_validate_zip_entry_rejects_windows_drive_path():
    with pytest.raises(ForbiddenError):
        PathGuard.validate_zip_entry_name("C:\\secret.txt")


def test_validate_zip_entry_rejects_control_chars():
    with pytest.raises(ForbiddenError):
        PathGuard.validate_zip_entry_name("bad\x01name.txt")


@pytest.mark.skipif(sys.platform == "win32", reason="symlink test requires Unix")
def test_validate_output_file_rejects_symlink(tmp_path):
    target = tmp_path / "real.txt"
    target.write_text("ok", encoding="utf-8")
    link = tmp_path / "link.txt"
    link.symlink_to(target)
    with pytest.raises(ForbiddenError):
        PathGuard.validate_output_file(link, tmp_path)
