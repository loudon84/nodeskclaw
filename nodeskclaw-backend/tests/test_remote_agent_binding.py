from app.services.remote_agent_binding_service import classify_binding_row, descriptor_field_names


_PUBLIC = {"crm.lookup"}
_BASE = dict(
    caller_org_id="org-1",
    binding_org_id="org-1",
    binding_deleted=False,
    instance_present=True,
    instance_deleted=False,
    instance_active=True,
    placement="central",
    kind="rest",
    release_status="published",
    skill_tool_name="crm.lookup",
    expert_public_tool_names=_PUBLIC,
    binding_id="11111111-1111-4111-8111-111111111111",
    connector_instance_id="instance-1",
    skill_release_id="release-1",
)


def test_classify_missing_deleted_and_cross_org_are_not_found():
    missing = classify_binding_row(**{**_BASE, "binding_org_id": None})
    deleted = classify_binding_row(**{**_BASE, "binding_deleted": True})
    other_org = classify_binding_row(**{**_BASE, "binding_org_id": "org-2"})
    for error in (missing, deleted, other_org):
        assert error.symbol == "CONNECTOR_BINDING_NOT_FOUND"
        assert error.code == 40403


def test_classify_disabled_placement_and_scope():
    disabled = classify_binding_row(**{**_BASE, "instance_active": False})
    assert disabled.symbol == "CONNECTOR_BINDING_DISABLED"
    assert disabled.code == 40906
    edge = classify_binding_row(**{**_BASE, "placement": "edge"})
    assert edge.symbol == "CONNECTOR_BINDING_PLACEMENT_UNSUPPORTED"
    assert edge.code == 40907
    draft = classify_binding_row(**{**_BASE, "release_status": "draft"})
    unknown_kind = classify_binding_row(**{**_BASE, "kind": "composio_mcp"})
    foreign_skill = classify_binding_row(**{**_BASE, "skill_tool_name": "other.tool"})
    for error in (draft, unknown_kind, foreign_skill):
        assert error.symbol == "CONNECTOR_SCOPE_DENIED"
        assert error.code == 40302


def test_classify_descriptor_whitelist():
    row = classify_binding_row(**_BASE)
    assert set(row) == set(descriptor_field_names())
    assert "secret_ref_id" not in row
    assert "url" not in row
    assert row["connector_kind"] == "rest"
    assert row["placement"] == "central"
