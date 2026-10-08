"""Constraints de DB del catálogo (C-04, SQL directo, PG16 real, nunca SQLite)."""

import itertools

import pytest
from sqlalchemy import text
from sqlalchemy.exc import DataError, IntegrityError

_seq = itertools.count(1)


def _uid() -> str:
    return f"{next(_seq)}"


def _exec_ok(session_factory, sql: str, **params):  # type: ignore[no-untyped-def]
    with session_factory() as session:
        value = session.execute(text(sql), params).scalar()
        session.commit()
        return value


def _exec_falla(session_factory, sql: str, **params) -> None:  # type: ignore[no-untyped-def]
    with session_factory() as session:
        with pytest.raises(IntegrityError):
            session.execute(text(sql), params)
        session.rollback()


def _sillon(session_factory, clinica: int, nombre: str | None = None) -> int:  # type: ignore[no-untyped-def]
    return _exec_ok(
        session_factory,
        "INSERT INTO sillon_recurso (clinica_id, nombre, tipo) VALUES (:c, :n, 'sillon') "
        "RETURNING id",
        c=clinica,
        n=nombre or f"Sillon {_uid()}",
    )


def _prof(session_factory, clinica: int, matricula: str | None = None) -> int:  # type: ignore[no-untyped-def]
    return _exec_ok(
        session_factory,
        "INSERT INTO profesional (clinica_id, nombre, matricula) VALUES (:c, 'Prof', :m) "
        "RETURNING id",
        c=clinica,
        m=matricula or f"M-{_uid()}",
    )


@pytest.mark.parametrize("tipo", ["cabina", "", "SILLON"])
def test_tipo_fuera_de_enum_falla(session_factory, auth_data, tipo) -> None:  # type: ignore[no-untyped-def]
    _exec_falla(
        session_factory,
        "INSERT INTO sillon_recurso (clinica_id, nombre, tipo) VALUES (:c, :n, :t)",
        c=auth_data["clinica_a"],
        n=f"x{_uid()}",
        t=tipo,
    )


@pytest.mark.parametrize("tipo", ["sillon", "box", "equipo"])
def test_tipo_valido_inserta(session_factory, auth_data, tipo) -> None:  # type: ignore[no-untyped-def]
    new_id = _exec_ok(
        session_factory,
        "INSERT INTO sillon_recurso (clinica_id, nombre, tipo) VALUES (:c, :n, :t) RETURNING id",
        c=auth_data["clinica_a"],
        n=f"ok{_uid()}",
        t=tipo,
    )
    assert new_id > 0


@pytest.mark.parametrize("duracion", [0, 4, 481])
def test_duracion_fuera_de_rango_falla(session_factory, auth_data, duracion) -> None:  # type: ignore[no-untyped-def]
    _exec_falla(
        session_factory,
        "INSERT INTO prestacion (clinica_id, nombre, duracion_min, precio_referencia) "
        "VALUES (:c, 'p', :d, 10)",
        c=auth_data["clinica_a"],
        d=duracion,
    )


@pytest.mark.parametrize("duracion", [5, 480])
def test_duracion_en_limites_inserta(session_factory, auth_data, duracion) -> None:  # type: ignore[no-untyped-def]
    assert _exec_ok(
        session_factory,
        "INSERT INTO prestacion (clinica_id, nombre, duracion_min, precio_referencia) "
        "VALUES (:c, 'p', :d, 0) RETURNING id",
        c=auth_data["clinica_a"],
        d=duracion,
    )


def test_precio_negativo_falla(session_factory, auth_data) -> None:  # type: ignore[no-untyped-def]
    _exec_falla(
        session_factory,
        "INSERT INTO prestacion (clinica_id, nombre, duracion_min, precio_referencia) "
        "VALUES (:c, 'p', 30, -0.01)",
        c=auth_data["clinica_a"],
    )


def test_precio_numeric_conserva_centavos(session_factory, auth_data) -> None:  # type: ignore[no-untyped-def]
    from decimal import Decimal

    valor = _exec_ok(
        session_factory,
        "INSERT INTO prestacion (clinica_id, nombre, duracion_min, precio_referencia) "
        "VALUES (:c, 'p', 30, 15000.50) RETURNING precio_referencia",
        c=auth_data["clinica_a"],
    )
    assert valor == Decimal("15000.50")


_BLOQUEO = (
    "INSERT INTO bloqueo (clinica_id, profesional_id, sillon_id, inicio, fin, motivo) "
    "VALUES (:c, :p, :s, :i, :f, 'm')"
)


def test_bloqueo_fin_igual_a_inicio_falla_por_check(session_factory, auth_data) -> None:  # type: ignore[no-untyped-def]
    _exec_falla(
        session_factory, _BLOQUEO, c=auth_data["clinica_a"], p=None, s=None,
        i="2030-01-01T10:00:00+00", f="2030-01-01T10:00:00+00",
    )  # fmt: skip


