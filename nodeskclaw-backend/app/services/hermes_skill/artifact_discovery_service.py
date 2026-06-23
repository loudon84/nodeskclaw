from __future__ import annotations

import hashlib
import logging
import re
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path, PurePosixPath

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.exceptions import ForbiddenError
from app.core.feature_gate import feature_gate
from app.models.base import not_deleted
from app.models.hermes_skill.hermes_agent_instance import HermesAgentInstance
from app.models.hermes_skill.hermes_artifact import HermesArtifact
from app.models.hermes_skill.hermes_task import EventType, HermesTask
from app.models.hermes_skill.skill_installation import HermesSkillInstallation
from app.services.hermes_skill.artifact_service import ArtifactService
from app.services.hermes_skill.output_manifest_parser import guess_artifact_type
from app.services.hermes_skill.path_guard import PathGuard
from app.services.hermes_skill.task_event_service import TaskEventService

logger = logging.getLogger(__name__)

CONTAINER_WORKSPACE_PATH_RE = re.compile(
    r"[`\"']?(?P<path>/data/hermes/workspace/[^\n`\"']+?)(?=[`\"']|\s|$)"
)

_TRAILING_PUNCT = ".,;，。、）)】]"

_MTIME_FALLBACK_EXTENSIONS = frozenset({
    ".md", ".pdf", ".docx", ".xlsx", ".pptx", ".json", ".csv", ".txt",
})

_MTIME_FALLBACK_KEYWORDS = ("reports", "output", "outputs", "artifacts", "export")


