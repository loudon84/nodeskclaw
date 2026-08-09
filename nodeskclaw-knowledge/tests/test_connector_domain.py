"""Connector domain schema/model unit tests."""

from app.models.connector import (
    ConnectorCredential,
    ConnectorSourceObject,
    ConnectorSyncItem,
    ConnectorSyncRun,
    KnowledgeSourceConnector,
)
from app.schemas import connector as connector_schemas


_SECRET_FIELD_TOKENS = ("password", "secret", "token", "access_key")


def test_connector_models_importable():
    assert KnowledgeSourceConnector.__tablename__ == "knowledge_source_connectors"
    assert ConnectorCredential.__tablename__ == "knowledge_connector_credentials"
    assert ConnectorSourceObject.__tablename__ == "knowledge_connector_source_objects"
    assert ConnectorSyncRun.__tablename__ == "knowledge_connector_sync_runs"
    assert ConnectorSyncItem.__tablename__ == "knowledge_connector_sync_items"


def test_connector_out_schemas_have_no_secret_fields():
    schema_classes = [
        connector_schemas.ConnectorCreate,
        connector_schemas.ConnectorUpdate,
        connector_schemas.ConnectorOut,
        connector_schemas.ConnectorSourceObjectOut,
        connector_schemas.ConnectorSyncRunOut,
        connector_schemas.ConnectorSyncItemOut,
    ]
    for cls in schema_classes:
        field_names = {name.lower() for name in cls.model_fields}
        for token in _SECRET_FIELD_TOKENS:
            assert not any(token in name for name in field_names), f"{cls.__name__} has secret-like field"


def test_connector_out_exposes_credential_flags_only():
    fields = connector_schemas.ConnectorOut.model_fields
    assert "credential_configured" in fields
    assert "credential_updated_at" in fields
    assert "ciphertext" not in fields
    assert "nonce" not in fields
    assert "credential_id" not in fields
