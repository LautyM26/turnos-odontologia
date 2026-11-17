"""Errores de dominio de la HC clínica (C-09, D6): status HTTP y traducción por el handler."""

import pytest
from fastapi import APIRouter
from fastapi.testclient import TestClient

from app.domain.clinica import errores
from app.domain.pacientes.servicios import PacienteError

CASOS = [
    (errores.AutorProfesionalRequerido, 422, ()),
    (errores.VersionOdontogramaConflicto, 409, ()),
    (errores.EvolucionYaCorregida, 409, (77,)),
    (errores.CorreccionNoAutorizada, 403, ()),
    (errores.CorreccionInvalida, 422, ()),
    (errores.EvolucionNoEncontrada, 404, ()),
]


@pytest.mark.parametrize(("cls", "status", "args"), CASOS)
def test_es_paciente_error_con_status(cls, status, args) -> None:  # type: ignore[no-untyped-def]
    exc = cls(*args)
    assert isinstance(exc, PacienteError)
    assert exc.status_code == status
    assert exc.detail


def test_evolucion_ya_corregida_nombra_la_vigente() -> None:
    exc = errores.EvolucionYaCorregida(77)
    assert exc.extra == {"evolucion_vigente_id": 77}
    assert "77" in exc.detail


@pytest.mark.parametrize(("cls", "status", "args"), CASOS)
def test_handler_de_create_app_lo_traduce(cls, status, args) -> None:  # type: ignore[no-untyped-def]
    from app.main import create_app

    router = APIRouter()

    @router.get("/_prueba_error_clinica")
    def _levantar() -> None:
        raise cls(*args)

    app = create_app()
    app.include_router(router)
    r = TestClient(app, raise_server_exceptions=False).get("/_prueba_error_clinica")
    assert r.status_code == status
    assert r.json()["detail"]
