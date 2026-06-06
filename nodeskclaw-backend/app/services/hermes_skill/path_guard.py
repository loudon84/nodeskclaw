from pathlib import Path

from app.core.exceptions import ForbiddenError


_FORBIDDEN_DIRS = frozenset({"/etc", "/root", "/boot", "/proc", "/sys"})
_FORBIDDEN_EXTENSIONS = frozenset({".env", ".pem", ".key", ".secret"})


class PathGuard:
    @staticmethod
    def validate_within_root(path: Path, root: Path) -> Path:
        resolved = path.resolve()
        root_resolved = root.resolve()
        if resolved.is_symlink():
            raise ForbiddenError(
                "禁止软链接",
                "errors.skill.symlink_forbidden",
            )
        try:
            resolved.relative_to(root_resolved)
        except ValueError:
            raise ForbiddenError(
                "路径越界",
                "errors.skill.path_outside_root",
            )
        return resolved

    @staticmethod
    def validate_file_for_download(path: Path, root: Path) -> Path:
        resolved = path.resolve()
        root_resolved = root.resolve()
        if resolved.is_symlink():
            raise ForbiddenError(
                "禁止软链接",
                "errors.skill.symlink_forbidden",
            )
        try:
            resolved.relative_to(root_resolved)
        except ValueError:
            raise ForbiddenError(
                "路径越界",
                "errors.skill.path_outside_root",
            )
        PathGuard.reject_system_dirs(resolved)
        PathGuard.reject_forbidden_extensions(resolved)
        return resolved

    @staticmethod
    def validate_output_file(path: Path, outputs_dir: Path) -> Path:
        resolved = path.resolve()
        outputs_resolved = outputs_dir.resolve()
        if resolved.is_symlink():
            raise ForbiddenError(
                "禁止软链接",
                "errors.skill.symlink_forbidden",
            )
        try:
            resolved.relative_to(outputs_resolved)
        except ValueError:
            raise ForbiddenError(
                "路径越界",
                "errors.skill.path_outside_root",
            )
        return resolved

    @staticmethod
    def reject_system_dirs(path: Path) -> None:
        resolved = str(path.resolve())
        for forbidden in _FORBIDDEN_DIRS:
            if resolved.startswith(forbidden):
                raise ForbiddenError(
                    "禁止访问系统目录",
                    "errors.skill.system_dir_forbidden",
                )

    @staticmethod
    def reject_forbidden_extensions(path: Path) -> None:
        if path.suffix.lower() in _FORBIDDEN_EXTENSIONS:
            raise ForbiddenError(
                "禁止下载密钥文件",
                "errors.skill.forbidden_file_type",
            )
