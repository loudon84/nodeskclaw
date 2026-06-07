import hashlib
import logging
import uuid
from pathlib import Path

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.exceptions import (
    NotFoundError,
    ForbiddenError,
    ArtifactNotFoundError,
    ArtifactFileNotFoundError,
    ArtifactForbiddenError,
    ArtifactPreviewUnsupportedError,
    ArtifactBatchSizeExceededError,
)
from app.core.feature_gate import feature_gate
from app.models.base import not_deleted
from app.models.hermes_skill.hermes_artifact import HermesArtifact, PermissionScope
from app.models.hermes_skill.hermes_task import HermesTask
from app.services.hermes_skill.path_guard import PathGuard
from app.services.hermes_skill.permission_checker import PermissionChecker
from app.services.hermes_skill.artifact_audit_service import ArtifactAuditService
from app.services.hermes_skill.download_token_service import DownloadTokenService
from app.services.hermes_skill.artifact_permission_service import ArtifactPermissionService
from app.services.hermes_skill.task_event_service import TaskEventService
from app.models.hermes_skill.hermes_task import EventType

logger = logging.getLogger(__name__)

PREVIEWABLE_PREFIXES = ("text/", "image/", "application/json")
PREVIEW_MAX_SIZE_BYTES = 512 * 1024


def _max_artifact_size_bytes() -> int:
    return settings.HERMES_ARTIFACT_MAX_SIZE_MB * 1024 * 1024


def _max_batch_download_bytes() -> int:
    return settings.HERMES_ARTIFACT_BATCH_DOWNLOAD_MAX_SIZE_MB * 1024 * 1024


