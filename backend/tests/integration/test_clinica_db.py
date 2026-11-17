"""Constraints e inmutabilidad a nivel DB de odontograma y evolucion (C-09 2.2). PG16 real."""

from uuid import uuid4

import pytest
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError, IntegrityError

from app.domain.clinica import servicios


def _paciente(session, clinica_id: int) -> int:  # type: ignore[no-untyped-def]
    return session.execute(
        text(
            "INSERT INTO paciente (clinica_id, nombre, apellido, dni, telefono, "
            "nombre_busqueda, es_seed) "
            "VALUES (:c, 'P', 'S', :d, '+5491155550001', 's p', true) RETURNING id"
        ),
        {"c": clinica_id, "d": f"9{uuid4().int % 10**7:07d}"},
    ).scalar()


def _evolucion(session, c, p, u, prof, **extra) -> int:  # type: ignore[no-untyped-def]
    cols = {"texto": "Evolucion sintetica", "pieza": None, "corrige": None, "motivo": None}
    cols.update(extra)
    return session.execute(
        text(
            "INSERT INTO evolucion (clinica_id, paciente_id, autor_usuario_id, profesional_id, "
            "texto, pieza_fdi, corrige_a_id, motivo_correccion) "
            "VALUES (:c, :p, :u, :prof, :texto, :pieza, :corrige, :motivo) RETURNING id"
        ),
        {"c": c, "p": p, "u": u, "prof": prof, **cols},
    ).scalar()


def _odonto(session, c, p, u, version=1, piezas="{}") -> int:  # type: ignore[no-untyped-def]
    return session.execute(
        text(
            "INSERT INTO odontograma (clinica_id, paciente_id, version, denticion, piezas, "
            "autor_usuario_id) VALUES (:c, :p, :v, 'permanente', CAST(:pz AS jsonb), :u) "
            "RETURNING id"
        ),
        {"c": c, "p": p, "v": version, "pz": piezas, "u": u},
    ).scalar()


@pytest.fixture()
def datos(session_factory, auth_data, catalogo_data):  # type: ignore[no-untyped-def]
    a, b = auth_data["clinica_a"], auth_data["clinica_b"]
    u = auth_data["user_ids"]["odonto@test.test"]
    prof = catalogo_data["prof_p"]
    with session_factory() as s:
        p1, p2, pb = _paciente(s, a), _paciente(s, a), _paciente(s, b)
        evo = _evolucion(s, a, p1, u, prof)
        odo = _odonto(s, a, p1, u)
        s.commit()
    return {
        "a": a, "b": b, "u": u, "prof": prof, "prof_b": catalogo_data["prof_b"],
        "p1": p1, "p2": p2, "pb": pb, "evo": evo, "odo": odo,
    }  # fmt: skip


MUTACIONES = [
    ("UPDATE evolucion SET texto='otro' WHERE id=:id", "evo", "evolucion"),
    ("DELETE FROM evolucion WHERE id=:id", "evo", "evolucion"),
    ("UPDATE odontograma SET denticion='temporal' WHERE id=:id", "odo", "odontograma"),
    ("DELETE FROM odontograma WHERE id=:id", "odo", "odontograma"),
]


@pytest.mark.parametrize(("sql", "clave", "tabla"), MUTACIONES)
def test_update_delete_rechazados_y_fila_persiste(  # type: ignore[no-untyped-def]
    session_factory, datos, sql, clave, tabla
) -> None:
    with session_factory() as s:
        with pytest.raises(DBAPIError, match="append-only"):
            s.execute(text(sql), {"id": datos[clave]})
        s.rollback()
    with session_factory() as s:
        n = s.execute(
            text(f"SELECT count(*) FROM {tabla} WHERE id=:id"),
            {"id": datos[clave]},  # noqa: S608
        ).scalar()
    assert n == 1


@pytest.mark.parametrize("tabla", ["evolucion", "odontograma"])
def test_truncate_rechazado(session_factory, datos, tabla) -> None:  # type: ignore[no-untyped-def]
    with session_factory() as s:
        with pytest.raises(DBAPIError, match="append-only"):
            s.execute(text(f"TRUNCATE {tabla} CASCADE"))
        s.rollback()
    with session_factory() as s:
        assert s.execute(text(f"SELECT count(*) FROM {tabla}")).scalar() >= 1  # noqa: S608


def test_texto_de_evolucion_intacto_tras_intento_de_update(session_factory, datos) -> None:  # type: ignore[no-untyped-def]
    with session_factory() as s:
        with pytest.raises(DBAPIError):
            s.execute(text("UPDATE evolucion SET texto='x' WHERE id=:id"), {"id": datos["evo"]})
        s.rollback()
        texto = s.execute(
            text("SELECT texto FROM evolucion WHERE id=:id"), {"id": datos["evo"]}
        ).scalar()
    assert texto == "Evolucion sintetica"


