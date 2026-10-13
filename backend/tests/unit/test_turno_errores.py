"""Mapeo de IntegrityError de PG a errores de dominio de turnos (sin base de datos)."""

import pytest
from sqlalchemy.exc import IntegrityError

from app.domain.agenda.servicio import CatalogoError, Conflicto
from app.domain.agenda.turnos import TurnoNoDisponible, commit_turno


class _Orig(Exception):
    def __init__(self, sqlstate: str) -> None:
        super().__init__(sqlstate)
        self.sqlstate = sqlstate


class _SesionFalsa:
    def __init__(self, error: Exception | None) -> None:
        self._error = error
        self.rollbacks = 0
        self.commits = 0

    def commit(self) -> None:
        if self._error is not None:
            raise self._error
        self.commits += 1

    def rollback(self) -> None:
        self.rollbacks += 1


def _integrity(sqlstate: str) -> IntegrityError:
    return IntegrityError("INSERT INTO turno ...", {"paciente_id": 77}, _Orig(sqlstate))


def test_exclusion_violation_se_traduce_a_409_generico() -> None:
    sesion = _SesionFalsa(_integrity("23P01"))
    with pytest.raises(TurnoNoDisponible) as exc:
        commit_turno(sesion)  # type: ignore[arg-type]
    assert exc.value.status_code == 409
    assert exc.value.detail == "Horario no disponible"
    assert isinstance(exc.value, Conflicto) and isinstance(exc.value, CatalogoError)
    assert "77" not in str(exc.value)
    assert sesion.rollbacks == 1


@pytest.mark.parametrize("sqlstate", ["23503", "23505", "23514"])
def test_otros_sqlstate_se_propagan_sin_traducir(sqlstate) -> None:  # type: ignore[no-untyped-def]
    sesion = _SesionFalsa(_integrity(sqlstate))
    with pytest.raises(IntegrityError):
        commit_turno(sesion)  # type: ignore[arg-type]
    assert sesion.rollbacks == 1


def test_commit_exitoso_no_hace_rollback() -> None:
    sesion = _SesionFalsa(None)
    commit_turno(sesion)  # type: ignore[arg-type]
    assert sesion.commits == 1 and sesion.rollbacks == 0
