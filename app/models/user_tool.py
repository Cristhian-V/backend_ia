from sqlalchemy import BigInteger, String, ForeignKey, UniqueConstraint, CheckConstraint, text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.constants import TOOL_KEYS, ROLES


class UserTool(Base):
    __tablename__ = "user_tools"
    __table_args__ = (
        UniqueConstraint("user_id", "tool_key", name="uq_user_tools"),
        CheckConstraint(
            f"tool_key IN ({','.join(repr(t) for t in TOOL_KEYS)})",
            name="ck_user_tools_key",
        ),
        CheckConstraint(
            f"role IS NULL OR role IN ({','.join(repr(r) for r in ROLES)})",
            name="ck_user_tools_role",
        ),
        {"schema": "core"},
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, server_default=text("gen_random_uuid()"))
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("auth.users.id", ondelete="CASCADE"), nullable=False)
    tool_key: Mapped[str] = mapped_column(String, nullable=False)
    role: Mapped[str | None] = mapped_column(String, nullable=True, default=None)
