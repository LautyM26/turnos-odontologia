"""Migración 013 (C-06): slug de clínica, token público y actor de enlace. PG16 real, sintético."""

from datetime import UTC, datetime, timedelta

import pytest
from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlalchemy import create_engine, text
from sqlalchemy.exc import IntegrityError

from alembic import command
from app.domain.agenda.turnos import Turno, TurnoTransicion
from app.domain.core.models import Clinica
from tests.integration.conftest import ALEMBIC_INI, BACKEND_DIR


@pytest.fixture()
def cfg(postgres_url):  # type: ignore[no-untyped-def]
    config = Config(ALEMBIC_INI)
    config.set_main_option("script_location", str(BACKEND_DIR / "alembic"))
    config.set_main_option("sqlalchemy.url", postgres_url)
    return config


def _all(url: str, sql: str) -> list:
    engine = create_engine(url)
    with engine.connect() as conn:
        rows = [r[0] for r in conn.execute(text(sql)).all()]
    engine.dispose()
    return rows


def _columnas(url: str, tabla: str) -> set[str]:
    return set(
        _all(url, f"SELECT column_name FROM information_schema.columns WHERE table_name='{tabla}'")
    )


def _falla(session_factory, obj, sqlstate: str) -> None:  # type: ignore[no-untyped-def]
    with session_factory() as session:
        session.add(obj)
        with pytest.raises(IntegrityError) as exc:
            session.commit()
        session.rollback()
    assert exc.value.orig.sqlstate == sqlstate


def test_upgrade_agrega_columnas_y_constraints(postgres_url) -> None:  # type: ignore[no-untyped-def]
    assert "slug" in _columnas(postgres_url, "clinica")
    assert "token_publico_hash" in _columnas(postgres_url, "turno")
    assert "actor_tipo" in _columnas(postgres_url, "turno_transicion")
    nombres = set(_all(postgres_url, "SELECT conname FROM pg_constraint"))
    assert {
        "ck_clinica_slug_formato",
        "uq_clinica_slug",
        "ck_turno_transicion_actor_tipo_valido",
        "ck_turno_transicion_actor_coherente",
    } <= nombres
    indice = _all(
        postgres_url,
        "SELECT indexdef FROM pg_indexes WHERE indexname='uq_turno_token_publico_hash'",
    )
    assert "UNIQUE" in indice[0] and "token_publico_hash IS NOT NULL" in indice[0]


def test_clinica_nueva_recibe_slug_valido_por_default(session_factory, auth_data) -> None:  # type: ignore[no-untyped-def]
    with session_factory() as session:
        c = Clinica(nombre="Clinica Slug Sintetica", cuit="30799999995", es_seed=True)
        session.add(c)
        session.commit()
        session.refresh(c)
        assert c.slug.startswith("c-") and len(c.slug) == 14
        piloto = session.get(Clinica, auth_data["clinica_a"])
        assert piloto.slug == "clinica-piloto"  # fijado por seed_core


@pytest.mark.parametrize("slug", ["Con-Mayus", "a", "doble--guion", "-borde", "con espacio"])
def test_slug_invalido_23514(session_factory, slug) -> None:  # type: ignore[no-untyped-def]
    _falla(session_factory, Clinica(nombre="X", cuit="30788888885", slug=slug), "23514")


def test_slug_duplicado_23505(session_factory, auth_data) -> None:  # type: ignore[no-untyped-def]
    _falla(session_factory, Clinica(nombre="X", cuit="30777777775", slug="clinica-piloto"), "23505")


def _turno(session_factory, td, dia: int, **over) -> int:  # type: ignore[no-untyped-def]
    inicio = datetime(2033, 2, dia, 10, tzinfo=UTC)
    cols = {
        "clinica_id": td["a"], "profesional_id": td["p"], "sillon_id": td["s1"],
        "paciente_id": td["pac_a"], "prestacion_id": td["prest_a"], "duracion_min": 30,
        "inicio": inicio, "fin": inicio + timedelta(minutes=30), **over,
    }  # fmt: skip
    with session_factory() as session:
        t = Turno(**cols)
        session.add(t)
        session.commit()
        return t.id


def test_token_publico_hash_unico(session_factory, turnos_data) -> None:  # type: ignore[no-untyped-def]
    _turno(session_factory, turnos_data, 1, token_publico_hash="a" * 64)
    _turno(session_factory, turnos_data, 2)  # varios turnos sin token conviven
    _turno(session_factory, turnos_data, 3)
    with pytest.raises(IntegrityError) as exc:
        _turno(session_factory, turnos_data, 4, token_publico_hash="a" * 64)
    assert exc.value.orig.sqlstate == "23505"


@pytest.mark.parametrize(
    ("tipo", "con_usuario"),
    [("usuario", False), ("paciente_enlace", True), ("robot", False)],
    ids=["usuario_sin_id", "enlace_con_id", "tipo_invalido"],
)
def test_actor_incoherente_23514(
    session_factory, turnos_data, auth_data, tipo, con_usuario
) -> None:  # type: ignore[no-untyped-def]
    td = turnos_data
    turno_id = _turno(session_factory, td, 10 + len(tipo) + int(con_usuario))
    actor = auth_data["user_ids"]["recepcion@test.test"] if con_usuario else None
    transicion = TurnoTransicion(
        clinica_id=td["a"], turno_id=turno_id, desde="reservado", hacia="cancelado",
        actor_usuario_id=actor, actor_tipo=tipo,
    )  # fmt: skip
    _falla(session_factory, transicion, "23514")


def test_transicion_previa_queda_como_usuario(session_factory, turnos_data, auth_data) -> None:  # type: ignore[no-untyped-def]
    td = turnos_data
    turno_id = _turno(session_factory, td, 25)
    with session_factory() as session:
        t = TurnoTransicion(
            clinica_id=td["a"], turno_id=turno_id, desde="reservado", hacia="confirmado",
            actor_usuario_id=auth_data["user_ids"]["recepcion@test.test"],
        )  # fmt: skip
        session.add(t)
        session.commit()
        assert t.actor_tipo == "usuario"


def test_downgrade_a_012_y_reupgrade(cfg, postgres_url) -> None:  # type: ignore[no-untyped-def]
    command.downgrade(cfg, "012_horario_atencion")
    try:
        assert "slug" not in _columnas(postgres_url, "clinica")
        assert "token_publico_hash" not in _columnas(postgres_url, "turno")
        assert "actor_tipo" not in _columnas(postgres_url, "turno_transicion")
    finally:
        command.upgrade(cfg, "head")
    assert "slug" in _columnas(postgres_url, "clinica")


def test_un_unico_head_y_013_encadenada_a_la_012() -> None:
    script = ScriptDirectory(str(BACKEND_DIR / "alembic"))
    assert len(script.get_heads()) == 1
    assert script.get_revision("013_reserva_online").down_revision == "012_horario_atencion"
