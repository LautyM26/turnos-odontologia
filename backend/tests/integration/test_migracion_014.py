"""Migración 014 (C-15): sesión, mensajes y textos base de WhatsApp. PG16 real, sintético."""

from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest
from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlalchemy import create_engine, text
from sqlalchemy.exc import IntegrityError

from alembic import command
from app.domain.agenda.turnos import Turno, TurnoTransicion
from app.domain.whatsapp.models import MensajeWhatsApp, WhatsappSesion
from tests.integration.conftest import ALEMBIC_INI, BACKEND_DIR

TEXTOS = {"recordatorio_24h", "confirmacion", "cancelacion", "reprogramacion", "oferta_hueco"}


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


def _tablas(url: str) -> set[str]:
    return set(_all(url, "SELECT tablename FROM pg_tables WHERE schemaname='public'"))


def _falla(session_factory, obj, sqlstate: str) -> None:  # type: ignore[no-untyped-def]
    with session_factory() as session:
        session.add(obj)
        with pytest.raises(IntegrityError) as exc:
            session.commit()
        session.rollback()
    assert exc.value.orig.sqlstate == sqlstate


_dia = iter(range(1, 400))


def _turno(session_factory, td, clinica: str = "a") -> int:  # type: ignore[no-untyped-def]
    inicio = datetime(2034, 1, 1, 10, tzinfo=UTC) + timedelta(days=next(_dia))
    if clinica == "a":
        refs = {"profesional_id": td["p"], "sillon_id": td["s1"], "paciente_id": td["pac_a"],
                "prestacion_id": td["prest_a"]}  # fmt: skip
    else:
        refs = {"profesional_id": td["prof_b"], "sillon_id": td["sillon_b"],
                "paciente_id": td["pac_b"], "prestacion_id": td["prest_b"]}  # fmt: skip
    with session_factory() as session:
        t = Turno(clinica_id=td[clinica], duracion_min=30, inicio=inicio,
                  fin=inicio + timedelta(minutes=30), **refs)  # fmt: skip
        session.add(t)
        session.commit()
        return t.id


def _saliente(td, turno_id: int, **over) -> MensajeWhatsApp:  # type: ignore[no-untyped-def]
    cols = {
        "clinica_id": td["a"], "turno_id": turno_id, "paciente_id": td["pac_a"],
        "plantilla": "recordatorio_24h", "direccion": "saliente", "telefono": "+5491100000001",
        "texto": "Recordatorio sintetico", "estado": "enviado", "costo_ars": Decimal("12.50"),
    }  # fmt: skip
    cols.update(over)
    return MensajeWhatsApp(**cols)


def test_upgrade_crea_tablas_y_siembra_textos(postgres_url) -> None:  # type: ignore[no-untyped-def]
    assert {"whatsapp_sesion", "mensaje_whatsapp", "plantilla_wa"} <= _tablas(postgres_url)
    assert set(_all(postgres_url, "SELECT clave FROM plantilla_wa")) == TEXTOS
    assert _all(postgres_url, "SELECT DISTINCT idioma FROM plantilla_wa") == ["es_AR"]
    tipo = _all(
        postgres_url,
        "SELECT data_type || ':' || numeric_precision || ',' || numeric_scale "
        "FROM information_schema.columns WHERE table_name='mensaje_whatsapp' "
        "AND column_name='costo_ars'",
    )
    assert tipo == ["numeric:12,2"]
    indices = set(_all(postgres_url, "SELECT indexname FROM pg_indexes"))
    assert {
        "ix_mensaje_whatsapp_clinica_turno_estado",
        "uq_mensaje_whatsapp_clinica_id_externo",
        "uq_mensaje_whatsapp_recordatorio_turno",
        "ix_mensaje_whatsapp_bandeja",
    } <= indices


def test_mensaje_valido_y_costo_exacto(session_factory, turnos_data) -> None:  # type: ignore[no-untyped-def]
    td = turnos_data
    tid = _turno(session_factory, td)
    with session_factory() as session:
        m = _saliente(td, tid, id_externo="FAKE-ok-1")
        session.add(m)
        session.commit()
        session.refresh(m)
        assert m.costo_ars == Decimal("12.50") and m.intentos == 0
        assert m.requiere_atencion is False


@pytest.mark.parametrize(
    "over",
    [
        {"estado": "volando"},
        {"direccion": "lateral"},
        {"costo_ars": Decimal("-1")},
        {"estado": "error"},  # error sin motivo
        {"motivo_error": "otro"},  # motivo sin error
        {"estado": "recibido"},  # saliente no puede estar recibido
        {"intencion": "confirmar"},  # intención solo en entrantes
        {"telefono": "1100000001"},  # no E.164
        {"telefono": None},  # sin teléfono solo con motivo sin_telefono
    ],
    ids=["estado", "direccion", "costo_negativo", "error_sin_motivo", "motivo_sin_error",
         "saliente_recibido", "intencion_saliente", "telefono_formato", "telefono_nulo"],
)
def test_checks_rechazan_valores_invalidos(session_factory, turnos_data, over) -> None:  # type: ignore[no-untyped-def]
    tid = _turno(session_factory, turnos_data)
    _falla(session_factory, _saliente(turnos_data, tid, **over), "23514")


