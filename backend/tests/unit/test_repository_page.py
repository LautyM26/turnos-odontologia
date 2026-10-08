"""BaseRepository.page: keyset por id, limit+1 y next_cursor (C-04, sin DB)."""

from types import SimpleNamespace
from unittest.mock import MagicMock

from sqlalchemy import BigInteger, Text
from sqlalchemy.dialects import postgresql
from sqlalchemy.orm import Mapped, mapped_column

from app.infrastructure.persistence.base import Base
from app.infrastructure.persistence.mixins import AuditMixin, TenantMixin
from app.infrastructure.persistence.repository import BaseRepository


class _Page(Base, TenantMixin, AuditMixin):
    __tablename__ = "repo_probe_page"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    nombre: Mapped[str] = mapped_column(Text)


def _repo(filas: list[int]) -> tuple[BaseRepository[_Page], MagicMock]:
    session = MagicMock()
    session.scalars.return_value.all.return_value = [SimpleNamespace(id=i) for i in filas]
    return BaseRepository(session, _Page, clinica_id=7), session


def _sql(session: MagicMock) -> str:
    stmt = session.scalars.call_args[0][0]
    return str(stmt.compile(dialect=postgresql.dialect(), compile_kwargs={"literal_binds": True}))


def test_statement_ordena_por_id_filtra_cursor_y_pide_limit_mas_uno() -> None:
    repo, session = _repo([])
    repo.page(after_id=10, limit=50)
    sql = _sql(session)
    assert "clinica_id = 7" in sql
    assert "id > 10" in sql
    assert "ORDER BY repo_probe_page.id" in sql
    assert "LIMIT 51" in sql
    assert "is_active IS true" in sql


def test_sin_cursor_no_filtra_id_y_extra_filtros_se_aplican() -> None:
    repo, session = _repo([])
    repo.page(None, 5, False, _Page.nombre == "x")
    sql = _sql(session)
    assert "id >" not in sql
    assert "nombre = 'x'" in sql
    assert "LIMIT 6" in sql


def test_include_inactive_omite_filtro_activos() -> None:
    repo, session = _repo([])
    repo.page(None, 5, include_inactive=True)
    assert "is_active IS true" not in _sql(session)


def test_next_cursor_cuando_hay_mas_filas() -> None:
    repo, _ = _repo([1, 2, 3])  # limit+1 filas
    items, cursor = repo.page(None, 2)
    assert [i.id for i in items] == [1, 2]
    assert cursor == 2


def test_next_cursor_nulo_en_ultima_pagina() -> None:
    repo, _ = _repo([4, 5])
    items, cursor = repo.page(3, 2)
    assert [i.id for i in items] == [4, 5]
    assert cursor is None
