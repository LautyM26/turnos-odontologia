"""Aislamiento por clínica de mensajes y sesiones de WhatsApp (C-15 2.2, regla dura 10)."""

from sqlalchemy import select

from app.domain.whatsapp.models import MensajeWhatsApp, WhatsappSesion, nombre_sesion
from app.infrastructure.persistence.repository import BaseRepository


def test_consulta_scoped_de_otra_clinica_da_0_filas(session_factory, turnos_data) -> None:  # type: ignore[no-untyped-def]
    a, b = turnos_data["a"], turnos_data["b"]
    with session_factory() as session:
        session.add(WhatsappSesion(clinica_id=a, nombre=nombre_sesion(a), estado="activa"))
        session.add(
            MensajeWhatsApp(
                clinica_id=a, paciente_id=turnos_data["pac_a"], direccion="entrante",
                telefono="+5491100000001", texto="hola", estado="recibido",
                intencion="desconocida", id_externo="FAKE-aisl-1", requiere_atencion=True,
            )
        )  # fmt: skip
        session.commit()

        assert len(BaseRepository(session, MensajeWhatsApp, a).list()) == 1
        assert BaseRepository(session, MensajeWhatsApp, b).list() == []
        sesiones_b = session.scalars(
            select(WhatsappSesion).where(WhatsappSesion.clinica_id == b)
        ).all()
        assert sesiones_b == []
