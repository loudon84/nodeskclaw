import pytest

from app.services.mcp_skill_gateway.audit_service import sanitize_input_summary


def test_sanitize_input_summary_redacts_sensitive_fields():
    summary = sanitize_input_summary({
        "instance_ref": "demo-profile",
        "token": "secret-token",
        "password": "secret-password",
        "webui_password": "abc",
    })

    assert summary == {
        "instance_ref": {"type": "string", "length": 12},
    }


def test_sanitize_input_summary_records_string_length():
    summary = sanitize_input_summary({"note": "hello"})

    assert summary == {"note": {"type": "string", "length": 5}}
