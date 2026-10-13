"""Fixtures PG16 + Alembic para tests de integración (NUNCA SQLite)."""

from pathlib import Path

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from testcontainers.postgres import PostgresContainer

BACKEND_DIR = Path(__file__).resolve().parents[2]
ALEMBIC_INI = str(BACKEND_DIR / "alembic.ini")


@pytest.fixture(scope="module")
def postgres_url():
    """Levanta postgres:16-alpine y aplica Alembic a head."""
    with PostgresContainer("postgres:16-alpine") as pg:
        url = pg.get_connection_url().replace("+psycopg2", "+psycopg")
        from alembic.config import Config

        from alembic import command

        cfg = Config(ALEMBIC_INI)
        cfg.set_main_option("script_location", str(BACKEND_DIR / "alembic"))
        cfg.set_main_option("sqlalchemy.url", url)
        command.upgrade(cfg, "head")
        yield url


@pytest.fixture(scope="module")
def session_factory(postgres_url):
    """Session factory contra el contenedor migrado."""
    engine = create_engine(postgres_url)
    return sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


TEST_JWT_SECRET = "test-sintetico-32-chars-minimo-0000"
TEST_PASSWORD = "Secreta123-sintetica"


@pytest.fixture(scope="module")
def password_hash() -> str:
    """Un hash bcrypt (cost 12) reutilizado por los usuarios sintéticos."""
    import bcrypt

    return bcrypt.hashpw(TEST_PASSWORD.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


@pytest.fixture(scope="module")
def auth_data(session_factory, password_hash):  # type: ignore[no-untyped-def]
    """Seed C-02 + clínica B + usuarios por rol. Solo datos sintéticos."""
    from sqlalchemy import select

    from app.domain.core.models import Clinica, Rol, Usuario, UsuarioRol
    from app.infrastructure.persistence.seed_core import SEED_ADMIN_EMAIL, seed_core

    with session_factory() as session:
        seed_core(session)
        admin = session.scalars(
            select(Usuario).where(Usuario.email == SEED_ADMIN_EMAIL)
        ).one()
        # Clave conocida para login en tests (hash sintético, cost 12).
        admin.password_hash = password_hash
        clinica_a = admin.clinica_id
        roles = {r.clave: r.id for r in session.scalars(select(Rol)).all()}

        b = Clinica(nombre="Clinica B Sintetica", cuit="30567812347", es_seed=True)
        session.add(b)
        session.flush()

        created = {}

        def _mk(email: str, clinica_id: int, claves: list[str]) -> int:
            user = Usuario(
                clinica_id=clinica_id,
                email=email,
                password_hash=password_hash,
                nombre="Usuario Sintetico",
            )
            session.add(user)
            session.flush()
            for clave in claves:
                session.add(
                    UsuarioRol(
                        usuario_id=user.id, rol_id=roles[clave], clinica_id=clinica_id
                    )
                )
            created[email] = user.id
            return user.id

        _mk("recepcion@test.test", clinica_a, ["recepcionista"])
        _mk("odonto@test.test", clinica_a, ["odontologo"])
        _mk("multi@test.test", clinica_a, ["odontologo", "recepcionista"])
        _mk("admin-b@test.test", b.id, ["admin"])
        session.commit()
        return {
            "clinica_a": clinica_a,
            "clinica_b": b.id,
            "admin_email": SEED_ADMIN_EMAIL,
            "user_ids": created,
        }


def make_test_client(session_factory, monkeypatch, *extra_routers):  # type: ignore[no-untyped-def]
    """TestClient con sesión PG real, secreto sintético y rate-limit limpio."""
    from fastapi.testclient import TestClient

    from app.domain.auth.ratelimit import reset_login_limits
    from app.infrastructure.db import get_session
    from app.main import create_app

    monkeypatch.setenv("JWT_SECRET_KEY", TEST_JWT_SECRET)
    app = create_app()
    for router in extra_routers:
        app.include_router(router)

    def _override():  # type: ignore[no-untyped-def]
        owned = session_factory()
        try:
            yield owned
        finally:
            owned.close()

    app.dependency_overrides[get_session] = _override
    reset_login_limits()
    return TestClient(app)


@pytest.fixture()
def client(session_factory, monkeypatch):  # type: ignore[no-untyped-def]
    """Cliente base (solo routers reales: health + auth)."""
    return make_test_client(session_factory, monkeypatch)



def bearer(client, email: str) -> dict[str, str]:  # type: ignore[no-untyped-def]
    """Login real y header Authorization para el usuario sintético ``email``."""
    resp = client.post("/api/auth/login", json={"email": email, "password": TEST_PASSWORD})
    assert resp.status_code == 200, resp.text
    return {"Authorization": f"Bearer {resp.json()['access_token']}"}


@pytest.fixture(scope="module")
def catalogo_data(session_factory, auth_data):  # type: ignore[no-untyped-def]
    """Catálogo sintético en A y B sobre ``auth_data`` (C-04).

    A: sillones S1..S3, profesional P (vinculado a ``odonto@test.test``), Q sin vínculo,
    una prestación. B: un sillón, un profesional, una prestación y un bloqueo.
    """
    from datetime import UTC, datetime
    from decimal import Decimal

    from app.domain.agenda.models import (
        Bloqueo,
        Prestacion,
        Profesional,
        SillonRecurso,
    )

    a, b = auth_data["clinica_a"], auth_data["clinica_b"]
    out: dict = {"a": a, "b": b}
    with session_factory() as session:
        sillones = [
            SillonRecurso(clinica_id=a, nombre=f"Sillon Fixture {n}", tipo="sillon")
            for n in (1, 2, 3)
        ]
        sillon_b = SillonRecurso(clinica_id=b, nombre="Sillon B Fixture", tipo="sillon")
        prof_p = Profesional(
            clinica_id=a,
            nombre="Profesional P Sintetico",
            matricula="FIX-P",
            usuario_id=auth_data["user_ids"]["odonto@test.test"],
        )
        prof_q = Profesional(clinica_id=a, nombre="Profesional Q Sintetico", matricula="FIX-Q")
        prof_b = Profesional(clinica_id=b, nombre="Profesional B Sintetico", matricula="FIX-B")
        prest_a = Prestacion(
            clinica_id=a, nombre="Prestacion A Fixture", duracion_min=30,
            precio_referencia=Decimal("1000.00"),
        )  # fmt: skip
        prest_b = Prestacion(
            clinica_id=b, nombre="Prestacion B Fixture", duracion_min=45,
            precio_referencia=Decimal("2000.00"),
        )  # fmt: skip
        session.add_all([*sillones, sillon_b, prof_p, prof_q, prof_b, prest_a, prest_b])
        session.flush()
        bloq_b = Bloqueo(
            clinica_id=b,
            profesional_id=prof_b.id,
            inicio=datetime(2031, 1, 1, 10, tzinfo=UTC),
            fin=datetime(2031, 1, 1, 11, tzinfo=UTC),
            motivo="fixture B",
        )
        session.add(bloq_b)
        session.commit()
        out.update(
            sillones=[s.id for s in sillones], sillon_b=sillon_b.id,
            prof_p=prof_p.id, prof_q=prof_q.id, prof_b=prof_b.id,
            prest_a=prest_a.id, prest_b=prest_b.id, bloqueo_b=bloq_b.id,
        )  # fmt: skip
    return out


def crear_usuario(session_factory, password_hash: str, clinica_id: int, email: str, claves):  # type: ignore[no-untyped-def]
    """Crea un usuario sintético activo con los roles ``claves``; devuelve su id."""
    from sqlalchemy import select

    from app.domain.core.models import Rol, Usuario, UsuarioRol

    with session_factory() as session:
        roles = {r.clave: r.id for r in session.scalars(select(Rol)).all()}
        user = Usuario(
            clinica_id=clinica_id, email=email, password_hash=password_hash, nombre="Sintetico"
        )
        session.add(user)
        session.flush()
        for clave in claves:
            session.add(UsuarioRol(usuario_id=user.id, rol_id=roles[clave], clinica_id=clinica_id))
        session.commit()
        return user.id


# --- C-08: pacientes / ficha / adjuntos --------------------------------------------------


@pytest.fixture(autouse=True)
def _adjuntos_en_tmp(tmp_path, monkeypatch):  # type: ignore[no-untyped-def]
    """Los adjuntos de los tests viven en un tmp dir, nunca dentro del repo."""
    monkeypatch.setenv("ADJUNTOS_STORAGE_DIR", str(tmp_path / "adjuntos"))


@pytest.fixture(scope="module")
def staff_c08(session_factory, auth_data, password_hash):  # type: ignore[no-untyped-def]
    """Usuarios extra de A: admin+odontólogo (dueño) y paciente-enlace; odontólogo extra."""
    a = auth_data["clinica_a"]
    return {
        "dueno": crear_usuario(
            session_factory, password_hash, a, "dueno@test.test", ["admin", "odontologo"]
        ),
        "enlace": crear_usuario(
            session_factory, password_hash, a, "enlace@test.test", ["paciente-enlace"]
        ),
        "odonto2": crear_usuario(
            session_factory, password_hash, a, "odonto2@test.test", ["odontologo"]
        ),
    }


_dni_seq = iter(range(90_000_000, 99_999_999))


def dni_sintetico() -> str:
    """DNI sintético único (rango 9xxxxxxx)."""
    return str(next(_dni_seq))


def alta_paciente(client, headers, **extra):  # type: ignore[no-untyped-def]
    """POST /api/pacientes con datos sintéticos; devuelve la response."""
    payload = {
        "nombre": "Paciente",
        "apellido": "Sintetico",
        "dni": dni_sintetico(),
        "telefono": "+5491155550001",
    }
    payload.update(extra)
    return client.post("/api/pacientes", json=payload, headers=headers)


# --- C-05 recorte: turnos sin solapamientos -------------------------------------------------


def paciente_sintetico(clinica_id: int, **over):  # type: ignore[no-untyped-def]
    """Paciente ORM sintético (DNI 9xxxxxxx, teléfono ficticio); regla dura 14."""
    from app.domain.pacientes.models import Paciente

    cols = {
        "nombre": "Paciente", "apellido": "Sintetico", "dni": dni_sintetico(),
        "telefono": "+5491155550001", "nombre_busqueda": "sintetico paciente", "es_seed": True,
    }  # fmt: skip
    cols.update(over)
    return Paciente(clinica_id=clinica_id, **cols)


@pytest.fixture(scope="module")
def turnos_data(session_factory, auth_data, catalogo_data, password_hash):  # type: ignore[no-untyped-def]
    """Habilitaciones, pacientes y recursos extra para turnos (sobre ``catalogo_data``).

    A: P y Q habilitados en S1 y S2 (P NO en S3); R con ``agenda_activa=false`` habilitado en
    S1; pacientes activo/inactivo; prestación inactiva. B: profesional habilitado en su sillón,
    paciente y un recepcionista propio (``recepcion-b@test.test``).
    """
    from decimal import Decimal  # noqa: I001

    from app.domain.agenda.models import Prestacion, Profesional, ProfesionalSillon

    a, b = catalogo_data["a"], catalogo_data["b"]
    s1, s2, s3 = catalogo_data["sillones"]
    p, q = catalogo_data["prof_p"], catalogo_data["prof_q"]
    with session_factory() as session:
        prof_r = Profesional(
            clinica_id=a, nombre="Profesional R Sintetico", matricula="FIX-R",
            agenda_activa=False,
        )  # fmt: skip
        prest_inactiva = Prestacion(
            clinica_id=a, nombre="Prestacion inactiva", duracion_min=30,
            precio_referencia=Decimal("500.00"), is_active=False,
        )  # fmt: skip
        pac_a = paciente_sintetico(a)
        pac_a_inactivo = paciente_sintetico(a, is_active=False)
        pac_b = paciente_sintetico(b)
        session.add_all([prof_r, prest_inactiva, pac_a, pac_a_inactivo, pac_b])
        session.flush()
        habilitaciones = [(a, p, s1), (a, p, s2), (a, q, s1), (a, q, s2), (a, prof_r.id, s1)]
        habilitaciones.append((b, catalogo_data["prof_b"], catalogo_data["sillon_b"]))
        session.add_all(
            ProfesionalSillon(clinica_id=c, profesional_id=pr, sillon_id=si)
            for c, pr, si in habilitaciones
        )
        session.commit()
        out = dict(
            catalogo_data, s1=s1, s2=s2, s3=s3, p=p, q=q, prof_r=prof_r.id,
            prest_inactiva=prest_inactiva.id, pac_a=pac_a.id,
            pac_a_inactivo=pac_a_inactivo.id, pac_b=pac_b.id,
        )  # fmt: skip
    crear_usuario(session_factory, password_hash, b, "recepcion-b@test.test", ["recepcionista"])
    return out
