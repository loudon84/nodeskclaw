import logging
import os
import uuid
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.exceptions import BadRequestError
from app.models.hermes_skill.skill_import import HermesSkillImport
from app.schemas.hermes_skill.common import ImportStatus
from app.services.hermes_skill.manifest_parser import ManifestParser, ManifestParseError

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

            if skill_dirs:
                for skill_dir in skill_dirs:
                    self._validate_path_safety(skill_dir)
                    dir_size = self._compute_dir_size(skill_dir)
                    if total_size + dir_size > _MAX_IMPORT_SIZE_BYTES:
                        failed_count += 1
                        continue

                    try:
                        manifest = ManifestParser.parse_skill_package(skill_dir)
                        imported_count += 1
                        total_size += dir_size
                    except ManifestParseError:
                        failed_count += 1

            import_record.imported_skills = imported_count
            import_record.failed_skills = failed_count
            import_record.total_skills = imported_count + failed_count
            import_record.status = ImportStatus.COMPLETED

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
