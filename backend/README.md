# Backend — Turnos Odontología (C-01 foundation)

FastAPI mínima multi-tenant (aislamiento real desde C-02).

## Dev local

```bash
pip install fastapi uvicorn pydantic-settings sqlalchemy "psycopg[binary]" alembic pytest httpx "testcontainers[postgres]" ruff
python -m pytest backend/tests -q
ruff check backend
uvicorn app.main:app --reload --app-dir backend
```

`GET /api/health` → `200 {"status":"ok"}` (sin auth, sin DB).

## Migraciones

```bash
alembic -c backend/alembic.ini upgrade head
```

`versions/` vacío en C-01: upgrade es no-op verificado contra testcontainers (`postgres:16-alpine`).
NUNCA SQLite (regla dura 9).

## Config

Ver `backend/.env.example` (12 vars de arquitectura; WhatsApp QR según decisión 2026-10-08).
Settings con `extra="forbid"` (regla dura 4). NUMERIC/TIMESTAMPTZ obligatorios desde C-02 (regla 7).

## Estructura

`app/domain/` (vacío hasta C-04/C-09) · `app/application/` (vacío hasta C-03+) ·
`app/infrastructure/` (settings, db) · `app/api/` (health).
