"""Migración 004 (C-08): pacientes, ficha, adjuntos, auditoría HC. PG16 real, datos sintéticos."""

import itertools

import pytest
from alembic.config import Config
from sqlalchemy import create_engine, text
from sqlalchemy.exc import IntegrityError

from alembic import command
from tests.integration.conftest import ALEMBIC_INI, BACKEND_DIR

TABLAS = ("paciente", "ficha_version", "adjunto", "auditoria_hc")
_seq = itertools.count(1)


def _dni() -> str:
    return f"9{next(_seq):07d}"[:8]


@pytest.fixture()
def cfg(postgres_url):  # type: ignore[no-untyped-def]
    config = Config(ALEMBIC_INI)
    config.set_main_option("script_location", str(BACKEND_DIR / "alembic"))
    config.set_main_option("sqlalchemy.url", postgres_url)
    return config


def _scalar(url: str, sql: str, **params):  # type: ignore[no-untyped-def]
    engine = create_engine(url)
    with engine.connect() as conn:
        value = conn.execute(text(sql), params).scalar()
    engine.dispose()
    return value


def _tablas(url: str) -> set[str]:
    engine = create_engine(url)
    with engine.connect() as conn:
        rows = conn.execute(
            text("SELECT table_name FROM information_schema.tables WHERE table_schema='public'")
        ).all()
    engine.dispose()
    return {r[0] for r in rows}


def _ok(session_factory, sql: str, **params):  # type: ignore[no-untyped-def]
    with session_factory() as session:
        value = session.execute(text(sql), params).scalar()
        session.commit()
        return value


def _falla(session_factory, sql: str, **params) -> None:  # type: ignore[no-untyped-def]
    with session_factory() as session:
        with pytest.raises(IntegrityError):
            session.execute(text(sql), params)
        session.rollback()


def _paciente(session_factory, clinica: int, **over):  # type: ignore[no-untyped-def]
    cols = {
        "c": clinica,
        "n": "Paciente",
        "a": "Sintetico",
        "d": _dni(),
        "t": "+5491155550001",
        "nb": "sintetico paciente",
    }
    cols.update(over)
    return _ok(
        session_factory,
        "INSERT INTO paciente (clinica_id, nombre, apellido, dni, telefono, nombre_busqueda, "
        "es_seed) VALUES (:c, :n, :a, :d, :t, :nb, true) RETURNING id",
        **cols,
    )


def test_upgrade_head_crea_tablas_extension_y_constraints(postgres_url) -> None:  # type: ignore[no-untyped-def]
    assert set(TABLAS) <= _tablas(postgres_url)
    sql_ext = "SELECT count(*) FROM pg_extension WHERE extname='pg_trgm'"
    assert _scalar(postgres_url, sql_ext) == 1
    for nombre in ("uq_paciente_clinica_id", "uq_usuario_clinica_id", "uq_paciente_clinica_dni"):
        sql = "SELECT count(*) FROM pg_constraint WHERE conname=:n"
        assert _scalar(postgres_url, sql, n=nombre) == 1, nombre


def test_indices_tenant_y_trigram(postgres_url) -> None:  # type: ignore[no-untyped-def]
    defs = _scalar(
        postgres_url,
        "SELECT string_agg(indexdef, ' | ') FROM pg_indexes WHERE schemaname='public' "
        "AND tablename IN ('paciente','ficha_version','adjunto','auditoria_hc')",
    )
    assert "gin_trgm_ops" in defs
    for fragmento in (
        "ON public.paciente USING btree (clinica_id, telefono)",
        "ON public.paciente USING btree (clinica_id, email)",
        "ON public.ficha_version USING btree (clinica_id, paciente_id, version DESC)",
        "ON public.adjunto USING btree (clinica_id, paciente_id, created_at DESC)",
        "ON public.auditoria_hc USING btree (clinica_id, paciente_id, id DESC)",
        "ON public.auditoria_hc USING btree (clinica_id, created_at)",
    ):
        assert fragmento in defs, fragmento


def test_fks_compuestas_a_paciente_y_usuario(postgres_url) -> None:  # type: ignore[no-untyped-def]
    defs = _scalar(
        postgres_url,
        "SELECT string_agg(pg_get_constraintdef(oid), ' | ') FROM pg_constraint "
        "WHERE contype='f' AND conrelid::regclass::text IN "
        "('ficha_version','adjunto','auditoria_hc','paciente')",
    )
    assert "FOREIGN KEY (clinica_id, paciente_id) REFERENCES paciente(clinica_id, id)" in defs
    assert "FOREIGN KEY (clinica_id, autor_usuario_id) REFERENCES usuario(clinica_id, id)" in defs
    assert "FOREIGN KEY (clinica_id, subido_por) REFERENCES usuario(clinica_id, id)" in defs
    assert "FOREIGN KEY (clinica_id, actor_usuario_id) REFERENCES usuario(clinica_id, id)" in defs
    assert (
        "FOREIGN KEY (clinica_id, consentimiento_datos_por) REFERENCES usuario(clinica_id, id)"
        in defs
    )


