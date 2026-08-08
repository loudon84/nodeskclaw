import pytest

from app.core.exceptions import ValidationError
from app.services.metadata_service import (
    validate_metadata,
    validate_schema_definition,
)


def test_invalid_enum_rejected():
    schema = validate_schema_definition(
        {
            "fields": [
                {
                    "key": "document_type",
                    "type": "enum",
                    "required": True,
                    "options": ["manual", "contract"],
                }
            ]
        }
    )
    with pytest.raises(ValidationError) as exc:
        validate_metadata({"document_type": "policy"}, schema)
    assert exc.value.status_code == 422
    assert exc.value.message_key == "errors.knowledge.metadata_invalid"


def test_nk_prefix_rejected():
    schema = validate_schema_definition(
        {
            "fields": [
                {
                    "key": "document_type",
                    "type": "enum",
                    "required": False,
                    "options": ["manual", "contract"],
                }
            ]
        }
    )
    with pytest.raises(ValidationError) as exc:
        validate_metadata({"nk_org_id": "x"}, schema)
    assert exc.value.status_code == 422
    assert exc.value.message_key == "errors.knowledge.metadata_invalid"
