"""Constraints e inmutabilidad a nivel DB de consentimientos y auditoría admin (C-18 2.2)."""

from uuid import uuid4

import pytest
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError, IntegrityError

HASH = "a" * 64


def _paciente(session, clinica_id: int) -> int:  # type: ignore[no-untyped-def]
    return session.execute(
        text(
            "INSERT INTO paciente (clinica_id, nombre, apellido, dni, telefono, "
            "nombre_busqueda, es_seed) "
            "VALUES (:c, 'P', 'S', :d, '+5491155550001', 's p', true) RETURNING id"
        ),
        {"c": clinica_id, "d": f"9{uuid4().int % 10**7:07d}"},
    ).scalar()


def _consentimiento(session, c, p, u, **extra) -> int:  # type: ignore[no-untyped-def]
    cols = {"tipo": "extraccion", "texto": "Texto sintetico", "version": "1.0", "hash": HASH}
    cols.update(extra)
    return session.execute(
        text(
            "INSERT INTO consentimiento (clinica_id, paciente_id, tipo, texto, texto_version, "
            "texto_hash, autor_usuario_id) "
            "VALUES (:c, :p, :tipo, :texto, :version, :hash, :u) RETURNING id"
        ),
        {"c": c, "p": p, "u": u, **cols},
    ).scalar()


def _firma(session, c, p, cid, u, **extra) -> int:  # type: ignore[no-untyped-def]
    cols = {"ip": "127.0.0.1", "ua": "pytest", "hash": HASH, "nombre": "Firmante Sintetico",
            "dni": "90000001"}  # fmt: skip
    cols.update(extra)
    return session.execute(
        text(
            "INSERT INTO consentimiento_firma (clinica_id, paciente_id, consentimiento_id, ip, "
            "dispositivo, texto_hash, firmante_nombre, firmante_dni, asistido_por_usuario_id) "
            "VALUES (:c, :p, :cid, :ip, :ua, :hash, :nombre, :dni, :u) RETURNING id"
        ),
        {"c": c, "p": p, "cid": cid, "u": u, **cols},
    ).scalar()


def _evento_admin(session, c, actor, accion="exportar") -> int:  # type: ignore[no-untyped-def]
    return session.execute(
        text(
            "INSERT INTO auditoria_admin (clinica_id, actor_usuario_id, accion) "
            "VALUES (:c, :u, :a) RETURNING id"
        ),
        {"c": c, "u": actor, "a": accion},
    ).scalar()


@pytest.fixture()
def datos(session_factory, auth_data):  # type: ignore[no-untyped-def]
    a, b = auth_data["clinica_a"], auth_data["clinica_b"]
    u = auth_data["user_ids"]["odonto@test.test"]
    ub = auth_data["user_ids"]["admin-b@test.test"]
    with session_factory() as s:
        p1, p2, pb = _paciente(s, a), _paciente(s, a), _paciente(s, b)
        cons = _consentimiento(s, a, p1, u)
        cons_firmado = _consentimiento(s, a, p1, u, tipo="anestesia")
        firma = _firma(s, a, p1, cons_firmado, u)
        evento = _evento_admin(s, a, u)
        s.commit()
    return {
        "a": a, "b": b, "u": u, "ub": ub, "p1": p1, "p2": p2, "pb": pb, "cons": cons,
        "cons_firmado": cons_firmado, "firma": firma, "evento": evento,
    }  # fmt: skip


MUTACIONES = [
    ("UPDATE consentimiento SET texto='otro' WHERE id=:id", "cons", "consentimiento"),
    ("DELETE FROM consentimiento WHERE id=:id", "cons", "consentimiento"),
    ("UPDATE consentimiento_firma SET firmante_nombre='otro' WHERE id=:id", "firma",
     "consentimiento_firma"),
    ("DELETE FROM consentimiento_firma WHERE id=:id", "firma", "consentimiento_firma"),
    ("UPDATE auditoria_admin SET accion='usuario_crear' WHERE id=:id", "evento",
     "auditoria_admin"),
    ("DELETE FROM auditoria_admin WHERE id=:id", "evento", "auditoria_admin"),
]  # fmt: skip


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
            text(f"SELECT count(*) FROM {tabla} WHERE id=:id"),  # noqa: S608
            {"id": datos[clave]},
        ).scalar()
    assert n == 1


@pytest.mark.parametrize(
    ("sentencia", "tabla"),
    [
        # consentimiento está referenciada por la constancia: PG exige truncar ambas a la vez.
        ("TRUNCATE consentimiento, consentimiento_firma", "consentimiento"),
        ("TRUNCATE consentimiento_firma", "consentimiento_firma"),
        ("TRUNCATE auditoria_admin", "auditoria_admin"),
    ],
)
def test_truncate_rechazado(session_factory, datos, sentencia, tabla) -> None:  # type: ignore[no-untyped-def]
    with session_factory() as s:
        with pytest.raises(DBAPIError, match="append-only"):
            s.execute(text(sentencia))
        s.rollback()
    with session_factory() as s:
        assert s.execute(text(f"SELECT count(*) FROM {tabla}")).scalar() >= 1  # noqa: S608


def test_segunda_firma_del_mismo_consentimiento_23505(session_factory, datos) -> None:  # type: ignore[no-untyped-def]
    with session_factory() as s:
        with pytest.raises(IntegrityError) as exc:
            _firma(s, datos["a"], datos["p1"], datos["cons_firmado"], datos["u"])
        assert exc.value.orig.sqlstate == "23505"
        s.rollback()


