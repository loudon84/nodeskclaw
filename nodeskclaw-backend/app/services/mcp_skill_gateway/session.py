from dataclasses import dataclass


@dataclass
class SessionState:
    initialized: bool = False
    client_name: str | None = None
    client_version: str | None = None


_session_state: dict[str, SessionState] = {}


def session_key(user_id: str, org_id: str) -> str:
    return f"{user_id}:{org_id}"


def mark_initialized(
    user_id: str,
    org_id: str,
    *,
    client_name: str | None = None,
    client_version: str | None = None,
) -> None:
    key = session_key(user_id, org_id)
    _session_state[key] = SessionState(
        initialized=True,
        client_name=client_name,
        client_version=client_version,
    )


def get_client_name(user_id: str, org_id: str) -> str | None:
    state = _session_state.get(session_key(user_id, org_id))
    return state.client_name if state else None


def is_initialized(user_id: str, org_id: str) -> bool:
    state = _session_state.get(session_key(user_id, org_id))
    return bool(state and state.initialized)


def clear_session(user_id: str, org_id: str) -> None:
    _session_state.pop(session_key(user_id, org_id), None)
