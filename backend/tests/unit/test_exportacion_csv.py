"""Serialización de celdas y escritura de CSV de la exportación (C-18 1.6)."""

import csv
import io
from datetime import UTC, datetime, timedelta, timezone
from decimal import Decimal

import pytest

from app.domain.cumplimiento.exportacion import celda, escribir_csv


def test_datetime_con_zona_a_iso_con_desplazamiento() -> None:
    assert celda(datetime(2026, 1, 2, 3, 4, 5, tzinfo=UTC)) == "2026-01-02T03:04:05+00:00"
    ar = timezone(timedelta(hours=-3))
    assert celda(datetime(2026, 1, 2, 3, 4, 5, tzinfo=ar)) == "2026-01-02T03:04:05-03:00"


def test_decimal_a_texto_exacto() -> None:
    assert celda(Decimal("1500.50")) == "1500.50"
    assert celda(Decimal("-10.00")) == "-10.00"  # los números no se neutralizan


def test_jsonb_a_json_ordenado_sin_escapar_unicode() -> None:
    assert celda({"b": 1, "a": "ñ"}) == '{"a": "ñ", "b": 1}'
    assert celda([1, 2]) == "[1, 2]"


def test_none_vacio_bool_y_enteros() -> None:
    assert celda(None) == ""
    assert celda(True) == "true"
    assert celda(False) == "false"
    assert celda(-5) == "-5"


@pytest.mark.parametrize("texto", ["=CMD()", "+1+1", "-1+1", "@SUM(A1)", "\tcmd", "\rcmd"])
def test_textos_peligrosos_se_prefijan_con_apostrofo(texto: str) -> None:
    assert celda(texto) == "'" + texto


@pytest.mark.parametrize("texto", ["Juan", "a=b", "1+1", "", " =x"])
def test_textos_comunes_no_se_tocan(texto: str) -> None:
    assert celda(texto) == texto


def test_csv_utf8_con_bom_conserva_caracteres_especiales() -> None:
    buf = io.BytesIO()
    filas = [(1, 'Peña, "Ñandú"\nsegunda línea', None), (2, "=HYPERLINK()", Decimal("2.5"))]
    n = escribir_csv(buf, ["id", "nombre", "otro"], filas)
    assert n == 2
    crudo = buf.getvalue()
    assert crudo.startswith(b"\xef\xbb\xbf")
    leido = list(csv.reader(io.StringIO(crudo.decode("utf-8-sig"), newline="")))
    assert leido[0] == ["id", "nombre", "otro"]
    assert leido[1] == ["1", 'Peña, "Ñandú"\nsegunda línea', ""]
    assert leido[2] == ["2", "'=HYPERLINK()", "2.5"]


def test_csv_sin_filas_solo_encabezados() -> None:
    buf = io.BytesIO()
    assert escribir_csv(buf, ["id", "x"], iter(())) == 0
    assert buf.getvalue().decode("utf-8-sig").strip() == "id,x"
