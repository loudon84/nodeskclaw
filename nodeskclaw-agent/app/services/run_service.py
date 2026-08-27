from __future__ import annotations

import hashlib
import json
import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.schemas import ArtifactDescriptor, CreateRunRequest, CreateRunResponse, RunEventView, RunView

SCHEMA = settings.SKILL_AGENT_SCHEMA

TERMINAL = {"COMPLETED", "FAILED", "CANCELLED", "TIMED_OUT"}


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _iso(value: datetime | None) -> str:
    if value is None:
        return ""
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.isoformat()


def build_snapshot(request: CreateRunRequest, *, org_id: str, user_id: str) -> dict[str, Any]:
    digest = request.skill_release_digest or hashlib.sha256(
        f"{request.skill_id}:{request.skill_version}:{request.tool_name}".encode()
    ).hexdigest()
    body = {
        "skill_id": request.skill_id or request.tool_name,
        "skill_version": request.skill_version,
        "skill_release_id": request.skill_release_id,
        "skill_release_digest": digest,
        "connector_binding_refs": list(request.connector_binding_refs or []),
        "knowledge_refs": list(request.knowledge_refs or []),
        "model_policy": {},
        "runtime_policy": dict(request.route_snapshot or {}),
        "placement": dict(request.placement or {"role": "central"}),
        "org_id": org_id,
        "user_id": user_id,
        "output_policy": dict(request.output_policy or {}),
        "client_context": dict(request.client_context or {}),
        "request_trace_id": request.request_trace_id,
    }
    snapshot_hash = request.snapshot_hash or hashlib.sha256(
        json.dumps(body, sort_keys=True, default=str).encode()
    ).hexdigest()
    body["snapshot_hash"] = snapshot_hash
    return body


async def create_run(
    db: AsyncSession,
    request: CreateRunRequest,
    *,
    org_id: str,
    user_id: str,
) -> CreateRunResponse:
    if not request.run_id:
        raise ValueError("run_id is required")

    snapshot = build_snapshot(request, org_id=org_id, user_id=user_id)
    cmd_body = {
        "tool_name": request.tool_name,
        "skill_id": request.skill_id,
        "skill_version": request.skill_version,
        "skill_release_id": request.skill_release_id,
        "snapshot_hash": snapshot.get("snapshot_hash"),
        "arguments": request.arguments or {},
        "placement": request.placement or {},
    }
    command_digest = hashlib.sha256(json.dumps(cmd_body, sort_keys=True, default=str).encode()).hexdigest()

    # Check existing by run_id or dispatch_id or idempotency_key
    conditions = ['id = :run_id']
    params: dict[str, Any] = {"run_id": request.run_id, "org_id": org_id}
    if request.dispatch_id:
        conditions.append('(org_id = :org_id AND dispatch_id = :dispatch_id)')
        params["dispatch_id"] = request.dispatch_id
    if request.idempotency_key:
        conditions.append('(org_id = :org_id AND user_id = :user_id AND tool_name = :tool_name AND idempotency_key = :idempotency_key)')
        params["user_id"] = user_id
        params["tool_name"] = request.tool_name
        params["idempotency_key"] = request.idempotency_key

    where_clause = " OR ".join(conditions)
    existing = (
        await db.execute(
            text(
                f"""
                SELECT id, status, snapshot, command_digest
                FROM "{SCHEMA}".runs
                WHERE {where_clause}
                LIMIT 1
                """
            ),
            params,
        )
    ).mappings().first()

    if existing:
        ex_digest = existing.get("command_digest")
        if ex_digest and ex_digest != command_digest:
            raise RuntimeError("idempotency conflict: payload digest mismatch")
        ex_snapshot = existing.get("snapshot") or {}
        return CreateRunResponse(
            run_id=existing["id"],
            status=existing["status"],
            snapshot_hash=ex_snapshot.get("snapshot_hash") or snapshot["snapshot_hash"],
            org_id=existing.get("org_id") or org_id,
        )

    status = "WAITING_APPROVAL" if request.requires_approval else "QUEUED"
    try:
        await db.execute(
            text(
                f"""
                INSERT INTO "{SCHEMA}".runs (
                    id, org_id, user_id, tool_name, skill_id, status, arguments, snapshot, requires_approval,
                    dispatch_id, idempotency_key, command_digest
                ) VALUES (
                    :id, :org_id, :user_id, :tool_name, :skill_id, :status, CAST(:arguments AS jsonb),
                    CAST(:snapshot AS jsonb), :requires_approval, :dispatch_id, :idempotency_key, :command_digest
                )
                """
            ),
            {
                "id": request.run_id,
                "org_id": org_id,
                "user_id": user_id,
                "tool_name": request.tool_name,
                "skill_id": request.skill_id,
                "status": status,
                "arguments": json.dumps(request.arguments or {}),
                "snapshot": json.dumps(snapshot),
                "requires_approval": request.requires_approval,
                "dispatch_id": request.dispatch_id,
                "idempotency_key": request.idempotency_key,
                "command_digest": command_digest,
            },
        )
    except Exception as exc:
        # Concurrent insert race: re-check existing by unique constraints
        await db.rollback()
        conflict_row = (
            await db.execute(
                text(
                    f"""
                    SELECT id, org_id, status, snapshot, command_digest
                    FROM "{SCHEMA}".runs
                    WHERE {where_clause}
                    LIMIT 1
                    """
                ),
                params,
            )
        ).mappings().first()
        if conflict_row:
            conf_digest = conflict_row.get("command_digest")
            if conf_digest and conf_digest != command_digest:
                raise RuntimeError("idempotency conflict: payload digest mismatch") from exc
            conf_snapshot = conflict_row.get("snapshot") or {}
            return CreateRunResponse(
                run_id=conflict_row["id"],
                status=conflict_row["status"],
                snapshot_hash=conf_snapshot.get("snapshot_hash") or snapshot["snapshot_hash"],
                org_id=conflict_row.get("org_id") or org_id,
            )
        raise

    await append_event(
        db,
        request.run_id,
        "run.created",
        {"status": status, "tool_name": request.tool_name},
    )
    if status == "QUEUED":
        await append_event(db, request.run_id, "run.queued", {"status": status})
    return CreateRunResponse(
        run_id=request.run_id,
        status=status,
        snapshot_hash=snapshot["snapshot_hash"],
        org_id=org_id,
    )


