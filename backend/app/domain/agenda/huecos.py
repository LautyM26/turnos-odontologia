"""Huecos libres de un profesional para una prestación (C-05c, design D1/D5, Flujo 1).

Un hueco es un inicio donde un ``POST /api/turnos`` normal respondería 201: dentro del horario
de atención (C-05d), profesional libre, al menos un sillón habilitado libre, sin bloqueos y no
en el pasado. Lo calcula PostgreSQL en
una sola consulta con multirangos (``range_agg`` y diferencia de ``tstzmultirange``, PG16 vía
Context7): misma semántica semiabierta ``[inicio, fin)`` que las exclusion constraints.
"""

from datetime import datetime, timedelta
from typing import Any

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.domain.agenda.duracion import calcular_fin
from app.domain.agenda.horario import SQL_HORARIO_CTE
from app.domain.agenda.models import Prestacion, Profesional
from app.domain.agenda.servicio import ReferenciaInvalida
from app.infrastructure.persistence.repository import BaseRepository

VENTANA_MAXIMA = timedelta(days=7)

#: Turnos que ocupan un recurso: mismo predicado que las exclusion constraints (migración 011).
_TURNO_OCUPA = (
    "t.clinica_id = :c AND t.is_active AND NOT t.es_sobreturno "
    "AND t.estado IN ('reservado','confirmado','asistido') AND t.rango && v.r"
)
_BLOQUEO_APLICA = "b.clinica_id = :c AND b.is_active AND b.rango && v.r"
_DE_CLINICA = "(b.profesional_id IS NULL AND b.sillon_id IS NULL)"

_SQL_HUECOS = text(f"""
WITH v AS (SELECT tstzrange(:desde, :hasta, '[)') AS r),
{SQL_HORARIO_CTE},
libre_prof AS MATERIALIZED (
    SELECT (tstzmultirange(v.r) * horario.m) - coalesce(
        (SELECT range_agg(x.rango) FROM (
            SELECT t.rango FROM turno t WHERE {_TURNO_OCUPA} AND t.profesional_id = :p
            UNION ALL
            SELECT b.rango FROM bloqueo b
            WHERE {_BLOQUEO_APLICA} AND (b.profesional_id = :p OR {_DE_CLINICA})
        ) x),
        '{{}}'::tstzmultirange) AS m
    FROM v, horario
),
libre_sillon AS MATERIALIZED (
    SELECT s.id, tstzmultirange(v.r) - coalesce(
        (SELECT range_agg(y.rango) FROM (
            SELECT t.rango FROM turno t WHERE {_TURNO_OCUPA} AND t.sillon_id = s.id
            UNION ALL
            SELECT b.rango FROM bloqueo b
            WHERE {_BLOQUEO_APLICA} AND (b.sillon_id = s.id OR {_DE_CLINICA})
        ) y),
        '{{}}'::tstzmultirange) AS m
    FROM v, profesional_sillon ps
    JOIN sillon_recurso s ON s.clinica_id = ps.clinica_id AND s.id = ps.sillon_id
    WHERE ps.clinica_id = :c AND ps.profesional_id = :p AND ps.is_active AND s.is_active
),
cand AS (
    SELECT g AS ini, tstzrange(g, g + make_interval(mins => :dur), '[)') AS r
    FROM generate_series(
        CAST(:desde AS timestamptz),
        CAST(:hasta AS timestamptz) - make_interval(mins => :dur),
        make_interval(mins => :paso)
    ) g
    WHERE g >= :ahora
)
SELECT cand.ini, array_agg(ls.id ORDER BY ls.id) AS sillon_ids
FROM cand, libre_prof lp, libre_sillon ls
WHERE cand.r <@ lp.m AND cand.r <@ ls.m
GROUP BY cand.ini
ORDER BY cand.ini
""")


def validar_ventana(desde: datetime, hasta: datetime) -> None:
    """Ventana de agenda válida: con zona, ``hasta > desde`` y a lo sumo 7 días (422 si no)."""
    if desde.tzinfo is None or hasta.tzinfo is None:
        raise ReferenciaInvalida("desde y hasta deben incluir zona horaria")
    if hasta <= desde:
        raise ReferenciaInvalida("hasta debe ser posterior a desde")
    if hasta - desde > VENTANA_MAXIMA:
        raise ReferenciaInvalida("La ventana de búsqueda no puede superar 7 días")


def buscar_huecos(
    session: Session,
    clinica_id: int,
    profesional_id: int,
    prestacion_id: int,
    desde: datetime,
    hasta: datetime,
    ahora: datetime,
    paso_min: int,
) -> list[dict[str, Any]]:
    """Inicios ``desde + k·paso`` libres para un turno normal de la prestación (D1/D5).

    422 (``ReferenciaInvalida``): fechas sin zona, ``hasta <= desde``, ventana > 7 días,
    profesional inexistente/inactivo/sin agenda o de otra clínica, prestación inactiva o ajena.
    """
    validar_ventana(desde, hasta)
    profesional = BaseRepository(session, Profesional, clinica_id).get(profesional_id)
    if profesional is None or not profesional.agenda_activa:
        raise ReferenciaInvalida("profesional_id inexistente, inactivo o sin agenda activa")
    prestacion = BaseRepository(session, Prestacion, clinica_id).get(prestacion_id)
    if prestacion is None:
        raise ReferenciaInvalida("prestacion_id inexistente, inactiva o de otra clinica")
    dur = prestacion.duracion_min
    filas = session.execute(
        _SQL_HUECOS,
        {"c": clinica_id, "p": profesional_id, "desde": desde, "hasta": hasta,
         "ahora": ahora, "dur": dur, "paso": paso_min},
    ).all()  # fmt: skip
    return [
        {"inicio": ini, "fin": calcular_fin(ini, dur), "sillon_ids": list(sillones)}
        for ini, sillones in filas
    ]
