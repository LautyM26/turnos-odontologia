"""Errores de dominio de administración de usuarios (C-18, D6).

Heredan de ``PacienteError``: el handler de ``create_app()`` ya los traduce a HTTP.
"""

from app.domain.pacientes.servicios import PacienteError


class UsuarioDuplicado(PacienteError):
    status_code = 409

    def __init__(self) -> None:
        super().__init__("Ya existe un usuario con ese email en la clínica")


class UsuarioNoEncontrado(PacienteError):
    status_code = 404

    def __init__(self) -> None:
        super().__init__("Usuario no encontrado")


class UltimoAdmin(PacienteError):
    status_code = 409

    def __init__(self) -> None:
        super().__init__("La clínica no puede quedar sin ningún administrador activo")
