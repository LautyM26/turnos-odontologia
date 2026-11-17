"""Servicio de reserva pública (C-06 D3/D4) contra PG16 real. Datos 100 % sintéticos.

``turnos_data``: P y Q atienden 00–24 todos los días, habilitados en S1 y S2; slug de A =
``clinica-piloto`` (seed_core). Cada test usa un día propio de 2033-06.
"""

import hashlib
import itertools
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import func, select

from app.domain.agenda.horario import reemplazar_horario
from app.domain.agenda.models import Profesional, ProfesionalSillon
from app.domain.agenda.reserva_publica import (
    cancelar_por_token,
    catalogo_publico,
    obtener_por_token,
    reservar,
)
from app.domain.agenda.schemas_publicas import ReservaIn
from app.domain.agenda.servicio import Conflicto, NoEncontrado, ReferenciaInvalida
from app.domain.agenda.turnos import Turno, TurnoNoDisponible, TurnoTransicion
from app.domain.auditoria.models import AuditoriaHC
from app.domain.core.models import Usuario
from app.domain.pacientes.models import Paciente

SLUG = "clinica-piloto"
AHORA = datetime(2033, 1, 1, tzinfo=UTC)
_dias = itertools.count(0)
_dnis = itertools.count(40_000_000)


def _dia() -> datetime:
    return datetime(2033, 6, 1, tzinfo=UTC) + timedelta(days=next(_dias))


def _dni() -> str:
    return str(next(_dnis))


def _datos(td, inicio, dni=None, prof=None, **over) -> ReservaIn:  # type: ignore[no-untyped-def]
    base = {
        "profesional_id": prof or td["p"], "prestacion_id": td["prest_a"],
        "inicio": inicio.isoformat(), "dni": dni or _dni(), "nombre": "Ana",
        "apellido": "Sintetica", "email": "ana.reserva@ejemplo.test", "acepta_privacidad": True,
    }  # fmt: skip
    base.update(over)
    return ReservaIn(**base)


def _reservar(session_factory, datos, ahora=AHORA):  # type: ignore[no-untyped-def]
    with session_factory() as session:
        return reservar(session, SLUG, datos, ahora)


def _turno(session_factory, token: str) -> Turno:  # type: ignore[no-untyped-def]
    digest = hashlib.sha256(token.encode()).hexdigest()
    with session_factory() as session:
        return session.scalars(select(Turno).where(Turno.token_publico_hash == digest)).one()


def test_paciente_nuevo_reserva_sin_usuario_y_auditado(session_factory, turnos_data) -> None:  # type: ignore[no-untyped-def]
    td, dni = turnos_data, _dni()
    with session_factory() as session:
        usuarios_antes = session.scalar(select(func.count()).select_from(Usuario))
    comprobante, token = _reservar(session_factory, _datos(td, _dia().replace(hour=10), dni))
    assert comprobante["estado"] == "reservado" and comprobante["cancelable"] is True
    assert "dni" not in comprobante and "nombre_paciente" not in comprobante
    turno = _turno(session_factory, token)
    assert turno.origen == "enlace"
    assert turno.token_publico_hash != token and len(token) >= 40
    with session_factory() as session:
        paciente = session.scalars(select(Paciente).where(Paciente.dni == dni)).one()
        assert paciente.id == turno.paciente_id and paciente.consentimiento_datos is False
        assert session.scalar(select(func.count()).select_from(Usuario)) == usuarios_antes
        evento = session.scalars(
            select(AuditoriaHC).where(AuditoriaHC.paciente_id == paciente.id)
        ).one()
        assert (evento.actor_tipo, evento.actor_usuario_id, evento.accion) == (
            "sistema", None, "crear",
        )  # fmt: skip


def test_dni_existente_no_modifica_la_ficha(session_factory, turnos_data) -> None:  # type: ignore[no-untyped-def]
    td = turnos_data
    with session_factory() as session:
        antes = session.get(Paciente, td["pac_a"])
        dni, tel, email = antes.dni, antes.telefono, antes.email
    datos = _datos(
        td, _dia().replace(hour=10), dni, email=None, telefono="+5491199999999", nombre="Otro"
    )
    _, token = _reservar(session_factory, datos)
    assert _turno(session_factory, token).paciente_id == td["pac_a"]
    with session_factory() as session:
        despues = session.get(Paciente, td["pac_a"])
        assert (despues.telefono, despues.email, despues.nombre) == (tel, email, antes.nombre)


def test_paciente_dado_de_baja_422(session_factory, turnos_data) -> None:  # type: ignore[no-untyped-def]
    with session_factory() as session:
        dni = session.get(Paciente, turnos_data["pac_a_inactivo"]).dni
    with pytest.raises(ReferenciaInvalida):
        _reservar(session_factory, _datos(turnos_data, _dia().replace(hour=10), dni))


def test_tope_de_dos_reservas_por_dni_y_cancelada_libera(session_factory, turnos_data) -> None:  # type: ignore[no-untyped-def]
    td, dni, dia = turnos_data, _dni(), _dia()
    _, token1 = _reservar(session_factory, _datos(td, dia.replace(hour=9), dni))
    _reservar(session_factory, _datos(td, dia.replace(hour=11), dni))
    with pytest.raises(Conflicto, match="Límite"):
        _reservar(session_factory, _datos(td, dia.replace(hour=13), dni))
    with session_factory() as session:
        cancelar_por_token(session, token1, AHORA)
    _reservar(session_factory, _datos(td, dia.replace(hour=13), dni))


