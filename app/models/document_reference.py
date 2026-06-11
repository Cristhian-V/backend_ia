from datetime import datetime
from sqlalchemy import BigInteger, String, DateTime, func, ForeignKey, CheckConstraint, Index, text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class DocumentReference(Base):
    __tablename__ = "document_references"
    __table_args__ = (
        CheckConstraint(
            "relation IN ('deroga','modifica','referencia','complementa','base_legal')",
            name="ck_refs_relation",
        ),
        CheckConstraint(
            "ref_type IN ('resolucion','circular','ley','decreto','reglamento','otro')",
            name="ck_refs_type",
        ),
        Index("ix_refs_pending", "user_id", "created_at", postgresql_where=text("resolved_document_id IS NULL")),
        Index("ix_refs_number_nrm", "ref_number_nrm", postgresql_where=text("resolved_document_id IS NULL")),
        Index("ix_refs_source", "source_document_id"),
        {"schema": "core"},
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, server_default=text("gen_random_uuid()"))
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("auth.users.id", ondelete="CASCADE"), nullable=False, index=True)
    source_document_id: Mapped[str] = mapped_column(String(36), ForeignKey("core.documents.id", ondelete="CASCADE"), nullable=False, index=True)
    chapter_title: Mapped[str] = mapped_column(String, nullable=False, default="")
    ref_type: Mapped[str] = mapped_column(String, nullable=False, default="otro")
    ref_number: Mapped[str] = mapped_column(String, nullable=False)
    ref_number_nrm: Mapped[str] = mapped_column(String, nullable=False)
    ref_title: Mapped[str] = mapped_column(String, nullable=False, default="")
    ref_article: Mapped[str] = mapped_column(String, nullable=False, default="")
    ref_date: Mapped[str] = mapped_column(String, nullable=False, default="")
    relation: Mapped[str] = mapped_column(String, nullable=False, default="referencia")
    resolved_document_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("core.documents.id", ondelete="SET NULL"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
