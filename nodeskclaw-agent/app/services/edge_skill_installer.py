from __future__ import annotations

import hashlib
import io
import json
import logging
import os
import shutil
import stat
import uuid
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

    @staticmethod
    def _validate_identifier(value: str) -> str:
        normalized = str(value).strip()
        if (
            not normalized
            or normalized in {".", ".."}
            or "/" in normalized
            or "\\" in normalized
            or Path(normalized).is_absolute()
            or Path(normalized).name != normalized
        ):
            raise ValueError(f"Invalid managed path identifier: {value}")
        return normalized

    def _get_skill_root(self, skill_id: str) -> Path:
        clean_skill_id = self._validate_identifier(skill_id)
        return self.base_dir / clean_skill_id

    def _get_version_dir(self, skill_id: str, version: str) -> Path:
        clean_version = self._validate_identifier(version)
        return self._get_skill_root(skill_id) / clean_version

    def _current_pointer_path(self, skill_id: str) -> Path:
        return self._get_skill_root(skill_id) / "current.json"

    def _resolve_under_root(self, root: Path, member_name: str) -> Path:
        normalized = member_name.replace("\\", "/")
        if not normalized or normalized.startswith("/") or ".." in normalized.split("/"):
            raise ValueError(f"Zip path traversal detected: {member_name}")
        target = (root / normalized).resolve()
        try:
            target.relative_to(root.resolve())
        except ValueError as exc:
            raise ValueError(f"Zip path traversal detected: {member_name}") from exc
        return target

    def _validate_zip_members(self, zf: zipfile.ZipFile, extract_root: Path) -> None:
        seen: set[str] = set()
        for member in zf.infolist():
            if member.is_dir():
                continue
            if stat.S_ISLNK(member.external_attr >> 16):
                raise ValueError(f"Zip symlink entry rejected: {member.filename}")
            target = self._resolve_under_root(extract_root, member.filename)
            key = os.path.normcase(str(target))
            if key in seen:
                raise ValueError(f"Duplicate zip entry conflict: {member.filename}")
            seen.add(key)

    def _write_current_pointer(self, skill_id: str, version: str) -> None:
        pointer = self._current_pointer_path(skill_id)
        pointer.parent.mkdir(parents=True, exist_ok=True)
        temporary = pointer.with_name(f".{pointer.name}.{uuid.uuid4().hex}.tmp")
        try:
            temporary.write_text(json.dumps({"version": version}), encoding="utf-8")
            os.replace(temporary, pointer)
        finally:
            temporary.unlink(missing_ok=True)

    def _read_current_version(self, skill_id: str) -> str | None:
        pointer = self._current_pointer_path(skill_id)
        if pointer.is_symlink() or not pointer.is_file():
            return None
        try:
            payload = json.loads(pointer.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return None
        version = payload.get("version")
        return str(version) if version else None

    def install(
        self,
        *,
        skill_id: str,
        version: str = "1.0.0",
        zip_bytes: bytes | None = None,
        expected_sha256: str | None = None,
        expected_size: int | None = None,
        meta: dict[str, Any] | None = None,
    ) -> Path:
        if not zip_bytes:
            raise ValueError("zip_bytes is required for bundle installation")

        if expected_size is not None and len(zip_bytes) != expected_size:
            raise ValueError(
                f"Package size mismatch: expected {expected_size}, got {len(zip_bytes)}"
            )

        actual_sha = hashlib.sha256(zip_bytes).hexdigest()
        if expected_sha256 and actual_sha.lower() != expected_sha256.lower():
            raise ValueError(f"Package checksum mismatch: expected {expected_sha256}, got {actual_sha}")

        skill_id = self._validate_identifier(skill_id)
        version = self._validate_identifier(version)
        skill_root = self._get_skill_root(skill_id)
        if skill_root.is_symlink():
            raise ValueError("Managed skill directory cannot be a symlink")
        version_dir = self._get_version_dir(skill_id, version)
        staging_dir = skill_root / f".stage-{version}-{uuid.uuid4().hex}"
        staging_dir.mkdir(parents=True, exist_ok=True)
        backup_dir: Path | None = None

        try:
            with zipfile.ZipFile(io.BytesIO(zip_bytes)) as zf:
                self._validate_zip_members(zf, staging_dir)
                for member in zf.infolist():
                    if member.is_dir():
                        continue
                    target_path = self._resolve_under_root(staging_dir, member.filename)
                    target_path.parent.mkdir(parents=True, exist_ok=True)
                    with zf.open(member) as source, target_path.open("wb") as dest:
                        shutil.copyfileobj(source, dest)

            metadata = {
                "skill_id": skill_id,
                "version": version,
                "installed_at": meta.get("installed_at") if meta else None,
                "meta": meta or {},
            }
            (staging_dir / "installation_meta.json").write_text(json.dumps(metadata), encoding="utf-8")

            if version_dir.is_symlink():
                raise ValueError("Managed version directory cannot be a symlink")
            if version_dir.exists():
                backup_dir = skill_root / f".backup-{version}-{uuid.uuid4().hex}"
                os.replace(version_dir, backup_dir)
            try:
                os.replace(staging_dir, version_dir)
                self._write_current_pointer(skill_id, version)
            except Exception:
                if version_dir.exists():
                    shutil.rmtree(version_dir)
                if backup_dir and backup_dir.exists():
                    os.replace(backup_dir, version_dir)
                raise
            if backup_dir and backup_dir.exists():
                shutil.rmtree(backup_dir)
            return version_dir
        except Exception:
            if staging_dir.exists():
                shutil.rmtree(staging_dir)
            raise

    def uninstall(self, *, skill_id: str, version: str | None = None) -> bool:
        skill_id = self._validate_identifier(skill_id)
        if version is not None:
            version = self._validate_identifier(version)
        skill_root = self._get_skill_root(skill_id)
        if skill_root.is_symlink():
            raise ValueError("Managed skill directory cannot be a symlink")
        if not skill_root.exists():
            return False

        removed = False
        current_version = self._read_current_version(skill_id)
        if version is not None and current_version != version:
            return False
        target_version = version or current_version
        if target_version:
            version_dir = self._get_version_dir(skill_id, target_version)
            if version_dir.is_symlink():
                raise ValueError("Managed version directory cannot be a symlink")
            try:
                version_dir.resolve().relative_to(self.base_dir.resolve())
            except ValueError as exc:
                raise ValueError("Uninstall path outside managed root") from exc
            if version_dir.exists() and version_dir.is_dir():
                shutil.rmtree(version_dir)
                removed = True

        pointer = self._current_pointer_path(skill_id)
        if current_version and target_version == current_version and (pointer.exists() or pointer.is_symlink()):
            pointer.unlink()
            removed = True

        if skill_root.exists() and not any(skill_root.iterdir()):
            shutil.rmtree(skill_root)
        return removed

    def is_installed(self, *, skill_id: str, version: str | None = None) -> bool:
        resolved_version = version or self._read_current_version(skill_id)
        if not resolved_version:
            return False
        target_dir = self._get_version_dir(skill_id, resolved_version)
        if not target_dir.exists() or not target_dir.is_dir():
            return False
        meta_file = target_dir / "installation_meta.json"
        return meta_file.exists()
