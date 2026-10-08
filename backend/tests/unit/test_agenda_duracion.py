"""calcular_fin: el fin del turno se calcula solo en servidor (regla dura 6)."""

from datetime import UTC, datetime, timedelta, timezone

import pytest

from app.domain.agenda.duracion import calcular_fin

AR = timezone(timedelta(hours=-3))


@pytest.mark.parametrize(
    ("minutos", "esperado"),
    [(30, datetime(2030, 1, 1, 10, 30, tzinfo=AR)), (60, datetime(2030, 1, 1, 11, 0, tzinfo=AR))],
)
def test_suma_duracion_conservando_offset(minutos, esperado) -> None:  # type: ignore[no-untyped-def]
    inicio = datetime(2030, 1, 1, 10, 0, tzinfo=AR)
    assert calcular_fin(inicio, minutos) == esperado


def test_cruce_de_medianoche() -> None:
    fin = calcular_fin(datetime(2030, 1, 1, 23, 30, tzinfo=AR), 60)
    assert fin == datetime(2030, 1, 2, 0, 30, tzinfo=AR)
    assert fin.date().day == 2


def test_resultado_es_aware_y_equivale_en_utc() -> None:
    fin = calcular_fin(datetime(2030, 1, 1, 10, 0, tzinfo=AR), 45)
    assert fin.tzinfo is not None
    assert fin.astimezone(UTC) == datetime(2030, 1, 1, 13, 45, tzinfo=UTC)


def test_inicio_naive_levanta_value_error() -> None:
    with pytest.raises(ValueError, match="zona horaria"):
        calcular_fin(datetime(2030, 1, 1, 10, 0), 30)


@pytest.mark.parametrize("minutos", [0, 4, 481, -10])
def test_duracion_fuera_de_rango_levanta_value_error(minutos) -> None:  # type: ignore[no-untyped-def]
    with pytest.raises(ValueError, match="duracion"):
        calcular_fin(datetime(2030, 1, 1, 10, 0, tzinfo=AR), minutos)


@pytest.mark.parametrize("minutos", [5, 480])
def test_limites_validos(minutos) -> None:  # type: ignore[no-untyped-def]
    inicio = datetime(2030, 1, 1, 10, 0, tzinfo=AR)
    assert calcular_fin(inicio, minutos) - inicio == timedelta(minutes=minutos)