async def get_run(db: AsyncSession, run_id: str, *, org_id: str) -> RunView | None:
    conditions = ['id = :id', 'org_id = :org_id']
    params: dict[str, Any] = {"id": run_id, "org_id": org_id}
    where_sql = " AND ".join(conditions)
    row = (
        await db.execute(
            text(
                f"""
                SELECT id, org_id, user_id, tool_name, status, snapshot, result, attempt_id, generation, created_at, updated_at
                FROM "{SCHEMA}".runs WHERE {where_sql}
                """
            ),
            params,
        )
    ).mappings().first()
    if not row:
        return None
    return RunView(
        run_id=row["id"],
        org_id=row["org_id"],
        user_id=row["user_id"],
        tool_name=row["tool_name"],
        status=row["status"],
        snapshot=row["snapshot"] or {},
        result=row["result"],
        attempt_id=row["attempt_id"],
        generation=int(row.get("generation") or 0),
        created_at=_iso(row["created_at"]),
        updated_at=_iso(row["updated_at"]),
    )


async def append_event(
    db: AsyncSession,
    run_id: str,
    event_type: str,
    payload: dict[str, Any] | None = None,
    *,
    attempt_id: str | None = None,
    source: str = "agent",
    source_event_id: str | None = None,
) -> RunEventView:
    if attempt_id:
        current = (
            await db.execute(
                text(f'SELECT attempt_id FROM "{SCHEMA}".runs WHERE id = :id'),
                {"id": run_id},
            )
        ).scalar_one_or_none()
        if current and current != attempt_id:
            raise RuntimeError("stale attempt cannot write events")

    payload = payload or {}
    now = _utcnow()

    # Idempotency check if source_event_id provided
    if source_event_id:
        existing_event = (
            await db.execute(
                text(
                    f"""
                    SELECT id, run_id, attempt_id, event_type, event_seq, source, source_event_id, payload, created_at
                    FROM "{SCHEMA}".run_events
                    WHERE run_id = :run_id AND source = :source AND source_event_id = :source_event_id
                    LIMIT 1
                    """
                ),
                {"run_id": run_id, "source": source, "source_event_id": source_event_id},
            )
        ).mappings().first()
        if existing_event:
            exist_payload = existing_event["payload"] or {}
            exist_digest = hashlib.sha256(json.dumps(exist_payload, sort_keys=True, default=str).encode()).hexdigest()
            new_digest = hashlib.sha256(json.dumps(payload, sort_keys=True, default=str).encode()).hexdigest()
            if exist_digest != new_digest:
                raise RuntimeError("idempotency conflict: source_event_id payload mismatch")
            return RunEventView(
                event_id=existing_event["id"],
                run_id=existing_event["run_id"],
                event_type=existing_event["event_type"],
                event_seq=existing_event["event_seq"],
                source=existing_event["source"],
                source_event_id=existing_event["source_event_id"],
                timestamp=_iso(existing_event["created_at"]),
                payload=exist_payload,
            )

    event_id = str(uuid.uuid4())

    # Per-run atomic event sequence allocator via UPDATE runs ... RETURNING next_event_seq
    seq_row = (
        await db.execute(
            text(
                f"""
                UPDATE "{SCHEMA}".runs
                SET next_event_seq = COALESCE(next_event_seq, 0) + 1,
                    updated_at = :now
                WHERE id = :run_id
                RETURNING next_event_seq
                """
            ),
            {"run_id": run_id, "now": now},
        )
    ).mappings().first()

    event_seq = seq_row["next_event_seq"] if seq_row else 1

    await db.execute(
        text(
            f"""
            INSERT INTO "{SCHEMA}".run_events (
                id, run_id, attempt_id, event_type, event_seq, source, source_event_id, payload, created_at
            ) VALUES (
                :id, :run_id, :attempt_id, :event_type, :event_seq, :source, :source_event_id, CAST(:payload AS jsonb), :created_at
            )
            """
        ),
        {
            "id": event_id,
            "run_id": run_id,
            "attempt_id": attempt_id,
            "event_type": event_type,
            "event_seq": event_seq,
            "source": source,
            "source_event_id": source_event_id,
            "payload": json.dumps(payload),
            "created_at": now,
        },
    )

    return RunEventView(
        event_id=event_id,
        run_id=run_id,
        event_type=event_type,
        event_seq=event_seq,
        source=source,
        source_event_id=source_event_id,
        timestamp=_iso(now),
        payload=payload,
    )


