"""Helpers sintéticos compartidos por los tests de WhatsApp (C-15). Regla dura 14."""

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from itertools import count

from app.domain.agenda.turnos import Turno
from app.infrastructure.settings import Settings
from tests.integration.conftest import TEST_JWT_SECRET, paciente_sintetico

#: Cada test pide su propio "ahora" (10 días de separación) para no ver turnos de otros tests:
#: el job recorre todas las clínicas y la ventana es de 24 h.
_dias = count(0)
BASE = datetime(2031, 3, 10, 12, tzinfo=UTC)


def nuevo_ahora() -> datetime:
    return BASE + timedelta(days=10 * next(_dias))


def settings_wa(**kw) -> Settings:  # type: ignore[no-untyped-def]
    base = {"jwt_secret_key": TEST_JWT_SECRET, "ars_precio_mensaje": Decimal("12.50"),
            "whatsapp_envios_por_minuto": 20, "whatsapp_max_intentos": 3}  # fmt: skip
    base.update(kw)
    return Settings(_env_file=None, **base)  # type: ignore[call-arg]


def turno_wa(  # type: ignore[no-untyped-def]
    session_factory, td, inicio: datetime, clinica: str = "a", estado: str = "reservado",
    telefono: str | None = "+5491100000001", sillon: str = "s1", prof: str = "p",
) -> tuple[int, int]:
    """Turno + paciente propio (teléfono configurable). Devuelve ``(turno_id, paciente_id)``."""
    c = td[clinica]
    extra = {"telefono": telefono} if telefono else {"telefono": None, "email": "wa@test.test"}
    if clinica == "a":
        refs = {"profesional_id": td[prof], "sillon_id": td[sillon], "prestacion_id": td["prest_a"]}
    else:
        refs = {"profesional_id": td["prof_b"], "sillon_id": td["sillon_b"],
                "prestacion_id": td["prest_b"]}  # fmt: skip
    with session_factory() as session:
        pac = paciente_sintetico(c, **extra)
        session.add(pac)
        session.flush()
        t = Turno(clinica_id=c, paciente_id=pac.id, duracion_min=30, inicio=inicio,
                  fin=inicio + timedelta(minutes=30), estado=estado, **refs)  # fmt: skip
        session.add(t)
        session.commit()
        return t.id, pac.id


_tel = count(1)


def telefono_unico() -> str:
    """Teléfono sintético distinto por test: la respuesta se asocia por número."""
    return f"+54911{next(_tel):08d}"


def recordatorio_enviado(session_factory, td, turno_id: int, paciente_id: int, telefono: str,
                         clinica: str = "a") -> int:  # type: ignore[no-untyped-def]
    """Fila de recordatorio ya enviado (como si hubiera corrido el job)."""
    from uuid import uuid4

    from app.domain.whatsapp.models import MensajeWhatsApp

    with session_factory() as session:
        m = MensajeWhatsApp(
            clinica_id=td[clinica], turno_id=turno_id, paciente_id=paciente_id,
            plantilla="recordatorio_24h", direccion="saliente", telefono=telefono,
            texto="Recordatorio sintetico", estado="enviado", intentos=1,
            id_externo=f"FAKE-{uuid4()}", costo_ars=Decimal("12.50"),
        )  # fmt: skip
        session.add(m)
        session.commit()
        return m.id
