"""Modelo TokenBlacklist (C-03, D5). Tabla global, NO tenant-scoped (jti único global)."""

from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, Index, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.infrastructure.persistence.base import Base


class TokenBlacklist(Base):
    """JTI revocado/rotado. Purga por ``exp`` (índice btree)."""

    __tablename__ = "token_blacklist"
    __table_args__ = (
        CheckConstraint(
            "type IN ('access', 'refresh')", name="token_blacklist_type"
        ),
        Index("ix_token_blacklist_exp", "exp"),
    )

    jti: Mapped[str] = mapped_column(Text, primary_key=True)
    type: Mapped[str] = mapped_column(Text, nullable=False)
    exp: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    revocado_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    motivo: Mapped[str | None] = mapped_column(Text, nullable=True)
