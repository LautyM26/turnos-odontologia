"""Calculo de fin de turno en servidor (regla dura 6, C-04 D8). Contrato para C-05."""

from datetime import datetime, timedelta

DURACION_MIN = 5
DURACION_MAX = 480


def calcular_fin(inicio: datetime, duracion_min: int) -> datetime:
    """``fin = inicio + duracion_min`` en tiempo absoluto.

    Raises:
        ValueError: ``inicio`` sin zona horaria o ``duracion_min`` fuera de 5..480.
    """
    if inicio.tzinfo is None or inicio.utcoffset() is None:
        raise ValueError("inicio debe incluir zona horaria (datetime aware)")
    if not DURACION_MIN <= duracion_min <= DURACION_MAX:
        raise ValueError(f"duracion_min debe estar entre {DURACION_MIN} y {DURACION_MAX}")
    return inicio + timedelta(minutes=duracion_min)
