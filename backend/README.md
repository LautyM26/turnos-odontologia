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

`app/domain/` (core, auth, agenda desde C-04) · `app/application/` (vacío hasta C-03+) ·
`app/infrastructure/` (settings, db) · `app/api/` (health).

## Catálogo y bloqueos (C-04)

Migración `003_clinica_catalogo` (sobre `002_token_blacklist`): `profesional`, `sillon_recurso`,
`prestacion`, `profesional_sillon`, `bloqueo` (+ `btree_gist` y `uq_usuario_clinica_id`).
C-08 apila su `004` sobre `003_clinica_catalogo` y **reutiliza** `uq_usuario_clinica_id`
(no lo recrea).

| Endpoint | Rol |
|----------|-----|
| `/api/admin/{profesionales,sillones,prestaciones,bloqueos}[/{id}]` (CRUD, baja lógica, paginado por cursor `limit`≤200 / `after_id`) | `admin` |
| `PUT /api/admin/profesionales/{id}/sillones` (reemplaza habilitación, atómico) | `admin` |
| `GET /api/catalogo/{profesionales,sillones,prestaciones}` (solo activos) | `admin`, `recepcionista`, `odontologo` |
| `GET/POST /api/profesionales/{id}/bloqueos`, `DELETE .../{bloqueo_id}` (agenda propia) | `admin`, `odontologo` dueño |

Errores: ajeno/inexistente `404`, referencia inválida `422`, unicidad (matrícula, nombre de
sillón, usuario ya vinculado) `409`. Contratos para C-05: `calcular_fin(inicio, duracion_min)`
(`app/domain/agenda/duracion.py`) y `bloqueos_solapados(...)` (`app/domain/agenda/bloqueos.py`).

Seed sintético: ejecutar `seed_core` y **luego** `seed_catalogo` (`app/infrastructure/persistence/`);
`borrar_seed_catalogo` retira solo filas `es_seed` antes del go-live (PA-09 / SU-06).
