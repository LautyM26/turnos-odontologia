"""Validador CUIT argentino offline, algoritmo módulo 11 (C-02, D7)."""

import re

_PESOS = (5, 4, 3, 2, 7, 6, 5, 4, 3, 2)
_SOLO_DIGITOS = re.compile(r"\D")


def normalizar_cuit(cuit: str) -> str:
    """Strip guiones/espacios; exige exactamente 11 dígitos.

    Raises:
        ValueError: si el valor no normaliza a 11 dígitos.
    """
    digitos = _SOLO_DIGITOS.sub("", cuit)
    if len(digitos) != 11 or not digitos.isdigit():
        raise ValueError(f"CUIT debe tener 11 dígitos, recibido: {cuit!r}")
    return digitos


def validar_cuit(cuit: str) -> bool:
    """Retorna True si el dígito verificador (módulo 11) es correcto."""
    try:
        digitos = normalizar_cuit(cuit)
    except ValueError:
        return False
    suma = sum(int(d) * p for d, p in zip(digitos[:10], _PESOS, strict=True))
    resto = suma % 11
    esperado = 11 - resto
    if esperado == 11:
        esperado = 0
    elif esperado == 10:
        esperado = 9
    return int(digitos[10]) == esperado
