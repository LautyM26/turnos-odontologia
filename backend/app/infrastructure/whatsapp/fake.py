"""Gateway simulado (C-15 D1): solo desarrollo, demo y tests; nunca en producción."""

from uuid import uuid4

from app.infrastructure.whatsapp.puerto import EstadoSesion, SesionNoActiva

#: PNG 1x1 transparente: un QR simulado no puede vincular ningún teléfono.
QR_SIMULADO = (
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNkYAAAAAYAAjCB0C8AAAAASUVORK5CYII="
)


class FakeMensajeria:
    nombre = "fake"
    simulado = True

    def __init__(self) -> None:
        self.enviados: list[tuple[str, str, str]] = []
        self.iniciadas: list[tuple[str, str, str | None]] = []
        self.estado_sesion = "activa"
        self._error: Exception | None = None

    def fallar_con(self, error: Exception | None) -> None:
        """Hook de tests: los envíos siguientes levantan ``error`` (``None`` lo apaga)."""
        self._error = error

    def enviar_texto(self, sesion: str, telefono: str, texto: str) -> str:
        if self._error is not None:
            raise self._error
        if self.estado_sesion != "activa":
            raise SesionNoActiva(f"sesión {self.estado_sesion}")
        self.enviados.append((sesion, telefono, texto))
        return f"FAKE-{uuid4()}"

    def estado(self, sesion: str) -> EstadoSesion:
        numero = "+5491100009999" if self.estado_sesion == "activa" else None
        return EstadoSesion(self.estado_sesion, numero)

    def qr(self, sesion: str) -> str | None:
        return QR_SIMULADO if self.estado_sesion == "escanear_qr" else None

    def iniciar(self, sesion: str, webhook_url: str, hmac_key: str | None) -> EstadoSesion:
        self.iniciadas.append((sesion, webhook_url, hmac_key))
        self.estado_sesion = "escanear_qr"
        return self.estado(sesion)
