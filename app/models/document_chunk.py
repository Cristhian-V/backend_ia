from datetime import datetime
from sqlalchemy import BigInteger, Integer, String, DateTime, ForeignKey, Index, text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class DocumentChunk(Base):
    __tablename__ = "document_chunks"
    __table_args__ = (
        UniqueConstraint("document_id", "chunk_index", name="uq_chunks_doc_idx"),
        Index("ix_chunks_document", "document_id"),
        {"schema": "core"},
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, server_default=text("gen_random_uuid()"))
    document_id: Mapped[str] = mapped_column(String(36), ForeignKey("core.documents.id", ondelete="CASCADE"), nullable=False)
    chunk_index: Mapped[int] = mapped_column(Integer, nullable=False)
    chapter_title: Mapped[str] = mapped_column(String, nullable=False, default="")
    page_start: Mapped[int | None] = mapped_column(Integer, nullable=True)
    page_end: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=text("now()"))
