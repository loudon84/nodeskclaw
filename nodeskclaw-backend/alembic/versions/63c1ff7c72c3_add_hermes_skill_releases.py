"""add_hermes_skill_releases

Revision ID: 63c1ff7c72c3
Revises: f3db2f401517
Create Date: 2026-08-26 14:37:35.827177

"""
from __future__ import annotations

import hashlib
import json
import uuid
from typing import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "63c1ff7c72c3"
down_revision: str | Sequence[str] | None = "f3db2f401517"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _digest_from_row(row: sa.RowMapping) -> str:
    payload = {
        "skill_id": row["skill_id"],
        "tool_name": row["tool_name"],
        "name": row["name"],
        "title": row["title"],
        "description": row["description"],
        "version": row["version"],
        "category": row["category"],
        "input_schema": row["input_schema"],
        "output_schema": row["output_schema"],
        "output_policy": row["output_policy"],
        "extra_metadata": row["extra_metadata"],
        "tags": row["tags"],
    }
    raw = json.dumps(payload, sort_keys=True, ensure_ascii=False, default=str)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def upgrade() -> None:
    op.create_table(
        "hermes_skill_releases",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("org_id", sa.String(length=36), nullable=False),
        sa.Column("skill_db_id", sa.String(length=36), nullable=False),
        sa.Column("skill_id", sa.String(length=255), nullable=False),
        sa.Column("tool_name", sa.String(length=255), nullable=True),
        sa.Column("version", sa.String(length=32), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("digest", sa.String(length=64), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=True),
        sa.Column("description", sa.String(length=1024), nullable=True),
        sa.Column("category", sa.String(length=64), nullable=True),
        sa.Column("input_schema", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("output_schema", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("output_policy", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("extra_metadata", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("payload", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("requirements", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("published_by", sa.String(length=36), nullable=True),
        sa.Column("deprecated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_by", sa.String(length=36), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["org_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["skill_db_id"], ["hermes_skills.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_hermes_skill_releases_org_id", "hermes_skill_releases", ["org_id"])
    op.create_index("ix_hermes_skill_releases_skill_db_id", "hermes_skill_releases", ["skill_db_id"])
    op.create_index("ix_hermes_skill_releases_deleted_at", "hermes_skill_releases", ["deleted_at"])
    op.create_index(
        "uq_hermes_skill_releases_skill_version",
        "hermes_skill_releases",
        ["skill_db_id", "version"],
        unique=True,
        postgresql_where=sa.text("deleted_at IS NULL"),
    )
    op.create_index(
        "uq_hermes_skill_releases_one_published",
        "hermes_skill_releases",
        ["skill_db_id"],
        unique=True,
        postgresql_where=sa.text("deleted_at IS NULL AND status = 'published'"),
    )
    op.create_index(
        "ix_hermes_skill_releases_org_skill",
        "hermes_skill_releases",
        ["org_id", "skill_id"],
        postgresql_where=sa.text("deleted_at IS NULL"),
    )
    op.create_index(
        "ix_hermes_skill_releases_org_status",
        "hermes_skill_releases",
        ["org_id", "status"],
        postgresql_where=sa.text("deleted_at IS NULL"),
    )

    conn = op.get_bind()
    rows = conn.execute(
        sa.text(
            """
            SELECT id, org_id, skill_id, tool_name, name, title, description, version,
                   category, input_schema, output_schema, output_policy, extra_metadata, tags,
                   source_type, source_ref, created_by
            FROM hermes_skills
            WHERE deleted_at IS NULL AND is_mcp_exposed = true
            """
        )
    ).mappings().all()

    insert_sql = sa.text(
        """
        INSERT INTO hermes_skill_releases (
            id, org_id, skill_db_id, skill_id, tool_name, version, status, digest,
            title, description, category, input_schema, output_schema, output_policy,
            extra_metadata, payload, requirements, published_at, published_by,
            created_by, notes, created_at, updated_at
        ) VALUES (
            :id, :org_id, :skill_db_id, :skill_id, :tool_name, :version, 'published', :digest,
            :title, :description, :category, CAST(:input_schema AS jsonb), CAST(:output_schema AS jsonb),
            CAST(:output_policy AS jsonb), CAST(:extra_metadata AS jsonb), CAST(:payload AS jsonb),
            CAST('{}' AS jsonb), NOW(), :published_by, :created_by, :notes, NOW(), NOW()
        )
        """
    )
    for row in rows:
        digest = _digest_from_row(row)
        payload = {
            "name": row["name"],
            "tags": row["tags"],
            "source_type": row["source_type"],
            "source_ref": row["source_ref"],
        }
        conn.execute(
            insert_sql,
            {
                "id": str(uuid.uuid4()),
                "org_id": row["org_id"],
                "skill_db_id": row["id"],
                "skill_id": row["skill_id"],
                "tool_name": row["tool_name"],
                "version": row["version"] or "1.0.0",
                "digest": digest,
                "title": row["title"],
                "description": row["description"],
                "category": row["category"],
                "input_schema": json.dumps(row["input_schema"]) if row["input_schema"] is not None else None,
                "output_schema": json.dumps(row["output_schema"]) if row["output_schema"] is not None else None,
                "output_policy": json.dumps(row["output_policy"]) if row["output_policy"] is not None else None,
                "extra_metadata": json.dumps(row["extra_metadata"]) if row["extra_metadata"] is not None else None,
                "payload": json.dumps(payload),
                "published_by": row["created_by"],
                "created_by": row["created_by"],
                "notes": "backfill from is_mcp_exposed skill",
            },
        )


def downgrade() -> None:
    op.drop_index("ix_hermes_skill_releases_org_status", table_name="hermes_skill_releases")
    op.drop_index("ix_hermes_skill_releases_org_skill", table_name="hermes_skill_releases")
    op.drop_index("uq_hermes_skill_releases_one_published", table_name="hermes_skill_releases")
    op.drop_index("uq_hermes_skill_releases_skill_version", table_name="hermes_skill_releases")
    op.drop_index("ix_hermes_skill_releases_deleted_at", table_name="hermes_skill_releases")
    op.drop_index("ix_hermes_skill_releases_skill_db_id", table_name="hermes_skill_releases")
    op.drop_index("ix_hermes_skill_releases_org_id", table_name="hermes_skill_releases")
    op.drop_table("hermes_skill_releases")