async def list_events(
    db: AsyncSession,
    run_id: str,
    *,
    after_seq: int = 0,
) -> list[RunEventView]:
    rows = (
        await db.execute(
            text(
                f"""
                SELECT id, run_id, attempt_id, event_type, event_seq, source, source_event_id, payload, created_at
                FROM "{SCHEMA}".run_events
                WHERE run_id = :run_id AND event_seq > :after_seq
                ORDER BY event_seq ASC
                """
            ),
            {"run_id": run_id, "after_seq": after_seq},
        )
    ).mappings().all()
    return [
        RunEventView(
            event_id=row["id"],
            run_id=row["run_id"],
            event_type=row["event_type"],
            event_seq=row["event_seq"],
            source=row.get("source") or "agent",
            source_event_id=row.get("source_event_id"),
            timestamp=_iso(row["created_at"]),
            payload=row["payload"] or {},
        )
        for row in rows
    ]


async def list_artifacts(db: AsyncSession, run_id: str) -> list[ArtifactDescriptor]:
    rows = (
        await db.execute(
            text(
                f"""
                SELECT id, name, content_type, size_bytes, storage_ref, checksum_sha256
                FROM "{SCHEMA}".run_artifacts WHERE run_id = :run_id ORDER BY created_at ASC
                """
            ),
            {"run_id": run_id},
        )
    ).mappings().all()
    return [
        ArtifactDescriptor(
            artifact_id=row["id"],
            name=row["name"],
            content_type=row["content_type"],
            size_bytes=row["size_bytes"],
            download_url=f"/api/v1/runs/{run_id}/artifacts/{row['id']}/download",
            checksum_sha256=row["checksum_sha256"],
        )
        for row in rows
    ]


