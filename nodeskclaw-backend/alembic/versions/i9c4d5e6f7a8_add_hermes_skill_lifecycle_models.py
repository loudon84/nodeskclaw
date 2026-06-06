"""add_hermes_skill_lifecycle_models

Revision ID: i9c4d5e6f7a8
Revises: h8b3c9d0e1f2
Create Date: 2026-06-03 10:00:00.000000

NOTE: This migration was handwritten because the database was not available
for autogenerate. When a database connection is available, please verify by
running: alembic revision --autogenerate -m "verify_hermes_skill_lifecycle"
and compare the output.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "i9c4d5e6f7a8"
down_revision: str | Sequence[str] | None = "h8b3c9d0e1f2"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "hermes_skills",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("org_id", sa.String(36), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("skill_id", sa.String(255), nullable=False),
        sa.Column("tool_name", sa.String(255), nullable=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("title", sa.String(255), nullable=True),
        sa.Column("description", sa.String(1024), nullable=True),
        sa.Column("version", sa.String(32), nullable=False, server_default="1.0.0"),
        sa.Column("agent_type", sa.String(64), nullable=True),
        sa.Column("category", sa.String(64), nullable=True),
        sa.Column("runtime", sa.String(64), nullable=True),
        sa.Column("source_type", sa.String(32), nullable=False, server_default="central"),
        sa.Column("source_url", sa.String(1024), nullable=True),
        sa.Column("source_ref", sa.String(255), nullable=True),
        sa.Column("source_hash", sa.String(64), nullable=True),
        sa.Column("canonical_path", sa.String(1024), nullable=True),
        sa.Column("relative_path", sa.String(1024), nullable=True),
        sa.Column("is_central", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("is_read_only", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("is_mcp_exposed", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("manifest_path", sa.String(1024), nullable=True),
        sa.Column("gateway_manifest_path", sa.String(1024), nullable=True),
        sa.Column("input_schema", postgresql.JSONB(), nullable=True),
        sa.Column("output_schema", postgresql.JSONB(), nullable=True),
        sa.Column("tags", postgresql.JSONB(), nullable=True),
        sa.Column("extra_metadata", postgresql.JSONB(), nullable=True),
        sa.Column("created_by", sa.String(36), nullable=True),
        sa.Column("scanned_at", sa.String(32), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_hermes_skills_deleted_at", "hermes_skills", ["deleted_at"])
    op.create_index(
        "ix_hermes_skills_skill_id_org_unique", "hermes_skills", ["skill_id", "org_id"],
        unique=True, postgresql_where=sa.text("deleted_at IS NULL"),
    )
    op.create_index(
        "ix_hermes_skills_tool_name_org_unique", "hermes_skills", ["tool_name", "org_id"],
        unique=True, postgresql_where=sa.text("deleted_at IS NULL"),
    )
    op.create_index(
        "ix_hermes_skills_canonical_path_org_unique", "hermes_skills", ["canonical_path", "org_id"],
        unique=True, postgresql_where=sa.text("deleted_at IS NULL"),
    )
    op.create_index("ix_hermes_skills_org_source", "hermes_skills", ["org_id", "source_type"])
    op.create_index("ix_hermes_skills_org_agent_type", "hermes_skills", ["org_id", "agent_type"])

    op.create_table(
        "hermes_skill_installations",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("org_id", sa.String(36), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("skill_id", sa.String(255), nullable=False, index=True),
        sa.Column("agent_id", sa.String(255), nullable=False, index=True),
        sa.Column("profile_id", sa.String(255), nullable=True),
        sa.Column("workspace_id", sa.String(36), nullable=True),
        sa.Column("install_mode", sa.String(32), nullable=False, server_default="copy"),
        sa.Column("installed_path", sa.String(1024), nullable=True),
        sa.Column("installed_version", sa.String(32), nullable=True),
        sa.Column("source_path", sa.String(1024), nullable=True),
        sa.Column("link_type", sa.String(32), nullable=True),
        sa.Column("symlink_target", sa.String(1024), nullable=True),
        sa.Column("status", sa.String(32), nullable=False, server_default="pending"),
        sa.Column("error_message", sa.String(1024), nullable=True),
        sa.Column("installed_by", sa.String(36), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_hermes_skill_inst_deleted_at", "hermes_skill_installations", ["deleted_at"])
    op.create_index(
        "ix_hermes_skill_inst_skill_agent_unique", "hermes_skill_installations", ["skill_id", "agent_id"],
        unique=True, postgresql_where=sa.text("deleted_at IS NULL"),
    )
    op.create_index("ix_hermes_skill_inst_org", "hermes_skill_installations", ["org_id"])
    op.create_index("ix_hermes_skill_inst_status", "hermes_skill_installations", ["status"])

    op.create_table(
        "hermes_skill_collections",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("org_id", sa.String(36), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("collection_id", sa.String(255), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("description", sa.String(1024), nullable=True),
        sa.Column("agent_type", sa.String(64), nullable=True),
        sa.Column("version", sa.String(32), nullable=False, server_default="1.0.0"),
        sa.Column("source_type", sa.String(32), nullable=True),
        sa.Column("is_builtin", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("is_read_only", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("tags", postgresql.JSONB(), nullable=True),
        sa.Column("created_by", sa.String(36), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_hermes_skill_coll_deleted_at", "hermes_skill_collections", ["deleted_at"])
    op.create_index(
        "ix_hermes_skill_coll_name_org_unique", "hermes_skill_collections", ["name", "org_id"],
        unique=True, postgresql_where=sa.text("deleted_at IS NULL"),
    )

    op.create_table(
        "hermes_collection_skills",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("org_id", sa.String(36), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("collection_id", sa.String(36), sa.ForeignKey("hermes_skill_collections.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("skill_id", sa.String(255), nullable=False, index=True),
        sa.Column("version_constraint", sa.String(64), nullable=True),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("is_required", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_hermes_coll_skill_deleted_at", "hermes_collection_skills", ["deleted_at"])
    op.create_index(
        "ix_hermes_coll_skill_unique", "hermes_collection_skills", ["collection_id", "skill_id"],
        unique=True, postgresql_where=sa.text("deleted_at IS NULL"),
    )

    op.create_table(
        "hermes_skill_registries",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("org_id", sa.String(36), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("source_type", sa.String(32), nullable=False),
        sa.Column("url", sa.String(1024), nullable=True),
        sa.Column("branch", sa.String(255), nullable=True),
        sa.Column("auth_mode", sa.String(32), nullable=False, server_default="none"),
        sa.Column("auth_secret_ref", sa.String(255), nullable=True),
        sa.Column("is_builtin", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("is_enabled", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("last_synced_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_sync_status", sa.String(32), nullable=False, server_default="never"),
        sa.Column("last_sync_error", sa.String(1024), nullable=True),
        sa.Column("cache_path", sa.String(1024), nullable=True),
        sa.Column("cache_updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("etag", sa.String(255), nullable=True),
        sa.Column("last_modified", sa.String(255), nullable=True),
        sa.Column("created_by", sa.String(36), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_hermes_skill_reg_deleted_at", "hermes_skill_registries", ["deleted_at"])
    op.create_index(
        "ix_hermes_skill_reg_name_org_unique", "hermes_skill_registries", ["name", "org_id"],
        unique=True, postgresql_where=sa.text("deleted_at IS NULL"),
    )

    op.create_table(
        "hermes_skill_imports",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("org_id", sa.String(36), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("source_url", sa.String(1024), nullable=False),
        sa.Column("source_ref", sa.String(255), nullable=True),
        sa.Column("source_type", sa.String(32), nullable=False, server_default="github"),
        sa.Column("target_category", sa.String(64), nullable=True),
        sa.Column("conflict_strategy", sa.String(32), nullable=True),
        sa.Column("status", sa.String(32), nullable=False, server_default="preview"),
        sa.Column("total_skills", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("imported_skills", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("failed_skills", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("skipped_skills", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("error_message", sa.String(1024), nullable=True),
        sa.Column("details", postgresql.JSONB(), nullable=True),
        sa.Column("created_by", sa.String(36), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_hermes_skill_imports_deleted_at", "hermes_skill_imports", ["deleted_at"])
    op.create_index("ix_hermes_skill_imports_org", "hermes_skill_imports", ["org_id"])
    op.create_index("ix_hermes_skill_imports_status", "hermes_skill_imports", ["status"])


def downgrade() -> None:
    op.drop_table("hermes_skill_imports")
    op.drop_table("hermes_skill_registries")
    op.drop_table("hermes_collection_skills")
    op.drop_table("hermes_skill_collections")
    op.drop_table("hermes_skill_installations")
    op.drop_table("hermes_skills")
