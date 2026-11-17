"""Errores de dominio de cumplimiento (C-18 1.5): status HTTP y traducción por el handler."""

import pytest
from fastapi import APIRouter
from fastapi.testclient import TestClient

from app.domain.cumplimiento import errores
from app.domain.pacientes.servicios import PacienteError

CASOS = [
    (errores.TipoConsentimientoInvalido, 422, ()),
    (errores.ConsentimientoNoEncontrado, 404, ()),
    (errores.FirmaIncompleta, 422, (["acepta"],)),
    (errores.HashNoCoincide, 409, ()),
    (errores.ConsentimientoYaFirmado, 409, ()),
    (errores.FormatoNoSoportado, 422, ("pdf",)),
]


@pytest.mark.parametrize(("cls", "status", "args"), CASOS)
def test_es_paciente_error_con_status(cls, status, args) -> None:  # type: ignore[no-untyped-def]
    exc = cls(*args)
    assert isinstance(exc, PacienteError)
    assert exc.status_code == status
    assert exc.detail


def test_firma_incompleta_es_reintentable_y_lista_faltantes() -> None:
    exc = errores.FirmaIncompleta(["acepta", "firmante_dni"])
    assert exc.extra == {"reintentable": True, "faltantes": ["acepta", "firmante_dni"]}


def test_formato_no_soportado_declara_formatos() -> None:
    assert errores.FormatoNoSoportado("pdf").extra == {"formatos": ["csv"]}


def _app_con_error(cls, args):  # type: ignore[no-untyped-def]
    from app.main import create_app

    router = APIRouter()

    @router.get("/_prueba_error_cumplimiento")
    def _levantar() -> None:
        raise cls(*args)

    app = create_app()
    app.include_router(router)
    return TestClient(app, raise_server_exceptions=False)


def test_firma_incompleta_serializa_por_el_handler_de_create_app() -> None:
    r = _app_con_error(errores.FirmaIncompleta, (["acepta"],)).get("/_prueba_error_cumplimiento")
    assert r.status_code == 422
    cuerpo = r.json()
    assert cuerpo["reintentable"] is True
    assert cuerpo["faltantes"] == ["acepta"]
    assert cuerpo["detail"]


@pytest.mark.parametrize(("cls", "status", "args"), CASOS)
def test_handler_traduce_cada_error(cls, status, args) -> None:  # type: ignore[no-untyped-def]
    r = _app_con_error(cls, args).get("/_prueba_error_cumplimiento")
    assert r.status_code == status
