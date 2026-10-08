"""Schemas de agenda: extra='forbid', rangos, Decimal exacto y fechas aware (C-04)."""

import json
from datetime import UTC, datetime
from decimal import Decimal

import pytest
from pydantic import ValidationError

from app.domain.agenda.schemas import (
    BloqueoCreate,
    BloqueoPropioCreate,
    BloqueoUpdate,
    HabilitacionIn,
    Pagina,
    PrestacionCreate,
    PrestacionOut,
    PrestacionUpdate,
    ProfesionalCreate,
    ProfesionalUpdate,
    SillonCreate,
    SillonUpdate,
)

VALIDOS = {
    SillonCreate: {"nombre": "S1", "tipo": "sillon"},
    SillonUpdate: {"nombre": "S1"},
    PrestacionCreate: {"nombre": "P", "duracion_min": 30, "precio_referencia": "10.00"},
    PrestacionUpdate: {"nombre": "P"},
    ProfesionalCreate: {"nombre": "Dra", "matricula": "M1"},
    ProfesionalUpdate: {"nombre": "Dra"},
    BloqueoCreate: {
        "inicio": "2030-01-01T10:00:00-03:00", "fin": "2030-01-01T11:00:00-03:00",
        "motivo": "feriado",
    },
    BloqueoUpdate: {"motivo": "x"},
    BloqueoPropioCreate: {
        "inicio": "2030-01-01T10:00:00-03:00", "fin": "2030-01-01T11:00:00-03:00",
        "motivo": "curso",
    },
}  # fmt: skip


@pytest.mark.parametrize("schema", list(VALIDOS))
@pytest.mark.parametrize("extra", ["clinica_id", "es_seed", "rango", "is_active", "id"])
def test_rechaza_campos_extra(schema, extra) -> None:  # type: ignore[no-untyped-def]
    schema(**VALIDOS[schema])  # el payload base es válido
    with pytest.raises(ValidationError) as exc:
        schema(**VALIDOS[schema], **{extra: 1})
    assert exc.value.errors()[0]["type"] == "extra_forbidden"


@pytest.mark.parametrize("tipo", ["quirofano", "", "Sillon"])
def test_tipo_invalido(tipo) -> None:  # type: ignore[no-untyped-def]
    with pytest.raises(ValidationError):
        SillonCreate(nombre="S", tipo=tipo)


@pytest.mark.parametrize("tipo", ["sillon", "box", "equipo"])
def test_tipo_valido(tipo) -> None:  # type: ignore[no-untyped-def]
    assert SillonCreate(nombre="S", tipo=tipo).tipo == tipo


@pytest.mark.parametrize("duracion", [0, 4, 481, 600, 30.5, "treinta", True])
def test_duracion_invalida(duracion) -> None:  # type: ignore[no-untyped-def]
    with pytest.raises(ValidationError):
        PrestacionCreate(nombre="P", duracion_min=duracion, precio_referencia="1.00")


@pytest.mark.parametrize("duracion", [5, 30, 480])
def test_duracion_valida(duracion) -> None:  # type: ignore[no-untyped-def]
    assert PrestacionCreate(nombre="P", duracion_min=duracion, precio_referencia="1").duracion_min


@pytest.mark.parametrize("precio", ["-1", "-0.01", "10.001", "12345678901.00"])
def test_precio_invalido(precio) -> None:  # type: ignore[no-untyped-def]
    with pytest.raises(ValidationError):
        PrestacionCreate(nombre="P", duracion_min=30, precio_referencia=precio)


def test_precio_decimal_exacto_y_serializa_como_string() -> None:
    out = PrestacionOut(
        id=1, nombre="P", duracion_min=30, precio_referencia=Decimal("15000.50"),
        is_active=True, es_seed=False,
    )  # fmt: skip
    assert isinstance(out.precio_referencia, Decimal)
    assert json.loads(out.model_dump_json())["precio_referencia"] == "15000.50"
    otro = PrestacionOut(
        id=2, nombre="Q", duracion_min=30, precio_referencia=Decimal("0.10"),
        is_active=True, es_seed=False,
    )  # fmt: skip
    assert json.loads(otro.model_dump_json())["precio_referencia"] == "0.10"


def test_fecha_naive_rechazada_y_aware_normaliza_a_utc() -> None:
    with pytest.raises(ValidationError):
        BloqueoCreate(inicio="2030-01-01T10:00:00", fin="2030-01-01T11:00:00", motivo="m")
    b = BloqueoCreate(**VALIDOS[BloqueoCreate])
    assert b.inicio == datetime(2030, 1, 1, 13, 0, tzinfo=UTC)
    assert b.inicio.utcoffset().total_seconds() == 0


def test_bloqueo_con_profesional_y_sillon_es_error() -> None:
    with pytest.raises(ValidationError):
        BloqueoCreate(**VALIDOS[BloqueoCreate], profesional_id=1, sillon_id=2)
    assert BloqueoCreate(**VALIDOS[BloqueoCreate], profesional_id=1).sillon_id is None
    assert BloqueoCreate(**VALIDOS[BloqueoCreate], sillon_id=2).profesional_id is None


def test_bloqueo_rango_invalido() -> None:
    base = {"motivo": "m"}
    with pytest.raises(ValidationError):
        BloqueoCreate(inicio="2030-01-01T10:00:00Z", fin="2030-01-01T10:00:00Z", **base)
    with pytest.raises(ValidationError):
        BloqueoCreate(inicio="2030-01-01T10:00:00Z", fin="2030-01-01T09:00:00Z", **base)
    with pytest.raises(ValidationError):
        BloqueoCreate(inicio="2030-01-01T00:00:00Z", fin="2030-02-10T00:00:00Z", **base)
    ok = BloqueoCreate(inicio="2030-01-01T00:00:00Z", fin="2030-02-01T00:00:00Z", **base)
    assert ok.fin > ok.inicio


def test_bloqueo_propio_no_acepta_sillon() -> None:
    with pytest.raises(ValidationError):
        BloqueoPropioCreate(**VALIDOS[BloqueoPropioCreate], sillon_id=1)


def test_motivo_vacio_o_largo_rechazado() -> None:
    for motivo in ("", "x" * 201):
        with pytest.raises(ValidationError):
            BloqueoCreate(inicio="2030-01-01T10:00:00Z", fin="2030-01-01T11:00:00Z", motivo=motivo)


def test_habilitacion_sin_duplicados() -> None:
    assert HabilitacionIn(sillon_ids=[1, 2]).sillon_ids == [1, 2]
    assert HabilitacionIn(sillon_ids=[]).sillon_ids == []
    with pytest.raises(ValidationError):
        HabilitacionIn(sillon_ids=[1, 1])


def test_profesional_defaults_de_flags() -> None:
    p = ProfesionalCreate(nombre="Dra", matricula="M1")
    assert p.agenda_activa is True
    assert p.tercerizado is False
    assert p.usuario_id is None
    for campo in ({"nombre": ""}, {"matricula": ""}, {"matricula": "x" * 51}):
        with pytest.raises(ValidationError):
            ProfesionalCreate(**{"nombre": "D", "matricula": "M", **campo})


def test_update_parcial_solo_campos_enviados() -> None:
    u = PrestacionUpdate(duracion_min=40)
    assert u.model_dump(exclude_unset=True) == {"duracion_min": 40}


def test_pagina_generica() -> None:
    p = Pagina[int](items=[1, 2], next_cursor=2)
    assert p.model_dump() == {"items": [1, 2], "next_cursor": 2}
    assert Pagina[int](items=[]).next_cursor is None
