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
        attempt_id: str | None = None,
        step_id: str | None = None,
        run_generation: int = 1,
        request_trace_id: str | None = None,
    ) -> EdgeJob:
        from app.models.connector.edge_job import EdgeJob, EdgeJobStatus
        # Idempotency check by idempotency_key or (org_id + run_id + edge_node_id + step_id/tool_name)
        if idempotency_key:
            existing = await self.db.execute(
                select(EdgeJob).where(
                    not_deleted(EdgeJob),
                    EdgeJob.org_id == org_id,
                    EdgeJob.idempotency_key == idempotency_key,
                ).limit(1)
            )
            found = existing.scalar_one_or_none()
            if found:
                return found

        query = select(EdgeJob).where(
            not_deleted(EdgeJob),
            EdgeJob.org_id == org_id,
            EdgeJob.edge_node_id == edge_node_id,
            EdgeJob.run_id == run_id,
        )
        if step_id:
            query = query.where(EdgeJob.step_id == step_id)
        else:
            query = query.where(EdgeJob.tool_name == tool_name)
        existing = await self.db.execute(query.limit(1))
        found = existing.scalar_one_or_none()
        if found:
            return found

        # Verify node exists & online/registered
        node = await self.get(org_id, edge_node_id)
        job = EdgeJob(
            org_id=org_id,
            edge_node_id=node.id,
            run_id=run_id,
            attempt_id=attempt_id,
            step_id=step_id,
            run_generation=run_generation,
            request_trace_id=request_trace_id,
            idempotency_key=idempotency_key,
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

    async def issue_on_demand_request(
        self,
        *,
        org_id: str,
        edge_node_id: str,
        job_id: str,
        run_id: str,
        name: str,
        artifact_id: str | None = None,
        attempt_id: str | None = None,
        step_id: str | None = None,
        run_generation: int = 1,
        delivery_generation: int = 0,
        ttl_seconds: int = 300,
    ) -> EdgeArtifactOnDemandRequest:
        from datetime import datetime, timedelta, timezone
        from app.models.connector.edge_artifact_on_demand_request import EdgeArtifactOnDemandRequest, OnDemandRequestStatus

        now = datetime.now(timezone.utc)
        # Check if active request already exists
        result = await self.db.execute(
            select(EdgeArtifactOnDemandRequest).where(
                not_deleted(EdgeArtifactOnDemandRequest),
                EdgeArtifactOnDemandRequest.org_id == org_id,
                EdgeArtifactOnDemandRequest.job_id == job_id,
                EdgeArtifactOnDemandRequest.name == name,
                EdgeArtifactOnDemandRequest.run_generation == run_generation,
            ).limit(1)
        )
        existing = result.scalar_one_or_none()
        if existing:
            if existing.status == OnDemandRequestStatus.ISSUED.value and existing.expires_at > now:
                return existing
            if existing.status == OnDemandRequestStatus.ISSUED.value and existing.expires_at <= now:
                existing.status = OnDemandRequestStatus.EXPIRED.value
                await self.db.flush()

        req = EdgeArtifactOnDemandRequest(
            org_id=org_id,
            edge_node_id=edge_node_id,
            job_id=job_id,
            run_id=run_id,
            attempt_id=attempt_id,
            step_id=step_id,
            run_generation=run_generation,
            delivery_generation=delivery_generation,
            artifact_id=artifact_id,
            name=name,
            status=OnDemandRequestStatus.ISSUED.value,
            expires_at=now + timedelta(seconds=ttl_seconds),
        )
        self.db.add(req)
        await self.db.flush()
        return req

    async def pull_on_demand_requests(
        self,
        *,
        org_id: str,
        edge_node_id: str,
    ) -> list[EdgeArtifactOnDemandRequest]:
        from datetime import datetime, timezone
        from app.models.connector.edge_artifact_on_demand_request import EdgeArtifactOnDemandRequest, OnDemandRequestStatus

        now = datetime.now(timezone.utc)
        result = await self.db.execute(
            select(EdgeArtifactOnDemandRequest).where(
                not_deleted(EdgeArtifactOnDemandRequest),
                EdgeArtifactOnDemandRequest.org_id == org_id,
                EdgeArtifactOnDemandRequest.edge_node_id == edge_node_id,
                EdgeArtifactOnDemandRequest.status == OnDemandRequestStatus.ISSUED.value,
            )
        )
        items = list(result.scalars().all())
        active_items = []
        for req in items:
            if req.expires_at <= now:
                req.status = OnDemandRequestStatus.EXPIRED.value
            else:
                active_items.append(req)
        await self.db.flush()
        return active_items

    async def consume_on_demand_request(
        self,
        *,
        org_id: str,
        job_id: str,
        name: str | None = None,
        artifact_id: str | None = None,
        run_generation: int | None = None,
    ) -> EdgeArtifactOnDemandRequest | None:
        from datetime import datetime, timezone
        from app.models.connector.edge_artifact_on_demand_request import EdgeArtifactOnDemandRequest, OnDemandRequestStatus

        now = datetime.now(timezone.utc)
        query = select(EdgeArtifactOnDemandRequest).where(
            not_deleted(EdgeArtifactOnDemandRequest),
            EdgeArtifactOnDemandRequest.org_id == org_id,
            EdgeArtifactOnDemandRequest.job_id == job_id,
        )
        if name:
            query = query.where(EdgeArtifactOnDemandRequest.name == name)
        if run_generation is not None:
            query = query.where(EdgeArtifactOnDemandRequest.run_generation == run_generation)

        result = await self.db.execute(query.order_by(EdgeArtifactOnDemandRequest.created_at.desc()).limit(1))
        req = result.scalar_one_or_none()
        if not req:
            return None

        if req.status == OnDemandRequestStatus.ISSUED.value:
            if req.expires_at <= now:
                req.status = OnDemandRequestStatus.EXPIRED.value
                await self.db.flush()
                return req
            req.status = OnDemandRequestStatus.CONSUMED.value
            req.consumed_at = now
            if artifact_id:
                req.artifact_id = artifact_id
            await self.db.flush()
        return req
