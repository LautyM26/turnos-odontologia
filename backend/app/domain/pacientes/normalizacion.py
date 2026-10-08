"""Normalización pura de identificadores de paciente (C-08, D3). Sin DB."""

import re
import unicodedata

import phonenumbers

_DNI_RE = re.compile(r"^[0-9]{7,8}$")
_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


class NormalizacionError(ValueError):
    """Valor de identificador no normalizable."""


def normalizar_dni(valor: str) -> str:
    """Quita puntos, espacios y guiones; exige 7-8 dígitos."""
    limpio = re.sub(r"[.\s-]", "", valor)
    if not _DNI_RE.fullmatch(limpio):
        raise NormalizacionError("DNI inválido: se esperan 7 u 8 dígitos")
    return limpio


def normalizar_email(valor: str) -> str:
    """Minúsculas sin espacios; formato básico validado."""
    limpio = valor.strip().lower()
    if len(limpio) > 320 or not _EMAIL_RE.fullmatch(limpio):
        raise NormalizacionError("Email inválido")
    return limpio


def normalizar_telefono(valor: str) -> str:
    """Teléfono argentino a E.164 (el ``15`` local se convierte al ``9`` móvil)."""
    try:
        numero = phonenumbers.parse(valor.strip(), "AR")
    except phonenumbers.NumberParseException as exc:
        raise NormalizacionError("Teléfono inválido") from exc
    if not phonenumbers.is_possible_number(numero):
        raise NormalizacionError("Teléfono inválido")
    return phonenumbers.format_number(numero, phonenumbers.PhoneNumberFormat.E164)


def normalizar_texto(valor: str) -> str:
    """Minúsculas sin marcas diacríticas y con espacios colapsados."""
    crudo = unicodedata.normalize("NFKD", valor)
    sin_marcas = "".join(c for c in crudo if not unicodedata.combining(c))
    return " ".join(sin_marcas.lower().split())


def nombre_busqueda(apellido: str, nombre: str) -> str:
    """``"apellido nombre"`` en minúsculas y sin marcas diacríticas."""
    return normalizar_texto(f"{apellido} {nombre}")