async def set_status(
    db: AsyncSession,
    run_id: str,
    status: str,
    *,
    attempt_id: str | None = None,
    expected_status: str | list[str] | None = None,
    result: dict[str, Any] | None = None,
) -> bool:
    if attempt_id:
        current = (
            await db.execute(
                text(f'SELECT attempt_id FROM "{SCHEMA}".runs WHERE id = :id'),
                {"id": run_id},
            )
        ).scalar_one_or_none()
        if current and current != attempt_id:
            raise RuntimeError("stale attempt cannot update status")

    conditions = ['id = :id']
    params: dict[str, Any] = {
        "id": run_id,
        "status": status,
        "result": json.dumps(result) if result is not None else None,
        "updated_at": _utcnow(),
    }
    if attempt_id is not None:
        conditions.append('attempt_id = :attempt_id')
        params["attempt_id"] = attempt_id

    if expected_status is not None:
        if isinstance(expected_status, str):
            conditions.append('status = :expected_status')
            params["expected_status"] = expected_status
        elif isinstance(expected_status, (list, tuple, set)):
            status_params = [f":st_{i}" for i in range(len(expected_status))]
            for i, st in enumerate(expected_status):
                params[f"st_{i}"] = st
            conditions.append(f'status IN ({", ".join(status_params)})')

    where_clause = " AND ".join(conditions)
    res = await db.execute(
        text(
            f"""
            UPDATE "{SCHEMA}".runs
            SET status = :status,
                result = COALESCE(CAST(:result AS jsonb), result),
                updated_at = :updated_at
            WHERE {where_clause}
            """
        ),
        params,
    )
    rowcount = getattr(res, "rowcount", 1)
    return (rowcount or 0) > 0


async def approve_run(
    db: AsyncSession,
    run_id: str,
    *,
    org_id: str,
    approval_id: str | None = None,
    evidence: dict[str, Any] | None = None,
) -> RunView | None:
    run = await get_run(db, run_id, org_id=org_id)
    if not run:
        return None
    
    # Idempotent approval record checking
    eff_approval_id = approval_id or f"appr-{run_id}"
    evidence_dict = evidence or {}

    try:
        await db.execute(
            text(
                f"""
                INSERT INTO "{SCHEMA}".run_approvals (id, run_id, approval_id, decision, evidence, created_at)
                VALUES (:id, :run_id, :approval_id, 'APPROVED', CAST(:evidence AS jsonb), NOW())
                ON CONFLICT (run_id, approval_id) DO NOTHING
                """
            ),
            {
                "id": str(uuid.uuid4()),
                "run_id": run_id,
                "approval_id": eff_approval_id,
                "evidence": json.dumps(evidence_dict),
            },
        )
    except Exception:
        logger.debug("run_approvals table insert skipped", exc_info=True)

    if run.status != "WAITING_APPROVAL":
        return run

    evidence_payload = {"status": "RESUMING", "approval_id": eff_approval_id, "evidence": evidence_dict}
    await set_status(db, run_id, "RESUMING", expected_status=["WAITING_APPROVAL"])
    await append_event(db, run_id, "run.resuming", evidence_payload)
    await set_status(db, run_id, "QUEUED", expected_status=["RESUMING"])
    await append_event(db, run_id, "run.queued", {"status": "QUEUED"})
    return await get_run(db, run_id, org_id=org_id)


async def cancel_run(db: AsyncSession, run_id: str, *, org_id: str) -> RunView | None:
    run = await get_run(db, run_id, org_id=org_id)
    if not run:
        return None
    if run.status in TERMINAL:
        return run

    # If already CANCELLING or in-flight (RUNNING/PREPARING with worker)
    if run.status in ("PREPARING", "RUNNING") and run.attempt_id:
        # Move to CANCELLING state
        await set_status(db, run_id, "CANCELLING", expected_status=["PREPARING", "RUNNING", "RESUMING"])
        await append_event(db, run_id, "run.cancelling", {"status": "CANCELLING"})
        return await get_run(db, run_id, org_id=org_id)

    # If QUEUED or WAITING_APPROVAL (no active in-flight worker execution), cancel immediately
    if run.attempt_id:
        await db.execute(
            text(
                f"""
                UPDATE "{SCHEMA}".run_attempts
                SET status = 'CANCELLED', completed_at = NOW(), error_message = 'run cancelled'
                WHERE id = :id AND status IN ('PREPARING', 'RUNNING')
                """
            ),
            {"id": run.attempt_id},
        )
    await set_status(db, run_id, "CANCELLED")
    await append_event(db, run_id, "run.cancelled", {"status": "CANCELLED"})
    return await get_run(db, run_id, org_id=org_id)


