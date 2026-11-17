"""Contrato del horario de atención (C-05d D1/D5): HH:MM <-> minutos, superposición, límites."""

import pytest
from pydantic import ValidationError

from app.domain.agenda.schemas import FranjaOut, HorarioIn


def _h(*franjas: tuple[int, str, str]) -> HorarioIn:
    return HorarioIn(franjas=[{"dia_semana": d, "inicio": i, "fin": f} for d, i, f in franjas])


def test_convierte_hhmm_a_minutos_y_ordena() -> None:
    horario = _h((2, "15:00", "19:00"), (1, "09:00", "13:00"), (2, "09:00", "13:00"))
    assert [(f.dia_semana, f.inicio, f.fin) for f in horario.franjas] == [
        (1, 540, 780), (2, 540, 780), (2, 900, 1140),
    ]  # fmt: skip


def test_24_00_es_dia_completo_y_contiguas_son_validas() -> None:
    horario = _h((6, "00:00", "24:00"), (1, "09:00", "10:00"), (1, "10:00", "11:00"))
    assert (horario.franjas[-1].inicio, horario.franjas[-1].fin) == (0, 1440)
    assert len(horario.franjas) == 3


def test_lista_vacia_es_valida() -> None:
    assert HorarioIn(franjas=[]).franjas == []


@pytest.mark.parametrize(
    "franjas",
    [
        [(1, "9:00", "13:00")],
        [(1, "09:00", "24:30")],
        [(1, "12:60", "13:00")],
        [(1, "25:00", "26:00")],
        [(1, "13:00", "13:00")],
        [(1, "14:00", "13:00")],
        [(0, "09:00", "13:00")],
        [(8, "09:00", "13:00")],
        [(1, "09:00", "13:00"), (1, "12:00", "16:00")],
        [(1, "09:00", "13:00"), (1, "10:00", "11:00")],
    ],
    ids=[
        "sin_cero", "24_30", "minuto_60", "hora_25", "ini_igual_fin", "ini_mayor",
        "dia_0", "dia_8", "superpuestas", "contenida",
    ],
)  # fmt: skip
def test_franjas_invalidas(franjas) -> None:  # type: ignore[no-untyped-def]
    with pytest.raises(ValidationError):
        _h(*franjas)


def test_mas_de_70_franjas_falla() -> None:
    with pytest.raises(ValidationError):
        HorarioIn(
            franjas=[
                {"dia_semana": 1 + i % 7, "inicio": f"{i // 7:02d}:00", "fin": f"{i // 7:02d}:30"}
                for i in range(71)
            ]
        )


def test_campo_extra_falla() -> None:
    with pytest.raises(ValidationError):
        HorarioIn(franjas=[{"dia_semana": 1, "inicio": "09:00", "fin": "10:00", "x": 1}])
    with pytest.raises(ValidationError):
        HorarioIn(franjas=[], otro=1)


def test_salida_formatea_minutos_como_hhmm() -> None:
    out = FranjaOut.model_validate({"dia_semana": 1, "inicio_min": 540, "fin_min": 1440})
    assert out.model_dump() == {"dia_semana": 1, "inicio": "09:00", "fin": "24:00"}
