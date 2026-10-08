# Proposal

## Why

El repo hoy no tiene código ejecutable (sin `backend/` ni `frontend/`): ningún change posterior (C-02 modelos multi-tenant, C-03 auth, etc.) puede construirse ni verificarse sin un monorepo base, una app mínima que arranque y una CI que falle rápido. C-01 sienta ese cimiento con governance BAJO y sin dependencias.

## What Changes

- Scaffolding monorepo: `backend/app/{domain,application,infrastructure}/`, `frontend/src/{features,shared,pages}/`, `jobs/`, `docs-legales/`.
- Backend Python + FastAPI mínimo con `GET /api/health`, settings por env (`DATABASE_URL`, `APP_BASE_URL`, `RESERVA_PREBLOQUEO_MIN`), logger estructurado, handler global de excepciones, Alembic inicializado, `docker-compose.yml` con PostgreSQL 16.
- Frontend React + Vite + TypeScript con router, cliente HTTP tipado que envía tenant header (`X-Clinica-Id`), Tailwind v4 CSS-first.
- `.env.example` en cada sub-proyecto con las 12 variables de `08_arquitectura_propuesta.md` §Variables de entorno; ningún secreto en repo (solo placeholders).
- CI GitHub Actions con jobs paralelos backend (`ruff` + `pytest` smoke) y frontend (`tsc` + `build` + `vitest run`).
- Tests mínimos: health check 200, carga de settings sin secretos hardcodeados, smoke de cliente HTTP (tenant header presente).
- Supuesto abierto documentado (ver Impact): variables WhatsApp del `.env.example` reflejan la DECISIÓN USUARIO 2026-10-08 (QR con número dedicado: sesión/reconexión/backup) y NO la API oficial Meta (DD-02/RN-WA-01), que queda marcada como contradicha pendiente de actualización en KB/CHANGES fase 5.

## Capabilities

### New Capabilities

- `platform-health`: expone el estado operativo mínimo del backend (`GET /api/health`) para CI, Docker y futuros gates de despliegue.
- `platform-config`: carga de configuración por variables de entorno con valores por defecto seguros, sin secretos hardcodeados ni en repo; base para las 12 variables de arquitectura.

### Modified Capabilities

Ninguna (no existen specs previas; `openspec list --specs` retorna vacío).

## Impact

- Afecta: raíz del repo (nuevos `backend/`, `frontend/`, `jobs/`, `docs-legales/`, `docker-compose.yml`, workflows CI). No modifica código existente porque no hay.
- APIs: nueva `GET /api/health` (único endpoint público de este change).
- Dependencias nuevas: FastAPI + Uvicorn + Pydantic Settings + Alembic + psycopg (backend); React 19 + Vite 8 + TS 6 strict + Tailwind v4 + Vitest 4 (frontend); `postgres:16-alpine` (dev + testcontainers).
- Contradicción conocida QR vs DD-02: `02_descripcion_general.md` §Integraciones y DD-02 exigen API oficial Meta y prohíben QR; la decisión usuario 2026-10-08 (AGENTS.md regla 17) invierte esto (QR con número dedicado, asumir riesgo bloqueo Meta/ToS). Este change NO resuelve la contradicción — solo la refleja en `.env.example` (vars `WHATSAPP_*` orientadas a sesión QR: p. ej. `WHATSAPP_SESSION_DIR`, `WHATSAPP_RECONNECT`, backup — en lugar de `WHATSAPP_API_TOKEN`/`WHATSAPP_PHONE_ID` de API oficial) y la deja como supuesto abierto a documentar en KB/CHANGES fase 5. C-15/C-17 quedan en espera de esa actualización.
- Riesgos: ninguno bloqueante; governance BAJO.
