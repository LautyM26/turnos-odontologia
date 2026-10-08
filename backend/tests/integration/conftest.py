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

