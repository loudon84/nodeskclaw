from __future__ import annotations

import hashlib
import json
import logging
import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.base import not_deleted
from app.models.integration.external_action_execution import ExternalActionExecution

logger = logging.getLogger("external_action.execution")


def arguments_digest(arguments: dict[str, Any] | None) -> str:
    body = arguments if isinstance(arguments, dict) else {}
    return hashlib.sha256(json.dumps(body, sort_keys=True, ensure_ascii=False).encode("utf-8")).hexdigest()


def provider_idempotency_key(
    *,
    run_id: str,
    attempt_id: str,
    generation: int,
    tool_call_id: str,
    arguments_digest: str,
) -> str:
    raw = json.dumps(
        [run_id, attempt_id, int(generation), tool_call_id, arguments_digest],
        ensure_ascii=False,
        separators=(",", ":"),
    )
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def ledger_gate(existing_state: str | None, stored_digest: str | None, arguments_digest: str) -> str:
    if existing_state is None:
        return "start"
    if stored_digest != arguments_digest:
        return "conflict"
    if existing_state == "EXECUTING":
        return "unknown"
    return "replay"


def _hash_text(value: str | None) -> str | None:
    if not value:
        return None
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _trace(row: ExternalActionExecution) -> None:
    logger.info(
        "external_action.execution",
        extra={
            "user_id": row.user_id,
            "org_id": row.org_id,
            "run_id": row.run_id,
            "attempt_id": row.attempt_id,
            "generation": int(row.generation or 0),
            "tool_call_id": row.tool_call_id,
            "tool_name": row.tool_name,
            "approval_id": row.approval_id,
            "outcome": row.outcome,
            "arguments_digest": row.arguments_digest,
            "provider_session_ref_hash": row.provider_session_ref_hash,
            "provider_idempotency_key_hash": _hash_text(row.provider_idempotency_key),
        },
    )


def _replay(row: ExternalActionExecution) -> dict[str, Any]:
    if row.state == "SUCCEEDED":
        return {"outcome": "ok", "result": row.result or {"isError": False, "content": []}, "replay": True}
    if row.state == "OUTCOME_UNKNOWN":
        return {"outcome": "outcome_unknown", "replay": True}
    return {"outcome": row.outcome or "tool_error", "replay": True}


class ExternalActionLedger:
    digest = staticmethod(arguments_digest)

    def __init__(self, db: AsyncSession):
        self.db = db

    async def reserve(self, **fields: Any) -> dict[str, Any] | None:
        row = await self._find(fields["run_id"], int(fields["generation"]), fields["tool_call_id"])
        decision = ledger_gate(row.state if row else None, row.arguments_digest if row else None, fields["arguments_digest"])
        if decision == "conflict":
            return {"outcome": "conflict"}
        if decision == "unknown" and row is not None:
            row.state = "OUTCOME_UNKNOWN"
            row.outcome = "outcome_unknown"
            row.completed_at = datetime.now(timezone.utc)
            await self.db.commit()
            _trace(row)
            return {"outcome": "outcome_unknown", "replay": True}
        if decision == "replay" and row is not None:
            return _replay(row)
        created = ExternalActionExecution(
            id=str(uuid.uuid4()),
            state="EXECUTING",
            started_at=datetime.now(timezone.utc),
            provider_idempotency_key=provider_idempotency_key(
                run_id=fields["run_id"],
                attempt_id=fields["attempt_id"],
                generation=int(fields["generation"]),
                tool_call_id=fields["tool_call_id"],
                arguments_digest=fields["arguments_digest"],
            ),
            **{key: value for key, value in fields.items() if key != "session_ref"},
        )
        self.db.add(created)
        try:
            await self.db.commit()
        except IntegrityError:
            await self.db.rollback()
            raced = await self._find(fields["run_id"], int(fields["generation"]), fields["tool_call_id"])
            if raced is None:
                raise
            return await self.reserve(**fields)
        return None

    async def finish(
        self,
        *,
        run_id: str,
        generation: int,
        tool_call_id: str,
        outcome: str,
        result: dict[str, Any] | None,
        error_code: str | None,
        session_ref: str | None,
        request_id: str | None,
    ) -> None:
        row = await self._find(run_id, generation, tool_call_id)
        if row is None or row.state != "EXECUTING":
            return
        if outcome == "ok":
            row.state = "SUCCEEDED"
        elif outcome == "outcome_unknown":
            row.state = "OUTCOME_UNKNOWN"
        else:
            row.state = "FAILED"
        row.outcome = outcome
        row.result = result
        row.error_code = error_code
        row.provider_request_id = request_id
        row.provider_session_ref_hash = _hash_text(session_ref)
        row.completed_at = datetime.now(timezone.utc)
        await self.db.commit()
        _trace(row)

    async def _find(self, run_id: str, generation: int, tool_call_id: str) -> ExternalActionExecution | None:
        result = await self.db.execute(
            select(ExternalActionExecution).where(
                not_deleted(ExternalActionExecution),
                ExternalActionExecution.run_id == run_id,
                ExternalActionExecution.generation == generation,
                ExternalActionExecution.tool_call_id == tool_call_id,
            )
        )
        return result.scalars().first()
