from __future__ import annotations

import uuid
from dataclasses import dataclass, field

from app.constants import DEFAULT_MAX_SESSIONS
from app.errors import AdapterError, session_busy, session_not_found


@dataclass
class SessionState:
    session_id: str
    cwd: str
    agent_ref: str
    turn_seq: int = 0
    active_run_id: str | None = None
    active_prompt_id: str | None = None
    last_sse_event_id: str | None = None
    cancel_requested: bool = False
    accumulated_text: str = ""
    delta_emitted: bool = False
    seen_event_ids: set[str] = field(default_factory=set)


class SessionRegistry:
    def __init__(self, agent_ref: str, max_sessions: int = DEFAULT_MAX_SESSIONS):
        self.agent_ref = agent_ref
        self.max_sessions = max_sessions
        self._sessions: dict[str, SessionState] = {}

    def create(self, cwd: str) -> SessionState:
        if len(self._sessions) >= self.max_sessions:
            raise AdapterError("ACP_SESSION_NOT_FOUND", f"超过 max_sessions={self.max_sessions}")
        state = SessionState(session_id=str(uuid.uuid4()), cwd=cwd, agent_ref=self.agent_ref)
        self._sessions[state.session_id] = state
        return state

    def get(self, session_id: str) -> SessionState:
        state = self._sessions.get(session_id)
        if state is None:
            raise session_not_found()
        return state

    def begin_turn(self, session_id: str) -> SessionState:
        state = self.get(session_id)
        if state.active_run_id or state.active_prompt_id:
            raise session_busy()
        state.turn_seq += 1
        state.cancel_requested = False
        state.accumulated_text = ""
        state.delta_emitted = False
        return state

    def end_turn(self, session_id: str) -> None:
        state = self.get(session_id)
        state.active_run_id = None
        state.active_prompt_id = None
        state.cancel_requested = False
