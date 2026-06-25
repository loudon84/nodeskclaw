import logging
import os
import shutil
from datetime import datetime
from pathlib import Path

from app.core.exceptions import BadRequestError

logger = logging.getLogger(__name__)


def backup_text_file(file_path: Path) -> Path | None:
    if not file_path.is_file():
        return None
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_path = file_path.parent / f"{file_path.name}.bak.{stamp}"
    backup_path.write_text(file_path.read_text(encoding="utf-8"), encoding="utf-8")
    return backup_path


def atomic_write_text_file(
    file_path: Path,
    content: str,
    *,
    mode: int = 0o644,
    backup: bool = True,
) -> None:
    file_path.parent.mkdir(parents=True, exist_ok=True)
    if backup and file_path.is_file():
        backup_text_file(file_path)

    tmp_path = file_path.with_suffix(file_path.suffix + ".tmp")
    tmp_path.write_text(content, encoding="utf-8")
    os.replace(tmp_path, file_path)
    try:
        os.chmod(file_path, mode)
    except OSError as exc:
        logger.warning("chmod %o failed for %s: %s", mode, file_path, exc)


def remove_directory(dir_path: Path) -> None:
    if not dir_path.exists():
        return
    if not dir_path.is_dir():
        raise BadRequestError(
            f"路径不是目录: {dir_path}",
            "errors.mcp_router.skill_delete_failed",
        )
    shutil.rmtree(dir_path)
