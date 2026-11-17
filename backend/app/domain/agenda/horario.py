"""Horario de atención por profesional (C-05d): franjas semanales en la zona de la clínica.

``SQL_HORARIO_CTE`` es la única definición del horario de un profesional como multirango de
instantes (design D4). La comparten ``buscar_huecos`` y ``crear_turno``, así que todo hueco
devuelto acepta un turno normal. Las franjas contiguas se unen (``range_agg``), y sin franjas el
multirango queda vacío: el profesional no atiende (falla cerrado). La conversión de hora local a
instante la hace PostgreSQL con ``timestamp AT TIME ZONE zona`` (doc PG16 vía Context7), que
aplica la regla de la zona para cada fecha.
"""

from datetime import datetime
from typing import Any

from sqlalchemy import delete, select, text
from sqlalchemy.orm import Session

from app.domain.agenda.models import FranjaHoraria, Profesional
from app.domain.agenda.servicio import NoEncontrado
from app.domain.core.models import Clinica

#: CTE ``horario(m)``: horario de ``:p`` (clínica ``:c``) entre ``:desde`` y ``:hasta``.
#: Las fechas locales arrancan un día antes para cubrir ventanas que cruzan la medianoche.
SQL_HORARIO_CTE = """
horario AS MATERIALIZED (
    SELECT coalesce(range_agg(tstzrange(
               (g.d + make_interval(mins => f.inicio_min)) AT TIME ZONE cl.zona_horaria,
               (g.d + make_interval(mins => f.fin_min)) AT TIME ZONE cl.zona_horaria,
               '[)')),
           '{}'::tstzmultirange) AS m
    FROM clinica cl
    CROSS JOIN LATERAL generate_series(
        date_trunc('day', CAST(:desde AS timestamptz) AT TIME ZONE cl.zona_horaria)
            - interval '1 day',
        date_trunc('day', CAST(:hasta AS timestamptz) AT TIME ZONE cl.zona_horaria),
        interval '1 day'
    ) AS g(d)
    JOIN franja_horaria f
      ON f.clinica_id = cl.id AND f.profesional_id = :p
     AND f.dia_semana = extract(isodow FROM g.d)
    WHERE cl.id = :c
)
"""

_SQL_DENTRO = text(
    f"WITH {SQL_HORARIO_CTE} SELECT tstzrange(:desde, :hasta, '[)') <@ horario.m FROM horario"
)


def dentro_de_horario(
    session: Session, clinica_id: int, profesional_id: int, inicio: datetime, fin: datetime
) -> bool:
    """True si ``[inicio, fin)`` cae completo dentro del horario del profesional."""
    params = {"c": clinica_id, "p": profesional_id, "desde": inicio, "hasta": fin}
    return bool(session.execute(_SQL_DENTRO, params).scalar())


def _franjas(session: Session, clinica_id: int, profesional_id: int) -> list[FranjaHoraria]:
    return list(
        session.scalars(
            select(FranjaHoraria)
            .where(
                FranjaHoraria.clinica_id == clinica_id,
                FranjaHoraria.profesional_id == profesional_id,
            )
            .order_by(FranjaHoraria.dia_semana, FranjaHoraria.inicio_min)
        ).all()
    )


def _salida(session: Session, clinica_id: int, profesional_id: int) -> dict[str, Any]:
    zona = session.scalar(select(Clinica.zona_horaria).where(Clinica.id == clinica_id))
    return {
        "profesional_id": profesional_id,
        "zona_horaria": zona,
        "franjas": _franjas(session, clinica_id, profesional_id),
    }


def _profesional_activo(
    session: Session, clinica_id: int, profesional_id: int, bloquear: bool = False
) -> Profesional:
    stmt = select(Profesional).where(
        Profesional.id == profesional_id,
        Profesional.clinica_id == clinica_id,
        Profesional.is_active.is_(True),
    )
    profesional = session.scalars(stmt.with_for_update() if bloquear else stmt).first()
    if profesional is None:
        raise NoEncontrado("No encontrado")
    return profesional


def obtener_horario(session: Session, clinica_id: int, profesional_id: int) -> dict[str, Any]:
    """Horario del profesional activo del tenant (ajeno/inexistente/baja -> 404)."""
    _profesional_activo(session, clinica_id, profesional_id)
    return _salida(session, clinica_id, profesional_id)


def reemplazar_horario(
    session: Session, clinica_id: int, profesional_id: int, franjas: list[dict[str, int]]
) -> dict[str, Any]:
    """Reemplaza el horario completo en una transacción (D3).

    El ``FOR UPDATE`` sobre el profesional serializa dos PUT concurrentes: sin él, ambos
    borrarían las filas viejas e insertarían las suyas, y quedaría la unión superpuesta.
    ``franjas`` ya viene validada y ordenada (``HorarioIn``).
    """
    _profesional_activo(session, clinica_id, profesional_id, bloquear=True)
    session.execute(
        delete(FranjaHoraria).where(
            FranjaHoraria.clinica_id == clinica_id,
            FranjaHoraria.profesional_id == profesional_id,
        )
    )
    session.add_all(
        FranjaHoraria(
            clinica_id=clinica_id,
            profesional_id=profesional_id,
            dia_semana=f["dia_semana"],
            inicio_min=f["inicio"],
            fin_min=f["fin"],
        )  # fmt: skip
        for f in franjas
    )
    session.commit()
    return _salida(session, clinica_id, profesional_id)