def test_entrante_con_costo_rechazado(session_factory, turnos_data) -> None:  # type: ignore[no-untyped-def]
    m = _saliente(
        turnos_data, None, direccion="entrante", estado="recibido", plantilla=None,
        intencion="confirmar", costo_ars=Decimal("1.00"),
    )  # fmt: skip
    _falla(session_factory, m, "23514")


def test_id_externo_unico_por_clinica(session_factory, turnos_data) -> None:  # type: ignore[no-untyped-def]
    td = turnos_data
    with session_factory() as session:
        session.add(_saliente(td, _turno(session_factory, td), id_externo="FAKE-dup"))
        session.commit()
    _falla(session_factory, _saliente(td, _turno(session_factory, td), id_externo="FAKE-dup"),
           "23505")  # fmt: skip


def test_un_recordatorio_por_turno(session_factory, turnos_data) -> None:  # type: ignore[no-untyped-def]
    td = turnos_data
    tid = _turno(session_factory, td)
    with session_factory() as session:
        session.add(_saliente(td, tid))
        session.add(_saliente(td, tid, plantilla="confirmacion"))  # otro texto base: OK
        session.commit()
    _falla(session_factory, _saliente(td, tid), "23505")


def test_turno_de_otra_clinica_23503(session_factory, turnos_data) -> None:  # type: ignore[no-untyped-def]
    tid_b = _turno(session_factory, turnos_data, "b")
    _falla(session_factory, _saliente(turnos_data, tid_b), "23503")


def test_sesion_nombre_coherente(session_factory, turnos_data) -> None:  # type: ignore[no-untyped-def]
    a = turnos_data["a"]
    _falla(session_factory, WhatsappSesion(clinica_id=a, nombre="otra-cosa"), "23514")
    _falla(
        session_factory,
        WhatsappSesion(clinica_id=a, nombre=f"clinica-{a}", estado="volando"),
        "23514",
    )


def _transicion(td, turno_id: int, tipo: str, actor: int | None) -> TurnoTransicion:  # type: ignore[no-untyped-def]
    return TurnoTransicion(
        clinica_id=td["a"], turno_id=turno_id, desde="reservado", hacia="confirmado",
        actor_usuario_id=actor, actor_tipo=tipo,
    )  # fmt: skip


def test_actor_paciente_whatsapp(session_factory, turnos_data, auth_data) -> None:  # type: ignore[no-untyped-def]
    td = turnos_data
    actor = auth_data["user_ids"]["recepcion@test.test"]
    _falla(session_factory, _transicion(td, _turno(session_factory, td), "paciente_whatsapp",
                                        actor), "23514")  # fmt: skip
    with session_factory() as session:
        session.add(_transicion(td, _turno(session_factory, td), "paciente_whatsapp", None))
        session.commit()


def test_downgrade_con_transicion_whatsapp_falla_claro(cfg, postgres_url) -> None:  # type: ignore[no-untyped-def]
    # test_actor_paciente_whatsapp dejó una fila paciente_whatsapp (append-only, no se borra).
    with pytest.raises(Exception, match="paciente_whatsapp"):
        command.downgrade(cfg, "013_reserva_online")
    assert "mensaje_whatsapp" in _tablas(postgres_url)


def test_un_unico_head_y_014_encadenada_a_la_013() -> None:
    script = ScriptDirectory(str(BACKEND_DIR / "alembic"))
    assert len(script.get_heads()) == 1
    assert script.get_revision("014_whatsapp").down_revision == "013_reserva_online"


def test_downgrade_a_013_y_reupgrade_en_base_limpia() -> None:
    from testcontainers.postgres import PostgresContainer

    with PostgresContainer("postgres:16-alpine") as pg:
        url = pg.get_connection_url().replace("+psycopg2", "+psycopg")
        config = Config(ALEMBIC_INI)
        config.set_main_option("script_location", str(BACKEND_DIR / "alembic"))
        config.set_main_option("sqlalchemy.url", url)
        command.upgrade(config, "head")
        command.downgrade(config, "013_reserva_online")
        assert not {"whatsapp_sesion", "mensaje_whatsapp", "plantilla_wa"} & _tablas(url)
        check = _all(
            url,
            "SELECT pg_get_constraintdef(oid) FROM pg_constraint "
            "WHERE conname='ck_turno_transicion_actor_tipo_valido'",
        )
        assert "paciente_whatsapp" not in check[0]
        command.upgrade(config, "head")
        assert set(_all(url, "SELECT clave FROM plantilla_wa")) == TEXTOS
