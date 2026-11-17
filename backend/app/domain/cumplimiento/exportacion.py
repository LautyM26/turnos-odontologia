"""Serialización pura de la exportación CSV (C-18, D5)."""

import csv
import io
import json
from collections.abc import Iterable, Sequence
from datetime import date, datetime
from typing import Any, BinaryIO

_PELIGROSOS = ("=", "+", "-", "@", "\t", "\r")


def celda(valor: Any) -> str:
    """Valor de DB -> texto de CSV. Los textos que una planilla ejecutaría como fórmula
    (OWASP CSV injection) se prefijan con ``'``; los números no se tocan."""
    if valor is None:
        return ""
    if isinstance(valor, bool):
        return "true" if valor else "false"
    if isinstance(valor, datetime | date):
        return valor.isoformat()
    if isinstance(valor, dict | list):
        return json.dumps(valor, ensure_ascii=False, sort_keys=True)
    if isinstance(valor, str):
        return "'" + valor if valor.startswith(_PELIGROSOS) else valor
    return str(valor)


def escribir_csv(destino: BinaryIO, columnas: Sequence[str], filas: Iterable[Sequence[Any]]) -> int:
    """Escribe UTF-8 con BOM; devuelve la cantidad de filas de datos. No cierra ``destino``."""
    texto = io.TextIOWrapper(destino, encoding="utf-8-sig", newline="")
    escritor = csv.writer(texto)
    escritor.writerow(columnas)
    n = 0
    for fila in filas:
        escritor.writerow([celda(v) for v in fila])
        n += 1
    texto.flush()
    texto.detach()
    return n
