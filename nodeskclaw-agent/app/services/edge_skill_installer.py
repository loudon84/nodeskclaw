from __future__ import annotations

import hashlib
import io
import json
import logging
import os
import shutil
import zipfile
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


class EdgeSkillInstaller:
    """Safely extracts, verifies and manages local edge skill package installations."""

    def __init__(self, base_dir: Path | str | None = None) -> None:
        if base_dir is None:
            base_dir = Path("./data/edge_skills")
        self.base_dir = Path(base_dir)
        self.base_dir.mkdir(parents=True, exist_ok=True)

    def _get_skill_dir(self, skill_id: str, version: str | None = None) -> Path:
        clean_skill_id = Path(skill_id).name
        if version:
            clean_version = Path(version).name
            return self.base_dir / clean_skill_id / clean_version
        return self.base_dir / clean_skill_id

    def install(
        self,
        *,
        skill_id: str,
        version: str = "1.0.0",
        zip_bytes: bytes | None = None,
        expected_sha256: str | None = None,
        meta: dict[str, Any] | None = None,
    ) -> Path:
        target_dir = self._get_skill_dir(skill_id, version)
        if target_dir.exists():
            shutil.rmtree(target_dir, ignore_errors=True)
        target_dir.mkdir(parents=True, exist_ok=True)

        if zip_bytes:
            actual_sha = hashlib.sha256(zip_bytes).hexdigest()
            if expected_sha256 and actual_sha.lower() != expected_sha256.lower():
                shutil.rmtree(target_dir, ignore_errors=True)
                raise ValueError(f"Package checksum mismatch: expected {expected_sha256}, got {actual_sha}")

            # Safe zip extraction with path traversal guard
            with zipfile.ZipFile(io.BytesIO(zip_bytes)) as zf:
                for member in zf.infolist():
                    target_path = (target_dir / member.filename).resolve()
                    if not str(target_path).startswith(str(target_dir.resolve())):
                        shutil.rmtree(target_dir, ignore_errors=True)
                        raise ValueError(f"Zip path traversal detected: {member.filename}")
                zf.extractall(target_dir)

        # Write metadata
        metadata = {
            "skill_id": skill_id,
            "version": version,
            "installed_at": meta.get("installed_at") if meta else None,
            "meta": meta or {},
        }
        (target_dir / "installation_meta.json").write_text(json.dumps(metadata), encoding="utf-8")
        return target_dir

    def uninstall(self, *, skill_id: str, version: str | None = None) -> bool:
        target_dir = self._get_skill_dir(skill_id, version)
        if target_dir.exists():
            shutil.rmtree(target_dir, ignore_errors=True)
            return True
        return False

    def is_installed(self, *, skill_id: str, version: str | None = None) -> bool:
        target_dir = self._get_skill_dir(skill_id, version)
        if not target_dir.exists() or not target_dir.is_dir():
            return False
        meta_file = target_dir / "installation_meta.json"
        return meta_file.exists()
