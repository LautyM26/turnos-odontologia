# Tasks

## 1. Backend FastAPI mínimo (salud + config)

- [x] 1.1 Crear layout `backend/app/{domain,application,infrastructure}/` + `api/` + `main.py` con `GET /api/health` → verificar `GET /api/health` responde `200 {"status":"ok"}` vía TestClient en local.
- [x] 1.2 Implementar `infrastructure/settings.py` (pydantic-settings, `extra="forbid"`, `DATABASE_URL`/`APP_BASE_URL`/`RESERVA_PREBLOQUEO_MIN=15`) + logger + handler global de excepciones (`detail` JSON, sin trazas al cliente) → verificar `pytest backend/tests/test_settings.py -q` pasa (forbid + defaults + sin secretos).
- [x] 1.3 Agregar `backend/tests/test_health.py` (200 sin auth, 404 JSON con `detail`, 500 genérico sin traza) + `pyproject.toml` (ruff + pytest) → verificar `ruff check backend` limpio y `pytest backend/tests -q` verde.

## 2. Alembic + PostgreSQL + base testcontainers

- [x] 2.1 Inicializar Alembic (`env.py` lee `DATABASE_URL` de settings, `versions/` vacío) + `docker-compose.yml` raíz (`db: postgres:16-alpine` con healthcheck `pg_isready`, servicio `api` dev opcional) → verificar `alembic upgrade head` es no-op y `docker compose config` valida.
- [x] 2.2 Agregar fixture pytest module-scoped `PostgresContainer("postgres:16-alpine")` + smoke Alembic up/down contra contenedor (NUNCA SQLite) → verificar el smoke pasa en local con Docker y documentar `withReuse(true)` + pull previo para CI.

## 3. Frontend React + Vite + TS + Tailwind

- [x] 3.1 Scaffold Vite 8 + React 19 + TS 6 strict (`module: preserve`, `moduleResolution: bundler`, `paths @/*`), router con `features/` + `pages/` (rutas públicas reserva/cumplimiento/comprobantes), Tailwind v4 CSS-first (`src/styles.css` con `@theme`, sin `tailwind.config.js`), Biome → verificar `tsc --noEmit` limpio y `vite build` genera `dist/`.
- [x] 3.2 Implementar `src/shared/api/client.ts` (fetch tipado, inyecta `X-Clinica-Id` desde `import.meta.env`, patrón `Promise.all` para cargas paralelas) + smoke Vitest (header presente, solo env `VITE_` en browser, sin secretos) con entorno `jsdom` → verificar `vitest run` verde.
- [x] 3.3 Respetar reglas frontend en todo el scaffold (sin `useMemo/useCallback/memo`, sin `forwardRef`, PascalCase, tokens semánticos, sin `bg-${x}` dinámico, componentes con `React.ComponentProps`) → verificar `tsc` + `build` + `vitest run` en un solo pase.

## 4. Variables de entorno y reglas duras transversales

- [x] 4.1 Escribir `backend/.env.example` y `frontend/.env.example` con las 12 variables de `08` (placeholders `changeme`; bloque WhatsApp QR: `WHATSAPP_SESSION_DIR`/`WHATSAPP_RECONNECT`/`WHATSAPP_BACKUP_DIR`/`WHATSAPP_PHONE_NUMBER` + comentario de contradicción DD-02) → verificar grep de secretos (`APP_USR-`, `EAAB`, `whsec_`, `-----BEGIN`) retorna 0 fuera de placeholders y las 12 vars están presentes.
- [x] 4.2 Verificar reglas duras aplicables en el diff (conventional-commits en mensajes, snake_case + hints + ruff, NUMERIC/TIMESTAMPTZ citados como constraint futura, `clinica_id` + índice reservados para C-02, datos de test sintéticos `seed=true`) → verificar checklist de reglas en el resumen del apply.

## 5. CI e integración final

- [x] 5.1 Crear `.github/workflows/ci.yml` (jobs paralelos: backend `ruff + pytest smoke`, frontend `tsc + vitest run + build`) → verificar workflow sintácticamente válido y ambos jobs en paralelo.
- [x] 5.2 Pase de integración: `docker compose up db` + backend dev + frontend dev + `GET /api/health` 200 de punta a punta, luego `openspec validate --change c-01-foundation-setup` → verificar validate sin errores y health E2E local.

## Workflow follow-up

- Aplicar con `/opsx:apply c-01-foundation-setup` (NO ejecutado en este propose).
- Archivar con `/opsx:archive c-01-foundation-setup` y marcar `[x] C-01` en CHANGES.md tras review.
