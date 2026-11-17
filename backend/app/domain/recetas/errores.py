"""Errores de dominio de recetas vía partner (C-19, D4). Heredan de ``PacienteError``."""

from app.domain.pacientes.servicios import PacienteError

MAX_MOTIVO = 300


def sanear_motivo(motivo: str, secreto: str | None) -> str:
    """Motivo del partner apto para mostrar: sin la credencial y de a lo sumo 300 caracteres."""
    if secreto:
        motivo = motivo.replace(secreto, "***")
    return motivo[:MAX_MOTIVO]


class PartnerNoConfigurado(PacienteError):
    status_code = 501

    def __init__(self, mensaje: str) -> None:
        super().__init__(mensaje)


class PartnerCaido(PacienteError):
    status_code = 502

    def __init__(self) -> None:
        super().__init__("El partner de recetas no está disponible; reintentá", reintentable=True)


class PartnerRechazoError(PacienteError):
    status_code = 422

    def __init__(self, motivo: str) -> None:
        super().__init__(f"El partner rechazó la receta: {motivo}")


class EvolucionNoValidaParaReceta(PacienteError):
    status_code = 422

    def __init__(self, ajena: bool = False) -> None:
        super().__init__(
            "La receta debe vincularse a una evolución propia"
            if ajena
            else "La evolución no existe para este paciente"
        )


class ClaveIdempotenciaReutilizada(PacienteError):
    status_code = 409

    def __init__(self) -> None:
        super().__init__("La clave de idempotencia ya se usó con otro contenido")


class RecetaNoEncontrada(PacienteError):
    status_code = 404

    def __init__(self) -> None:
        super().__init__("Receta no encontrada")
