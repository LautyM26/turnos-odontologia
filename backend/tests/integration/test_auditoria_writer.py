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


# --- C-09 2.3: odontograma / evolucion / corregir ------------------------------------------


@pytest.mark.parametrize(
    ("accion", "entidad", "diff"),
    [
        ("actualizar", "odontograma", {"odontograma_id": 3, "version": 2, "campos": ["16", "21"]}),
        ("crear", "odontograma", {"odontograma_id": 1, "version": 1, "campos": ["denticion"]}),
        ("crear", "evolucion", {"evolucion_id": 11}),
        ("corregir", "evolucion", {"evolucion_id": 12, "corrige_a_id": 11}),
        ("leer", "evolucion", {}),
        ("leer", "odontograma", {"version": 0}),
    ],
)
def test_acepta_entidades_acciones_y_claves_de_c09(  # type: ignore[no-untyped-def]
    session_factory, auth_data, paciente_id, accion, entidad, diff
) -> None:
    with session_factory() as session:
        evento = registrar_evento(
            session, _auth(auth_data), accion, entidad, 5, paciente_id, diff
        )
        session.commit()
        fila = session.get(AuditoriaHC, evento.id)
        assert (fila.accion, fila.entidad, fila.diff) == (accion, entidad, diff)


@pytest.mark.parametrize(
    "diff",
    [
        {"texto": "caries en 16"},
        {"motivo_correccion": "pieza mal indicada"},
        {"piezas": {"16": {"estado": {"codigo": "corona"}}}},
        {"evolucion_id": "11"},  # debe ser int
        {"corrige_a_id": True},  # bool no es id
        {"odontograma_id": 1.5},
    ],
)
def test_sigue_rechazando_texto_clinico_y_tipos_invalidos_en_c09(  # type: ignore[no-untyped-def]
    session_factory, auth_data, paciente_id, diff
) -> None:
    with session_factory() as session, pytest.raises(ValueError):
        registrar_evento(session, _auth(auth_data), "crear", "evolucion", 1, paciente_id, diff)


def test_db_acepta_corregir_y_rechaza_acciones_desconocidas(  # type: ignore[no-untyped-def]
    session_factory, auth_data, paciente_id
) -> None:
    from sqlalchemy.exc import IntegrityError

    insert = (
        "INSERT INTO auditoria_hc (clinica_id, paciente_id, actor_usuario_id, actor_tipo, "
        "accion, entidad, entidad_id) VALUES (:c, :p, :u, 'usuario', :a, :e, 1)"
    )
    base = {
        "c": auth_data["clinica_a"], "p": paciente_id,
        "u": auth_data["user_ids"]["odonto@test.test"],
    }  # fmt: skip
    with session_factory() as session:
        session.execute(text(insert), {**base, "a": "corregir", "e": "evolucion"})
        session.commit()
        with pytest.raises(IntegrityError):
            session.execute(text(insert), {**base, "a": "borrar", "e": "evolucion"})
        session.rollback()
        with pytest.raises(IntegrityError):
            session.execute(text(insert), {**base, "a": "leer", "e": "entidad_inexistente"})
        session.rollback()


# --- C-18 2.3: consentimiento / firmar / auditoría administrativa ------------------------------


@pytest.mark.parametrize(
    ("accion", "diff"),
    [
        ("crear", {"consentimiento_id": 4, "texto_version": "1.0"}),
        ("firmar", {"consentimiento_id": 4, "texto_version": "1.0"}),
        ("leer", {}),
    ],
)
def test_acepta_consentimiento_y_firmar(  # type: ignore[no-untyped-def]
    session_factory, auth_data, paciente_id, accion, diff
) -> None:
    with session_factory() as session:
        evento = registrar_evento(
            session, _auth(auth_data), accion, "consentimiento", 4, paciente_id, diff
        )
        session.commit()
        fila = session.get(AuditoriaHC, evento.id)
        assert (fila.accion, fila.entidad, fila.diff) == (accion, "consentimiento", diff)


