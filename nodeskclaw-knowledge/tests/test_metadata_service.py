"""Metadata schema validation and biz_* mapping tests."""

import pytest

from app.core.exceptions import ValidationError
from app.services.metadata_service import (
    build_meta_fields,
    metadata_matches_filters,
    normalize_metadata_schema,
    validate_metadata_values,
    validate_retrieval_filters,
)


def test_build_meta_fields_includes_revision_and_biz():
    meta = build_meta_fields(
        source_file_id="sf1",
        file_version_id="sfv1",
        knowledge_base_id="kb1",
        org_id="o1",
        metadata={"document_type": "contract", "tags": ["a", "b"]},
        metadata_revision=3,
    )
    assert meta["nk_source_file_id"] == "sf1"
    assert meta["nk_metadata_revision"] == "3"
    assert meta["biz_document_type"] == "contract"
    assert meta["biz_tags"] == '["a","b"]'
    assert "allowed_users" not in meta
    assert "nk_document_type" not in meta


def test_validate_rejects_nk_prefix_and_acl_keys():
    schema = {
        "fields": [
            {"key": "document_type", "type": "enum", "required": True, "options": ["manual", "contract"]},
        ]
    }
    with pytest.raises(ValidationError) as exc:
        validate_metadata_values({"nk_org_id": "x"}, schema)
    assert exc.value.message_key == "errors.knowledge.metadata_invalid"
    with pytest.raises(ValidationError):
        validate_metadata_values({"allowed_users": ["m1"]}, schema)


def test_validate_required_and_enum():
    schema = {
        "fields": [
            {"key": "document_type", "type": "enum", "required": True, "options": ["manual", "contract"]},
            {"key": "region", "type": "string"},
        ]
    }
    with pytest.raises(ValidationError):
        validate_metadata_values({}, schema)
    with pytest.raises(ValidationError):
        validate_metadata_values({"document_type": "policy"}, schema)
    ok = validate_metadata_values({"document_type": "contract", "region": "SG"}, schema)
    assert ok["document_type"] == "contract"


def test_normalize_schema_rejects_bad_type():
    with pytest.raises(ValidationError):
        normalize_metadata_schema({"fields": [{"key": "x", "type": "object"}]})


def test_retrieval_filters_and_match():
    schema = {
        "fields": [
            {"key": "document_type", "type": "enum", "required": False, "options": ["manual", "contract"]},
            {"key": "region", "type": "string"},
        ]
    }
    filters = validate_retrieval_filters({"document_type": ["contract"]}, [schema])
    assert metadata_matches_filters({"document_type": "contract", "region": "SG"}, filters)
    assert not metadata_matches_filters({"document_type": "manual"}, filters)
    with pytest.raises(ValidationError):
        validate_retrieval_filters({"nk_source_file_id": ["x"]}, [schema])
