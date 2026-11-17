"""Errores de dominio de odontograma y evoluciones (C-09, D6).

Heredan de ``PacienteError``: el handler de ``create_app()`` ya los traduce a HTTP.
"""

from app.domain.pacientes.servicios import PacienteError


class AutorProfesionalRequerido(PacienteError):
    status_code = 422

    def __init__(self) -> None:
        super().__init__("Se requiere un profesional activo vinculado al usuario como autor")


class VersionOdontogramaConflicto(PacienteError):
    status_code = 409

    def __init__(self) -> None:
        super().__init__("El odontograma cambió: la versión esperada no coincide con la vigente")


class EvolucionYaCorregida(PacienteError):
    status_code = 409

    def __init__(self, vigente_id: int) -> None:
        super().__init__(
            f"La evolución ya fue corregida: corregí la versión vigente (evolución {vigente_id})",
            evolucion_vigente_id=vigente_id,
        )


class CorreccionNoAutorizada(PacienteError):
    status_code = 403

    def __init__(self) -> None:
        super().__init__("Solo el autor puede corregir su evolución")


class CorreccionInvalida(PacienteError):
    status_code = 422

    def __init__(self) -> None:
        super().__init__("La evolución a corregir no existe para este paciente")


class EvolucionNoEncontrada(PacienteError):
    status_code = 404

    def __init__(self) -> None:
        super().__init__("Evolución no encontrada")