@pytest.mark.parametrize(
    "diff",
    [
        {"tipo": "extraccion"},
        {"texto": "consiento"},
        {"firmante_nombre": "Nombre Sintetico"},
        {"firmante_dni": "90000001"},
        {"consentimiento_id": "4"},  # debe ser int
        {"texto_version": 1},  # debe ser str
    ],
)
def test_diff_de_consentimiento_descarta_tipo_texto_y_firmante(  # type: ignore[no-untyped-def]
    session_factory, auth_data, paciente_id, diff
) -> None:
    with session_factory() as session, pytest.raises(ValueError):
        registrar_evento(
            session, _auth(auth_data), "firmar", "consentimiento", 1, paciente_id, diff
        )


@pytest.mark.parametrize(
    ("accion", "entidad_id", "diff"),
    [
        ("usuario_crear", 9, {"roles": ["odontologo"]}),
        ("usuario_roles", 9, {"roles_anteriores": ["recepcionista"], "roles": ["odontologo"]}),
        ("exportar", None, {"formato": "csv", "conteos": {"pacientes": 3}, "faltantes": [7]}),
    ],
)
def test_registrar_evento_admin_guarda_con_allowlist(  # type: ignore[no-untyped-def]
    session_factory, auth_data, accion, entidad_id, diff
) -> None:
    from app.domain.auditoria.models import AuditoriaAdmin
    from app.domain.auditoria.writer import registrar_evento_admin

    with session_factory() as session:
        evento = registrar_evento_admin(
            session, _auth(auth_data), accion, entidad_id, diff, ip="127.0.0.1"
        )
        session.commit()
        fila = session.get(AuditoriaAdmin, evento.id)
        assert fila.actor_usuario_id == auth_data["user_ids"]["odonto@test.test"]
        assert fila.clinica_id == auth_data["clinica_a"]
        assert (fila.accion, fila.entidad_id, fila.diff, fila.ip) == (
            accion, entidad_id, diff, "127.0.0.1",
        )  # fmt: skip
        assert fila.created_at is not None


@pytest.mark.parametrize(
    "diff",
    [
        {"email": "alguien@example.com"},
        {"password": "x"},
        {"nombre": "Nombre"},
        {"roles": "admin"},  # debe ser lista
        {"conteos": {"pacientes": "3"}},  # valores int
    ],
)
def test_evento_admin_descarta_email_password_y_tipos_invalidos(  # type: ignore[no-untyped-def]
    session_factory, auth_data, diff
) -> None:
    from app.domain.auditoria.writer import registrar_evento_admin

    with session_factory() as session, pytest.raises(ValueError):
        registrar_evento_admin(session, _auth(auth_data), "usuario_roles", 1, diff)


def test_evento_admin_accion_invalida(session_factory, auth_data) -> None:  # type: ignore[no-untyped-def]
    from app.domain.auditoria.writer import registrar_evento_admin

    with session_factory() as session, pytest.raises(ValueError):
        registrar_evento_admin(session, _auth(auth_data), "borrar_todo", None)


def test_writer_admin_no_expone_update_ni_delete() -> None:
    publicos = {n for n in dir(writer) if not n.startswith("_")}
    assert "registrar_evento_admin" in publicos
    assert not {n for n in publicos if "actualizar" in n or "borrar" in n or "delete" in n}


# --- C-19 2.3: entidad receta ---------------------------------------------------------------


def test_acepta_receta_con_ids_y_partner(  # type: ignore[no-untyped-def]
    session_factory, auth_data, paciente_id
) -> None:
    diff = {"receta_id": 5, "evolucion_id": 9, "partner": "fake"}
    with session_factory() as session:
        evento = registrar_evento(
            session, _auth(auth_data), "crear", "receta", 5, paciente_id, diff
        )
        session.commit()
        fila = session.get(AuditoriaHC, evento.id)
        assert (fila.accion, fila.entidad, fila.diff) == ("crear", "receta", diff)


@pytest.mark.parametrize(
    "diff",
    [
        {"items": [{"nombre_generico": "x"}]},
        {"diagnostico": "texto clinico"},
        {"id_externo": "FAKE-123"},
        {"receta_id": "5"},  # debe ser int
        {"partner": 3},  # debe ser str
    ],
)
def test_diff_de_receta_descarta_items_diagnostico_e_id_externo(  # type: ignore[no-untyped-def]
    session_factory, auth_data, paciente_id, diff
) -> None:
    with session_factory() as session, pytest.raises(ValueError):
        registrar_evento(session, _auth(auth_data), "crear", "receta", 1, paciente_id, diff)