class ArtifactService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.audit = ArtifactAuditService(db)

    async def scan_and_register(
        self,
        task_id: str,
        org_id: str,
        outputs_dir: Path | None = None,
    ) -> list[HermesArtifact]:
        task = await self.db.get(HermesTask, task_id)
        if not task or task.deleted_at is not None or task.org_id != org_id:
            raise NotFoundError("Task 不存在", "errors.task.not_found")

        event_service = TaskEventService(self.db)
        await event_service.write_event(
            task_id=task_id,
            org_id=org_id,
            event_type=EventType.ARTIFACT_SCAN_STARTED,
            payload={"status": "started"},
        )

        if outputs_dir is None:
            outputs_dir = await self.compute_outputs_dir(task)

        if outputs_dir is None or not outputs_dir.is_dir():
            await event_service.write_event(
                task_id=task_id,
                org_id=org_id,
                event_type=EventType.ARTIFACT_SCAN_COMPLETED,
                payload={"status": "completed", "count": 0},
            )
            return []

        artifacts: list[HermesArtifact] = []
        max_size = _max_artifact_size_bytes()

        try:
            for file_path in outputs_dir.rglob("*"):
                if not file_path.is_file():
                    continue

                try:
                    stat = file_path.stat()
                    if stat.st_size == 0 or stat.st_size > max_size:
                        continue
                except OSError:
                    continue

                try:
                    PathGuard.validate_output_file(file_path, outputs_dir)
                except ForbiddenError:
                    continue

                sha256_hash = None
                try:
                    sha256_hash = hashlib.sha256(file_path.read_bytes()).hexdigest()
                except Exception:
                    logger.warning("sha256 计算失败: %s", file_path)

                relative_path = str(file_path.relative_to(outputs_dir))
                content_type = self._guess_content_type(file_path)
                size_bytes = file_path.stat().st_size

                existing = await self.db.execute(
                    select(HermesArtifact).where(
                        not_deleted(HermesArtifact),
                        HermesArtifact.task_id == task_id,
                        HermesArtifact.org_id == org_id,
                        HermesArtifact.file_path == str(file_path),
                        HermesArtifact.sha256 == sha256_hash if sha256_hash else HermesArtifact.file_name == file_path.name,
                    )
                )
                if existing.scalar_one_or_none():
                    continue

                permission_scope = "org" if not feature_gate.is_ee else "workspace"
                if feature_gate.is_ee and not task.workspace_id:
                    permission_scope = "task_creator"

                preview_supported = content_type.startswith(PREVIEWABLE_PREFIXES) if content_type else False

                artifact = HermesArtifact(
                    id=str(uuid.uuid4()),
                    org_id=org_id,
                    task_id=task_id,
                    skill_id=task.skill_id,
                    agent_id=task.agent_id,
                    workspace_id=task.workspace_id,
                    file_name=file_path.name,
                    file_path=str(file_path),
                    relative_path=relative_path,
                    content_type=content_type,
                    size_bytes=size_bytes,
                    sha256=sha256_hash,
                    permission_scope=permission_scope,
                    source_run_id=task.hermes_run_id,
                    preview_supported=preview_supported,
                    metadata_json=None,
                    created_by=task.user_id,
                )
                self.db.add(artifact)
                artifacts.append(artifact)

                await self.db.flush()
                await event_service.write_event(
                    task_id=task_id,
                    org_id=org_id,
                    event_type=EventType.ARTIFACT_CREATED,
                    payload={"artifact_id": artifact.id, "file_name": file_path.name},
                )

            await self.db.flush()
            await event_service.write_event(
                task_id=task_id,
                org_id=org_id,
                event_type=EventType.ARTIFACT_SCAN_COMPLETED,
                payload={"status": "completed", "count": len(artifacts)},
            )
        except Exception as exc:
            logger.error("Artifact scan failed for task %s: %s", task_id, exc)
            await event_service.write_event(
                task_id=task_id,
                org_id=org_id,
                event_type=EventType.ARTIFACT_SCAN_FAILED,
                payload={"status": "failed", "error": str(exc)[:1024]},
            )

        return artifacts

    async def list_artifacts(
        self,
        org_id: str,
        user_id: str | None = None,
        task_id: str | None = None,
        workspace_id: str | None = None,
        skill_id: str | None = None,
        content_type: str | None = None,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[list[HermesArtifact], int]:
        from sqlalchemy import func

        base = select(HermesArtifact).where(
            not_deleted(HermesArtifact),
            HermesArtifact.org_id == org_id,
        )

        if task_id:
            base = base.where(HermesArtifact.task_id == task_id)
        if workspace_id:
            base = base.where(HermesArtifact.workspace_id == workspace_id)
        if skill_id:
            base = base.where(HermesArtifact.skill_id == skill_id)
        if content_type:
            base = base.where(HermesArtifact.content_type == content_type)

        if user_id:
            scope_filter = await PermissionChecker.build_scope_filter(self.db, user_id, org_id)
            base = base.where(scope_filter)

        count_stmt = select(func.count()).select_from(base.subquery())
        total = (await self.db.execute(count_stmt)).scalar_one()

        offset = (page - 1) * page_size
        result = await self.db.execute(
            base.order_by(HermesArtifact.created_at.desc()).offset(offset).limit(page_size)
        )
        return result.scalars().all(), total

    async def get_artifact(
        self,
        artifact_id: str,
        org_id: str,
    ) -> HermesArtifact:
        artifact = await self.db.get(HermesArtifact, artifact_id)
        if not artifact or artifact.deleted_at is not None or artifact.org_id != org_id:
            raise ArtifactNotFoundError()
        return artifact

    async def ensure_artifact_visible(
        self, artifact: HermesArtifact, user_id: str, org_id: str,
    ) -> None:
        if not await PermissionChecker.can_view_artifact(self.db, artifact, user_id, org_id):
            raise ArtifactForbiddenError()

    async def ensure_artifact_downloadable(
        self, artifact: HermesArtifact, user_id: str, org_id: str,
    ) -> None:
        if not await PermissionChecker.can_download_artifact(self.db, artifact, user_id, org_id):
            raise ArtifactForbiddenError()

    async def ensure_artifact_mutable(
        self, artifact: HermesArtifact, user_id: str, org_id: str,
    ) -> None:
        if not await PermissionChecker.can_delete_artifact(self.db, artifact, user_id, org_id):
            raise ArtifactForbiddenError()

    async def ensure_artifact_permission_manageable(
        self, artifact: HermesArtifact, user_id: str, org_id: str,
    ) -> None:
        if not await PermissionChecker.can_manage_artifact_permission(self.db, artifact, user_id, org_id):
            raise ArtifactForbiddenError()

    async def preview(
        self,
        artifact_id: str,
        org_id: str,
        user_id: str | None = None,
    ) -> tuple[HermesArtifact, str]:
        artifact = await self.get_artifact(artifact_id, org_id)

        if user_id:
            await self.ensure_artifact_visible(artifact, user_id, org_id)

        if not artifact.content_type or not any(
            artifact.content_type.startswith(p) for p in PREVIEWABLE_PREFIXES
        ):
            raise ArtifactPreviewUnsupportedError()

        file_path = Path(artifact.file_path)
        self.validate_artifact_file_path(file_path, artifact)

        if not file_path.is_file():
            raise ArtifactFileNotFoundError()

        try:
            stat = file_path.stat()
            if stat.st_size > PREVIEW_MAX_SIZE_BYTES:
                raise ArtifactPreviewUnsupportedError()
        except OSError:
            raise ArtifactFileNotFoundError()

        if artifact.content_type == "application/octet-stream":
            raise ArtifactPreviewUnsupportedError()

        content = file_path.read_text(encoding="utf-8", errors="replace")

        await self.audit.log_artifact_action(
            action="artifact.previewed",
            artifact_id=artifact_id,
            org_id=org_id,
            actor_id=user_id,
        )
        return artifact, content

    async def download(
        self,
        artifact_id: str,
        org_id: str,
        user_id: str | None = None,
        actor_name: str | None = None,
    ) -> Path:
        artifact = await self.db.get(HermesArtifact, artifact_id)
        if not artifact or artifact.deleted_at is not None or artifact.org_id != org_id:
            raise ArtifactNotFoundError()

        if user_id:
            await self.ensure_artifact_downloadable(artifact, user_id, org_id)

        file_path = Path(artifact.file_path)
        self.validate_artifact_file_path(file_path, artifact)

        if not file_path.is_file():
            raise ArtifactFileNotFoundError()

        stmt = select(HermesArtifact).where(
            HermesArtifact.id == artifact_id,
        ).with_for_update()
        locked = (await self.db.execute(stmt)).scalar_one()
        locked.download_count += 1
        await self.db.flush()

        await self.audit.log_artifact_action(
            action="artifact.downloaded",
            artifact_id=artifact_id,
            org_id=org_id,
            actor_id=user_id or "",
            actor_name=actor_name,
        )
        return file_path

    async def soft_delete(
        self,
        artifact_id: str,
        org_id: str,
        user_id: str | None = None,
        actor_name: str | None = None,
    ) -> None:
        artifact = await self.get_artifact(artifact_id, org_id)

        if user_id:
            await self.ensure_artifact_mutable(artifact, user_id, org_id)

        artifact.soft_delete()
        await self.db.flush()

        token_svc = DownloadTokenService(self.db)
        await token_svc.deactivate_tokens_for_artifact(artifact_id)

        perm_svc = ArtifactPermissionService(self.db)
        await perm_svc.cascade_revoke_for_artifact(artifact_id)

        await self.audit.log_artifact_action(
            action="artifact.deleted",
            artifact_id=artifact_id,
            org_id=org_id,
            actor_id=user_id or "",
            actor_name=actor_name,
        )

    async def batch_delete(
        self,
        artifact_ids: list[str],
        org_id: str,
        user_id: str | None = None,
        actor_name: str | None = None,
    ) -> tuple[int, int]:
        success_count = 0
        skip_count = 0
        for aid in artifact_ids:
            try:
                await self.soft_delete(aid, org_id, user_id, actor_name)
                success_count += 1
            except (ArtifactNotFoundError, ForbiddenError):
                skip_count += 1
        return success_count, skip_count

    @staticmethod
    def _guess_content_type(path: Path) -> str:
        suffix_map = {
            ".json": "application/json",
            ".txt": "text/plain",
            ".csv": "text/csv",
            ".html": "text/html",
            ".md": "text/markdown",
            ".png": "image/png",
            ".jpg": "image/jpeg",
            ".pdf": "application/pdf",
            ".zip": "application/zip",
        }
        return suffix_map.get(path.suffix.lower(), "application/octet-stream")

    async def compute_outputs_dir(self, task: HermesTask) -> Path:
        workspace_root = await self._resolve_workspace_root_for_task(task)
        return workspace_root / settings.HERMES_OUTPUT_BASE_DIR_NAME / "runs" / task.id / "outputs"

    async def _resolve_workspace_root_for_task(self, task: HermesTask) -> Path:
        if task.workspace_id:
            try:
                from app.models.workspace import Workspace
                from app.models.base import not_deleted as _nd
                ws = await self.db.get(Workspace, task.workspace_id)
                if ws and ws.deleted_at is None:
                    for attr in ("storage_root", "root_path", "local_root_path"):
                        val = getattr(ws, attr, None)
                        if val:
                            return Path(val)
            except Exception as exc:
                logger.warning("Workspace root lookup failed: %s", exc)

        if task.agent_id:
            try:
                from app.models.instance import Instance
                instance = await self.db.get(Instance, task.agent_id)
                if instance and instance.deleted_at is None:
                    advanced = instance.advanced_config or {}
                    wrp = advanced.get("workspace_root_path")
                    if wrp:
                        return Path(wrp)
            except Exception as exc:
                logger.warning("Instance workspace_root_path lookup failed: %s", exc)

        if settings.HERMES_WORKSPACE_ROOT:
            return Path(settings.HERMES_WORKSPACE_ROOT)

        return Path(f"/tmp/nodeskclaw-workspaces/{task.workspace_id or 'default'}")

    @staticmethod
    def _compute_outputs_dir(task: HermesTask) -> Path | None:
        return Path(f"/tmp/nodeskclaw-workspaces/{task.workspace_id or 'default'}") / settings.HERMES_OUTPUT_BASE_DIR_NAME / "runs" / task.id / "outputs"

    @staticmethod
    def _get_workspace_root(artifact: HermesArtifact) -> Path | None:
        if artifact.file_path and settings.HERMES_OUTPUT_BASE_DIR_NAME in artifact.file_path:
            idx = artifact.file_path.index(settings.HERMES_OUTPUT_BASE_DIR_NAME)
            return Path(artifact.file_path[:idx]).resolve()
        return None

    @staticmethod
    def resolve_artifact_file_path(artifact: HermesArtifact) -> Path | None:
        if not artifact.file_path:
            return None
        return Path(artifact.file_path)

    @staticmethod
    def validate_artifact_file_path(file_path: Path, artifact: HermesArtifact) -> None:
        workspace_root = ArtifactService._get_workspace_root(artifact)
        if workspace_root:
            PathGuard.validate_file_for_download(file_path, workspace_root)
        else:
            PathGuard.validate_file_for_download(file_path, Path("/tmp"))
