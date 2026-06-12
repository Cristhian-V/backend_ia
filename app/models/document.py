from datetime import datetime
from sqlalchemy import BigInteger, String, DateTime, func, ForeignKey, CheckConstraint, Index, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class Document(Base):
    __tablename__ = "documents"
    __table_args__ = (
        CheckConstraint("status IN ('processing','ready','error')", name="ck_documents_status"),
        CheckConstraint("chunks_count >= 0", name="ck_documents_chunks_positive"),
        CheckConstraint("page_count >= 0", name="ck_documents_page_count"),
        Index("ix_documents_user_created", "user_id", "created_at"),
        Index("ix_documents_number_nrm", "doc_number_nrm", postgresql_where=text("doc_number_nrm IS NOT NULL")),
        {"schema": "core"},
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, server_default=text("gen_random_uuid()"))
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("auth.users.id", ondelete="CASCADE"), nullable=False, index=True)
    filename: Mapped[str] = mapped_column(String, nullable=False)
    page_count: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    doc_type: Mapped[str] = mapped_column(String, nullable=False, default="otro")
    doc_number: Mapped[str | None] = mapped_column(String, nullable=True)
    doc_number_nrm: Mapped[str | None] = mapped_column(String, nullable=True)
    doc_title: Mapped[str | None] = mapped_column(String, nullable=True)
    doc_date: Mapped[str | None] = mapped_column(String, nullable=True)
    issuing_body: Mapped[str | None] = mapped_column(String, nullable=True)
    status: Mapped[str] = mapped_column(String, nullable=False, default="processing")
    chunks_count: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    chunks = relationship("DocumentChunk", backref="document", lazy="selectin", cascade="all, delete-orphan")
