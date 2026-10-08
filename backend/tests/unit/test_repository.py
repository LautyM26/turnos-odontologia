"""BaseRepository: filtro clinica_id + is_active por defecto, soft-delete (Task 1.2)."""

from unittest.mock import MagicMock

from sqlalchemy import BigInteger, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.infrastructure.persistence.base import Base
from app.infrastructure.persistence.mixins import AuditMixin, TenantMixin
from app.infrastructure.persistence.repository import BaseRepository
from app.infrastructure.persistence.uow import UnitOfWork


class _Item(Base, TenantMixin, AuditMixin):
    __tablename__ = "repo_probe_item"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    email: Mapped[str] = mapped_column(Text)


def _repo() -> tuple[BaseRepository[_Item], MagicMock]:
    session = MagicMock()
    return BaseRepository(session, _Item, clinica_id=7), session


def test_list_filtra_tenant_y_activos_por_defecto() -> None:
    repo, session = _repo()
    repo.list()
    stmt_str = str(session.scalars.call_args[0][0])
    assert "clinica_id" in stmt_str
    assert "IS true" in stmt_str


def test_list_include_inactive_omite_filtro_activos() -> None:
    repo, session = _repo()
    repo.list(include_inactive=True)
    stmt_str = str(session.scalars.call_args[0][0])
    assert "clinica_id" in stmt_str
    assert "IS true" not in stmt_str


def test_add_fuerza_clinica_id_del_scope() -> None:
    repo, _ = _repo()
    obj = _Item(email="a@demo.com", clinica_id=999)
    repo.add(obj)
    assert obj.clinica_id == 7


def test_delete_es_logico_nunca_fisico() -> None:
    repo, session = _repo()
    obj = _Item(email="b@demo.com", clinica_id=7)
    repo.delete(obj)
    assert obj.is_active is False
    assert obj.deleted_at is not None
    session.delete.assert_not_called()


def test_uow_commit_y_rollback_delegan_en_sesion() -> None:
    session = MagicMock()
    uow = UnitOfWork(session)
    uow.commit()
    session.commit.assert_called_once_with()
    uow.rollback()
    session.rollback.assert_called_once_with()