def test_segundo_sillon_libre(session_factory, turnos_data) -> None:  # type: ignore[no-untyped-def]
    td, inicio = turnos_data, _dia().replace(hour=10)
    with session_factory() as session:
        session.add(
            Turno(
                clinica_id=td["a"], profesional_id=td["q"], sillon_id=td["s1"],
                paciente_id=td["pac_a"], prestacion_id=td["prest_a"], duracion_min=30,
                inicio=inicio, fin=inicio + timedelta(minutes=30),
            )
        )  # fmt: skip
        session.commit()
    _, token = _reservar(session_factory, _datos(td, inicio))
    assert _turno(session_factory, token).sillon_id == td["s2"]


def test_profesional_ocupado_en_todos_los_sillones_409(session_factory, turnos_data) -> None:  # type: ignore[no-untyped-def]
    td, inicio = turnos_data, _dia().replace(hour=10)
    _reservar(session_factory, _datos(td, inicio))
    with pytest.raises(TurnoNoDisponible):
        _reservar(session_factory, _datos(td, inicio))


@pytest.fixture(scope="module")
def prof_horario(session_factory, turnos_data):  # type: ignore[no-untyped-def]
    """Profesional con horario lunes 09–13 (local) y otro sin horario, ambos en S1."""
    td, ids = turnos_data, []
    with session_factory() as session:
        for matricula in ("FIX-RP1", "FIX-RP2"):
            prof = Profesional(clinica_id=td["a"], nombre=f"Prof {matricula}", matricula=matricula)
            session.add(prof)
            session.flush()
            session.add(
                ProfesionalSillon(clinica_id=td["a"], profesional_id=prof.id, sillon_id=td["s1"])
            )
            ids.append(prof.id)
        session.commit()
    with session_factory() as session:
        reemplazar_horario(session, td["a"], ids[0], [{"dia_semana": 1, "inicio": 540, "fin": 780}])
    return {"con": ids[0], "sin": ids[1]}


def test_catalogo_solo_lista_profesionales_con_horario(session_factory, prof_horario) -> None:  # type: ignore[no-untyped-def]
    with session_factory() as session:
        cat = catalogo_publico(session, SLUG)
    ids = {p["id"] for p in cat["profesionales"]}
    assert prof_horario["con"] in ids and prof_horario["sin"] not in ids
    assert cat["zona_horaria"] == "America/Argentina/Buenos_Aires"
    assert all(set(p) == {"id", "nombre", "duracion_min"} for p in cat["prestaciones"])


def test_slug_inexistente_404(session_factory) -> None:  # type: ignore[no-untyped-def]
    with session_factory() as session, pytest.raises(NoEncontrado):
        catalogo_publico(session, "no-existe")


def test_fuera_de_horario_409_y_sin_horario_422(session_factory, turnos_data, prof_horario) -> None:  # type: ignore[no-untyped-def]
    lunes = datetime(2033, 6, 6, tzinfo=UTC)  # lunes
    assert lunes.isoweekday() == 1
    tarde = lunes + timedelta(hours=18)  # 15:00 local, fuera de 09–13
    with pytest.raises(TurnoNoDisponible):
        _reservar(session_factory, _datos(turnos_data, tarde, prof=prof_horario["con"]))
    with pytest.raises(ReferenciaInvalida):
        _reservar(session_factory, _datos(turnos_data, lunes + timedelta(hours=13),
                                          prof=prof_horario["sin"]))  # fmt: skip


def test_no_reserva_en_el_pasado_422(session_factory, turnos_data) -> None:  # type: ignore[no-untyped-def]
    with pytest.raises(ReferenciaInvalida):
        _reservar(session_factory, _datos(turnos_data, AHORA - timedelta(days=1)))


def test_consulta_y_cancelacion_con_token(session_factory, turnos_data) -> None:  # type: ignore[no-untyped-def]
    inicio = _dia().replace(hour=10)
    _, token = _reservar(session_factory, _datos(turnos_data, inicio))
    with session_factory() as session:
        vista = obtener_por_token(session, token, AHORA)
        assert vista["inicio"] == inicio and vista["estado"] == "reservado"
        cancelado = cancelar_por_token(session, token, AHORA)
        assert cancelado["estado"] == "cancelado" and cancelado["cancelable"] is False
    turno = _turno(session_factory, token)
    with session_factory() as session:
        tr = session.scalars(
            select(TurnoTransicion).where(TurnoTransicion.turno_id == turno.id)
        ).one()
        assert (tr.desde, tr.hacia, tr.actor_tipo, tr.actor_usuario_id) == (
            "reservado", "cancelado", "paciente_enlace", None,
        )  # fmt: skip
    # el hueco se liberó: otra persona puede reservarlo
    _reservar(session_factory, _datos(turnos_data, inicio))


def test_cancelar_despues_del_inicio_422(session_factory, turnos_data) -> None:  # type: ignore[no-untyped-def]
    inicio = _dia().replace(hour=10)
    _, token = _reservar(session_factory, _datos(turnos_data, inicio))
    with session_factory() as session, pytest.raises(ReferenciaInvalida):
        cancelar_por_token(session, token, inicio + timedelta(minutes=1))
    assert _turno(session_factory, token).estado == "reservado"


def test_cancelar_dos_veces_422(session_factory, turnos_data) -> None:  # type: ignore[no-untyped-def]
    _, token = _reservar(session_factory, _datos(turnos_data, _dia().replace(hour=10)))
    with session_factory() as session:
        cancelar_por_token(session, token, AHORA)
    with session_factory() as session, pytest.raises(ReferenciaInvalida):
        cancelar_por_token(session, token, AHORA)


def test_token_invalido_404(session_factory) -> None:  # type: ignore[no-untyped-def]
    with session_factory() as session:
        with pytest.raises(NoEncontrado):
            obtener_por_token(session, "token-que-no-existe", AHORA)
        with pytest.raises(NoEncontrado):
            cancelar_por_token(session, "token-que-no-existe", AHORA)
