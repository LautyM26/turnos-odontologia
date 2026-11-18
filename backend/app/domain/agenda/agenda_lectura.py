"""Lectura de la agenda para el staff (C-07 D1/D2): turnos y bloqueos de una ventana.

Solo lectura y siempre scopeado por ``clinica_id``. De cada turno se expone lo mínimo para la
grilla: "Apellido, Nombre" del paciente (dato de contacto, no clínico) y el nombre de la
prestación. Las reglas de rol (odontólogo = solo su agenda) las aplica la ruta.
"""

from datetime import datetime
from typing import Any

from sqlalchemy import and_, func, or_, select
from sqlalchemy.dialects.postgresql import TSTZRANGE
from sqlalchemy.orm import Session

from app.domain.agenda.huecos import validar_ventana
from app.domain.agenda.models import Bloqueo, Prestacion
from app.domain.agenda.turnos import Turno
from app.domain.pacientes.models import Paciente


def turnos_de_ventana(
    session: Session,
    clinica_id: int,
    desde: datetime,
    hasta: datetime,
    profesional_id: int | None = None,
    sillon_id: int | None = None,
) -> list[dict[str, Any]]:
    """Turnos no dados de baja que se superponen con ``[desde, hasta)``, en todos los estados."""
    validar_ventana(desde, hasta)
    ventana = func.tstzrange(desde, hasta, "[)", type_=TSTZRANGE)
    stmt = (
        select(Turno, Paciente.apellido, Paciente.nombre, Prestacion.nombre)
        .join(Paciente, and_(Paciente.id == Turno.paciente_id,
                             Paciente.clinica_id == Turno.clinica_id))
        .join(Prestacion, and_(Prestacion.id == Turno.prestacion_id,
                               Prestacion.clinica_id == Turno.clinica_id))
        .where(
            Turno.clinica_id == clinica_id,
            Turno.is_active.is_(True),
            Turno.rango.op("&&")(ventana),
        )
        .order_by(Turno.inicio, Turno.id)
    )  # fmt: skip
    if profesional_id is not None:
        stmt = stmt.where(Turno.profesional_id == profesional_id)
    if sillon_id is not None:
        stmt = stmt.where(Turno.sillon_id == sillon_id)
    return [
        {
            "id": t.id,
            "profesional_id": t.profesional_id,
            "sillon_id": t.sillon_id,
            "paciente_id": t.paciente_id,
            "paciente_nombre": f"{apellido}, {nombre}",
            "prestacion_id": t.prestacion_id,
            "prestacion_nombre": prestacion,
            "inicio": t.inicio,
            "fin": t.fin,
            "estado": t.estado,
            "origen": t.origen,
            "es_sobreturno": t.es_sobreturno,
            "motivo_sobreturno": t.motivo_sobreturno,
        }  # fmt: skip
        for t, apellido, nombre, prestacion in session.execute(stmt).all()
    ]


def bloqueos_de_ventana(
    session: Session,
    clinica_id: int,
    desde: datetime,
    hasta: datetime,
    profesional_id: int | None = None,
) -> list[dict[str, Any]]:
    """Bloqueos activos de la ventana: de clínica, de sillón y de profesional (o del pedido)."""
    validar_ventana(desde, hasta)
    ventana = func.tstzrange(desde, hasta, "[)", type_=TSTZRANGE)
    de_profesional = (
        Bloqueo.profesional_id.is_not(None)
        if profesional_id is None
        else Bloqueo.profesional_id == profesional_id
    )
    stmt = (
        select(Bloqueo)
        .where(
            Bloqueo.clinica_id == clinica_id,
            Bloqueo.is_active.is_(True),
            Bloqueo.rango.op("&&")(ventana),
            or_(
                and_(Bloqueo.profesional_id.is_(None), Bloqueo.sillon_id.is_(None)),
                Bloqueo.sillon_id.is_not(None),
                de_profesional,
            ),
        )
        .order_by(Bloqueo.inicio, Bloqueo.id)
    )
    salida = []
    for b in session.scalars(stmt).all():
        alcance = "profesional" if b.profesional_id else "sillon" if b.sillon_id else "clinica"
        salida.append(
            {"id": b.id, "alcance": alcance, "profesional_id": b.profesional_id,
             "sillon_id": b.sillon_id, "inicio": b.inicio, "fin": b.fin, "motivo": b.motivo}
        )  # fmt: skip
    return salida
