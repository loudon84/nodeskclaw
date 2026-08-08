"""Ragflow mapper and blue/green activation tests."""

from datetime import UTC, datetime
from types import SimpleNamespace

from app.integrations.ragflow.mapper import map_ragflow_payload, map_transport_error
from app.services.source_file_service import activate_version


def test_map_ragflow_forbidden():
    err = map_ragflow_payload(102, "You do not own the dataset xxx")
    assert err.message_key == "errors.knowledge.ragflow_forbidden"
    assert err.status_code == 403


def test_map_ragflow_bad_request():
    err = map_ragflow_payload(102, "`datasets` is required.")
    assert err.message_key == "errors.knowledge.ragflow_bad_request"


def test_map_transport_error():
    err = map_transport_error(TimeoutError())
    assert err.message_key == "errors.knowledge.ragflow_unavailable"


def test_activate_version_blue_green():
    sf = SimpleNamespace(active_version_id="v1", status="updating")
    old = SimpleNamespace(id="v1", parse_status="active", superseded_at=None)
    new = SimpleNamespace(id="v2", parse_status="parsing", activated_at=None)
    activate_version(sf, new, old)
    assert sf.active_version_id == "v2"
    assert sf.status == "active"
    assert new.parse_status == "active"
    assert new.activated_at is not None
    assert old.parse_status == "superseded"
    assert old.superseded_at is not None
    assert isinstance(new.activated_at, datetime)
    assert new.activated_at.tzinfo == UTC
