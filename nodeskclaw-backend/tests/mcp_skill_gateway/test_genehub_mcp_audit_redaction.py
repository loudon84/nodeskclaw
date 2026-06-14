from app.services.mcp_skill_gateway.audit_service import sanitize_input_summary


def test_genehub_mcp_audit_redacts_sensitive_fields():
    summary = sanitize_input_summary({
        "gene_slug": "contact-to-order",
        "profile_id": "profile-1",
        "accessToken": "secret",
        "authorization": "Bearer secret",
    })

    assert summary == {
        "gene_slug": {"type": "string", "length": 16},
        "profile_id": {"type": "string", "length": 9},
    }
