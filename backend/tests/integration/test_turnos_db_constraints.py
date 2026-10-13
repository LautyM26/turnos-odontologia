"""Anti-solapamiento en la capa de persistencia (regla dura 8), por SQL directo sin servicio.

PG16 real; fechas futuras 2031 y datos 100 % sintéticos (reglas duras 9 y 14).
"""

from datetime import UTC, datetime

import pytest
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError, IntegrityError

from app.domain.agenda.turnos import Turno
from app.infrastructure.persistence.repository import BaseRepository

SQL_INSERT = (
    "INSERT INTO turno (clinica_id, profesional_id, sillon_id, paciente_id, prestacion_id, "
    "duracion_min, inicio, fin, estado, origen, is_active) "
    "VALUES (:c, :p, :s, :pac, :pre, :dur, :ini, :fin, :est, :ori, :act) RETURNING id"
)


def _t(dia: int, h: int, m: int = 0) -> datetime:
    return datetime(2031, 5, dia, h, m, tzinfo=UTC)


def _a(td, **over):  # type: ignore[no-untyped-def]
    """Parámetros por defecto de un turno de la clínica A (P en S1)."""
    base = {
        "c": td["a"], "p": td["p"], "s": td["s1"], "pac": td["pac_a"], "pre": td["prest_a"],
        "dur": 30, "ini": _t(1, 10), "fin": _t(1, 10, 30), "est": "reservado",
        "ori": "mostrador", "act": True,
    }  # fmt: skip
    base.update(over)
    return base


def _ok(session_factory, **params):  # type: ignore[no-untyped-def]
    with session_factory() as session:
        value = session.execute(text(SQL_INSERT), params).scalar()
        session.commit()
        return value


def _falla(session_factory, sqlstate: str, **params) -> None:  # type: ignore[no-untyped-def]
    with session_factory() as session:
        with pytest.raises(IntegrityError) as exc:
            session.execute(text(SQL_INSERT), params)
        session.rollback()
    assert exc.value.orig.sqlstate == sqlstate


def test_superpuesto_por_profesional_en_otro_sillon_23P01(session_factory, turnos_data) -> None:  # type: ignore[no-untyped-def]
    td = turnos_data
    _ok(session_factory, **_a(td, ini=_t(2, 10), fin=_t(2, 10, 30)))
    _falla(session_factory, "23P01", **_a(td, s=td["s2"], ini=_t(2, 10, 15), fin=_t(2, 10, 45)))
    # triangulación: mismo rango exacto en otro sillón y contenido dentro del otro
    _falla(session_factory, "23P01", **_a(td, s=td["s2"], ini=_t(2, 10), fin=_t(2, 10, 30)))
    _falla(session_factory, "23P01", **_a(td, s=td["s2"], ini=_t(2, 10, 5), fin=_t(2, 10, 20)))


def test_superpuesto_por_sillon_con_otro_profesional_23P01(session_factory, turnos_data) -> None:  # type: ignore[no-untyped-def]
    td = turnos_data
    _ok(session_factory, **_a(td, ini=_t(3, 10), fin=_t(3, 10, 30)))
    _falla(session_factory, "23P01", **_a(td, p=td["q"], ini=_t(3, 10), fin=_t(3, 10, 30)))
    _falla(session_factory, "23P01", **_a(td, p=td["q"], ini=_t(3, 9, 45), fin=_t(3, 10, 15)))


def test_turnos_contiguos_no_se_superponen(session_factory, turnos_data) -> None:  # type: ignore[no-untyped-def]
    td = turnos_data
    _ok(session_factory, **_a(td, ini=_t(4, 10), fin=_t(4, 10, 30)))
    _ok(session_factory, **_a(td, ini=_t(4, 10, 30), fin=_t(4, 11)))  # empieza donde termina
    _ok(session_factory, **_a(td, ini=_t(4, 9, 30), fin=_t(4, 10)))  # termina donde empieza


@pytest.mark.parametrize(
    ("dia", "previo"),
    [
        (5, {"est": "cancelado"}),
        (6, {"est": "ausente"}),
        (7, {"est": "sobreturno"}),
        (8, {"act": False}),
    ],
    ids=["cancelado", "ausente", "sobreturno", "baja_logica"],
)
def test_turno_no_activo_no_ocupa_el_horario(session_factory, turnos_data, dia, previo) -> None:  # type: ignore[no-untyped-def]
    td = turnos_data
    _ok(session_factory, **_a(td, ini=_t(dia, 10), fin=_t(dia, 10, 30), **previo))
    # Mismo profesional y sillon, mismo rango: debe entrar.
    _ok(session_factory, **_a(td, ini=_t(dia, 10), fin=_t(dia, 10, 30)))


