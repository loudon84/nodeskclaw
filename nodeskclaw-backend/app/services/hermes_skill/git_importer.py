import asyncio
import logging
import os
import shutil
import tempfile
import uuid
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.exceptions import BadRequestError
from app.models.hermes_skill.skill_import import HermesSkillImport
from app.schemas.hermes_skill.common import ImportStatus
from app.services.hermes_skill.manifest_parser import ManifestParser, ManifestParseError
from app.services.hermes_skill.conflict_detector import ConflictDetector
from app.services.hermes_skill.skill_audit_logger import SkillAuditLogger

logger = logging.getLogger(__name__)

_FORBIDDEN_EXTENSIONS = frozenset({".pem", ".key", ".env", ".secret"})
_MAX_IMPORT_SIZE_BYTES = settings.HERMES_SKILL_IMPORT_MAX_SIZE_MB * 1024 * 1024


class GitImporter:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def preview(
        self,
        org_id: str,
        source_url: str,
        source_type: str = "github",
        branch: str = "main",
        target_category: str = "",
        created_by: str | None = None,
    ) -> HermesSkillImport:
        import_record = HermesSkillImport(
            id=str(uuid.uuid4()),
            org_id=org_id,
            source_url=source_url,
            source_type=source_type,
            source_ref=branch,
            target_category=target_category,
            status=ImportStatus.PREVIEW,
            created_by=created_by,
        )
        self.db.add(import_record)
        await self.db.flush()

        try:
            clone_dir = await self._clone_repo(source_url, branch)
            skill_dirs = []
            conflicts = []

            for skill_dir in self._walk_skill_dirs(clone_dir):
                try:
                    manifest = ManifestParser.parse_skill_package(skill_dir)
                    skill_dirs.append({
                        "path": str(skill_dir),
                        "skill_id": manifest.meta.skill_id,
                        "name": manifest.meta.name,
                        "version": manifest.meta.version,
                    })
                except ManifestParseError:
                    pass

            import_record.details = {
                "clone_dir": str(clone_dir),
                "skills": skill_dirs,
                "conflicts": conflicts,
                "total_skills": len(skill_dirs),
            }
            import_record.total_skills = len(skill_dirs)
        except Exception as exc:
            import_record.error_message = str(exc)[:1024]
            import_record.details = {"error": str(exc)}

        await self.db.flush()
        return import_record

    async def execute_import(
        self,
        import_id: str,
        org_id: str,
        skill_dirs: list[Path] | None = None,
    ) -> HermesSkillImport:
        import_record = await self.db.get(HermesSkillImport, import_id)
        if not import_record or import_record.org_id != org_id:
            from app.core.exceptions import NotFoundError
            raise NotFoundError("导入记录不存在", "errors.skill.import_not_found")

        import_record.status = ImportStatus.IMPORTING
        await self.db.flush()

        try:
            imported_count = 0
            failed_count = 0
            total_size = 0
            imported_paths: list[str] = []
            hub_root = Path(settings.HERMES_SKILL_HUB_ROOT)
            imported_dir = hub_root / "imported"

            clone_dir_str = None
            if import_record.details and isinstance(import_record.details, dict):
                clone_dir_str = import_record.details.get("clone_dir")

            source_dirs = skill_dirs
            if not source_dirs and clone_dir_str:
                source_dirs = list(self._walk_skill_dirs(Path(clone_dir_str)))

            if source_dirs:
                for skill_dir in source_dirs:
                    self._validate_path_safety(skill_dir)
                    dir_size = self._compute_dir_size(skill_dir)
                    if total_size + dir_size > _MAX_IMPORT_SIZE_BYTES:
                        failed_count += 1
                        continue

                    try:
                        manifest = ManifestParser.parse_skill_package(skill_dir)
                        safe_skill_id = manifest.meta.skill_id.replace(".", "-")
                        target_dir = imported_dir / (import_record.target_category or "uncategorized") / safe_skill_id
                        target_dir.parent.mkdir(parents=True, exist_ok=True)

                        self._copy_filtered(skill_dir, target_dir)

                        imported_count += 1
                        total_size += dir_size
                        imported_paths.append(str(target_dir))
                    except ManifestParseError:
                        failed_count += 1

            import_record.imported_skills = imported_count
            import_record.failed_skills = failed_count
            import_record.total_skills = imported_count + failed_count
            import_record.status = ImportStatus.COMPLETED

            audit_logger = SkillAuditLogger(self.db)
            await audit_logger.log(
                action="hermes.skill.imported",
                target_id=import_id,
                org_id=org_id,
                details={
                    "imported_count": imported_count,
                    "failed_count": failed_count,
                    "source_url": import_record.source_url,
                },
            )

        except Exception as exc:
            import_record.status = ImportStatus.FAILED
            import_record.error_message = str(exc)[:1024]
            logger.error("导入失败: %s", exc)

        await self.db.flush()
        return import_record

    @staticmethod
    def _validate_path_safety(path: Path) -> None:
        resolved = path.resolve()
        if ".." in str(path):
            raise BadRequestError("路径包含穿越字符", "errors.skill.path_traversal")
        for file_path in resolved.rglob("*"):
            if file_path.suffix.lower() in _FORBIDDEN_EXTENSIONS:
                raise BadRequestError(
                    f"禁止导入密钥文件: {file_path.name}",
                    "errors.skill.forbidden_file",
                )

    @staticmethod
    def _compute_dir_size(directory: Path) -> int:
        total = 0
        for file_path in directory.rglob("*"):
            if file_path.is_file():
                try:
                    total += file_path.stat().st_size
                except OSError:
                    pass
        return total

    @staticmethod
    def _copy_filtered(source: Path, target: Path) -> None:
        for item in source.rglob("*"):
            if not item.is_file():
                continue
            if item.suffix.lower() in _FORBIDDEN_EXTENSIONS:
                continue
            if item.name.startswith("."):
                continue
            relative = item.relative_to(source)
            dest = target / relative
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(str(item), str(dest))

    async def _clone_repo(self, source_url: str, branch: str) -> Path:
        clone_dir = Path(tempfile.mkdtemp(prefix="hermes_import_"))
        cmd = [
            "git", "clone", "--depth", "1",
            "--branch", branch,
            source_url, str(clone_dir),
        ]
        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        _, stderr = await process.communicate()
        if process.returncode != 0:
            shutil.rmtree(str(clone_dir), ignore_errors=True)
            raise BadRequestError(
                f"git clone 失败: {stderr.decode()[:500]}",
                "errors.skill.git_clone_failed",
            )
        return clone_dir

    def _walk_skill_dirs(self, root: Path, max_depth: int = 4):
        def _walk(current: Path, depth: int):
            if depth > max_depth:
                return
            try:
                entries = list(current.iterdir())
            except (OSError, PermissionError):
                return

            if (current / "SKILL.md").is_file():
                yield current
                return

            for entry in entries:
                if not entry.is_dir():
                    continue
                if entry.name in {"node_modules", ".git", "dist", "build", ".venv", "__pycache__"}:
                    continue
                if entry.name.startswith("."):
                    continue
                yield from _walk(entry, depth + 1)

        yield from _walk(root, 0)
