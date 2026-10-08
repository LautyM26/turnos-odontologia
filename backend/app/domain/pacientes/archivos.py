"""Tipos de adjunto por firma de bytes y saneo de nombres (C-08, D9). Funciones puras."""

import re

_FIRMAS: tuple[tuple[bytes, str, str], ...] = (
    (b"\xff\xd8\xff", "foto", "image/jpeg"),
    (b"\x89PNG\r\n\x1a\n", "foto", "image/png"),
    (b"%PDF-", "pdf", "application/pdf"),
)

#: Bytes iniciales que hay que leer para decidir el tipo.
LARGO_CABECERA = 8


class TipoNoPermitido(ValueError):
    """Contenido fuera de JPEG/PNG/PDF o content-type declarado que no coincide (415)."""


def detectar_tipo(cabecera: bytes, declarado: str | None = None) -> tuple[str, str]:
    """``(tipo, mime)`` según la firma real; ``declarado`` (si viene) debe coincidir."""
    for firma, tipo, mime in _FIRMAS:
        if cabecera.startswith(firma):
            if declarado is not None:
                base = declarado.split(";", 1)[0].strip().lower()
                if base != mime:
                    raise TipoNoPermitido("El content-type declarado no coincide con el archivo")
            return tipo, mime
    raise TipoNoPermitido("Solo se admiten JPEG, PNG o PDF")


def sanear_nombre(nombre: str | None) -> str | None:
    """Basename sin caracteres de control, <= 255; solo para mostrar (nunca para rutas)."""
    if not nombre:
        return None
    base = re.split(r"[\\/]", nombre)[-1]
    limpio = "".join(c for c in base if c.isprintable()).strip()
    if not limpio or limpio in {".", ".."}:
        return None
    return limpio[-255:]
