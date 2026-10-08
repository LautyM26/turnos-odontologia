"""Consulta de solapamiento de bloqueos: contrato estable para C-05 (design D7)."""

from datetime import datetime

from sqlalchemy import and_, func, or_, select
from sqlalchemy.dialects.postgresql import TSTZRANGE
from sqlalchemy.orm import Session

from app.domain.agenda.models import Bloqueo


def bloqueos_solapados(
    session: Session,
    clinica_id: int,
    inicio: datetime,
    fin: datetime,
    profesional_id: int | None,
    sillon_id: int | None,
) -> list[Bloqueo]:
    """Bloqueos activos de la clinica que se superponen con ``[inicio, fin)``.

    Aplican: bloqueos de toda la clinica, del profesional y del sillon indicados.
    Rangos semiabiertos: un bloqueo ``[12, 13)`` no toca un turno ``[13, 13:30)``.

    Raises:
        ValueError: fechas sin zona horaria o ``fin <= inicio``.
    """
    if inicio.tzinfo is None or fin.tzinfo is None:
        raise ValueError("inicio y fin deben incluir zona horaria")
    if fin <= inicio:
        raise ValueError("fin debe ser posterior a inicio")
    ventana = func.tstzrange(inicio, fin, "[)", type_=TSTZRANGE)
    alcance = [and_(Bloqueo.profesional_id.is_(None), Bloqueo.sillon_id.is_(None))]
    if profesional_id is not None:
        alcance.append(Bloqueo.profesional_id == profesional_id)
    if sillon_id is not None:
        alcance.append(Bloqueo.sillon_id == sillon_id)
    stmt = (
        select(Bloqueo)
        .where(
            Bloqueo.clinica_id == clinica_id,
            Bloqueo.is_active.is_(True),
            Bloqueo.rango.op("&&")(ventana),
            or_(*alcance),
        )
        .order_by(Bloqueo.inicio, Bloqueo.id)
    )
    return list(session.scalars(stmt).all())
