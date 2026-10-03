from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.base import not_deleted
from app.models.hermes_skill.hermes_task import HermesTask, TaskStatus
from app.services.remote_agent_provider_service import (
    REMOTE_AGENT_TOOL_NAME,
    RemoteAgentRouteError,
)

NON_TERMINAL = {
    TaskStatus.QUEUED,
    TaskStatus.ACCEPTED,
    TaskStatus.RUNNING,
    TaskStatus.WAITING_APPROVAL,
}

ACP_TURN = re.compile(r"^acp:([^:]+):([1-9][0-9]*)$")


@dataclass
class SessionProof:
    session_ref: str
    agent_ref: str
    status: str
    last_run_id: str | None
    next_turn_seq: int
    frozen: dict[str, Any]
    non_terminal_run_ids: list[str]
    has_acp_turn: bool


def _task_time(task: HermesTask) -> datetime:
    return task.updated_at or task.created_at


def parse_acp_turn(session_ref: str, key: str | None) -> int | None:
    if not key:
        return None
    match = ACP_TURN.fullmatch(key)
    if match is None:
        if key.startswith(f"acp:{session_ref}:"):
            return -1
        return None
    if match.group(1) != session_ref:
        return None
    return int(match.group(2))


def derive_session_proof(session_ref: str, tasks: list[HermesTask]) -> SessionProof:
    if not tasks:
        raise RemoteAgentRouteError(
            "REMOTE_AGENT_SESSION_NOT_FOUND",
            404,
            40406,
            "errors.remote_agent.session_not_found",
            "会话不存在",
        )
    seqs: list[int] = []
    for task in tasks:
        parsed = parse_acp_turn(session_ref, task.idempotency_key)
        if parsed == -1:
            raise RemoteAgentRouteError(
                "REMOTE_AGENT_SESSION_SEQ_AMBIGUOUS",
                409,
                40906,
                "errors.remote_agent.session_seq_ambiguous",
                "无法推导 next_turn_seq",
            )
        if parsed is not None:
            seqs.append(parsed)
    next_turn_seq = (max(seqs) + 1) if seqs else 1
    ordered = sorted(tasks, key=_task_time, reverse=True)
    last = ordered[0]
    non_terminal = [task for task in tasks if task.status in NON_TERMINAL]
    if len(non_terminal) > 1:
        error = RemoteAgentRouteError(
            "REMOTE_AGENT_SESSION_AMBIGUOUS",
            409,
            40907,
            "errors.remote_agent.session_ambiguous",
            "会话存在多个非终态运行",
        )
        error.data = {"non_terminal_run_ids": [task.id for task in non_terminal]}
        raise error
    status = "busy" if len(non_terminal) == 1 else "idle"
    last_run_id = last.id
    if status == "busy":
        last_run_id = non_terminal[0].id
    agent_ref = str(last.catalog_slug or (last.routing_metadata or {}).get("agent_ref") or "")
    acp_tasks = [task for task in tasks if parse_acp_turn(session_ref, task.idempotency_key) not in (None, -1)]
    source = sorted(acp_tasks, key=_task_time)[0] if acp_tasks else last
    snapshot = source.request_snapshot if isinstance(source.request_snapshot, dict) else {}
    frozen = {
        "agent_ref": agent_ref,
        "knowledge_refs": list(snapshot.get("knowledge_refs") or []),
        "connector_binding_refs": list(snapshot.get("connector_binding_refs") or []),
        "integration_account_refs": list(snapshot.get("integration_account_refs") or []),
    }
    return SessionProof(
        session_ref=session_ref,
        agent_ref=agent_ref,
        status=status,
        last_run_id=last_run_id,
        next_turn_seq=next_turn_seq,
        frozen=frozen,
        non_terminal_run_ids=[task.id for task in non_terminal],
        has_acp_turn=bool(acp_tasks),
    )


def public_proof_body(proof: SessionProof) -> dict[str, Any]:
    return {
        "session_ref": proof.session_ref,
        "agent_ref": proof.agent_ref,
        "status": proof.status,
        "last_run_id": proof.last_run_id,
        "next_turn_seq": proof.next_turn_seq,
    }


def selectors_match(frozen: dict[str, Any], expected: dict[str, Any]) -> bool:
    keys = ("agent_ref", "knowledge_refs", "connector_binding_refs", "integration_account_refs")
    for key in keys:
        left = frozen.get(key)
        right = expected.get(key)
        if key == "agent_ref":
            if str(left or "") != str(right or ""):
                return False
            continue
        if [str(item) for item in (left or [])] != [str(item) for item in (right or [])]:
            return False
    return True


class RemoteAgentSessionProofService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def _load_owned(self, org_id: str, user_id: str, session_ref: str) -> list[HermesTask]:
        stmt = select(HermesTask).where(
            HermesTask.org_id == org_id,
            HermesTask.user_id == user_id,
            HermesTask.tool_name == REMOTE_AGENT_TOOL_NAME,
            not_deleted(HermesTask),
            HermesTask.routing_metadata["session_ref"].as_string() == session_ref,
        )
        return list((await self.db.execute(stmt)).scalars().all())

    async def get_proof(
        self,
        org_id: str,
        user_id: str,
        session_ref: str,
        expected: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        tasks = await self._load_owned(org_id, user_id, session_ref)
        proof = derive_session_proof(session_ref, tasks)
        if expected is not None:
            if proof.has_acp_turn:
                frozen = proof.frozen
                compare = expected
            else:
                frozen = {
                    "agent_ref": proof.agent_ref,
                    "knowledge_refs": [],
                    "connector_binding_refs": [],
                    "integration_account_refs": [],
                }
                compare = {
                    "agent_ref": expected.get("agent_ref"),
                    "knowledge_refs": [],
                    "connector_binding_refs": [],
                    "integration_account_refs": [],
                }
            if not selectors_match(frozen, compare):
                raise RemoteAgentRouteError(
                    "REMOTE_AGENT_SESSION_AGENT_MISMATCH",
                    409,
                    40908,
                    "errors.remote_agent.session_agent_mismatch",
                    "会话上下文与当前 Expert Profile 不一致",
                )
        return public_proof_body(proof)

    async def non_terminal_run_ids(self, org_id: str, user_id: str, session_ref: str) -> list[str]:
        tasks = await self._load_owned(org_id, user_id, session_ref)
        return [task.id for task in tasks if task.status in NON_TERMINAL]
