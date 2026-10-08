"""Writer de auditoría HC (C-08 4.2): atomicidad, hora del servidor, diff sin PHI."""

from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from sqlalchemy import func, select, text

from app.api.deps import AuthContext
from app.domain.auditoria import writer
from app.domain.auditoria.models import AuditoriaHC
from app.domain.auditoria.writer import registrar_evento


def _auth(auth_data, email="odonto@test.test") -> AuthContext:  # type: ignore[no-untyped-def]
    return AuthContext(
        sub=auth_data["user_ids"][email],
        tenant_id=auth_data["clinica_a"],
        roles=("odontologo",),
        email=email,
        jti="j",
    )


@pytest.fixture()
def paciente_id(session_factory, auth_data) -> int:  # type: ignore[no-untyped-def]
    with session_factory() as session:
        pid = session.execute(
            text(
                "INSERT INTO paciente (clinica_id, nombre, apellido, dni, telefono, "
                "nombre_busqueda, es_seed) "
                "VALUES (:c, 'P', 'S', :d, '+5491155550001', 's p', true) "
                "RETURNING id"
            ),
            {"c": auth_data["clinica_a"], "d": f"9{uuid4().int % 10**7:07d}"},
        ).scalar()
        session.commit()
    return pid


def test_registrar_evento_inserta_con_hora_del_servidor(  # type: ignore[no-untyped-def]
    session_factory, auth_data, paciente_id
) -> None:
    with session_factory() as session:
        evento = registrar_evento(
            session,
            _auth(auth_data),
            "actualizar",
            "ficha",
            entidad_id=7,
            paciente_id=paciente_id,
            diff={"campos": ["alergias"], "version": 2},
        )
        session.commit()
        fila = session.get(AuditoriaHC, evento.id)
        assert fila.actor_usuario_id == auth_data["user_ids"]["odonto@test.test"]
        assert fila.actor_tipo == "usuario"
        assert fila.clinica_id == auth_data["clinica_a"]
        assert fila.diff == {"campos": ["alergias"], "version": 2}
        ahora = session.execute(select(func.now())).scalar()
        assert fila.created_at.tzinfo is not None
        assert abs(ahora - fila.created_at) < timedelta(minutes=1)
        assert abs(datetime.now(UTC) - fila.created_at) < timedelta(minutes=1)


def test_diff_por_defecto_vacio_y_booleano_consentimiento(  # type: ignore[no-untyped-def]
    session_factory, auth_data, paciente_id
) -> None:
    with session_factory() as session:
        e1 = registrar_evento(session, _auth(auth_data), "leer", "ficha", 1, paciente_id)
        e2 = registrar_evento(
            session,
            _auth(auth_data),
            "consentimiento_otorgado",
            "paciente",
            paciente_id,
            paciente_id,
            {"consentimiento_datos": True},
        )
        session.commit()
        assert e1.diff == {}
        assert e2.diff == {"consentimiento_datos": True}


def test_rollback_no_deja_evento(session_factory, auth_data, paciente_id) -> None:  # type: ignore[no-untyped-def]
    with session_factory() as session:
        n_antes = session.execute(select(func.count()).select_from(AuditoriaHC)).scalar()
        registrar_evento(session, _auth(auth_data), "crear", "paciente", paciente_id, paciente_id)
        session.rollback()
    with session_factory() as session:
        n_despues = session.execute(select(func.count()).select_from(AuditoriaHC)).scalar()
    assert n_despues == n_antes


@pytest.mark.parametrize(
    "diff",
    [
        {"alergias_texto": "penicilina"},
        {"telefono_valor": "+5491155550001"},
        {"campos": "alergias"},  # debe ser lista
        {"campos": ["alergias", 3]},
        {"version": "2"},
        {"consentimiento_datos": "si"},
    ],
)
def test_diff_no_permitido_levanta_value_error(  # type: ignore[no-untyped-def]
    session_factory, auth_data, paciente_id, diff
) -> None:
    with session_factory() as session, pytest.raises(ValueError):
        registrar_evento(
            session, _auth(auth_data), "actualizar", "ficha", 1, paciente_id, diff
        )


def test_writer_no_expone_update_ni_delete() -> None:
    publicos = {n for n in dir(writer) if not n.startswith("_")}
    assert "registrar_evento" in publicos
    assert not {n for n in publicos if "actualizar" in n or "borrar" in n or "delete" in n}
