from __future__ import annotations

from fastapi import HTTPException

from app.api.internal_automation import _verify_autotask_token
from app.core.config import settings


def test_autotask_internal_token_accepts_current_and_previous(monkeypatch):
    monkeypatch.setattr(settings, "AUTOTASK_INTERNAL_TOKEN", "curr-token")
    monkeypatch.setattr(settings, "AUTOTASK_INTERNAL_TOKEN_PREVIOUS", "prev-token")
    _verify_autotask_token(x_autotask_internal_token="curr-token")
    _verify_autotask_token(x_autotask_internal_token="prev-token")
    try:
        _verify_autotask_token(x_autotask_internal_token="bad")
        raise AssertionError("expected unauthorized")
    except HTTPException as exc:
        assert exc.status_code == 401


def test_autotask_internal_token_rejects_missing(monkeypatch):
    monkeypatch.setattr(settings, "AUTOTASK_INTERNAL_TOKEN", "curr-token")
    monkeypatch.setattr(settings, "AUTOTASK_INTERNAL_TOKEN_PREVIOUS", "")
    try:
        _verify_autotask_token(x_autotask_internal_token=None)
        raise AssertionError("expected unauthorized")
    except HTTPException as exc:
        assert exc.status_code == 401