@pytest.mark.parametrize("columna", ["autor_usuario_id", "profesional_id"])
def test_insert_sin_autor_o_profesional_falla(session_factory, datos, columna) -> None:  # type: ignore[no-untyped-def]
    params = {"c": datos["a"], "p": datos["p1"], "u": datos["u"], "prof": datos["prof"]}
    if columna == "autor_usuario_id":
        params["u"] = None
    else:
        params["prof"] = None
    with session_factory() as s:
        with pytest.raises(IntegrityError) as exc:
            s.execute(
                text(
                    "INSERT INTO evolucion (clinica_id, paciente_id, autor_usuario_id, "
                    "profesional_id, texto) VALUES (:c, :p, :u, :prof, 'x')"
                ),
                params,
            )
        assert exc.value.orig.sqlstate == "23502"  # not_null_violation
        s.rollback()


def test_profesional_de_otra_clinica_23503(session_factory, datos) -> None:  # type: ignore[no-untyped-def]
    with session_factory() as s:
        with pytest.raises(IntegrityError) as exc:
            _evolucion(s, datos["a"], datos["p1"], datos["u"], datos["prof_b"])
        assert exc.value.orig.sqlstate == "23503"
        s.rollback()


def test_corrige_a_id_de_otro_paciente_23503(session_factory, datos) -> None:  # type: ignore[no-untyped-def]
    with session_factory() as s:
        with pytest.raises(IntegrityError) as exc:
            _evolucion(
                s, datos["a"], datos["p2"], datos["u"], datos["prof"],
                corrige=datos["evo"], motivo="Motivo sintetico",
            )  # fmt: skip
        assert exc.value.orig.sqlstate == "23503"
        s.rollback()


def test_segunda_correccion_de_la_misma_evolucion_23505(session_factory, datos) -> None:  # type: ignore[no-untyped-def]
    with session_factory() as s:
        _evolucion(
            s, datos["a"], datos["p1"], datos["u"], datos["prof"],
            corrige=datos["evo"], motivo="Primera",
        )  # fmt: skip
        s.commit()
        with pytest.raises(IntegrityError) as exc:
            _evolucion(
                s, datos["a"], datos["p1"], datos["u"], datos["prof"],
                corrige=datos["evo"], motivo="Segunda",
            )  # fmt: skip
        assert exc.value.orig.sqlstate == "23505"
        s.rollback()


@pytest.mark.parametrize("pieza", [19, 10, 49, 56, 86, 90])
def test_pieza_fdi_invalida_23514(session_factory, datos, pieza) -> None:  # type: ignore[no-untyped-def]
    with session_factory() as s:
        with pytest.raises(IntegrityError) as exc:
            _evolucion(s, datos["a"], datos["p1"], datos["u"], datos["prof"], pieza=pieza)
        assert exc.value.orig.sqlstate == "23514"
        s.rollback()


@pytest.mark.parametrize("pieza", [11, 18, 48, 51, 85])
def test_pieza_fdi_valida_en_bordes(session_factory, datos, pieza) -> None:  # type: ignore[no-untyped-def]
    with session_factory() as s:
        assert _evolucion(s, datos["a"], datos["p1"], datos["u"], datos["prof"], pieza=pieza)
        s.rollback()


@pytest.mark.parametrize(
    "extra",
    [
        {"corrige": 1},  # corrige sin motivo
        {"motivo": "solo motivo"},  # motivo sin corrige
        {"texto": "   "},  # texto en blanco
    ],
)
def test_checks_de_texto_y_correccion_23514(session_factory, datos, extra) -> None:  # type: ignore[no-untyped-def]
    with session_factory() as s:
        with pytest.raises(IntegrityError) as exc:
            _evolucion(s, datos["a"], datos["p1"], datos["u"], datos["prof"], **extra)
        assert exc.value.orig.sqlstate in {"23514", "23503"}
        s.rollback()


def test_piezas_como_array_23514(session_factory, datos) -> None:  # type: ignore[no-untyped-def]
    with session_factory() as s:
        with pytest.raises(IntegrityError) as exc:
            _odonto(s, datos["a"], datos["p1"], datos["u"], version=9, piezas="[]")
        assert exc.value.orig.sqlstate == "23514"
        s.rollback()


def test_version_duplicada_de_odontograma_23505(session_factory, datos) -> None:  # type: ignore[no-untyped-def]
    with session_factory() as s:
        with pytest.raises(IntegrityError) as exc:
            _odonto(s, datos["a"], datos["p1"], datos["u"], version=1)
        assert exc.value.orig.sqlstate == "23505"
        s.rollback()


def test_paciente_de_otra_clinica_en_odontograma_23503(session_factory, datos) -> None:  # type: ignore[no-untyped-def]
    with session_factory() as s:
        with pytest.raises(IntegrityError) as exc:
            _odonto(s, datos["a"], datos["pb"], datos["u"])
        assert exc.value.orig.sqlstate == "23503"
        s.rollback()


def test_consulta_con_otra_clinica_devuelve_0_filas(session_factory, datos) -> None:  # type: ignore[no-untyped-def]
    """Regla dura 10: las consultas del servicio acotan por clinica_id."""
    with session_factory() as s:
        assert servicios.versiones_odontograma(s, datos["a"], datos["p1"])
        assert servicios.evoluciones_pagina(s, datos["a"], datos["p1"], None, 50)[0]
        # Mismo paciente, otra clínica -> nada.
        assert servicios.versiones_odontograma(s, datos["b"], datos["p1"]) == []
        assert servicios.evoluciones_pagina(s, datos["b"], datos["p1"], None, 50)[0] == []
