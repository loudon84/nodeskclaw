import pytest
from pathlib import Path

from app.services.hermes_skill.path_guard import PathGuard
from app.core.exceptions import ForbiddenError


class TestValidateWithinRoot:
    def test_legal_file(self, tmp_path):
        root = tmp_path / "outputs"
        root.mkdir()
        f = root / "result.txt"
        f.write_text("ok")
        result = PathGuard.validate_within_root(f, root)
        assert result == f.resolve()

    def test_symlink_escape(self, tmp_path):
        root = tmp_path / "outputs"
        root.mkdir()
        target = tmp_path / "etc_passwd"
        target.write_text("root:x:0:0")
        link = root / "bad"
        link.symlink_to(target)
        with pytest.raises(ForbiddenError):
            PathGuard.validate_within_root(link, root)

    def test_path_outside_root(self, tmp_path):
        root = tmp_path / "outputs"
        root.mkdir()
        outside = tmp_path / "secret.txt"
        outside.write_text("secret")
        with pytest.raises(ForbiddenError):
            PathGuard.validate_within_root(outside, root)


class TestValidateFileForDownload:
    def test_system_dir_rejected(self, tmp_path):
        f = Path("/etc/passwd")
        with pytest.raises(ForbiddenError):
            PathGuard.validate_file_for_download(f, Path("/etc"))

    def test_forbidden_extension(self, tmp_path):
        root = tmp_path / "outputs"
        root.mkdir()
        f = root / "config.env"
        f.write_text("KEY=VAL")
        with pytest.raises(ForbiddenError):
            PathGuard.validate_file_for_download(f, root)

    def test_directory_rejected(self, tmp_path):
        root = tmp_path / "outputs"
        root.mkdir()
        subdir = root / "subdir"
        subdir.mkdir()
        with pytest.raises(ForbiddenError):
            PathGuard.validate_file_for_download(subdir, root)

    def test_legal_download(self, tmp_path):
        root = tmp_path / "outputs"
        root.mkdir()
        f = root / "report.pdf"
        f.write_text("pdf")
        result = PathGuard.validate_file_for_download(f, root)
        assert result == f.resolve()


class TestValidateZipEntryName:
    def test_absolute_path_rejected(self):
        with pytest.raises(ForbiddenError):
            PathGuard.validate_zip_entry_name("/etc/passwd")

    def test_parent_traversal_rejected(self):
        with pytest.raises(ForbiddenError):
            PathGuard.validate_zip_entry_name("../../etc/passwd")

    def test_mid_traversal_rejected(self):
        with pytest.raises(ForbiddenError):
            PathGuard.validate_zip_entry_name("foo/../../etc/passwd")

    def test_legal_relative_path(self):
        PathGuard.validate_zip_entry_name("outputs/result.txt")

    def test_legal_nested_path(self):
        PathGuard.validate_zip_entry_name("a/b/c/result.txt")


class TestRejectSystemDirs:
    def test_etc_rejected(self):
        with pytest.raises(ForbiddenError):
            PathGuard.reject_system_dirs(Path("/etc/passwd"))

    def test_root_rejected(self):
        with pytest.raises(ForbiddenError):
            PathGuard.reject_system_dirs(Path("/root/.ssh"))

    def test_proc_rejected(self):
        with pytest.raises(ForbiddenError):
            PathGuard.reject_system_dirs(Path("/proc/1/cmdline"))

    def test_var_run_rejected(self):
        with pytest.raises(ForbiddenError):
            PathGuard.reject_system_dirs(Path("/var/run/docker.sock"))

    def test_dev_rejected(self):
        with pytest.raises(ForbiddenError):
            PathGuard.reject_system_dirs(Path("/dev/null"))

    def test_legal_path_passes(self):
        PathGuard.reject_system_dirs(Path("/tmp/nodeskclaw-workspaces/ws1/.nodeskclaw/runs/t1/outputs/result.txt"))


class TestRejectForbiddenExtensions:
    def test_env_rejected(self):
        with pytest.raises(ForbiddenError):
            PathGuard.reject_forbidden_extensions(Path("config.env"))

    def test_pem_rejected(self):
        with pytest.raises(ForbiddenError):
            PathGuard.reject_forbidden_extensions(Path("cert.pem"))

    def test_key_rejected(self):
        with pytest.raises(ForbiddenError):
            PathGuard.reject_forbidden_extensions(Path("id_rsa.key"))

    def test_secret_rejected(self):
        with pytest.raises(ForbiddenError):
            PathGuard.reject_forbidden_extensions(Path("data.secret"))

    def test_legal_extension_passes(self):
        PathGuard.reject_forbidden_extensions(Path("report.pdf"))
