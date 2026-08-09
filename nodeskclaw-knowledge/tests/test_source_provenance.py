"""Source provenance schema unit tests."""

from app.models.enums import (
    ArchiveReason,
    KnowledgeActorType,
    SourceKind,
    SourceSyncState,
)
from app.models.source_file import SourceFile
from app.models.source_file_version import SourceFileVersion


def test_source_kind_enums_exist():
    assert SourceKind.manual.value == "manual"
    assert SourceKind.connector.value == "connector"
    assert SourceSyncState.in_sync.value == "in_sync"
    assert SourceSyncState.stale.value == "stale"
    assert SourceSyncState.error.value == "error"
    assert SourceSyncState.detached.value == "detached"
    assert KnowledgeActorType.member.value == "member"
    assert KnowledgeActorType.connector.value == "connector"
    assert KnowledgeActorType.system.value == "system"
    assert ArchiveReason.user.value == "user"
    assert ArchiveReason.source_deleted.value == "source_deleted"
    assert ArchiveReason.connector_deleted.value == "connector_deleted"
    assert ArchiveReason.detached.value == "detached"


def test_source_file_partial_unique_indexes():
    index_names = {idx.name for idx in SourceFile.__table_args__ if hasattr(idx, "name")}
    assert "uq_source_file_kb_name_manual" in index_names
    assert "uq_source_file_connector_object" in index_names

    by_name = {idx.name: idx for idx in SourceFile.__table_args__ if hasattr(idx, "name")}
    manual = by_name["uq_source_file_kb_name_manual"]
    connector = by_name["uq_source_file_connector_object"]

    assert manual.unique is True
    assert list(manual.columns.keys()) == ["knowledge_base_id", "file_name"]
    assert "connector_id IS NULL" in str(manual.dialect_options["postgresql"]["where"])
    assert "deleted_at IS NULL" in str(manual.dialect_options["postgresql"]["where"])

    assert connector.unique is True
    assert list(connector.columns.keys()) == ["connector_id", "external_object_id"]
    assert "connector_id IS NOT NULL" in str(connector.dialect_options["postgresql"]["where"])
    assert "deleted_at IS NULL" in str(connector.dialect_options["postgresql"]["where"])


def test_uploaded_by_member_id_nullable():
    col = SourceFileVersion.__table__.c.uploaded_by_member_id
    assert col.nullable is True