def test_dni_unico_por_clinica_y_permitido_en_otra(session_factory, auth_data) -> None:  # type: ignore[no-untyped-def]
    a, b = auth_data["clinica_a"], auth_data["clinica_b"]
    dni = _dni()
    _paciente(session_factory, a, d=dni)
    _paciente(session_factory, b, d=dni)  # otra clínica: OK
    _falla(
        session_factory,
        "INSERT INTO paciente (clinica_id, nombre, apellido, dni, telefono, nombre_busqueda) "
        "VALUES (:c, 'X', 'Y', :d, '+5491155550001', 'y x')",
        c=a,
        d=dni,
    )


@pytest.mark.parametrize("dni", ["12AB", "123456", "123456789", "1234567a"])
def test_check_dni(session_factory, auth_data, dni) -> None:  # type: ignore[no-untyped-def]
    _falla(
        session_factory,
        "INSERT INTO paciente (clinica_id, nombre, apellido, dni, telefono, nombre_busqueda) "
        "VALUES (:c, 'X', 'Y', :d, '+5491155550001', 'y x')",
        c=auth_data["clinica_a"],
        d=dni,
    )


@pytest.mark.parametrize("tel", ["1155550001", "+54", "+54abc", "+" + "1" * 16])
def test_check_telefono_e164(session_factory, auth_data, tel) -> None:  # type: ignore[no-untyped-def]
    _falla(
        session_factory,
        "INSERT INTO paciente (clinica_id, nombre, apellido, dni, telefono, nombre_busqueda) "
        "VALUES (:c, 'X', 'Y', :d, :t, 'y x')",
        c=auth_data["clinica_a"],
        d=_dni(),
        t=tel,
    )


def test_check_contacto_obligatorio(session_factory, auth_data) -> None:  # type: ignore[no-untyped-def]
    _falla(
        session_factory,
        "INSERT INTO paciente (clinica_id, nombre, apellido, dni, nombre_busqueda) "
        "VALUES (:c, 'X', 'Y', :d, 'y x')",
        c=auth_data["clinica_a"],
        d=_dni(),
    )
    # Solo email es válido.
    _ok(
        session_factory,
        "INSERT INTO paciente (clinica_id, nombre, apellido, dni, email, nombre_busqueda) "
        "VALUES (:c, 'X', 'Y', :d, 'a@example.com', 'y x') RETURNING id",
        c=auth_data["clinica_a"],
        d=_dni(),
    )


@pytest.mark.parametrize("riesgo", [-1, 101])
def test_check_riesgo_ausencia(session_factory, auth_data, riesgo) -> None:  # type: ignore[no-untyped-def]
    _falla(
        session_factory,
        "INSERT INTO paciente (clinica_id, nombre, apellido, dni, telefono, nombre_busqueda, "
        "riesgo_ausencia) VALUES (:c, 'X', 'Y', :d, '+5491155550001', 'y x', :r)",
        c=auth_data["clinica_a"],
        d=_dni(),
        r=riesgo,
    )


def test_check_consentimiento_requiere_fecha(session_factory, auth_data) -> None:  # type: ignore[no-untyped-def]
    _falla(
        session_factory,
        "INSERT INTO paciente (clinica_id, nombre, apellido, dni, telefono, nombre_busqueda, "
        "consentimiento_datos) VALUES (:c, 'X', 'Y', :d, '+5491155550001', 'y x', true)",
        c=auth_data["clinica_a"],
        d=_dni(),
    )
    _ok(
        session_factory,
        "INSERT INTO paciente (clinica_id, nombre, apellido, dni, telefono, nombre_busqueda, "
        "consentimiento_datos, consentimiento_datos_at) "
        "VALUES (:c, 'X', 'Y', :d, '+5491155550001', 'y x', true, now()) RETURNING id",
        c=auth_data["clinica_a"],
        d=_dni(),
    )


def test_fk_consentimiento_por_otra_clinica_falla(session_factory, auth_data) -> None:  # type: ignore[no-untyped-def]
    usuario_b = _ok(
        session_factory,
        "SELECT id FROM usuario WHERE clinica_id=:c LIMIT 1",
        c=auth_data["clinica_b"],
    )
    _falla(
        session_factory,
        "INSERT INTO paciente (clinica_id, nombre, apellido, dni, telefono, nombre_busqueda, "
        "consentimiento_datos, consentimiento_datos_at, consentimiento_datos_por) "
        "VALUES (:c, 'X', 'Y', :d, '+5491155550001', 'y x', true, now(), :u)",
        c=auth_data["clinica_a"],
        d=_dni(),
        u=usuario_b,
    )


