"""GeneInstallAdapter -- abstract interface for runtime-specific gene installation logic.

Each AI runtime (OpenClaw, Hermes) implements its own adapter to handle:
- Skill file deployment
- Tool availability (e.g. OpenClaw's tool_allow whitelist)
- Python script deployment
- Cache invalidation / hot-reload triggers
- Skill removal on uninstall
"""

from __future__ import annotations

import logging
import re
from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

from app.core.exceptions import BadRequestError, UnsupportedCapabilityError

if TYPE_CHECKING:
    from app.services.nfs_mount import RemoteFS

logger = logging.getLogger(__name__)
SAFE_SKILL_NAME_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")


def validate_skill_name_segment(value: object, message: str = "非法 skill name") -> str:
    skill_name = str(value or "").strip()
    if not skill_name:
        raise BadRequestError(f"{message}: skill name 不能为空")
    if skill_name in (".", "..") or skill_name.startswith("."):
        raise BadRequestError(f"{message}: skill name 不能是隐藏或相对路径段")
    if "/" in skill_name or "\\" in skill_name:
        raise BadRequestError(f"{message}: skill name 不能包含路径分隔符")
    if any(ord(ch) < 32 or ord(ch) == 127 for ch in skill_name):
        raise BadRequestError(f"{message}: skill name 不能包含控制字符")
    if not SAFE_SKILL_NAME_PATTERN.fullmatch(skill_name):
        raise BadRequestError(f"{message}: skill name 只能包含字母、数字、点、下划线或连字符")
    return skill_name


class GeneInstallAdapter(ABC):
    """Runtime-specific gene installation adapter."""

    runtime_id = "unknown"

    @abstractmethod
    async def deploy_skill(
        self, fs: RemoteFS, skill_name: str, content: str, description: str = "",
    ) -> None:
        """Deploy a skill file to the runtime's skill directory."""

    async def allow_tools(self, fs: RemoteFS, tool_names: list[str]) -> None:
        """Make tools immediately available in the runtime."""
        if tool_names:
            raise UnsupportedCapabilityError(
                runtime_id=self.runtime_id,
                capability="tool_allow",
                operation="gene.allow_tools",
            )

    @abstractmethod
    async def deploy_scripts(self, fs: RemoteFS, scripts: dict[str, str]) -> None:
        """Deploy executable Python scripts to the instance.

        Args:
            fs: Remote filesystem handle.
            scripts: Mapping of filename -> script content.
        """

    async def apply_config(self, fs: RemoteFS, config_patch: dict) -> None:
        """Apply runtime-specific configuration patches."""
        if config_patch:
            raise UnsupportedCapabilityError(
                runtime_id=self.runtime_id,
                capability="runtime_config_patch",
                operation="gene.apply_config",
            )

    @abstractmethod
    async def invalidate_cache(self, fs: RemoteFS, skill_name: str, event: str = "installed") -> None:
        """Invalidate runtime caches after installation and notify the agent."""

    @abstractmethod
    async def remove_skill(self, fs: RemoteFS, skill_name: str) -> None:
        """Remove a skill on uninstall."""

    @abstractmethod
    async def post_remove_cleanup(self, fs: RemoteFS, skill_name: str) -> None:
        """Post-removal cleanup: cache invalidation and uninstall notification."""
