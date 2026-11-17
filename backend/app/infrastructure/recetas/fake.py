"""Partner simulado (C-19, D1): solo desarrollo, demo y tests; nunca en producción."""

from uuid import NAMESPACE_URL, uuid5

from app.infrastructure.recetas.partner_client import EmisionPartner, SolicitudPartner


class FakePartner:
    nombre = "fake"
    simulado = True

    def __init__(self) -> None:
        self.solicitudes: list[SolicitudPartner] = []
        self._error: Exception | None = None

    def fallar_con(self, error: Exception | None) -> None:
        """Hook de tests: la próxima ``emitir`` (y las siguientes) levanta ``error``."""
        self._error = error

    def emitir(self, solicitud: SolicitudPartner) -> EmisionPartner:
        if self._error is not None:
            raise self._error
        self.solicitudes.append(solicitud)
        id_externo = f"FAKE-{uuid5(NAMESPACE_URL, str(solicitud.clave_idempotencia))}"
        # .invalid (RFC 2606) nunca resuelve: un enlace simulado no puede confundirse con real.
        return EmisionPartner(
            id_externo=id_externo,
            pdf_url=f"https://partner-simulado.invalid/recetas/{id_externo}.pdf",
        )