def test_ficha_con_paciente_o_autor_de_otra_clinica_falla(session_factory, auth_data) -> None:  # type: ignore[no-untyped-def]
    a, b = auth_data["clinica_a"], auth_data["clinica_b"]
    pac_a = _paciente(session_factory, a)
    autor_a = auth_data["user_ids"]["odonto@test.test"]
    autor_b = auth_data["user_ids"]["admin-b@test.test"]
    ok = (
        "INSERT INTO ficha_version (clinica_id, paciente_id, version, autor_usuario_id) "
        "VALUES (:c, :p, :v, :u) RETURNING id"
    )
    _ok(session_factory, ok, c=a, p=pac_a, v=1, u=autor_a)
    # paciente de A referenciado desde B
    _falla(session_factory, ok, c=b, p=pac_a, v=1, u=autor_b)
    # autor de B en clínica A
    _falla(session_factory, ok, c=a, p=pac_a, v=2, u=autor_b)
    # versión duplicada
    _falla(session_factory, ok, c=a, p=pac_a, v=1, u=autor_a)
    # versión no positiva
    _falla(session_factory, ok, c=a, p=pac_a, v=0, u=autor_a)


def test_adjunto_checks_y_fk(session_factory, auth_data) -> None:  # type: ignore[no-untyped-def]
    a, b = auth_data["clinica_a"], auth_data["clinica_b"]
    pac_a = _paciente(session_factory, a)
    autor_a = auth_data["user_ids"]["odonto@test.test"]
    autor_b = auth_data["user_ids"]["admin-b@test.test"]
    sql = (
        "INSERT INTO adjunto (clinica_id, paciente_id, tipo, mime, tamano_bytes, sha256, "
        "storage_key, nombre_original, subido_por) "
        "VALUES (:c, :p, :t, :m, :s, :h, :k, 'x.png', :u) RETURNING id"
    )
    base = {
        "c": a, "p": pac_a, "t": "foto", "m": "image/png", "s": 10,
        "h": "a" * 64, "k": f"k-{_dni()}", "u": autor_a,
    }  # fmt: skip
    _ok(session_factory, sql, **base)
    for cambio in (
        {"t": "video"},
        {"m": "image/gif"},
        {"s": 0},
        {"h": "abc"},
        {"c": b},  # paciente de A desde B
        {"u": autor_b},  # autor de otra clínica
    ):
        _falla(session_factory, sql, **{**base, "k": f"k-{_dni()}", **cambio})
    # storage_key único
    _falla(session_factory, sql, **{**base, "k": base["k"]})


def test_auditoria_checks_y_fk(session_factory, auth_data) -> None:  # type: ignore[no-untyped-def]
    a, b = auth_data["clinica_a"], auth_data["clinica_b"]
    pac_a = _paciente(session_factory, a)
    actor_a = auth_data["user_ids"]["odonto@test.test"]
    actor_b = auth_data["user_ids"]["admin-b@test.test"]
    sql = (
        "INSERT INTO auditoria_hc (clinica_id, paciente_id, actor_usuario_id, actor_tipo, "
        "accion, entidad, entidad_id) VALUES (:c, :p, :u, :at, :ac, :e, 1) RETURNING id"
    )
    base = {"c": a, "p": pac_a, "u": actor_a, "at": "usuario", "ac": "crear", "e": "paciente"}
    _ok(session_factory, sql, **base)
    # sistema sin actor es válido; usuario sin actor no
    _ok(session_factory, sql, **{**base, "u": None, "at": "sistema"})
    for cambio in (
        {"u": None},
        {"ac": "borrar"},
        {"e": "evolucion"},
        {"at": "bot"},
        {"c": b},
        {"u": actor_b},
    ):
        _falla(session_factory, sql, **{**base, **cambio})


def test_downgrade_elimina_004_y_reupgrade_restaura(cfg, postgres_url) -> None:  # type: ignore[no-untyped-def]
    command.downgrade(cfg, "-1")
    try:
        assert not set(TABLAS) & _tablas(postgres_url)
        sql_fn = "SELECT count(*) FROM pg_proc WHERE proname='fn_rechazar_mutacion'"
        assert _scalar(postgres_url, sql_fn) == 0
        sql_tg = "SELECT count(*) FROM pg_trigger WHERE tgname LIKE 'trg_%append_only%'"
        assert _scalar(postgres_url, sql_tg) == 0
        # La 003 queda intacta.
        assert "profesional" in _tablas(postgres_url)
        sql_uq = "SELECT count(*) FROM pg_constraint WHERE conname='uq_usuario_clinica_id'"
        assert _scalar(postgres_url, sql_uq) == 1
    finally:
        command.upgrade(cfg, "head")
    assert set(TABLAS) <= _tablas(postgres_url)
