from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ForbiddenError
from app.models.base import not_deleted
from app.models.hermes_skill.skill_run_approval_decision import SkillRunApprovalDecision

IDEMPOTENCY_TTL_SECONDS = 86400
ALLOWED_DECISIONS = frozenset({"allow", "deny"})
COMMENT_MAX_LENGTH = 500


class ApprovalDecisionContractError(Exception):
    def __init__(self, status_code: int, error_code: str, message_key: str, message: str):
        super().__init__(message)
        self.status_code = status_code
        self.error_code = error_code
        self.message_key = message_key
        self.message = message


def _rfc3339(value: datetime) -> str:
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _contract_error(status_code: int, error_code: str, message_key: str, message: str) -> ApprovalDecisionContractError:
    return ApprovalDecisionContractError(status_code, error_code, message_key, message)


def parse_public_decision(
    body: dict[str, Any] | None,
    *,
    strict_body: bool,
    allow_legacy_aliases: bool,
) -> tuple[str, str | None, dict[str, Any]]:
    payload = dict(body or {})
    if strict_body:
        extra = set(payload) - {"decision", "comment"}
        if extra:
            raise _contract_error(
                400,
                "APPROVAL_DECISION_INVALID",
                "errors.run.approval_decision_invalid",
                "Public approval decision only accepts decision and optional comment",
            )
    raw = str(payload.get("decision") or payload.get("choice") or "").strip().lower()
    if not raw and allow_legacy_aliases:
        raw = "allow"
    if raw in {"session", "always"}:
        raise _contract_error(
            400,
            "APPROVAL_DECISION_INVALID",
            "errors.run.approval_choice_forbidden",
            "Public approval only accepts allow or deny",
        )
    if raw in ALLOWED_DECISIONS:
        decision = raw
    elif allow_legacy_aliases and raw in {"approve", "approved", "once"}:
        decision = "allow"
    elif allow_legacy_aliases and raw in {"denied", "reject"}:
        decision = "deny"
    else:
        raise _contract_error(
            400,
            "APPROVAL_DECISION_INVALID",
            "errors.run.approval_choice_forbidden",
            "Public approval only accepts allow or deny",
        )
    comment = payload.get("comment")
    if comment is None:
        comment_text = None
    elif not isinstance(comment, str) or len(comment) > COMMENT_MAX_LENGTH:
        raise _contract_error(
            400,
            "APPROVAL_DECISION_INVALID",
            "errors.run.approval_decision_invalid",
            "comment must be a string of at most 500 characters",
        )
    else:
        comment_text = comment
    agent_body = dict(payload)
    agent_body.pop("choice", None)
    agent_body["decision"] = "deny" if decision == "deny" else "approve"
    if comment_text is None:
        agent_body.pop("comment", None)
    else:
        agent_body["comment"] = comment_text
    return decision, comment_text, agent_body


async def _load_decision(
    db: AsyncSession,
    *,
    org_id: str,
    user_id: str,
    run_id: str,
    approval_id: str,
) -> SkillRunApprovalDecision | None:
    result = await db.execute(
        select(SkillRunApprovalDecision).where(
            SkillRunApprovalDecision.org_id == org_id,
            SkillRunApprovalDecision.user_id == user_id,
            SkillRunApprovalDecision.run_id == run_id,
            SkillRunApprovalDecision.approval_id == approval_id,
            not_deleted(SkillRunApprovalDecision),
        )
    )
    return result.scalar_one_or_none()


def _replay_or_conflict(existing: SkillRunApprovalDecision, *, idempotency_key: str, decision: str) -> dict[str, Any]:
    if existing.idempotency_key == idempotency_key:
        if existing.decision == decision:
            return dict(existing.response_body)
        raise _contract_error(
            409,
            "IDEMPOTENCY_CONFLICT",
            "errors.run.idempotency_conflict",
            "Idempotency key was reused with a different decision",
        )
    raise _contract_error(
        409,
        "APPROVAL_ALREADY_DECIDED",
        "errors.run.approval_already_decided",
        "This approval has already been decided",
    )


# @lat: [[architecture/skill-agent#RM-17 Public Approval Decision]]
async def submit_approval_decision(
    db: AsyncSession,
    *,
    org_id: str,
    user_id: str,
    run_id: str,
    approval_id: str,
    body: dict[str, Any] | None,
    idempotency_key: str | None,
    require_idempotency_key: bool,
    strict_body: bool,
    allow_legacy_aliases: bool,
    agent_post,
    agent_get,
    public_run_status,
) -> dict[str, Any]:
    key = idempotency_key.strip() if isinstance(idempotency_key, str) else ""
    if require_idempotency_key and not key:
        raise _contract_error(
            400,
            "IDEMPOTENCY_KEY_REQUIRED",
            "errors.run.idempotency_key_required",
            "X-Idempotency-Key is required",
        )
    decision, _comment, agent_body = parse_public_decision(
        body,
        strict_body=strict_body,
        allow_legacy_aliases=allow_legacy_aliases,
    )
    existing = await _load_decision(
        db,
        org_id=org_id,
        user_id=user_id,
        run_id=run_id,
        approval_id=approval_id,
    )
    if existing:
        if not key:
            raise _contract_error(
                409,
                "APPROVAL_ALREADY_DECIDED",
                "errors.run.approval_already_decided",
                "This approval has already been decided",
            )
        return _replay_or_conflict(existing, idempotency_key=key, decision=decision)

    agent_data = await agent_post(
        f"/internal/v1/runs/{run_id}/approvals/{approval_id}",
        json_body=agent_body,
        org_id=org_id,
        user_id=user_id,
    )
    if str(agent_data.get("org_id") or "") != org_id or str(agent_data.get("run_id") or "") != run_id:
        raise ForbiddenError("无权访问该 Run", "errors.run.forbidden")
    run_view = await agent_get(f"/internal/v1/runs/{run_id}", org_id=org_id, user_id=user_id)
    decided_at = datetime.now(timezone.utc)
    receipt = {
        "run_id": run_id,
        "approval_id": approval_id,
        "decision": decision,
        "status": public_run_status(run_view.get("status") if isinstance(run_view, dict) else None),
        "decided_at": _rfc3339(decided_at),
    }
    if not key:
        return receipt

    row = SkillRunApprovalDecision(
        org_id=org_id,
        user_id=user_id,
        run_id=run_id,
        approval_id=approval_id,
        idempotency_key=key,
        decision=decision,
        response_body=receipt,
        decided_at=decided_at,
    )
    try:
        async with db.begin_nested():
            db.add(row)
            await db.flush()
    except IntegrityError:
        raced = await _load_decision(
            db,
            org_id=org_id,
            user_id=user_id,
            run_id=run_id,
            approval_id=approval_id,
        )
        if raced is None:
            raise
        return _replay_or_conflict(raced, idempotency_key=key, decision=decision)
    await db.commit()
    return receipt
