"""Per-instance LLM provider configuration (merged UserLlmConfig + InstanceLlmOverride)."""

from sqlalchemy import ForeignKey, Index, String, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import BaseModel


class InstanceProviderConfig(BaseModel):
    __tablename__ = "instance_provider_configs"
    __table_args__ = (
        Index(
            "uq_instance_provider_configs_inst_provider",
            "instance_id", "provider",
            unique=True,
            postgresql_where=text("deleted_at IS NULL"),
        ),
    )

    instance_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("instances.id"), nullable=False, index=True
    )
    provider: Mapped[str] = mapped_column(String(32), nullable=False)
    key_source: Mapped[str] = mapped_column(
        String(16), nullable=False, server_default="org"
    )
    selected_models: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    base_url: Mapped[str | None] = mapped_column(String(512), nullable=True)
    api_type: Mapped[str | None] = mapped_column(String(32), nullable=True)
