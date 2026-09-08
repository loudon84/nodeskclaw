from __future__ import annotations

import hashlib
import secrets
import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import BadRequestError, ConflictError, ForbiddenError, NotFoundError
from app.models.base import not_deleted
from app.models.connector.edge_node import EdgeNode, EdgeNodeStatus
from app.models.operation_audit_log import OperationAuditLog
from app.services.connector.edge_control_channel import EdgeControlChannel


def hash_edge_token(plain: str) -> str:
    return hashlib.sha256(plain.encode("utf-8")).hexdigest()


def hash_edge_bootstrap(plain: str) -> str:
    return hash_edge_token(plain)


class EdgeNodeService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def _audit(
        self,
        *,
        action: str,
        target_id: str,
        org_id: str,
        actor_type: str,
        actor_id: str,
        actor_name: str | None = None,
        details: dict | None = None,
    ) -> None:
        record = OperationAuditLog(
            id=str(uuid.uuid4()),
            org_id=org_id,
            action=action,
            target_type="edge_node",
            target_id=target_id,
            actor_type=actor_type,
            actor_id=actor_id,
            actor_name=actor_name,
            details=details or {},
            created_at=datetime.now(timezone.utc),
        )
        self.db.add(record)
        await self.db.flush()

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
    ) -> tuple[EdgeNode, str, datetime]:
        existing = await self._get_by_name(org_id, name)
        if existing:
            raise ConflictError(
                "Edge 节点名称已存在",
                "errors.connector.edge_node_name_conflict",
            )

        bootstrap = secrets.token_urlsafe(32)
        now = datetime.now(timezone.utc)
        ttl = EdgeControlChannel.bootstrap_ttl_seconds()
        expires_at = now + timedelta(seconds=ttl)
        node = EdgeNode(
            org_id=org_id,
            name=name,
            status=EdgeNodeStatus.PENDING.value,
            token_hash=hash_edge_bootstrap(bootstrap),
            bootstrap_expires_at=expires_at,
            created_by=operator_user_id,
        )
        self.db.add(node)
        await self.db.flush()
        await self._audit(
            action="edge_node.register",
            target_id=node.id,
            org_id=org_id,
            actor_type="user",
            actor_id=operator_user_id or "",
            details={"node_name": name, "bootstrap_expires_at": expires_at.isoformat()},
        )
        return node, bootstrap, expires_at

    async def bind_identity(
        self,
        *,
        org_id: str,
        node_id: str,
        bootstrap: str,
        public_key: str,
    ) -> dict:
        node = await self.get(org_id, node_id)
        if node.bootstrap_consumed_at is not None:
            raise ForbiddenError("引导材料已使用", "errors.connector.edge_bootstrap_reused")
        if node.bootstrap_expires_at and node.bootstrap_expires_at < datetime.now(timezone.utc):
            raise ForbiddenError("引导材料已过期", "errors.connector.edge_bootstrap_expired")
        if node.token_hash != hash_edge_bootstrap(bootstrap):
            raise ForbiddenError("引导材料无效", "errors.connector.edge_bootstrap_invalid")
        if node.identity_revoked_at is not None:
            raise ForbiddenError("Edge 身份已撤销", "errors.connector.edge_identity_revoked")
        if node.status == EdgeNodeStatus.DISABLED.value:
            raise ForbiddenError("Edge 节点已禁用", "errors.connector.edge_node_disabled")
        now = datetime.now(timezone.utc)
        node.public_key = public_key
        node.identity_version = 1
        node.bootstrap_consumed_at = now
        node.last_request_seq = 0
        node.status = EdgeNodeStatus.PENDING.value
        await self.db.flush()
        bundle = EdgeControlChannel(self.db).issuer_bundle()
        await self._audit(
            action="edge_node.bind",
            target_id=node.id,
            org_id=org_id,
            actor_type="edge_node",
            actor_id=node.id,
            details={"identity_version": node.identity_version},
        )
        return {
            "node_id": node.id,
            "org_id": node.org_id,
            "identity_version": node.identity_version,
            "issuer_key_id": bundle.issuer_key_id,
            "issuer_public_key": bundle.issuer_public_key,
            "previous_issuer_key_id": bundle.previous_issuer_key_id,
            "previous_issuer_public_key": bundle.previous_issuer_public_key,
            "issuer_rotation_expires_at": (
                bundle.issuer_rotation_expires_at.isoformat()
                if bundle.issuer_rotation_expires_at
                else None
            ),
        }

    async def disable_node(self, org_id: str, node_id: str, operator_user_id: str) -> EdgeNode:
        node = await self.get(org_id, node_id)
        node.status = EdgeNodeStatus.DISABLED.value
        await self.db.flush()
        await self._audit(
            action="edge_node.disable",
            target_id=node.id,
            org_id=org_id,
            actor_type="user",
            actor_id=operator_user_id,
        )
        return node

    async def enable_node(self, org_id: str, node_id: str, operator_user_id: str) -> EdgeNode:
        node = await self.get(org_id, node_id)
        if not node.public_key or node.identity_revoked_at is not None:
            raise BadRequestError("节点身份无效，无法启用", "errors.connector.edge_identity_not_bound")
        node.status = EdgeNodeStatus.PENDING.value
        await self.db.flush()
        await self._audit(
            action="edge_node.enable",
            target_id=node.id,
            org_id=org_id,
            actor_type="user",
            actor_id=operator_user_id,
        )
        return node

    async def revoke_node(self, org_id: str, node_id: str, operator_user_id: str) -> EdgeNode:
        node = await self.get(org_id, node_id)
        now = datetime.now(timezone.utc)
        node.identity_revoked_at = now
        node.status = EdgeNodeStatus.DISABLED.value
        await self.db.flush()
        await self._audit(
            action="edge_node.revoke",
            target_id=node.id,
            org_id=org_id,
            actor_type="user",
            actor_id=operator_user_id,
        )
        return node

    async def start_rotation(self, org_id: str, node_id: str, operator_user_id: str) -> EdgeNode:
        node = await self.get(org_id, node_id)
        if not node.public_key or node.identity_revoked_at is not None:
            raise BadRequestError("节点尚未绑定有效身份", "errors.connector.edge_identity_not_bound")
        now = datetime.now(timezone.utc)
        window = EdgeControlChannel.rotation_window_seconds()
        node.identity_rotation_expires_at = now + timedelta(seconds=window)
        await self.db.flush()
        await self._audit(
            action="edge_node.rotate_start",
            target_id=node.id,
            org_id=org_id,
            actor_type="user",
            actor_id=operator_user_id,
            details={"rotation_expires_at": node.identity_rotation_expires_at.isoformat()},
        )
        return node

    async def complete_rotation(
        self,
        *,
        org_id: str,
        node_id: str,
        new_public_key: str,
    ) -> dict:
        node = await self.get(org_id, node_id)
        if not node.identity_rotation_expires_at:
            raise ForbiddenError("未处于轮换窗口", "errors.connector.edge_rotation_not_active")
        now = datetime.now(timezone.utc)
        if node.identity_rotation_expires_at < now:
            raise ForbiddenError("轮换窗口已结束", "errors.connector.edge_rotation_expired")
        node.previous_public_key = node.public_key
        node.public_key = new_public_key
        node.identity_version = (node.identity_version or 0) + 1
        node.last_request_seq = 0
        node.identity_rotation_expires_at = None
        await self.db.flush()
        bundle = EdgeControlChannel(self.db).issuer_bundle()
        await self._audit(
            action="edge_node.rotate_complete",
            target_id=node.id,
            org_id=org_id,
            actor_type="edge_node",
            actor_id=node.id,
            details={"identity_version": node.identity_version},
        )
        return {
            "node_id": node.id,
            "org_id": node.org_id,
            "identity_version": node.identity_version,
            "issuer_key_id": bundle.issuer_key_id,
            "issuer_public_key": bundle.issuer_public_key,
            "previous_issuer_key_id": bundle.previous_issuer_key_id,
            "previous_issuer_public_key": bundle.previous_issuer_public_key,
            "issuer_rotation_expires_at": (
                bundle.issuer_rotation_expires_at.isoformat()
                if bundle.issuer_rotation_expires_at
                else None
            ),
        }

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
