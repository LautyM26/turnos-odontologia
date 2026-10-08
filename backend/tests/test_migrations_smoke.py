"""Alembic + PostgreSQL smoke via testcontainers (NUNCA SQLite). Synthetic DB only."""

import pytest
from testcontainers.postgres import PostgresContainer


@pytest.fixture(scope="module")
def postgres_url() -> str:
    with PostgresContainer("postgres:16-alpine") as pg:
        yield pg.get_connection_url().replace("+psycopg2", "+psycopg")


def test_postgres_container_accepts_connections(postgres_url: str) -> None:
    import psycopg

    with psycopg.connect(postgres_url.replace("+psycopg", "")) as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT 1")
            assert cur.fetchone() == (1,)


def test_alembic_upgrade_head_is_noop_on_empty_versions(postgres_url: str) -> None:
    from alembic.config import Config

    from alembic import command

    cfg = Config("backend/alembic.ini")
    cfg.set_main_option("sqlalchemy.url", postgres_url)
    command.upgrade(cfg, "head")
    command.downgrade(cfg, "base")
    command.upgrade(cfg, "head")
