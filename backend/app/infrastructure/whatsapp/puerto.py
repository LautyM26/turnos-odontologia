"""Puerto de mensajería WhatsApp (C-15 D1, DD-10; ``MensajeriaPort`` en la KB).

El dominio solo conoce este puerto: migrar a la plataforma oficial de Meta en F2 = un adapter
nuevo + un valor de ``WHATSAPP_GATEWAY``. Sin gateway configurado nada se envía
(``NoConfigurado``): la API arranca igual y los recordatorios quedan en la bandeja.
"""

from dataclasses import dataclass
from typing import Protocol


class GatewayNoDisponible(Exception):
    """Timeout, 5xx o conexión caída: se reintenta en una corrida posterior."""


class SesionNoActiva(Exception):
    """La sesión QR no está vinculada/activa o el número está bloqueado."""


@dataclass(frozen=True)
class NoConfigurado:
    """Resultado de la factory cuando no hay gateway utilizable (nunca una excepción)."""

    mensaje: str


@dataclass(frozen=True)
class EstadoSesion:
    #: desconocido | iniciando | escanear_qr | activa | caida | detenida
    estado: str
    numero: str | None = None


class Mensajeria(Protocol):
    nombre: str
    simulado: bool

    def enviar_texto(self, sesion: str, telefono: str, texto: str) -> str:
        """Envía ``texto`` al ``telefono`` E.164; devuelve el id externo del mensaje."""
        ...

    def estado(self, sesion: str) -> EstadoSesion: ...

    def qr(self, sesion: str) -> str | None:
        """QR en base64 (PNG) si la sesión espera escaneo; si no, ``None``."""
        ...

    def iniciar(self, sesion: str, webhook_url: str, hmac_key: str | None) -> EstadoSesion:
        """Crea o reinicia la sesión con el webhook firmado hacia el sistema."""
        ...