async def add_artifact(
    db: AsyncSession,
    run_id: str,
    *,
    name: str,
    content_type: str | None = None,
    size_bytes: int | None = None,
    storage_ref: str | None = None,
    checksum_sha256: str | None = None,
    attempt_id: str | None = None,
) -> ArtifactDescriptor:
    if attempt_id:
        current = (
            await db.execute(
                text(f'SELECT attempt_id FROM "{SCHEMA}".runs WHERE id = :id'),
                {"id": run_id},
            )
        ).scalar_one_or_none()
        if current and current != attempt_id:
            raise RuntimeError("stale attempt cannot write artifacts")

    artifact_id = str(uuid.uuid4())
    await db.execute(
        text(
            f"""
            INSERT INTO "{SCHEMA}".run_artifacts (
                id, run_id, attempt_id, name, content_type, size_bytes, storage_ref, checksum_sha256
            ) VALUES (
                :id, :run_id, :attempt_id, :name, :content_type, :size_bytes, :storage_ref, :checksum_sha256
            )
            """
        ),
        {
            "id": artifact_id,
            "run_id": run_id,
            "attempt_id": attempt_id,
            "name": name,
            "content_type": content_type,
            "size_bytes": size_bytes,
            "storage_ref": storage_ref,
            "checksum_sha256": checksum_sha256,
        },
    )
    await append_event(
        db,
        run_id,
        "run.artifact_ready",
        {"artifact_id": artifact_id, "name": name},
        attempt_id=attempt_id,
    )
    return ArtifactDescriptor(
        artifact_id=artifact_id,
        name=name,
        content_type=content_type,
        size_bytes=size_bytes,
        download_url=f"/api/v1/runs/{run_id}/artifacts/{artifact_id}/download",
        checksum_sha256=checksum_sha256,
    )


async def store_artifact_bytes(
    db: AsyncSession,
    run_id: str,
    *,
    name: str,
    content: bytes,
    content_type: str | None = "text/plain",
    attempt_id: str | None = None,
) -> ArtifactDescriptor:
    if attempt_id:
        current = (
            await db.execute(
                text(f'SELECT attempt_id FROM "{SCHEMA}".runs WHERE id = :id'),
                {"id": run_id},
            )
        ).scalar_one_or_none()
        if current and current != attempt_id:
            raise RuntimeError("stale attempt cannot write artifacts")

    from pathlib import Path

    root = Path(settings.SKILL_AGENT_ARTIFACT_DIR) / run_id
    root.mkdir(parents=True, exist_ok=True)
    artifact_id = str(uuid.uuid4())
    path = root / f"{artifact_id}_{name}"
    path.write_bytes(content)
    checksum = hashlib.sha256(content).hexdigest()
    await db.execute(
        text(
            f"""
            INSERT INTO "{SCHEMA}".run_artifacts (
                id, run_id, attempt_id, name, content_type, size_bytes, storage_ref, checksum_sha256
            ) VALUES (
                :id, :run_id, :attempt_id, :name, :content_type, :size_bytes, :storage_ref, :checksum_sha256
            )
            """
        ),
        {
            "id": artifact_id,
            "run_id": run_id,
            "attempt_id": attempt_id,
            "name": name,
            "content_type": content_type,
            "size_bytes": len(content),
            "storage_ref": str(path),
            "checksum_sha256": checksum,
        },
    )
    await append_event(
        db,
        run_id,
        "run.artifact_ready",
        {"artifact_id": artifact_id, "name": name},
        attempt_id=attempt_id,
    )
    return ArtifactDescriptor(
        artifact_id=artifact_id,
        name=name,
        content_type=content_type,
        size_bytes=len(content),
        download_url=f"/api/v1/runs/{run_id}/artifacts/{artifact_id}/download",
        checksum_sha256=checksum,
    )


async def get_artifact_bytes(db: AsyncSession, run_id: str, artifact_id: str) -> tuple[dict, bytes] | None:
    import base64
    from pathlib import Path

    row = (
        await db.execute(
            text(
                f"""
                SELECT id, name, content_type, size_bytes, storage_ref, checksum_sha256
                FROM "{SCHEMA}".run_artifacts
                WHERE run_id = :run_id AND id = :artifact_id
                """
            ),
            {"run_id": run_id, "artifact_id": artifact_id},
        )
    ).mappings().first()
    if not row or not row["storage_ref"]:
        return None
    ref = str(row["storage_ref"])
    if ref.startswith("data:base64:"):
        return dict(row), base64.b64decode(ref.removeprefix("data:base64:"))
    path = Path(ref)
    if not path.is_file():
        return None
    return dict(row), path.read_bytes()
