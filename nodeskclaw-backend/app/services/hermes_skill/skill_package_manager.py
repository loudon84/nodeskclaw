import hashlib
import logging
from pathlib import Path

logger = logging.getLogger(__name__)


class SkillPackageManager:
    @staticmethod
    def compute_hash(skill_dir: Path) -> str:
        hasher = hashlib.sha256()
        for file_path in sorted(skill_dir.rglob("*")):
            if file_path.is_file():
                try:
                    hasher.update(file_path.read_bytes())
                except (OSError, PermissionError) as exc:
                    logger.warning("跳过不可读文件 %s: %s", file_path, exc)
        return hasher.hexdigest()

    @staticmethod
    def read_file(path: Path) -> str | None:
        try:
            return path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            return None
