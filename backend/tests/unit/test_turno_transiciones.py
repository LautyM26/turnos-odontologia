"""C-05b: tabla de transiciones (D1), schema de transicion (D6) y error 403 (D2). Sin base."""

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from pydantic import ValidationError

from app.domain.agenda.schemas import TurnoTransicionIn
from app.domain.agenda.servicio import CatalogoError, PermisoDenegado
from app.domain.agenda.turnos import ESTADOS_TURNO, puede_transicionar

PERMITIDAS = {
    ("reservado", "confirmado"),
    ("reservado", "cancelado"),
    ("reservado", "asistido"),
    ("reservado", "ausente"),
    ("confirmado", "asistido"),
    ("confirmado", "ausente"),
    ("confirmado", "cancelado"),
}


@pytest.mark.parametrize(("desde", "hacia"), sorted(PERMITIDAS))
def test_aristas_permitidas(desde: str, hacia: str) -> None:
    assert puede_transicionar(desde, hacia)


@pytest.mark.parametrize(
    ("desde", "hacia"),
    sorted((d, h) for d in ESTADOS_TURNO for h in ESTADOS_TURNO if (d, h) not in PERMITIDAS),
)
def test_todo_lo_demas_rechazado(desde: str, hacia: str) -> None:
    """Incluye terminales -> cualquiera, repetir estado, -> reservado y -> sobreturno."""
    assert not puede_transicionar(desde, hacia)


def test_estado_desconocido_rechazado() -> None:
    assert not puede_transicionar("inventado", "confirmado")
    assert not puede_transicionar("reservado", "inventado")


@pytest.mark.parametrize("estado", ["confirmado", "cancelado", "asistido", "ausente"])
def test_schema_acepta_los_cuatro_destinos(estado: str) -> None:
    assert TurnoTransicionIn(estado=estado).estado == estado


@pytest.mark.parametrize("estado", ["reservado", "sobreturno", "CONFIRMADO", "", None])
def test_schema_rechaza_otros_destinos(estado: object) -> None:
    with pytest.raises(ValidationError):
        TurnoTransicionIn(estado=estado)  # type: ignore[arg-type]


@pytest.mark.parametrize("extra", [{"inicio": "2031-01-01T10:00:00Z"}, {"clinica_id": 2}])
def test_schema_rechaza_campos_extra(extra: dict) -> None:
    with pytest.raises(ValidationError):
        TurnoTransicionIn(estado="cancelado", **extra)


def test_motivo_se_normaliza() -> None:
    assert TurnoTransicionIn(estado="cancelado").motivo is None
    assert TurnoTransicionIn(estado="cancelado", motivo="   ").motivo is None
    assert TurnoTransicionIn(estado="cancelado", motivo="  avisó  ").motivo == "avisó"
    assert TurnoTransicionIn(estado="cancelado", motivo="x" * 500).motivo == "x" * 500


def test_motivo_largo_rechazado() -> None:
    with pytest.raises(ValidationError):
        TurnoTransicionIn(estado="cancelado", motivo="x" * 501)


def test_permiso_denegado_se_traduce_a_403() -> None:
    assert issubclass(PermisoDenegado, CatalogoError)
    from app.main import create_app

    app: FastAPI = create_app()

    @app.get("/__prueba_403")
    def _ruta() -> None:
        raise PermisoDenegado("No autorizado")

    resp = TestClient(app).get("/__prueba_403")
    assert resp.status_code == 403
    assert resp.json() == {"detail": "No autorizado"}
