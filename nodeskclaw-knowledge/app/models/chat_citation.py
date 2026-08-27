"""Knowledge chat citation / evidence ORM model."""

from sqlalchemy import Float, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import BaseModel


class ChatCitation(BaseModel):
    __tablename__ = "knowledge_chat_citations"

    org_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    issued_member_id: Mapped[str] = mapped_column(String(36), nullable=False)
    message_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)
    knowledge_base_id: Mapped[str] = mapped_column(String(36), nullable=False)
    source_file_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    file_version_id: Mapped[str] = mapped_column(String(36), nullable=False)
    ragflow_document_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    ragflow_chunk_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    page: Mapped[int | None] = mapped_column(Integer, nullable=True)
    positions: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    score: Mapped[float | None] = mapped_column(Float, nullable=True)
    quote: Mapped[str | None] = mapped_column(Text, nullable=True)
    evidence_type: Mapped[str] = mapped_column(String(64), nullable=False, default="chunk")
    content: Mapped[str | None] = mapped_column(Text, nullable=True)
    source_refs: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    runtime_payload: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    origin: Mapped[str] = mapped_column(String(64), nullable=False, default="chat")
