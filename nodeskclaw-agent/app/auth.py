import hmac
from fastapi import Header, HTTPException

from app.config import settings


def require_internal_token(
    x_skill_agent_token: str | None = Header(default=None, alias="X-Skill-Agent-Token"),
) -> None:
    expected_curr = settings.SKILL_AGENT_INTERNAL_TOKEN
    expected_prev = settings.SKILL_AGENT_INTERNAL_TOKEN_PREVIOUS
    if not x_skill_agent_token:
        raise HTTPException(status_code=401, detail="invalid skill agent token")

    curr_match = expected_curr and hmac.compare_digest(x_skill_agent_token, expected_curr)
    prev_match = expected_prev and hmac.compare_digest(x_skill_agent_token, expected_prev)

    if not curr_match and not prev_match:
        raise HTTPException(status_code=401, detail="invalid skill agent token")
