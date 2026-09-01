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


def _sanitize_sensitive_keys(data: Any) -> Any:
    if isinstance(data, dict):
        sanitized = {}
        for k, v in data.items():
            if any(s in k.lower() for s in ("token", "secret", "password", "api_key", "authorization", "auth_token")):
                sanitized[k] = "[REDACTED]"
            else:
                sanitized[k] = _sanitize_sensitive_keys(v)
        return sanitized
    elif isinstance(data, list):
        return [_sanitize_sensitive_keys(x) for x in data]
    return data


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
        "runtime_policy": _sanitize_sensitive_keys(dict(request.route_snapshot or {})),
        "placement": dict(request.placement or {"role": "central"}),
        "org_id": org_id,
        "user_id": user_id,
        "output_policy": dict(request.output_policy or {}),
        "client_context": _sanitize_sensitive_keys(dict(request.client_context or {})),
        "request_trace_id": request.request_trace_id,
        "run_session_id": request.run_session_id,
    }
    if request.execution_context is not None:
        body["execution_context"] = _sanitize_sensitive_keys(dict(request.execution_context))
    if request.context_version is not None:
        body["context_version"] = int(request.context_version)
    snapshot_hash = request.snapshot_hash or hashlib.sha256(
        json.dumps(body, sort_keys=True, default=str).encode()
    ).hexdigest()
    body["snapshot_hash"] = snapshot_hash
    return body


async def _ensure_run_session(
    db: AsyncSession,
    *,
    run_session_id: str,
    org_id: str,
    user_id: str,
    context_version: int | None = None,
) -> int:
    if not run_session_id or len(run_session_id) > 36:
        raise ValueError("run session id invalid")

    sess_row = (
        await db.execute(
            text(
                f"""
                SELECT id, org_id, user_id, context_version, deleted_at, expires_at
                FROM "{SCHEMA}".run_sessions
                WHERE id = :id
                LIMIT 1
                """
            ),
            {"id": run_session_id},
        )
    ).mappings().first()

    now = _utcnow()
    if sess_row:
        if sess_row["org_id"] != org_id:
            raise ValueError("cross-org run session access rejected")
        if sess_row["user_id"] != user_id:
            raise ValueError("run session subject mismatch rejected")
        if sess_row.get("deleted_at") is not None:
            raise ValueError("run session unrecoverable: soft deleted")
        expires_at = sess_row.get("expires_at")
        if expires_at is not None:
            exp = expires_at
            if exp.tzinfo is None:
                exp = exp.replace(tzinfo=timezone.utc)
            if exp <= now:
                raise ValueError("run session unrecoverable: expired")
        current_version = int(sess_row.get("context_version") or 0)
        if context_version is not None and context_version > current_version:
            await db.execute(
                text(
                    f"""
                    UPDATE "{SCHEMA}".run_sessions
                    SET context_version = :context_version, updated_at = :now
                    WHERE id = :id AND org_id = :org_id AND user_id = :user_id AND deleted_at IS NULL
                    """
                ),
                {
                    "id": run_session_id,
                    "org_id": org_id,
                    "user_id": user_id,
                    "context_version": int(context_version),
                    "now": now,
                },
            )
            return int(context_version)
        return current_version

    await db.execute(
        text(
            f"""
            INSERT INTO "{SCHEMA}".run_sessions (
                id, org_id, user_id, metadata, context_version, created_at, updated_at
            ) VALUES (
                :id, :org_id, :user_id, '{{}}'::jsonb, :context_version, :now, :now
            )
            """
        ),
        {
            "id": run_session_id,
            "org_id": org_id,
            "user_id": user_id,
            "context_version": int(context_version or 0),
            "now": now,
        },
    )
    return int(context_version or 0)


