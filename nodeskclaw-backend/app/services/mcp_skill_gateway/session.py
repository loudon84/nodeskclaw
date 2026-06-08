_sessions: set[str] = set()


def session_key(user_id: str, org_id: str) -> str:
    return f"{user_id}:{org_id}"


def mark_initialized(user_id: str, org_id: str) -> None:
    _sessions.add(session_key(user_id, org_id))


def is_initialized(user_id: str, org_id: str) -> bool:
    return session_key(user_id, org_id) in _sessions


def clear_session(user_id: str, org_id: str) -> None:
    _sessions.discard(session_key(user_id, org_id))
