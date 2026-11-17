"""Hash del texto exacto de un consentimiento (C-18, D2): sin normalizar."""

import hashlib


def sha256_hex(texto: str) -> str:
    """SHA-256 en hexadecimal de los bytes UTF-8 del texto, tal cual (espacios y tildes cuentan)."""
    return hashlib.sha256(texto.encode("utf-8")).hexdigest()