def test_firma_de_consentimiento_de_otro_paciente_23503(session_factory, datos) -> None:  # type: ignore[no-untyped-def]
    with session_factory() as s:
        with pytest.raises(IntegrityError) as exc:
            _firma(s, datos["a"], datos["p2"], datos["cons"], datos["u"])
        assert exc.value.orig.sqlstate == "23503"
        s.rollback()


def test_firma_de_consentimiento_de_otra_clinica_23503(session_factory, datos) -> None:  # type: ignore[no-untyped-def]
    with session_factory() as s:
        with pytest.raises(IntegrityError) as exc:
            _firma(s, datos["b"], datos["pb"], datos["cons"], datos["ub"])
        assert exc.value.orig.sqlstate == "23503"
        s.rollback()


@pytest.mark.parametrize("dni", ["123456", "123456789", "abcdefgh", "12.345.67"])
def test_dni_del_firmante_invalido_23514(session_factory, datos, dni) -> None:  # type: ignore[no-untyped-def]
    with session_factory() as s:
        con = _consentimiento(s, datos["a"], datos["p1"], datos["u"])
        with pytest.raises(IntegrityError) as exc:
            _firma(s, datos["a"], datos["p1"], con, datos["u"], dni=dni)
        assert exc.value.orig.sqlstate == "23514"
        s.rollback()


@pytest.mark.parametrize("h", ["g" * 64, "A" * 64, "a" * 63])
def test_hash_no_hex_23514(session_factory, datos, h) -> None:  # type: ignore[no-untyped-def]
    with session_factory() as s:
        with pytest.raises(IntegrityError) as exc:
            _consentimiento(s, datos["a"], datos["p1"], datos["u"], hash=h)
        assert exc.value.orig.sqlstate in {"23514", "22001"}
        s.rollback()
    with session_factory() as s:
        con = _consentimiento(s, datos["a"], datos["p1"], datos["u"])
        with pytest.raises(IntegrityError) as exc:
            _firma(s, datos["a"], datos["p1"], con, datos["u"], hash=h)
        assert exc.value.orig.sqlstate in {"23514", "22001"}
        s.rollback()


def test_tipo_fuera_del_catalogo_23514(session_factory, datos) -> None:  # type: ignore[no-untyped-def]
    with session_factory() as s:
        with pytest.raises(IntegrityError) as exc:
            _consentimiento(s, datos["a"], datos["p1"], datos["u"], tipo="inexistente")
        assert exc.value.orig.sqlstate == "23514"
        s.rollback()


def test_nombre_del_firmante_vacio_23514(session_factory, datos) -> None:  # type: ignore[no-untyped-def]
    with session_factory() as s:
        con = _consentimiento(s, datos["a"], datos["p1"], datos["u"])
        with pytest.raises(IntegrityError) as exc:
            _firma(s, datos["a"], datos["p1"], con, datos["u"], nombre="   ")
        assert exc.value.orig.sqlstate == "23514"
        s.rollback()


def test_autor_de_otra_clinica_23503(session_factory, datos) -> None:  # type: ignore[no-untyped-def]
    with session_factory() as s:
        with pytest.raises(IntegrityError) as exc:
            _consentimiento(s, datos["a"], datos["p1"], datos["ub"])
        assert exc.value.orig.sqlstate == "23503"
        s.rollback()


def test_evento_admin_con_actor_de_otra_clinica_23503(session_factory, datos) -> None:  # type: ignore[no-untyped-def]
    with session_factory() as s:
        with pytest.raises(IntegrityError) as exc:
            _evento_admin(s, datos["a"], datos["ub"])
        assert exc.value.orig.sqlstate == "23503"
        s.rollback()


def test_evento_admin_accion_desconocida_23514(session_factory, datos) -> None:  # type: ignore[no-untyped-def]
    with session_factory() as s:
        with pytest.raises(IntegrityError) as exc:
            _evento_admin(s, datos["a"], datos["u"], accion="borrar_todo")
        assert exc.value.orig.sqlstate == "23514"
        s.rollback()


def test_evento_admin_sin_entidad_se_guarda(session_factory, datos) -> None:  # type: ignore[no-untyped-def]
    with session_factory() as s:
        fila = s.execute(
            text("SELECT entidad_id, diff, created_at FROM auditoria_admin WHERE id=:id"),
            {"id": datos["evento"]},
        ).one()
    assert fila.entidad_id is None and fila.diff == {} and fila.created_at is not None


@pytest.mark.parametrize("tabla", ["consentimiento", "consentimiento_firma", "auditoria_admin"])
def test_consulta_con_otra_clinica_devuelve_0_filas(session_factory, datos, tabla) -> None:  # type: ignore[no-untyped-def]
    """Regla dura 10: filtrar por la clínica B no devuelve filas de A."""
    with session_factory() as s:
        propias = s.execute(
            text(f"SELECT count(*) FROM {tabla} WHERE clinica_id=:c"),  # noqa: S608
            {"c": datos["a"]},
        ).scalar()
        ajenas = s.execute(
            text(f"SELECT count(*) FROM {tabla} WHERE clinica_id=:c AND id IN "  # noqa: S608
                 f"(SELECT id FROM {tabla} WHERE clinica_id=:a)"),
            {"c": datos["b"], "a": datos["a"]},
        ).scalar()
    assert propias >= 1 and ajenas == 0
