from __future__ import annotations

import hashlib
from dataclasses import dataclass

from app.services import storage_service


@dataclass(frozen=True)
class StoredArtifact:
    object_key: str
    size_bytes: int
    sha256: str


class ArtifactStoreService:
    @staticmethod
    def build_object_key(org_id: str, task_id: str, artifact_id: str, filename: str) -> str:
        safe_name = filename.replace("\\", "/").split("/")[-1]
        return f"orgs/{org_id}/tasks/{task_id}/artifacts/{artifact_id}/{safe_name}"

    async def store(
        self,
        *,
        org_id: str,
        task_id: str,
        artifact_id: str,
        filename: str,
        content: bytes,
    ) -> StoredArtifact:
        object_key = self.build_object_key(org_id, task_id, artifact_id, filename)
        await storage_service.upload_raw(object_key, content)
        return StoredArtifact(
            object_key=object_key,
            size_bytes=len(content),
            sha256=hashlib.sha256(content).hexdigest(),
        )

    async def read(self, object_key: str) -> bytes:
        return await storage_service.download_raw(object_key)
