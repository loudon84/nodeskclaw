import hashlib
import logging
from pathlib import Path

from app.core.config import settings

logger = logging.getLogger(__name__)


class HubManager:
    def __init__(self, hub_root: str | None = None):
        self.hub_root = Path(hub_root or settings.HERMES_SKILL_HUB_ROOT)

    def ensure_dirs(self) -> None:
        for subdir in ("central", "marketplace", "imported", "collections", "cache"):
            (self.hub_root / subdir).mkdir(parents=True, exist_ok=True)

    def canonical_path(self, source_type: str, category: str, skill_id: str) -> Path:
        safe_skill_id = skill_id.replace(".", "-")
        return self.hub_root / source_type / category / safe_skill_id

    def validate_path(self, path: Path) -> Path:
        resolved = path.resolve()
        hub_resolved = self.hub_root.resolve()
        if not str(resolved).startswith(str(hub_resolved)):
            raise ValueError(f"路径跳出 Hub 根目录: {resolved}")
        forbidden = ("/etc", "/root", "/usr")
        for prefix in forbidden:
            if str(resolved).startswith(prefix):
                raise ValueError(f"禁止写入系统目录: {resolved}")
        return resolved
