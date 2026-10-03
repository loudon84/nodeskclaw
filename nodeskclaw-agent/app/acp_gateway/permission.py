from __future__ import annotations

from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.acp_gateway.errors import AcpGatewayError
from app.services import run_service


def _choice_from_outcome(outcome: Any) -> str:
    if isinstance(outcome, dict):
        option = str(outcome.get("optionId") or outcome.get("outcome") or "")
    else:
        option = str(outcome or "")
    if option in {"reject_once", "deny", "rejected"}:
        return "deny"
    return "approve"


async def apply_permission(
    db: AsyncSession,
    *,
    run_id: str,
    org_id: str,
    approval_id: str,
    outcome: Any,
    expected_attempt_id: str | None = None,
    expected_generation: int | None = None,
) -> None:
    run = await run_service.get_run(db, run_id, org_id=org_id)
    if not run:
        raise AcpGatewayError("ACP_PERMISSION_FAILED", "run not found")
    if expected_attempt_id and run.attempt_id and expected_attempt_id != run.attempt_id:
        raise AcpGatewayError("ACP_STALE_ATTEMPT", "stale attempt")
    if expected_generation is not None and int(run.generation or 0) != int(expected_generation):
        raise AcpGatewayError("ACP_STALE_ATTEMPT", "stale generation")
    choice = _choice_from_outcome(outcome)
    try:
        await run_service.approve_run(
            db,
            run_id,
            org_id=org_id,
            approval_id=approval_id,
            decision=choice,
        )
    except ValueError as exc:
        text = str(exc)
        if "stale" in text:
            raise AcpGatewayError("ACP_STALE_ATTEMPT", text) from exc
        raise AcpGatewayError("ACP_PERMISSION_FAILED", text) from exc