async def create_run(
    db: AsyncSession,
    request: CreateRunRequest,
    *,
    org_id: str,
    user_id: str,
) -> CreateRunResponse:
    if not request.run_id:
        raise ValueError("run_id is required")

    if request.run_session_id:
        await _ensure_run_session(
            db,
            run_session_id=request.run_session_id,
            org_id=org_id,
            user_id=user_id,
            context_version=request.context_version,
        )

    snapshot = build_snapshot(request, org_id=org_id, user_id=user_id)
    cmd_body = {
        "tool_name": request.tool_name,
        "skill_id": request.skill_id,
        "skill_version": request.skill_version,
        "skill_release_id": request.skill_release_id,
        "snapshot_hash": snapshot.get("snapshot_hash"),
        "arguments": request.arguments or {},
        "placement": request.placement or {},
        "run_session_id": request.run_session_id,
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
                SELECT id, org_id, status, snapshot, command_digest, run_session_id
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
            run_session_id=existing.get("run_session_id") or request.run_session_id,
        )

    status = "WAITING_APPROVAL" if request.requires_approval else "QUEUED"
    try:
        await db.execute(
            text(
                f"""
                INSERT INTO "{SCHEMA}".runs (
                    id, org_id, user_id, tool_name, skill_id, status, arguments, snapshot, requires_approval,
                    dispatch_id, idempotency_key, command_digest, run_session_id
                ) VALUES (
                    :id, :org_id, :user_id, :tool_name, :skill_id, :status, CAST(:arguments AS jsonb),
                    CAST(:snapshot AS jsonb), :requires_approval, :dispatch_id, :idempotency_key, :command_digest,
                    :run_session_id
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
                "run_session_id": request.run_session_id,
            },
        )
    except Exception as exc:
        # Concurrent insert race: re-check existing by unique constraints
        await db.rollback()
        conflict_row = (
            await db.execute(
                text(
                    f"""
                    SELECT id, org_id, status, snapshot, command_digest, run_session_id
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
                run_session_id=conflict_row.get("run_session_id") or request.run_session_id,
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
        run_session_id=request.run_session_id,
    )


async def get_run(db: AsyncSession, run_id: str, *, org_id: str) -> RunView | None:
    conditions = ['id = :id', 'org_id = :org_id']
    params: dict[str, Any] = {"id": run_id, "org_id": org_id}
    where_sql = " AND ".join(conditions)
    row = (
        await db.execute(
            text(
                f"""
                SELECT id, org_id, user_id, tool_name, status, snapshot, result, attempt_id, run_session_id, generation, created_at, updated_at
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
        run_session_id=row.get("run_session_id"),
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
    org_id: str | None = None,
    attempt_id: str | None = None,
    generation: int | None = None,
    source: str = "agent",
    source_event_id: str | None = None,
    request_trace_id: str | None = None,
    context_version: int | None = None,
) -> RunEventView:
    payload = dict(payload or {})
    if context_version is not None and "context_version" not in payload:
        payload["context_version"] = context_version
    now = _utcnow()

    # If request_trace_id not explicitly provided, try to fetch from run's snapshot
    if not request_trace_id:
        try:
            snap_row = (
                await db.execute(
                    text(f'SELECT snapshot FROM "{SCHEMA}".runs WHERE id = :run_id LIMIT 1'),
                    {"run_id": run_id},
                )
            ).mappings().first()
            if snap_row and snap_row.get("snapshot"):
                snap = snap_row["snapshot"]
                if isinstance(snap, dict):
                    request_trace_id = snap.get("request_trace_id")
        except Exception:
            pass

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
                request_trace_id=request_trace_id,
                timestamp=_iso(existing_event["created_at"]),
                payload=exist_payload,
            )

    event_id = str(uuid.uuid4())

    # Single-statement atomic sequence allocation and attempt/generation verification
    conditions = ['id = :run_id']
    terminal_list = ", ".join([f"'{s}'" for s in TERMINAL])
    conditions.append(f"status NOT IN ({terminal_list})")
    params: dict[str, Any] = {"run_id": run_id, "now": now}
    if org_id is not None:
        conditions.append('org_id = :org_id')
        params["org_id"] = org_id
    if attempt_id is not None:
        conditions.append('attempt_id = :attempt_id')
        params["attempt_id"] = attempt_id
    if generation is not None:
        conditions.append('generation = :generation')
        params["generation"] = generation

    where_clause = " AND ".join(conditions)
    seq_row = (
        await db.execute(
            text(
                f"""
                UPDATE "{SCHEMA}".runs
                SET next_event_seq = COALESCE(next_event_seq, 0) + 1,
                    updated_at = :now
                WHERE {where_clause}
                RETURNING next_event_seq
                """
            ),
            params,
        )
    ).mappings().first()

    if not seq_row:
        raise RuntimeError("stale attempt, invalid generation, or terminal run cannot write events")

    event_seq = seq_row["next_event_seq"]

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
        request_trace_id=request_trace_id,
        timestamp=_iso(now),
        payload=payload,
    )


async def list_events(
    db: AsyncSession,
    run_id: str,
    *,
    after_seq: int = 0,
) -> list[RunEventView]:
    # Fetch run snapshot to populate request_trace_id
    request_trace_id = None
    try:
        snap_row = (
            await db.execute(
                text(f'SELECT snapshot FROM "{SCHEMA}".runs WHERE id = :run_id LIMIT 1'),
                {"run_id": run_id},
            )
        ).mappings().first()
        if snap_row and snap_row.get("snapshot"):
            snap = snap_row["snapshot"]
            if isinstance(snap, dict):
                request_trace_id = snap.get("request_trace_id")
    except Exception:
        pass

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
            request_trace_id=request_trace_id,
            timestamp=_iso(row["created_at"]),
            payload=row["payload"] or {},
        )
        for row in rows
    ]


async def list_artifacts(db: AsyncSession, run_id: str) -> list[ArtifactDescriptor]:
    try:
        rows_res = await db.execute(
            text(
                f"""
                SELECT id, name, content_type, size_bytes, storage_ref, checksum_sha256, storage_state
                FROM "{SCHEMA}".run_artifacts
                WHERE run_id = :run_id AND (storage_state = 'PERSISTED' OR storage_state IS NULL)
                ORDER BY created_at ASC
                """
            ),
            {"run_id": run_id},
        )
        rows = rows_res.mappings().all() if hasattr(rows_res, "mappings") else []
    except Exception:
        rows = []
    return [
        ArtifactDescriptor(
            artifact_id=row["id"],
            name=row["name"],
            content_type=row["content_type"],
            size_bytes=row["size_bytes"],
            download_url=f"/api/v1/runs/{run_id}/artifacts/{row['id']}/download",
            checksum_sha256=row["checksum_sha256"],
            storage_state=str(row.get("storage_state") or "persisted").lower(),
        )
        for row in rows
    ]


async def set_status(
    db: AsyncSession,
    run_id: str,
    status: str,
    *,
    org_id: str | None = None,
    attempt_id: str | None = None,
    generation: int | None = None,
    expected_status: str | list[str] | set[str] | tuple[str, ...] | None = None,
    result: dict[str, Any] | None = None,
) -> bool:
    conditions = ['id = :id']
    params: dict[str, Any] = {
        "id": run_id,
        "status": status,
        "result": json.dumps(result) if result is not None else None,
        "updated_at": _utcnow(),
    }
    if org_id is not None:
        conditions.append('org_id = :org_id')
        params["org_id"] = org_id
    if attempt_id is not None:
        conditions.append('attempt_id = :attempt_id')
        params["attempt_id"] = attempt_id
    if generation is not None:
        conditions.append('generation = :generation')
        params["generation"] = generation

    if expected_status is not None:
        if isinstance(expected_status, str):
            conditions.append('status = :expected_status')
            params["expected_status"] = expected_status
        elif isinstance(expected_status, (list, tuple, set)):
            status_params = [f":st_{i}" for i in range(len(expected_status))]
            for i, st in enumerate(expected_status):
                params[f"st_{i}"] = st
            conditions.append(f'status IN ({", ".join(status_params)})')
    else:
        # Non-terminal transitions cannot overwrite terminal status,
        # and terminal status cannot overwrite another terminal status (terminal CAS)
        if status in TERMINAL:
            terminal_list = ", ".join([f"'{s}'" for s in TERMINAL])
            conditions.append(f"status NOT IN ({terminal_list})")

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
    rowcount = getattr(res, "rowcount", None)
    if isinstance(rowcount, int):
        if rowcount == 0:
            if attempt_id is not None:
                raise RuntimeError("stale attempt cannot update status")
            return False
    elif rowcount is not None and not isinstance(rowcount, (int, float)):
        return True
    return True


async def resume_run(
    db: AsyncSession,
    run_id: str,
    *,
    org_id: str,
    evidence: dict[str, Any] | None = None,
) -> RunView | None:
    run = await get_run(db, run_id, org_id=org_id)
    if not run:
        return None

    if run.status == "WAITING_APPROVAL":
        raise ValueError("run in WAITING_APPROVAL state requires approval via approve endpoint, not resume")

    if run.status in ("PAUSED", "SUSPENDED"):
        evidence_dict = evidence or {}
        evidence_payload = {"status": "RESUMING", "evidence": evidence_dict}
        await set_status(db, run_id, "RESUMING", org_id=org_id, expected_status=["PAUSED", "SUSPENDED"])
        await append_event(db, run_id, "run.resuming", evidence_payload, org_id=org_id)
        await set_status(db, run_id, "QUEUED", org_id=org_id, expected_status=["RESUMING"])
        await append_event(db, run_id, "run.queued", {"status": "QUEUED"}, org_id=org_id)
        return await get_run(db, run_id, org_id=org_id)

    return run


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

    if not approval_id:
        raise ValueError("approval_id is required to approve run")

    evidence_dict = evidence or {}

    try:
        await db.execute(
            text(
                f"""
                INSERT INTO "{SCHEMA}".run_approvals (id, run_id, approval_id, decision, evidence, created_at)
                VALUES (:id, :run_id, :approval_id, 'APPROVED', CAST(:evidence AS jsonb), NOW())
                ON CONFLICT (run_id, approval_id) DO UPDATE SET evidence = CAST(:evidence AS jsonb)
                """
            ),
            {
                "id": str(uuid.uuid4()),
                "run_id": run_id,
                "approval_id": approval_id,
                "evidence": json.dumps(evidence_dict),
            },
        )
    except Exception:
        pass

    if run.status != "WAITING_APPROVAL":
        return run

    evidence_payload = {"status": "RESUMING", "approval_id": approval_id, "evidence": evidence_dict}
    await set_status(db, run_id, "RESUMING", org_id=org_id, expected_status=["WAITING_APPROVAL"])
    await append_event(db, run_id, "run.resuming", evidence_payload, org_id=org_id)
    await set_status(db, run_id, "QUEUED", org_id=org_id, expected_status=["RESUMING"])
    await append_event(db, run_id, "run.queued", {"status": "QUEUED"}, org_id=org_id)
    return await get_run(db, run_id, org_id=org_id)


async def cancel_run(db: AsyncSession, run_id: str, *, org_id: str) -> RunView | None:
    run = await get_run(db, run_id, org_id=org_id)
    if not run:
        return None
    if run.status in TERMINAL:
        return run

    # If WAITING_EDGE, transition to CANCELLING and cancel non-terminal steps, then aggregate
    if run.status == "WAITING_EDGE":
        ok = await set_status(
            db,
            run_id,
            "CANCELLING",
            org_id=org_id,
            expected_status=["WAITING_EDGE", "PREPARING", "RUNNING", "RESUMING"],
        )
        if ok:
            await append_event(db, run_id, "run.cancelling", {"status": "CANCELLING"}, org_id=org_id)
        await db.execute(
            text(
                f"""
                UPDATE "{SCHEMA}".run_steps
                SET status = 'CANCELLED', updated_at = NOW()
                WHERE run_id = :run_id AND status IN ('PENDING', 'READY', 'DISPATCHED', 'RUNNING')
                """
            ),
            {"run_id": run_id},
        )
        return await aggregate_run_terminal(db, run_id, org_id=org_id)

    # If already CANCELLING or in-flight (RUNNING/PREPARING/RESUMING with worker)
    if run.status in ("PREPARING", "RUNNING", "RESUMING") and run.attempt_id:
        # Move to CANCELLING state
        ok = await set_status(db, run_id, "CANCELLING", org_id=org_id, expected_status=["PREPARING", "RUNNING", "RESUMING"])
        if ok:
            await append_event(db, run_id, "run.cancelling", {"status": "CANCELLING"}, org_id=org_id)
        return await get_run(db, run_id, org_id=org_id)

    # If QUEUED, WAITING_APPROVAL, PAUSED, SUSPENDED (no active in-flight worker execution), cancel immediately
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
    await db.execute(
        text(
            f"""
            UPDATE "{SCHEMA}".run_steps
            SET status = 'CANCELLED', updated_at = NOW()
            WHERE run_id = :run_id AND status IN ('PENDING', 'READY', 'DISPATCHED', 'RUNNING')
            """
        ),
        {"run_id": run_id},
    )
    ok = await set_status(
        db,
        run_id,
        "CANCELLED",
        org_id=org_id,
        expected_status=["QUEUED", "WAITING_APPROVAL", "PAUSED", "SUSPENDED", "CANCELLING"],
    )
    if ok:
        await append_event(db, run_id, "run.cancelled", {"status": "CANCELLED"}, org_id=org_id)
    return await get_run(db, run_id, org_id=org_id)


async def persist_step_plan(
    db: AsyncSession,
    run_id: str,
    step_plan: list[dict[str, Any]],
    *,
    org_id: str | None = None,
    attempt_id: str | None = None,
    run_generation: int = 0,
) -> list[dict[str, Any]]:
    try:
        res = await db.execute(
            text(
                f"""
                SELECT id, run_id, step_id, owner_role, engine, status, depends_on, required, required_artifacts, attempt_id, run_generation, edge_job_id, version, result, error_message, created_at, updated_at
                FROM "{SCHEMA}".run_steps
                WHERE run_id = :run_id
                ORDER BY created_at ASC
                """
            ),
            {"run_id": run_id},
        )
        existing = res.mappings().all() if hasattr(res, "mappings") else []
    except Exception:
        existing = []

    if existing:
        return [dict(row) for row in existing]

    persisted = []
    now = _utcnow()
    for item in step_plan:
        step_id = str(item.get("step_id") or item.get("step") or f"step_{uuid.uuid4().hex[:8]}")
        owner_role = str(item.get("role") or item.get("owner_role") or "central")
        engine = str(item.get("engine") or "hermes")
        required = bool(item.get("required", True))
        depends_on = item.get("dependencies") or item.get("depends_on") or []
        required_artifacts = item.get("required_artifacts") or []
        step_uuid = str(uuid.uuid4())

        await db.execute(
            text(
                f"""
                INSERT INTO "{SCHEMA}".run_steps (
                    id, run_id, step_id, owner_role, engine, status, depends_on,
                    required, required_artifacts, attempt_id, run_generation,
                    version, created_at, updated_at
                )
                VALUES (
                    :id, :run_id, :step_id, :owner_role, :engine, 'PENDING',
                    CAST(:depends_on AS jsonb), :required, CAST(:required_artifacts AS jsonb),
                    :attempt_id, :run_generation, 1, :now, :now
                )
                ON CONFLICT (run_id, step_id) DO NOTHING
                """
            ),
            {
                "id": step_uuid,
                "run_id": run_id,
                "step_id": step_id,
                "owner_role": owner_role,
                "engine": engine,
                "depends_on": json.dumps(depends_on),
                "required": required,
                "required_artifacts": json.dumps(required_artifacts),
                "attempt_id": attempt_id,
                "run_generation": run_generation,
                "now": now,
            },
        )
        persisted.append({
            "id": step_uuid,
            "run_id": run_id,
            "step_id": step_id,
            "owner_role": owner_role,
            "engine": engine,
            "status": "PENDING",
            "depends_on": depends_on,
            "required": required,
            "required_artifacts": required_artifacts,
            "attempt_id": attempt_id,
            "run_generation": run_generation,
            "version": 1,
        })
    return persisted


async def update_step_state(
    db: AsyncSession,
    run_id: str,
    step_id: str,
    status: str,
    *,
    attempt_id: str | None = None,
    run_generation: int | None = None,
    edge_job_id: str | None = None,
    result: dict[str, Any] | None = None,
    error_message: str | None = None,
    expected_status: str | list[str] | set[str] | tuple[str, ...] | None = None,
) -> bool:
    conditions = ["run_id = :run_id", "step_id = :step_id"]
    params: dict[str, Any] = {
        "run_id": run_id,
        "step_id": step_id,
        "status": status,
        "attempt_id": attempt_id,
        "run_generation": run_generation,
        "edge_job_id": edge_job_id,
        "result": json.dumps(result) if result is not None else None,
        "error_message": error_message,
        "now": _utcnow(),
    }

    if expected_status is not None:
        if isinstance(expected_status, str):
            conditions.append("status = :expected_status")
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
            UPDATE "{SCHEMA}".run_steps
            SET status = :status,
                version = version + 1,
                attempt_id = COALESCE(:attempt_id, attempt_id),
                run_generation = COALESCE(:run_generation, run_generation),
                edge_job_id = COALESCE(:edge_job_id, edge_job_id),
                result = COALESCE(CAST(:result AS jsonb), result),
                error_message = COALESCE(:error_message, error_message),
                updated_at = :now
            WHERE {where_clause}
            """
        ),
        params,
    )
    rowcount = getattr(res, "rowcount", None)
    if isinstance(rowcount, int):
        return rowcount > 0
    return True


async def record_event_rejection(
    db: AsyncSession,
    run_id: str,
    *,
    reason: str,
    event_id: str | None = None,
    source_event_id: str | None = None,
    details: dict[str, Any] | None = None,
) -> None:
    try:
        await db.execute(
            text(
                f"""
                INSERT INTO "{SCHEMA}".run_event_rejections (id, run_id, event_id, source_event_id, reason, details, created_at)
                VALUES (:id, :run_id, :event_id, :source_event_id, :reason, CAST(:details AS jsonb), :now)
                """
            ),
            {
                "id": str(uuid.uuid4()),
                "run_id": run_id,
                "event_id": event_id,
                "source_event_id": source_event_id,
                "reason": reason,
                "details": json.dumps(details or {}),
                "now": _utcnow(),
            },
        )
    except Exception:
        pass


async def aggregate_run_terminal(
    db: AsyncSession,
    run_id: str,
    *,
    org_id: str | None = None,
    attempt_id: str | None = None,
    generation: int | None = None,
) -> RunView | None:
    run = await get_run(db, run_id, org_id=org_id)
    if not run:
        return None
    if run.status in TERMINAL:
        return run

    try:
        steps_res = await db.execute(
            text(
                f"""
                SELECT id, run_id, step_id, owner_role, engine, status, depends_on, required, required_artifacts, attempt_id, run_generation, edge_job_id, version, result, error_message, created_at, updated_at
                FROM "{SCHEMA}".run_steps
                WHERE run_id = :run_id
                ORDER BY created_at ASC
                """
            ),
            {"run_id": run_id},
        )
        steps = steps_res.mappings().all() if hasattr(steps_res, "mappings") else []
    except Exception:
        steps = []

    if not steps:
        return run

    # 1. Cancellation check
    if run.status == "CANCELLING":
        all_stopped = all(s["status"] in ("SUCCEEDED", "FAILED", "CANCELLED") for s in steps)
        if all_stopped:
            ok = await set_status(db, run_id, "CANCELLED", org_id=org_id, expected_status=["CANCELLING"])
            if ok:
                await append_event(db, run_id, "run.cancelled", {"status": "CANCELLED"}, org_id=org_id)
            return await get_run(db, run_id, org_id=org_id)
        return run

    # 2. Required step failure check
    failed_required = [s for s in steps if s.get("required") and s.get("status") == "FAILED"]
    if failed_required:
        first_err = failed_required[0].get("error_message") or "required step failed"
        ok = await set_status(
            db,
            run_id,
            "FAILED",
            org_id=org_id,
            expected_status=["RUNNING", "WAITING_EDGE", "PREPARING", "RESUMING", "QUEUED"],
            result={"error": first_err, "failed_step_id": failed_required[0].get("step_id")},
        )
        if ok:
            await append_event(db, run_id, "run.failed", {"status": "FAILED", "error": first_err}, org_id=org_id)
        return await get_run(db, run_id, org_id=org_id)

    # 3. Required steps success check
    required_steps = [s for s in steps if s.get("required")]
    all_required_succeeded = bool(required_steps) and all(s.get("status") == "SUCCEEDED" for s in required_steps)

    if all_required_succeeded:
        # Check required artifacts for all steps
        all_required_artifacts = []
        for s in steps:
            req_art = s.get("required_artifacts") or []
            if isinstance(req_art, list):
                all_required_artifacts.extend(req_art)
            elif isinstance(req_art, str):
                all_required_artifacts.append(req_art)

        if all_required_artifacts:
            artifacts = await list_artifacts(db, run_id)
            persisted_names = {a.name for a in artifacts if a.checksum_sha256 and getattr(a, "storage_state", "persisted") in ("persisted", None)}
            missing = [name for name in all_required_artifacts if name not in persisted_names]
            if missing:
                # Required artifacts not ready/verified yet, cannot mark COMPLETED
                return run

        combined_result: dict[str, Any] = {}
        for s in steps:
            res = s.get("result")
            if isinstance(res, dict):
                combined_result.update(res)
            elif res is not None:
                combined_result[str(s.get("step_id"))] = res

        ok = await set_status(
            db,
            run_id,
            "COMPLETED",
            org_id=org_id,
            expected_status=["RUNNING", "WAITING_EDGE", "PREPARING", "RESUMING", "QUEUED"],
            result=combined_result,
        )
        if ok:
            await append_event(db, run_id, "run.completed", combined_result, org_id=org_id)
            content = combined_result.get("content") or combined_result.get("summary") or json.dumps(combined_result)
            raw = content if isinstance(content, (bytes, bytearray)) else str(content).encode("utf-8")
            try:
                await store_artifact_bytes(
                    db,
                    run_id,
                    name="result.txt",
                    content=bytes(raw),
                    content_type="text/plain; charset=utf-8",
                    org_id=org_id,
                    attempt_id=attempt_id,
                    generation=generation,
                )
            except Exception:
                pass
        return await get_run(db, run_id, org_id=org_id)

    return run


async def add_artifact(
    db: AsyncSession,
    run_id: str,
    *,
    name: str,
    content_type: str | None = None,
    size_bytes: int | None = None,
    storage_ref: str | None = None,
    checksum_sha256: str | None = None,
    org_id: str | None = None,
    attempt_id: str | None = None,
    generation: int | None = None,
) -> ArtifactDescriptor:
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
        org_id=org_id,
        attempt_id=attempt_id,
        generation=generation,
    )
    return ArtifactDescriptor(
        artifact_id=artifact_id,
        name=name,
        content_type=content_type,
        size_bytes=size_bytes,
        download_url=f"/api/v1/runs/{run_id}/artifacts/{artifact_id}/download",
        checksum_sha256=checksum_sha256,
        storage_state="persisted",
    )


async def store_artifact_bytes(
    db: AsyncSession,
    run_id: str,
    *,
    name: str,
    content: bytes,
    content_type: str | None = "text/plain",
    org_id: str | None = None,
    attempt_id: str | None = None,
    generation: int | None = None,
    step_id: str | None = None,
    upload_mode: str | None = "eager",
    idempotency_key: str | None = None,
) -> ArtifactDescriptor:
    from app.services.storage_port import get_storage_driver

    checksum = hashlib.sha256(content).hexdigest()

    # Idempotency check: if artifact with same idempotency_key or name and run_id exists
    existing_row = None
    try:
        if idempotency_key:
            check_res = await db.execute(
                text(
                    f"""
                    SELECT id, name, content_type, size_bytes, storage_ref, checksum_sha256, storage_state, idempotency_key
                    FROM "{SCHEMA}".run_artifacts
                    WHERE run_id = :run_id AND idempotency_key = :idempotency_key
                    LIMIT 1
                    """
                ),
                {"run_id": run_id, "idempotency_key": idempotency_key},
            )
        else:
            check_res = await db.execute(
                text(
                    f"""
                    SELECT id, name, content_type, size_bytes, storage_ref, checksum_sha256, storage_state, idempotency_key
                    FROM "{SCHEMA}".run_artifacts
                    WHERE run_id = :run_id AND name = :name
                    LIMIT 1
                    """
                ),
                {"run_id": run_id, "name": name},
            )
        if hasattr(check_res, "mappings"):
            mappings = check_res.mappings()
            if hasattr(mappings, "first"):
                existing_row = mappings.first()
            elif hasattr(mappings, "__await__"):
                awaited_m = await mappings
                if hasattr(awaited_m, "first"):
                    existing_row = awaited_m.first()
    except Exception:
        pass

    if existing_row and isinstance(existing_row, dict) and "checksum_sha256" in existing_row:
        if existing_row["checksum_sha256"] != checksum or (existing_row.get("name") and existing_row["name"] != name):
            raise RuntimeError(f"errors.artifact.idempotency_conflict: Artifact conflict: '{name}' already exists with different checksum")
        return ArtifactDescriptor(
            artifact_id=existing_row["id"],
            name=existing_row["name"],
            content_type=existing_row["content_type"],
            size_bytes=existing_row["size_bytes"],
            download_url=f"/api/v1/runs/{run_id}/artifacts/{existing_row['id']}/download",
            checksum_sha256=existing_row["checksum_sha256"],
            storage_state=str(existing_row.get("storage_state") or "persisted").lower(),
        )

    artifact_id = str(uuid.uuid4())
    storage_driver = get_storage_driver()
    driver_name = getattr(settings, "SKILL_AGENT_STORAGE_DRIVER", "local") or "local"
    storage_key = f"{run_id}/{artifact_id}_{name}"

    # Phase 1: Insert metadata with INIT state
    await db.execute(
        text(
            f"""
            INSERT INTO "{SCHEMA}".run_artifacts (
                id, run_id, attempt_id, step_id, name, content_type, size_bytes, storage_ref, checksum_sha256,
                storage_state, storage_driver, storage_key, upload_mode, idempotency_key
            ) VALUES (
                :id, :run_id, :attempt_id, :step_id, :name, :content_type, :size_bytes, :storage_ref, :checksum_sha256,
                'INIT', :storage_driver, :storage_key, :upload_mode, :idempotency_key
            )
            """
        ),
        {
            "id": artifact_id,
            "run_id": run_id,
            "attempt_id": attempt_id,
            "step_id": step_id,
            "name": name,
            "content_type": content_type or "text/plain",
            "size_bytes": len(content),
            "storage_ref": storage_key,
            "checksum_sha256": checksum,
            "storage_driver": driver_name,
            "storage_key": storage_key,
            "upload_mode": upload_mode or "eager",
            "idempotency_key": idempotency_key,
        },
    )

    # Phase 2: Write bytes and verify integrity
    try:
        write_res = await storage_driver.write(
            storage_key,
            content,
            expected_sha256=checksum,
            expected_size=len(content),
        )
        storage_ref = write_res.get("storage_ref") or storage_key

        # CAS update to PERSISTED
        cas = await db.execute(
            text(
                f"""
                UPDATE "{SCHEMA}".run_artifacts
                SET storage_state = 'PERSISTED',
                    storage_ref = :storage_ref,
                    persisted_at = :now
                WHERE id = :id AND storage_state = 'INIT'
                """
            ),
            {"id": artifact_id, "storage_ref": storage_ref, "now": _utcnow()},
        )
        cas_rowcount = getattr(cas, "rowcount", None)
        if isinstance(cas_rowcount, int):
            persisted = cas_rowcount > 0
        else:
            persisted = True
    except Exception as exc:
        await db.execute(
            text(
                f"""
                UPDATE "{SCHEMA}".run_artifacts
                SET storage_state = 'CORRUPTED',
                    state_reason = :reason
                WHERE id = :id
                """
            ),
            {"id": artifact_id, "reason": str(exc)[:500]},
        )
        raise

    await append_event(
        db,
        run_id,
        "run.artifact_ready",
        {"artifact_id": artifact_id, "name": name},
        org_id=org_id,
        attempt_id=attempt_id,
        generation=generation,
    )
    if persisted:
        await append_event(
            db,
            run_id,
            "artifact.persisted",
            {
                "artifact_id": artifact_id,
                "name": name,
                "content_type": content_type or "text/plain",
                "size": len(content),
                "checksum_sha256": checksum,
            },
            org_id=org_id,
            attempt_id=attempt_id,
            generation=generation,
            source_event_id=f"artifact:{artifact_id}:persisted",
        )
    return ArtifactDescriptor(
        artifact_id=artifact_id,
        name=name,
        content_type=content_type or "text/plain",
        size_bytes=len(content),
        download_url=f"/api/v1/runs/{run_id}/artifacts/{artifact_id}/download",
        checksum_sha256=checksum,
        storage_state="persisted",
    )


async def mark_artifact_corrupted(
    db: AsyncSession,
    artifact_id: str,
    *,
    reason: str | None = None,
) -> bool:
    res = await db.execute(
        text(
            f"""
            UPDATE "{SCHEMA}".run_artifacts
            SET storage_state = 'CORRUPTED',
                state_reason = :reason
            WHERE id = :id
            """
        ),
        {"id": artifact_id, "reason": reason or "corrupted"},
    )
    rowcount = getattr(res, "rowcount", 1)
    return rowcount > 0 if isinstance(rowcount, int) else True


async def mark_artifact_expired(
    db: AsyncSession,
    artifact_id: str,
    *,
    reason: str | None = None,
) -> bool:
    res = await db.execute(
        text(
            f"""
            UPDATE "{SCHEMA}".run_artifacts
            SET storage_state = 'EXPIRED',
                state_reason = :reason,
                expires_at = :now
            WHERE id = :id
            """
        ),
        {"id": artifact_id, "reason": reason or "expired", "now": _utcnow()},
    )
    rowcount = getattr(res, "rowcount", 1)
    return rowcount > 0 if isinstance(rowcount, int) else True


async def get_artifact_bytes(db: AsyncSession, run_id: str, artifact_id: str) -> tuple[dict, bytes] | None:
    import base64
    from pathlib import Path
    from app.services.storage_port import get_storage_driver

    row = (
        await db.execute(
            text(
                f"""
                SELECT id, name, content_type, size_bytes, storage_ref, checksum_sha256, storage_key, storage_driver, storage_state
                FROM "{SCHEMA}".run_artifacts
                WHERE run_id = :run_id AND id = :artifact_id
                """
            ),
            {"run_id": run_id, "artifact_id": artifact_id},
        )
    ).mappings().first()
    if not row or not row.get("storage_ref"):
        return None
    if row.get("storage_state") and row["storage_state"] not in ("PERSISTED", "persisted"):
        return None

    ref = str(row["storage_ref"])
    if ref.startswith("data:base64:"):
        return dict(row), base64.b64decode(ref.removeprefix("data:base64:"))

    storage_key = row.get("storage_key") or f"{run_id}/{artifact_id}_{row['name']}"
    storage_driver = get_storage_driver(row.get("storage_driver"))
    try:
        content = await storage_driver.read(storage_key)
        return dict(row), content
    except Exception:
        path = Path(ref)
        if path.is_file():
            return dict(row), path.read_bytes()
        return None
