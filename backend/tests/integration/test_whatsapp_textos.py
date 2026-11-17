"""Render de textos base con hora local de la clínica (C-15 4.2, D4). PG16 real, sintético."""

from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import update

from app.domain.agenda.turnos import Turno
from app.domain.whatsapp.models import PlantillaWA
from app.domain.whatsapp.servicios import TextoIncompleto, renderizar


def _turno(session_factory, td, hora: int = 10) -> int:  # type: ignore[no-untyped-def]
    inicio = datetime(2031, 3, 11, hora, tzinfo=UTC)
    with session_factory() as session:
        t = Turno(
            clinica_id=td["a"], profesional_id=td["p"], sillon_id=td["s1"],
            paciente_id=td["pac_a"], prestacion_id=td["prest_a"], duracion_min=30,
            inicio=inicio, fin=inicio + timedelta(minutes=30),
        )  # fmt: skip
        session.add(t)
        session.commit()
        return t.id


def test_recordatorio_con_hora_local_y_opciones(session_factory, turnos_data) -> None:  # type: ignore[no-untyped-def]
    tid = _turno(session_factory, turnos_data)
    with session_factory() as session:
        texto = renderizar(session, turnos_data["a"], "recordatorio_24h", tid)
    # Clínica en America/Argentina/Buenos_Aires (UTC-3): 10:00 UTC -> 07:00.
    assert "11/03" in texto and "07:00" in texto
    assert "Profesional P Sintetico" in texto and "Paciente" in texto
    for opcion in ("1 para confirmar", "2 para cancelar", "3 para reprogramar"):
        assert opcion in texto
    assert "{" not in texto


def test_variable_faltante_es_error(session_factory, turnos_data) -> None:  # type: ignore[no-untyped-def]
    tid = _turno(session_factory, turnos_data, hora=12)
    with session_factory() as session:
        session.execute(
            update(PlantillaWA)
            .where(PlantillaWA.clave == "confirmacion")
            .values(texto="Hola {paciente_nombre}, {variable_inexistente}")
        )
        with pytest.raises(TextoIncompleto):
            renderizar(session, turnos_data["a"], "confirmacion", tid)
        session.rollback()  # el texto base no queda modificado
