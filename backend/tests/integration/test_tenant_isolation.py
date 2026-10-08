"""Aislamiento multi-tenant + integridad + soft-delete en PG16 (Tasks 5.1/5.2).

NUNCA SQLite. Specs: tenant-isolation (query cruzada = 0, escritura sin
tenant rechazada, soft-delete) y core-models (email único por tenant).
"""

import pytest
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError

from app.domain.core.models import Clinica, Usuario
from app.infrastructure.persistence.repository import BaseRepository

CUIT_A = "30123456781"
CUIT_B = "30567812347"


def _clinica(session, nombre: str, cuit: str) -> Clinica:  # type: ignore[no-untyped-def]
    row = Clinica(nombre=nombre, cuit=cuit)
    session.add(row)
    session.flush()
    return row


def _usuario(repo: BaseRepository[Usuario], email: str) -> Usuario:
    user = Usuario(email=email.lower(), password_hash="hash-sintetico")
    repo.add(user)
    repo._session.flush()
    return user


@pytest.fixture(scope="module")
def tenants(session_factory):  # type: ignore[no-untyped-def]
    """Crea clínicas A/B con usuarios. Un contenedor por módulo."""
    with session_factory() as session:
        a = _clinica(session, "Clinica A Sintetica", CUIT_A)
        b = _clinica(session, "Clinica B Sintetica", CUIT_B)
        repo_a = BaseRepository(session, Usuario, clinica_id=a.id)
        repo_b = BaseRepository(session, Usuario, clinica_id=b.id)
        _usuario(repo_a, "compartido@demo.com")
        _usuario(repo_a, "solo-a@demo.com")
        _usuario(repo_b, "compartido@demo.com")
        _usuario(repo_b, "solo-b@demo.com")
        session.commit()
        yield {"a_id": a.id, "b_id": b.id}


def test_query_cruzada_retorna_cero_filas_de_otro_tenant(
    session_factory, tenants  # type: ignore[no-untyped-def]
) -> None:
    with session_factory() as session:
        repo_a = BaseRepository(session, Usuario, clinica_id=tenants["a_id"])
        emails = sorted(u.email for u in repo_a.list())
        assert emails == ["compartido@demo.com", "solo-a@demo.com"]
        cruzadas = (
            session.scalars(
                select(Usuario).where(
                    Usuario.clinica_id == tenants["a_id"],
                    Usuario.email.in_(["solo-b@demo.com"]),
                )
            ).all()
        )
        assert cruzadas == []


def test_mismo_email_distintas_clinicas_permitido(session_factory, tenants) -> None:  # type: ignore[no-untyped-def]
    with session_factory() as session:
        total = (
            session.scalar(
                select(func.count())
                .select_from(Usuario)
                .where(func.lower(Usuario.email) == "compartido@demo.com")
            )
            or 0
        )
        assert total == 2


def test_email_duplicado_misma_clinica_rechazado(
    session_factory, tenants  # type: ignore[no-untyped-def]
) -> None:
    with session_factory() as session:
        repo_a = BaseRepository(session, Usuario, clinica_id=tenants["a_id"])
        repo_a.add(
            Usuario(email="COMPARTIDO@DEMO.COM", password_hash="hash-sintetico")
        )
        with pytest.raises(IntegrityError):
            session.flush()
        session.rollback()


def test_escritura_sin_clinica_id_rechazada(session_factory) -> None:  # type: ignore[no-untyped-def]
    with session_factory() as session:
        session.add(Usuario(email="huerfano@demo.com", password_hash="x"))
        with pytest.raises(IntegrityError):
            session.flush()
        session.rollback()


def test_soft_delete_oculta_en_listados_pero_persiste(
    session_factory, tenants  # type: ignore[no-untyped-def]
) -> None:
    with session_factory() as session:
        repo_a = BaseRepository(session, Usuario, clinica_id=tenants["a_id"])
        target = next(u for u in repo_a.list() if u.email == "solo-a@demo.com")
        repo_a.delete(target)
        session.commit()
        visibles = [u.email for u in repo_a.list()]
        assert "solo-a@demo.com" not in visibles
        con_inactivos = [u.email for u in repo_a.list(include_inactive=True)]
        assert "solo-a@demo.com" in con_inactivos
        persistida = session.scalars(
            select(Usuario).where(Usuario.id == target.id)
        ).one()
        assert persistida.is_active is False
        assert persistida.deleted_at is not None
