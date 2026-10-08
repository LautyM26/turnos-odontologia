"""Generic tenant-scoped repository (C-02, D6). Sole domain DB access point."""

from collections.abc import Sequence
from datetime import UTC, datetime

from sqlalchemy import ColumnElement, func, select
from sqlalchemy.orm import Session

from app.infrastructure.persistence.mixins import AuditMixin, TenantMixin


class BaseRepository[ModelT: TenantMixin]:
    """CRUD filtered by ``clinica_id`` + active rows by default.

    ``include_inactive=True`` opts into soft-deleted/inactive rows (admin paths).
    ``delete`` is logical only; physical DELETE is forbidden in domain.
    """

    def __init__(self, session: Session, model: type[ModelT], clinica_id: int) -> None:
        self._session = session
        self._model = model
        self._clinica_id = clinica_id

    def _scoped(self, include_inactive: bool = False):  # type: ignore[no-untyped-def]
        stmt = select(self._model).where(self._model.clinica_id == self._clinica_id)
        if not include_inactive and issubclass(self._model, AuditMixin):
            stmt = stmt.where(self._model.is_active.is_(True))
        return stmt

    def get(self, row_id: int, include_inactive: bool = False) -> ModelT | None:
        """Fetch one row by PK within the tenant scope."""
        stmt = self._scoped(include_inactive).where(self._model.id == row_id)  # type: ignore[attr-defined]
        return self._session.scalars(stmt).one_or_none()

    def list(self, include_inactive: bool = False) -> Sequence[ModelT]:
        """List tenant rows, active only unless ``include_inactive``."""
        return self._session.scalars(self._scoped(include_inactive)).all()

    def page(
        self,
        after_id: int | None,
        limit: int,
        include_inactive: bool = False,
        *filtros: ColumnElement[bool],
    ) -> tuple[Sequence[ModelT], int | None]:
        """Keyset pagination by ``id`` (never OFFSET). Returns ``(items, next_cursor)``.

        Fetches ``limit + 1`` rows to know whether another page exists; ``next_cursor``
        is the id of the last returned row, or ``None`` on the final page.
        """
        stmt = self._scoped(include_inactive)
        if after_id is not None:
            stmt = stmt.where(self._model.id > after_id)  # type: ignore[attr-defined]
        if filtros:
            stmt = stmt.where(*filtros)
        stmt = stmt.order_by(self._model.id).limit(limit + 1)  # type: ignore[attr-defined]
        rows = list(self._session.scalars(stmt).all())
        if len(rows) > limit:
            rows = rows[:limit]
            return rows, rows[-1].id  # type: ignore[attr-defined]
        return rows, None

    def add(self, obj: ModelT) -> ModelT:
        """Attach a row, forcing the repository tenant scope."""
        obj.clinica_id = self._clinica_id
        self._session.add(obj)
        return obj

    def delete(self, obj: ModelT) -> ModelT:
        """Soft-delete: flag inactive + timestamp, never physical DELETE."""
        if isinstance(obj, AuditMixin):
            obj.is_active = False
            obj.deleted_at = datetime.now(UTC)
        self._session.add(obj)
        return obj

    def count_active_by_email(self, email: str) -> int:
        """Count active rows matching a normalized (lower) email."""
        stmt = (
            select(func.count())
            .select_from(self._model)
            .where(
                self._model.clinica_id == self._clinica_id,
                func.lower(self._model.email) == email.lower(),  # type: ignore[attr-defined]
            )
        )
        if issubclass(self._model, AuditMixin):
            stmt = stmt.where(self._model.is_active.is_(True))
        return int(self._session.scalars(stmt).one())