class ArtifactDiscoveryService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def discover_and_register_for_task(
        self,
        task: HermesTask,
        result_text: str | None = None,
        force_rescan: bool = False,
    ) -> list[HermesArtifact]:
        if not settings.HERMES_ARTIFACT_DISCOVERY_ENABLED:
            return []

        event_service = TaskEventService(self.db)
        route_snapshot = await self._get_route_snapshot(task)
        route_type = str(route_snapshot.get("route_type") or "")
        if route_type != "hermes_api_server":
            return []

        hermes_agent_instance_id = str(route_snapshot.get("hermes_agent_instance_id") or "")
        hermes_instance_name = str(
            route_snapshot.get("hermes_instance_name")
            or route_snapshot.get("agent_profile")
            or ""
        )
        runtime_skill_id = str(route_snapshot.get("runtime_skill_id") or "")

        instance = await self._load_hermes_instance(task.org_id, hermes_agent_instance_id)
        if not instance:
            logger.warning(
                "artifact_discovery.failed task_id=%s reason=instance_not_found instance_id=%s",
                task.id,
                hermes_agent_instance_id,
            )
            return []

        container_root = Path(
            route_snapshot.get("container_workspace_root")
            or settings.HERMES_ARTIFACT_DISCOVERY_CONTAINER_WORKSPACE_ROOT
        )
        host_workspace_root = self._resolve_host_workspace_root(instance)
        if host_workspace_root is None:
            logger.warning(
                "artifact_discovery.failed task_id=%s reason=host_workspace_unresolved instance=%s",
                task.id,
                hermes_instance_name,
            )
            return []

        text = result_text or self._extract_result_text(task)
        container_paths = self._extract_container_paths(text, container_root)

        if not container_paths and settings.HERMES_ARTIFACT_DISCOVERY_ENABLE_MTIME_FALLBACK:
            container_paths = self._mtime_fallback_paths(
                host_workspace_root,
                container_root,
                task,
            )

        await event_service.write_event(
            task_id=task.id,
            org_id=task.org_id,
            event_type=EventType.ARTIFACT_SCAN_STARTED,
            payload={
                "source": "hermes_api_server_workspace",
                "hermes_instance_name": hermes_instance_name,
                "runtime_skill_id": runtime_skill_id,
                "path_count": len(container_paths),
            },
        )

        artifacts: list[HermesArtifact] = []
        max_size = settings.HERMES_ARTIFACT_DISCOVERY_MAX_FILE_SIZE_MB * 1024 * 1024

        for container_path_str in container_paths:
            try:
                relative_path, host_path = self._map_to_host_path(
                    container_path_str,
                    container_root,
                    host_workspace_root,
                )
            except (ValueError, ForbiddenError) as exc:
                await event_service.write_event(
                    task_id=task.id,
                    org_id=task.org_id,
                    event_type=EventType.ARTIFACT_SCAN_FAILED,
                    payload={
                        "error_code": "path_mapping_failed",
                        "container_path": container_path_str,
                        "error": str(exc)[:512],
                    },
                )
                continue

            if not host_path.exists() or not host_path.is_file():
                await event_service.write_event(
                    task_id=task.id,
                    org_id=task.org_id,
                    event_type=EventType.ARTIFACT_SCAN_FAILED,
                    payload={
                        "error_code": "host_file_not_found",
                        "container_path": container_path_str,
                        "mapped_host_path": str(host_path),
                    },
                )
                logger.warning(
                    "artifact_discovery.file_missing task_id=%s container_path=%s host_path=%s",
                    task.id,
                    container_path_str,
                    host_path,
                )
                continue

            try:
                PathGuard.validate_file_for_download(host_path, host_workspace_root, max_size=max_size)
            except ForbiddenError as exc:
                await event_service.write_event(
                    task_id=task.id,
                    org_id=task.org_id,
                    event_type=EventType.ARTIFACT_SCAN_FAILED,
                    payload={
                        "error_code": "file_validation_failed",
                        "container_path": container_path_str,
                        "mapped_host_path": str(host_path),
                        "error": str(exc)[:512],
                    },
                )
                continue

            metadata = self._build_file_metadata(host_path)
            artifact = await self._upsert_artifact(
                task=task,
                host_path=host_path,
                container_path=container_path_str,
                relative_path=relative_path,
                route_snapshot=route_snapshot,
                host_workspace_root=host_workspace_root,
                hermes_instance_name=hermes_instance_name,
                runtime_skill_id=runtime_skill_id,
                metadata=metadata,
                force_rescan=force_rescan,
            )
            artifacts.append(artifact)
            await self.db.flush()
            await event_service.write_event(
                task_id=task.id,
                org_id=task.org_id,
                event_type=EventType.ARTIFACT_CREATED,
                payload={
                    "artifact_id": artifact.id,
                    "file_name": artifact.file_name,
                    "relative_path": relative_path,
                    "hermes_instance_name": hermes_instance_name,
                    "runtime_skill_id": runtime_skill_id,
                },
            )
            logger.info(
                "artifact_discovery.artifact_registered task_id=%s relative_path=%s",
                task.id,
                relative_path,
            )

        completed_payload: dict = {
            "status": "completed",
            "count": len(artifacts),
            "hermes_instance_name": hermes_instance_name,
            "runtime_skill_id": runtime_skill_id,
        }
        if not artifacts and not container_paths:
            completed_payload["reason"] = "no_artifact_path_found"

        await event_service.write_event(
            task_id=task.id,
            org_id=task.org_id,
            event_type=EventType.ARTIFACT_SCAN_COMPLETED,
            payload=completed_payload,
        )
        logger.info(
            "artifact_discovery.completed task_id=%s count=%s",
            task.id,
            len(artifacts),
        )
        return artifacts

    async def _get_route_snapshot(self, task: HermesTask) -> dict:
        metadata = task.routing_metadata or {}
        snapshot = metadata.get("route_snapshot")
        if isinstance(snapshot, dict) and snapshot:
            return snapshot
        if metadata.get("route_type"):
            return metadata

        if task.installation_id:
            installation = await self.db.get(HermesSkillInstallation, task.installation_id)
            if installation and installation.deleted_at is None:
                inst_meta = installation.routing_metadata or {}
                if isinstance(inst_meta, dict) and inst_meta:
                    return inst_meta

        return {}

    async def _load_hermes_instance(
        self,
        org_id: str,
        instance_id: str,
    ) -> HermesAgentInstance | None:
        if not instance_id:
            return None
        instance = await self.db.get(HermesAgentInstance, instance_id)
        if not instance or instance.deleted_at is not None or instance.org_id != org_id:
            return None
        return instance

    @staticmethod
    def _resolve_host_workspace_root(instance: HermesAgentInstance) -> Path | None:
        if instance.data_dir:
            return Path(instance.data_dir) / "workspace"
        if instance.instance_dir:
            return Path(instance.instance_dir) / "data" / "hermes" / "workspace"
        return None

    @staticmethod
    def _extract_result_text(task: HermesTask) -> str:
        if task.result_summary:
            return task.result_summary
        arguments = task.arguments or {}
        for key in ("result", "final_response", "text"):
            val = arguments.get(key)
            if isinstance(val, str) and val.strip():
                return val
        return ""

    @staticmethod
    def _extract_container_paths(text: str, container_root: Path) -> list[str]:
        if not text:
            return []
        prefix = container_root.as_posix().rstrip("/") + "/"
        seen: set[str] = set()
        paths: list[str] = []
        for match in CONTAINER_WORKSPACE_PATH_RE.finditer(text):
            raw = match.group("path").strip().strip(_TRAILING_PUNCT)
            if not raw.startswith(prefix):
                continue
            if raw in seen:
                continue
            seen.add(raw)
            paths.append(raw)
        return paths

    @staticmethod
    def _map_to_host_path(
        container_path_str: str,
        container_root: Path,
        host_workspace_root: Path,
    ) -> tuple[str, Path]:
        container_root_posix = PurePosixPath(container_root.as_posix().rstrip("/"))
        container_path = PurePosixPath(container_path_str.replace("\\", "/"))
        try:
            relative = container_path.relative_to(container_root_posix)
        except ValueError as exc:
            raise ValueError(f"container path outside workspace root: {container_path_str}") from exc

        relative_str = relative.as_posix()
        if ".." in relative_str.split("/"):
            raise ForbiddenError("路径穿越", "errors.skill.path_outside_root")

        host_path = (host_workspace_root / relative).resolve()
        host_root_resolved = host_workspace_root.resolve()
        try:
            host_path.relative_to(host_root_resolved)
        except ValueError as exc:
            raise ForbiddenError("路径越界", "errors.skill.path_outside_root") from exc

        return relative_str, host_path

    def _mtime_fallback_paths(
        self,
        host_workspace_root: Path,
        container_root: Path,
        task: HermesTask,
    ) -> list[str]:
        if not host_workspace_root.is_dir():
            return []

        window = timedelta(seconds=settings.HERMES_ARTIFACT_DISCOVERY_MTIME_WINDOW_SECONDS)
        created_at = task.created_at or datetime.now(timezone.utc)
        completed_at = task.completed_at or datetime.now(timezone.utc)
        start = created_at - window
        end = completed_at + window

        paths: list[str] = []
        for file_path in host_workspace_root.rglob("*"):
            if not file_path.is_file():
                continue
            if file_path.suffix.lower() not in _MTIME_FALLBACK_EXTENSIONS:
                continue
            rel_lower = str(file_path.relative_to(host_workspace_root)).lower()
            if not any(kw in rel_lower for kw in _MTIME_FALLBACK_KEYWORDS):
                continue
            try:
                mtime = datetime.fromtimestamp(file_path.stat().st_mtime, tz=timezone.utc)
            except OSError:
                continue
            if mtime < start or mtime > end:
                continue
            relative = file_path.relative_to(host_workspace_root)
            container_path = str(container_root / relative)
            paths.append(container_path)
        return paths

    @staticmethod
    def _build_file_metadata(host_path: Path) -> dict:
        stat = host_path.stat()
        sha256 = hashlib.sha256()
        with host_path.open("rb") as f:
            for chunk in iter(lambda: f.read(1024 * 1024), b""):
                sha256.update(chunk)
        content_type = ArtifactService._guess_content_type(host_path)
        return {
            "filename": host_path.name,
            "size_bytes": stat.st_size,
            "sha256": sha256.hexdigest(),
            "mime_type": content_type,
            "artifact_type": guess_artifact_type(host_path),
        }

    async def _upsert_artifact(
        self,
        *,
        task: HermesTask,
        host_path: Path,
        container_path: str,
        relative_path: str,
        route_snapshot: dict,
        host_workspace_root: Path,
        hermes_instance_name: str,
        runtime_skill_id: str,
        metadata: dict,
        force_rescan: bool,
    ) -> HermesArtifact:
        existing_result = await self.db.execute(
            select(HermesArtifact).where(
                not_deleted(HermesArtifact),
                HermesArtifact.org_id == task.org_id,
                HermesArtifact.task_id == task.id,
                HermesArtifact.relative_path == relative_path,
            )
        )
        existing = existing_result.scalar_one_or_none()

        content_type = metadata["mime_type"]
        preview_supported = bool(
            content_type and content_type.startswith(("text/", "image/", "application/json"))
        )
        metadata_json = {
            "source": "hermes_api_server_workspace",
            "container_path": container_path,
            "host_workspace_root": str(host_workspace_root),
            "hermes_instance_name": hermes_instance_name,
            "hermes_agent_instance_id": route_snapshot.get("hermes_agent_instance_id"),
            "runtime_skill_id": runtime_skill_id,
            "discovered_from": "result_summary",
        }

        if existing and not force_rescan:
            return existing

        if existing and force_rescan:
            existing.file_path = str(host_path)
            existing.file_name = metadata["filename"]
            existing.content_type = content_type
            existing.artifact_type = metadata["artifact_type"]
            existing.size_bytes = metadata["size_bytes"]
            existing.sha256 = metadata["sha256"]
            existing.preview_supported = preview_supported
            existing.metadata_json = metadata_json
            return existing

        permission_scope = "org" if not feature_gate.is_ee else "workspace"
        if feature_gate.is_ee and not task.workspace_id:
            permission_scope = "task_creator"

        artifact = HermesArtifact(
            id=str(uuid.uuid4()),
            org_id=task.org_id,
            task_id=task.id,
            skill_id=task.skill_id,
            agent_id=task.agent_id,
            workspace_id=task.workspace_id,
            file_name=metadata["filename"],
            file_path=str(host_path),
            relative_path=relative_path,
            content_type=content_type,
            size_bytes=metadata["size_bytes"],
            sha256=metadata["sha256"],
            permission_scope=permission_scope,
            source_run_id=task.hermes_run_id,
            preview_supported=preview_supported,
            title=metadata["filename"],
            artifact_type=metadata["artifact_type"],
            metadata_json=metadata_json,
            created_by=task.user_id,
        )
        self.db.add(artifact)
        return artifact