def test_sobreturno_puede_superponerse_a_un_turno_activo(session_factory, turnos_data) -> None:  # type: ignore[no-untyped-def]
    td = turnos_data
    _ok(session_factory, **_a(td, ini=_t(9, 10), fin=_t(9, 10, 30)))
    _ok(session_factory, **_a(td, ini=_t(9, 10), fin=_t(9, 10, 30), est="sobreturno"))


def test_mismo_rango_en_otra_clinica_es_valido(session_factory, turnos_data) -> None:  # type: ignore[no-untyped-def]
    td = turnos_data
    _ok(session_factory, **_a(td, ini=_t(10, 10), fin=_t(10, 10, 30)))
    _ok(
        session_factory,
        **_a(
            td, c=td["b"], p=td["prof_b"], s=td["sillon_b"], pac=td["pac_b"], pre=td["prest_b"],
            ini=_t(10, 10), fin=_t(10, 10, 30),
        ),  # fmt: skip
    )


@pytest.mark.parametrize(
    "cambio",
    [
        {"fin": _t(11, 10)},  # fin == inicio
        {"est": "inexistente"},
        {"ori": "telepatia"},
        {"dur": 0},
        {"dur": 481},
    ],
    ids=["fin_igual", "estado", "origen", "dur_0", "dur_481"],
)
def test_checks_rechazan_valores_invalidos_23514(session_factory, turnos_data, cambio) -> None:  # type: ignore[no-untyped-def]
    td = turnos_data
    params = _a(td, **{"ini": _t(11, 10), "fin": _t(11, 10, 30), **cambio})
    _falla(session_factory, "23514", **params)


def test_fin_menor_que_inicio_rechazado_por_la_base(session_factory, turnos_data) -> None:  # type: ignore[no-untyped-def]
    """fin < inicio: la columna generada ``rango`` falla (22000) antes de evaluar el CHECK."""
    td = turnos_data
    with session_factory() as session:
        with pytest.raises(DBAPIError) as exc:
            session.execute(text(SQL_INSERT), _a(td, ini=_t(11, 10), fin=_t(11, 9)))
        session.rollback()
    assert exc.value.orig.sqlstate == "22000"


@pytest.mark.parametrize(
    "cruzado",
    [{"p": "prof_b"}, {"s": "sillon_b"}, {"pac": "pac_b"}, {"pre": "prest_b"}],
    ids=["profesional", "sillon", "paciente", "prestacion"],
)
def test_fk_compuesta_rechaza_referencias_de_otra_clinica_23503(  # type: ignore[no-untyped-def]
    session_factory, turnos_data, cruzado
) -> None:
    td = turnos_data
    cambio = {campo: td[clave] for campo, clave in cruzado.items()}
    _falla(session_factory, "23503", **_a(td, ini=_t(12, 10), fin=_t(12, 10, 30), **cambio))


def test_rango_generado_es_semiabierto(session_factory, turnos_data) -> None:  # type: ignore[no-untyped-def]
    td = turnos_data
    tid = _ok(session_factory, **_a(td, ini=_t(13, 10), fin=_t(13, 10, 30)))
    with session_factory() as session:
        fila = session.execute(
            text("SELECT lower(rango), upper(rango), lower_inc(rango), upper_inc(rango) "
                 "FROM turno WHERE id=:i"),
            {"i": tid},
        ).one()  # fmt: skip
    assert fila == (_t(13, 10), _t(13, 10, 30), True, False)


def test_repositorio_de_otra_clinica_no_ve_turnos_ajenos(session_factory, turnos_data) -> None:  # type: ignore[no-untyped-def]
    td = turnos_data
    id_a = _ok(session_factory, **_a(td, ini=_t(14, 10), fin=_t(14, 10, 30)))
    id_b = _ok(
        session_factory,
        **_a(
            td, c=td["b"], p=td["prof_b"], s=td["sillon_b"], pac=td["pac_b"], pre=td["prest_b"],
            ini=_t(14, 10), fin=_t(14, 10, 30),
        ),  # fmt: skip
    )
    with session_factory() as session:
        repo_b = BaseRepository(session, Turno, td["b"])
        ids_b = {t.id for t in repo_b.list(include_inactive=True)}
        assert id_b in ids_b
        assert id_a not in ids_b
        assert repo_b.get(id_a) is None
        assert repo_b.get(id_b) is not None
        assert BaseRepository(session, Turno, td["a"]).get(id_b) is None
