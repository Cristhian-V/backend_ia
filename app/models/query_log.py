from datetime import datetime
from sqlalchemy import BigInteger, String, DateTime, func, ForeignKey, text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class QueryLog(Base):
    __tablename__ = "query_logs"
    __table_args__ = {"schema": "core"}

    id: Mapped[str] = mapped_column(String(36), primary_key=True, server_default=text("gen_random_uuid()"))
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("auth.users.id", ondelete="CASCADE"), nullable=False, index=True)
    query: Mapped[str] = mapped_column(String, nullable=False)
    answer: Mapped[str] = mapped_column(String, nullable=False)
    model: Mapped[str] = mapped_column(String, nullable=False)
    chunks_count: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
