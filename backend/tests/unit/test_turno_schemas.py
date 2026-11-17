"""TurnoCreate: contrato de alta (extra='forbid', inicio aware -> UTC). C-05 recorte."""

from datetime import UTC, datetime, timedelta

import pytest
from pydantic import ValidationError

from app.domain.agenda.schemas import TurnoCreate

BASE = {
    "profesional_id": 1,
    "sillon_id": 2,
    "paciente_id": 3,
    "prestacion_id": 4,
    "inicio": "2031-03-10T10:00:00Z",
}


def test_acepta_payload_minimo_y_normaliza_a_utc() -> None:
    zulu = TurnoCreate(**BASE)
    arg = TurnoCreate(**{**BASE, "inicio": "2031-03-10T07:00:00-03:00"})
    assert zulu.inicio == datetime(2031, 3, 10, 10, tzinfo=UTC)
    assert arg.inicio == zulu.inicio  # mismo instante
    assert arg.inicio.utcoffset() == timedelta(0)


def test_normaliza_a_utc_un_datetime_con_offset_distinto() -> None:
    plus = TurnoCreate(**{**BASE, "inicio": "2031-03-10T13:00:00+03:00"})
    assert plus.inicio.hour == 10
    assert plus.inicio.utcoffset() == timedelta(0)


@pytest.mark.parametrize("inicio", ["2031-03-10T10:00:00", "2031-03-10", "no-es-fecha"])
def test_rechaza_inicio_naive_o_invalido(inicio) -> None:  # type: ignore[no-untyped-def]
    with pytest.raises(ValidationError):
        TurnoCreate(**{**BASE, "inicio": inicio})


@pytest.mark.parametrize(
    "extra",
    [
        {"fin": "2031-03-10T11:00:00Z"},
        {"duracion_min": 60},
        {"estado": "confirmado"},
        {"origen": "enlace"},
        {"clinica_id": 9},
    ],
)
def test_rechaza_campos_extra(extra) -> None:  # type: ignore[no-untyped-def]
    with pytest.raises(ValidationError) as exc:
        TurnoCreate(**BASE, **extra)
    assert "extra_forbidden" in str(exc.value)


@pytest.mark.parametrize("campo", ["profesional_id", "sillon_id", "paciente_id", "prestacion_id"])
def test_rechaza_ids_faltantes_o_no_enteros(campo) -> None:  # type: ignore[no-untyped-def]
    faltante = {k: v for k, v in BASE.items() if k != campo}
    with pytest.raises(ValidationError):
        TurnoCreate(**faltante)
    with pytest.raises(ValidationError):
        TurnoCreate(**{**BASE, campo: "abc"})


# --- Sobreturno (C-05c D4) -----------------------------------------------------------------


def test_sobreturno_con_motivo_se_acepta_y_recorta() -> None:
    body = TurnoCreate(**BASE, sobreturno=True, motivo_sobreturno="  urgencia, dolor agudo  ")
    assert body.sobreturno is True
    assert body.motivo_sobreturno == "urgencia, dolor agudo"


def test_por_defecto_no_es_sobreturno() -> None:
    body = TurnoCreate(**BASE)
    assert body.sobreturno is False
    assert body.motivo_sobreturno is None


@pytest.mark.parametrize(
    "extra",
    [
        {"sobreturno": True},
        {"sobreturno": True, "motivo_sobreturno": None},
        {"sobreturno": True, "motivo_sobreturno": "   "},
        {"motivo_sobreturno": "motivo sin marca"},
        {"sobreturno": False, "motivo_sobreturno": "motivo sin marca"},
        {"sobreturno": True, "motivo_sobreturno": "x" * 501},
        {"sobreturno": "true", "motivo_sobreturno": "urgencia"},
        {"sobreturno": 1, "motivo_sobreturno": "urgencia"},
    ],
    ids=[
        "sin_motivo", "motivo_null", "motivo_en_blanco", "motivo_sin_marca",
        "marca_false_con_motivo", "motivo_501", "marca_string", "marca_int",
    ],
)  # fmt: skip
def test_sobreturno_invalido(extra) -> None:  # type: ignore[no-untyped-def]
    with pytest.raises(ValidationError):
        TurnoCreate(**BASE, **extra)
