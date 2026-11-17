"""Catálogos FDI y de estados del odontograma (C-09, RN-CL-03, DC-3). Puro, sin DB.

Piezas FDI: permanentes = cuadrantes 1–4 con piezas 1–8 (32); temporales = cuadrantes 5–8
con piezas 1–5 (20). ``mixta`` es la unión de ambos sets (DC-4); lo "fino" (recambio,
erupción) es F2.
"""

PERMANENTES: frozenset[int] = frozenset(c * 10 + p for c in range(1, 5) for p in range(1, 9))
TEMPORALES: frozenset[int] = frozenset(c * 10 + p for c in range(5, 9) for p in range(1, 6))

DENTICIONES = ("permanente", "temporal", "mixta")
MAX_PIEZAS = len(PERMANENTES | TEMPORALES)

#: Caras de la pieza; ``O`` = oclusal/incisal.
CARAS = ("V", "L", "M", "D", "O")
ESTADOS_PIEZA = ("ausente", "extraida", "extraccion_indicada", "corona", "endodoncia", "implante")
ESTADOS_CARA = ("caries", "obturacion", "sellador", "fractura")
#: Estados de pieza que no admiten marcas por cara.
PIEZA_SIN_CARAS = ("ausente", "extraida")
REGISTROS = ("existente", "a_realizar")


def piezas_validas(denticion: str) -> frozenset[int]:
    """Códigos FDI permitidos para la dentición declarada."""
    if denticion == "permanente":
        return PERMANENTES
    if denticion == "temporal":
        return TEMPORALES
    if denticion == "mixta":
        return PERMANENTES | TEMPORALES
    raise ValueError(f"Dentición desconocida: {denticion!r}")


def es_pieza_fdi(pieza: int) -> bool:
    """¿Es un código FDI válido de cualquiera de los dos sets?"""
    return pieza in PERMANENTES or pieza in TEMPORALES