def test_bloqueo_fin_anterior_a_inicio_es_rechazado_por_db(session_factory, auth_data) -> None:  # type: ignore[no-untyped-def]
    # La columna generada ``rango`` falla antes que el CHECK: DataError (también es rechazo).
    with session_factory() as session:
        with pytest.raises((IntegrityError, DataError)):
            session.execute(
                text(_BLOQUEO),
                {"c": auth_data["clinica_a"], "p": None, "s": None,
                 "i": "2030-01-01T10:00:00+00", "f": "2030-01-01T09:00:00+00"},
            )  # fmt: skip
        session.rollback()


def test_bloqueo_mas_de_31_dias_falla_y_31_dias_pasa(session_factory, auth_data) -> None:  # type: ignore[no-untyped-def]
    a = auth_data["clinica_a"]
    _exec_falla(
        session_factory, _BLOQUEO, c=a, p=None, s=None,
        i="2030-01-01T00:00:00+00", f="2030-02-01T00:00:01+00",
    )  # fmt: skip
    with session_factory() as session:
        session.execute(
            text(_BLOQUEO),
            {"c": a, "p": None, "s": None, "i": "2030-01-01T00:00:00+00",
             "f": "2030-02-01T00:00:00+00"},
        )  # fmt: skip
        session.commit()


def test_bloqueo_profesional_y_sillon_a_la_vez_falla(session_factory, auth_data) -> None:  # type: ignore[no-untyped-def]
    a = auth_data["clinica_a"]
    _exec_falla(
        session_factory, _BLOQUEO, c=a, p=_prof(session_factory, a), s=_sillon(session_factory, a),
        i="2030-03-01T10:00:00+00", f="2030-03-01T11:00:00+00",
    )  # fmt: skip


def test_fk_compuesta_rechaza_sillon_de_otra_clinica(session_factory, auth_data) -> None:  # type: ignore[no-untyped-def]
    a, b = auth_data["clinica_a"], auth_data["clinica_b"]
    prof_a = _prof(session_factory, a)
    sillon_b = _sillon(session_factory, b)
    # Aunque se declare clinica_id=A, el sillón B no existe en A.
    _exec_falla(
        session_factory,
        "INSERT INTO profesional_sillon (profesional_id, sillon_id, clinica_id) "
        "VALUES (:p, :s, :c)",
        p=prof_a,
        s=sillon_b,
        c=a,
    )
    _exec_falla(
        session_factory,
        "INSERT INTO profesional_sillon (profesional_id, sillon_id, clinica_id) "
        "VALUES (:p, :s, :c)",
        p=prof_a,
        s=sillon_b,
        c=b,
    )


def test_fk_compuesta_acepta_misma_clinica(session_factory, auth_data) -> None:  # type: ignore[no-untyped-def]
    a = auth_data["clinica_a"]
    _exec_ok(
        session_factory,
        "INSERT INTO profesional_sillon (profesional_id, sillon_id, clinica_id) "
        "VALUES (:p, :s, :c) RETURNING profesional_id",
        p=_prof(session_factory, a),
        s=_sillon(session_factory, a),
        c=a,
    )


def test_profesional_rechaza_usuario_de_otra_clinica(session_factory, auth_data) -> None:  # type: ignore[no-untyped-def]
    usuario_b = auth_data["user_ids"]["admin-b@test.test"]
    _exec_falla(
        session_factory,
        "INSERT INTO profesional (clinica_id, nombre, matricula, usuario_id) "
        "VALUES (:c, 'P', :m, :u)",
        c=auth_data["clinica_a"],
        m=f"U-{_uid()}",
        u=usuario_b,
    )


def test_matricula_activa_repetida_falla_pero_baja_y_otro_tenant_permiten(  # type: ignore[no-untyped-def]
    session_factory, auth_data
) -> None:
    a, b = auth_data["clinica_a"], auth_data["clinica_b"]
    matricula = f"DUP-{_uid()}"
    prof = _prof(session_factory, a, matricula)
    _exec_falla(
        session_factory,
        "INSERT INTO profesional (clinica_id, nombre, matricula) VALUES (:c, 'P', :m)",
        c=a,
        m=matricula.lower(),  # case-insensitive
    )
    _prof(session_factory, b, matricula)  # otro tenant: permitido
    _exec_ok(
        session_factory,
        "UPDATE profesional SET is_active = false WHERE id = :i RETURNING id",
        i=prof,
    )
    _prof(session_factory, a, matricula)  # tras baja lógica: permitido


def test_rango_generado_es_semiabierto(session_factory, auth_data) -> None:  # type: ignore[no-untyped-def]
    a = auth_data["clinica_a"]
    with session_factory() as session:
        row = session.execute(
            text(
                "INSERT INTO bloqueo (clinica_id, inicio, fin, motivo) VALUES "
                "(:c, '2030-05-01T12:00:00+00', '2030-05-01T13:00:00+00', 'm') "
                "RETURNING lower_inc(rango), upper_inc(rango), lower(rango), upper(rango), "
                "rango && tstzrange('2030-05-01T13:00:00+00', '2030-05-01T13:30:00+00', '[)')"
            ),
            {"c": a},
        ).one()
        session.commit()
    assert row[0] is True and row[1] is False
    assert row[2].isoformat().startswith("2030-05-01T12:00:00")
    assert row[3].isoformat().startswith("2030-05-01T13:00:00")
    assert row[4] is False  # contiguo no se superpone
