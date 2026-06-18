from sqlalchemy import Boolean, String, CheckConstraint, Index, text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class Checklist(Base):
    __tablename__ = "checklist"
    __table_args__ = (
        CheckConstraint(
            "categoria IN ('LGA','RLGA','RD','Circular','Instructivo','CTB','Ley','DS','Convenio','Otros')",
            name="ck_checklist_categoria",
        ),
        Index("ix_checklist_categoria", "categoria"),
        Index("ix_checklist_subido", "subido"),
        {"schema": "core"},
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, server_default=text("gen_random_uuid()"))
    indice: Mapped[str] = mapped_column(String, nullable=False)
    categoria: Mapped[str] = mapped_column(String, nullable=False)
    codigo: Mapped[str] = mapped_column(String, nullable=False)
    subido: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default=text("false"))
    documento_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
