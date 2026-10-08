"""Tenant + audit mixins (C-02, D6). All tenant tables compose both."""

from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, func
from sqlalchemy.orm import Mapped, mapped_column


class TenantMixin:
    """Adds mandatory ``clinica_id`` FK. Only ``Clinica`` itself is exempt."""

    __abstract__ = True
    __abstract_attrs__ = ("clinica_id",)

    clinica_id: Mapped[int] = mapped_column(
        ForeignKey("clinica.id", ondelete="restrict"), nullable=False
    )


class AuditMixin:
    """Soft-delete + timestamps. Time ALWAYS TIMESTAMPTZ (regla dura 7)."""

    __abstract__ = True
    __abstract_attrs__ = ("is_active", "created_at", "updated_at", "deleted_at")

    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
