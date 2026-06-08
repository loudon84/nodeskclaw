"""GeneHub skill entitlements for organizations and users."""

from enum import Enum

from sqlalchemy import ForeignKey, Index, String, text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import BaseModel


class EntitlementTargetType(str, Enum):
    organization = "organization"
    user = "user"
    role = "role"
    department = "department"


class EntitlementPermission(str, Enum):
    view = "view"
    install = "install"
    update = "update"
    uninstall = "uninstall"


class GeneHubEntitlement(BaseModel):
    __tablename__ = "genehub_entitlements"
    __table_args__ = (
        Index(
            "ix_genehub_entitlements_gene",
            "gene_id",
            postgresql_where=text("deleted_at IS NULL"),
        ),
        Index(
            "ix_genehub_entitlements_target",
            "org_id",
            "target_type",
            "target_id",
            postgresql_where=text("deleted_at IS NULL"),
        ),
    )

    org_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("organizations.id"), nullable=False
    )
    gene_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("genes.id"), nullable=False
    )
    target_type: Mapped[str] = mapped_column(String(32), nullable=False)
    target_id: Mapped[str] = mapped_column(String(64), nullable=False)
    permission: Mapped[str] = mapped_column(String(32), nullable=False)
    profile_scope: Mapped[str | None] = mapped_column(String(128), nullable=True)
    created_by: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("users.id"), nullable=True
    )
