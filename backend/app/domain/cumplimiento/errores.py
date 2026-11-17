"""Errores de dominio de consentimientos y exportación (C-18, D3 y D5).

Heredan de ``PacienteError``: el handler de ``create_app()`` ya los traduce a HTTP.
"""

from app.domain.pacientes.servicios import PacienteError


class TipoConsentimientoInvalido(PacienteError):
    status_code = 422

    def __init__(self) -> None:
        super().__init__("Tipo de consentimiento fuera del catálogo")


class ConsentimientoNoEncontrado(PacienteError):
    status_code = 404

    def __init__(self) -> None:
        super().__init__("Consentimiento no encontrado")


class FirmaIncompleta(PacienteError):
    """422 reintentable: no se registra constancia y el documento sigue pendiente."""

    status_code = 422

    def __init__(self, faltantes: list[str]) -> None:
        super().__init__(
            "Firma incompleta: completá los datos y reintentá",
            reintentable=True,
            faltantes=faltantes,
        )


class HashNoCoincide(PacienteError):
    status_code = 409

    def __init__(self) -> None:
        super().__init__("El texto mostrado no es el del documento (el hash no coincide)")


class ConsentimientoYaFirmado(PacienteError):
    status_code = 409

    def __init__(self) -> None:
        super().__init__("El consentimiento ya está firmado y bloqueado")


class FormatoNoSoportado(PacienteError):
    status_code = 422

    def __init__(self, formato: str) -> None:
        super().__init__(
            f"Formato no soportado: {formato!r}; el formato disponible es csv", formatos=["csv"]
        )
