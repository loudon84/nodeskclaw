from __future__ import annotations

import hashlib
import secrets

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ConflictError, NotFoundError
from app.models.base import not_deleted
from app.models.connector.edge_node import EdgeNode, EdgeNodeStatus


def hash_edge_token(plain: str) -> str:
    return hashlib.sha256(plain.encode("utf-8")).hexdigest()


class EdgeNodeService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def enqueue_edge_job(
        self,
        *,
        org_id: str,
        edge_node_id: str,
        run_id: str,
        tool_name: str,
        arguments: dict | None = None,
        snapshot: dict | None = None,
        idempotency_key: str | None = None,
    ) -> EdgeJob:
        from app.models.connector.edge_job import EdgeJob, EdgeJobStatus
        # Idempotency check: if job for same run_id + edge_node_id + tool_name already exists, return existing
        existing = await self.db.execute(
            select(EdgeJob).where(
                not_deleted(EdgeJob),
                EdgeJob.org_id == org_id,
                EdgeJob.edge_node_id == edge_node_id,
                EdgeJob.run_id == run_id,
                EdgeJob.tool_name == tool_name,
            ).limit(1)
        )
        found = existing.scalar_one_or_none()
        if found:
            return found

        # Verify node exists & online/registered
        node = await self.get(org_id, edge_node_id)
        job = EdgeJob(
            org_id=org_id,
            edge_node_id=node.id,
            run_id=run_id,
            tool_name=tool_name,
            arguments=arguments or {},
            snapshot=snapshot or {},
            status=EdgeJobStatus.QUEUED.value,
            delivery_generation=0,
        )
        self.db.add(job)
        await self.db.flush()
        return job

    async def _get_by_name(self, org_id: str, name: str) -> EdgeNode | None:
        result = await self.db.execute(
            select(EdgeNode).where(
                not_deleted(EdgeNode),
                EdgeNode.org_id == org_id,
                EdgeNode.name == name,
            )
        )
        return result.scalar_one_or_none()

    async def get(self, org_id: str, node_id: str) -> EdgeNode:
        result = await self.db.execute(
            select(EdgeNode).where(
                not_deleted(EdgeNode),
                EdgeNode.org_id == org_id,
                EdgeNode.id == node_id,
            )
        )
        node = result.scalar_one_or_none()
        if not node:
            raise NotFoundError("Edge 节点不存在", "errors.connector.edge_node_not_found")
        return node

    async def list_nodes(self, org_id: str) -> list[EdgeNode]:
        result = await self.db.execute(
            select(EdgeNode)
            .where(not_deleted(EdgeNode), EdgeNode.org_id == org_id)
            .order_by(EdgeNode.created_at.desc())
        )
        return list(result.scalars().all())

    async def register(
        self,
        *,
        org_id: str,
        name: str,
        operator_user_id: str | None = None,
    ) -> tuple[EdgeNode, str]:
        existing = await self._get_by_name(org_id, name)
        if existing:
            raise ConflictError(
                "Edge 节点名称已存在",
                "errors.connector.edge_node_name_conflict",
            )

        plain_token = secrets.token_urlsafe(32)
        node = EdgeNode(
            org_id=org_id,
            name=name,
            status=EdgeNodeStatus.PENDING.value,
            token_hash=hash_edge_token(plain_token),
            created_by=operator_user_id,
        )
        self.db.add(node)
        await self.db.flush()
        return node, plain_token
