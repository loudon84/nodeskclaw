from __future__ import annotations

import time

from app.services.automation_permission import can_manage_automation, has_automation_permission
from app.services.prompt_renderer import map_rpa_output_to_input, render_prompt_template
from app.services.webhook_hmac import (
    body_sha256,
    hash_webhook_secret,
    open_webhook_secret,
    seal_webhook_secret,
    sign_payload,
    verify_webhook_signature,
)


def test_automation_role_permissions():
    assert has_automation_permission("admin", "automation:manage")
    assert has_automation_permission("member", "automation:run")
    assert not has_automation_permission("viewer", "automation:run")
    assert has_automation_permission("viewer", "automation:view")
    assert can_manage_automation(
        org_role="member",
        user_id="u1",
        owner_user_id="u1",
    )
    assert not can_manage_automation(
        org_role="member",
        user_id="u1",
        owner_user_id="u2",
    )


def test_prompt_render_and_mapper():
    assert render_prompt_template("hello {{ name }}", {"name": "world"}) == "hello world"
    mapped = map_rpa_output_to_input(
        {"a": 1, "b": 2, "c": 3},
        {"properties": {"a": {}, "c": {}}},
    )
    assert mapped == {"a": 1, "c": 3}


def test_webhook_hmac_and_sealed_secret():
    secret = "super-secret"
    sealed = seal_webhook_secret(secret)
    assert open_webhook_secret(sealed) == secret
    assert hash_webhook_secret(secret) != secret
    raw = b'{"source_event_id":"evt-1"}'
    ts = str(int(time.time()))
    nonce = "n1"
    digest = body_sha256(raw)
    signature = sign_payload(secret=secret, timestamp=ts, nonce=nonce, body_digest=digest)
    assert verify_webhook_signature(
        secret=secret,
        timestamp=ts,
        nonce=nonce,
        signature=signature,
        raw_body=raw,
    ) is None
    assert verify_webhook_signature(
        secret=secret,
        timestamp=str(int(time.time()) - 1000),
        nonce=nonce,
        signature=signature,
        raw_body=raw,
    ) == "WEBHOOK_AUTH_FAILED"
