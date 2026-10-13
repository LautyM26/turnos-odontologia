# Turnos Odontología — SaaS multi-tenant (AR)

Sistema de gestión de turnos para clínicas odontológicas argentinas: agenda con
anti-solapamiento duro, reserva online sin cuenta, odontograma + HC append-only,
presupuesto → plan → turnos, caja con Mercado Pago, factura electrónica ARCA,
WhatsApp por QR con número dedicado y cumplimiento Ley 25.326/26.529.

## Stack (DD-08)

Backend Python + FastAPI · PostgreSQL 16 · Frontend React + Vite + TS · Alembic.

## Quick start (C-01)

```bash
docker compose up db            # PostgreSQL 16 en :5432
uvicorn app.main:app --reload --app-dir backend   # API en :8000
cd frontend && npm install && npm run dev          # UI en :5173
curl http://localhost:8000/api/health             # {"status":"ok"}
```

## Cómo correr los tests

Requisitos: Python 3.12+ y **Docker Desktop corriendo** (los tests de integración levantan
PostgreSQL 16 real con testcontainers; nunca SQLite).

```bash
python -m venv .venv
# Windows: .venv\Scripts\activate   ·   Linux/macOS: source .venv/bin/activate
pip install fastapi uvicorn "pydantic[email]" pydantic-settings sqlalchemy "psycopg[binary]" \
  alembic bcrypt PyJWT slowapi phonenumbers python-multipart \
  pytest httpx "testcontainers[postgres]" ruff
docker version                      # debe mostrar la sección "Server"
python -m pytest backend/tests -q   # unit + integración
ruff check backend
```

Solo los tests del change `crear-turno-sin-solapamientos` (un archivo por grupo de escenarios del spec
`openspec/specs/appointments/spec.md`):

```bash
python -m pytest backend/tests/unit/test_turno_schemas.py backend/tests/unit/test_turno_errores.py \
  backend/tests/integration/test_migracion_005.py backend/tests/integration/test_turnos_db_constraints.py \
  backend/tests/integration/test_turnos_api.py backend/tests/integration/test_turnos_concurrencia.py -v
```

## Documentación del trabajo (Metodología I)

- `docs/discovery/` — informe de Discovery (`.md` + `.pdf`) y checklist de 11 puntos.
- `knowledge-base/` — 10 archivos canónicos · `CHANGES.md` — roadmap · `AGENTS.md`/`CLAUDE.md` — reglas del agente.
- `openspec/changes/archive/` — changes archivados (el del ciclo OPSX de la Etapa 6: `crear-turno-sin-solapamientos`).

## Estructura

`backend/` · `frontend/` · `jobs/` · `docs-legales/` · `knowledge-base/` ·
`openspec/` · `CHANGES.md` (roadmap de 19 changes) · `AGENTS.md` (17 reglas duras).

## Estado

Archivados: C-01, C-02, C-03, C-04, C-08 y `crear-turno-sin-solapamientos` (recorte de C-05). Ver `CHANGES.md` y `openspec/changes/archive/`.
