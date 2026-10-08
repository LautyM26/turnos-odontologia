# Design

## Context

Ver `proposal.md` (Why). Estado actual: repo sin `backend/` ni `frontend/`; `openspec/` inicializado (schema spec-driven); KB con stack DECIDIDO (DD-08: Python + FastAPI + PostgreSQL 16 + React/Vite) y SaaS multi-tenant (DD-09). Restricciones: 17 reglas duras de `AGENTS.md` (extra=forbid, ruff, tsc estricto, solo `VITE_` en browser, sin secretos en repo, datos sintéticos), compact rules de `typescript-dev` / `docker-testcontainers` / `vitest`, y decisión usuario 2026-10-08 (WhatsApp por QR, contradice DD-02 — solo se refleja en `.env.example`, no se implementa cliente WA en este change).

## Goals / Non-Goals

**Goals:**

- Monorepo arranca de cero con `docker compose up` + dos comandos dev (backend/frontend) y CI verde en <10 min.
- Base multi-tenant lista para C-02: tenant header ya viaja desde el frontend; settings ya soportan `clinica_id`-scoped session futura sin refactor de config.
- Base de testing PG lista para C-02/C-05: fixture testcontainers + Alembic up/down verificados desde C-01.

**Non-Goals:**

- Ningún modelo de dominio, auth/RBAC, agenda, HC u odontograma (C-02 en adelante).
- Ningún cliente WhatsApp/MP/ARCA real — solo placeholders de env (la elección de librería QR es de C-15).
- Despliegue cloud, vault gestionado, firma de consentimientos (fases posteriores).

## Decisions

### D1 — Layout backend `backend/app/{domain,application,infrastructure}/` + `main.py` delgado

Estructura:

```
backend/
├── app/
│   ├── __init__.py
│   ├── main.py              # create_app(): router health, exception handlers, logging
│   ├── domain/              # vacío con __init__ + README (motor agenda/HC viven acá desde C-04/C-09)
│   ├── application/         # vacío con __init__ (casos de uso desde C-03+)
│   ├── infrastructure/
│   │   ├── __init__.py
│   │   ├── settings.py      # pydantic-settings, extra="forbid"
│   │   └── db.py            # engine/session factory (sin modelos aún)
│   └── api/
│       └── health.py        # GET /api/health
├── alembic/                 # env.py lee DATABASE_URL de settings; versions/ vacío
├── tests/
│   ├── test_health.py       # TestClient → 200 {"status":"ok"}
│   └── test_settings.py     # carga settings, forbid, sin secretos
├── pyproject.toml           # ruff + pytest config
└── .env.example
```

Alternativa descartada: layout plano `app/main.py` único — ahorra 3 archivos pero obliga a mover todo en C-02/C-04; el costo de crear dirs vacíos ahora es ~0.
Regla dura 4: `class Settings(BaseSettings): model_config = SettingsConfigDict(extra="forbid")`. Regla 5: snake_case + type hints + ruff limpio.

### D2 — Settings con 12 vars documentadas, QR-oriented en WhatsApp

`backend/.env.example` declara las 12 de `08` §Variables de entorno con placeholders (`changeme`, nunca valores reales). Diferencia vs KB: bloque WhatsApp con vars de sesión QR (`WHATSAPP_SESSION_DIR`, `WHATSAPP_RECONNECT`, `WHATSAPP_BACKUP_DIR`, `WHATSAPP_PHONE_NUMBER`) en lugar de `WHATSAPP_API_TOKEN`/`WHATSAPP_PHONE_ID`/`WHATSAPP_WEBHOOK_VERIFY` de API oficial; se comenta la contradicción con DD-02 inline. `frontend/.env.example` solo `VITE_API_BASE_URL` + `VITE_CLINICA_ID` (regla 12). `ARS_PRECIO_MENSAJE` queda como string `"0.00"` no sensible (precio transparente, se parsea a NUMERIC en C-08 — regla 7 anticipada). `RESERVA_PREBLOQUEO_MIN` default `15` (SU-04).

### D3 — Frontend Vite 8 + React 19 + TS 6 strict + Tailwind v4 CSS-first + Biome + Vitest 4

Aplicando `typescript-dev`: sin `useMemo/useCallback/memo`, sin `forwardRef`; Tailwind sin `tailwind.config.js` (tokens en `src/styles.css` con `@theme`, clases literales completas); `tsconfig` con `module: preserve` + `moduleResolution: bundler` + `paths @/*`; router (react-router) con `pages/` para reserva/cumplimiento/comprobantes (rutas públicas según `03`); cliente HTTP (`src/shared/api/client.ts`, fetch tipado) que inyecta `X-Clinica-Id` desde `import.meta.env` y usa `Promise.all` para futuras cargas paralelas de agenda (regla 13 anticipada como patrón). `vite.config.ts` con alias `@`, plugin Tailwind, `vitest run` en CI, entorno `jsdom` solo para tests de componentes.

### D4 — PostgreSQL vía `docker-compose.yml` + testcontainers solo en tests

`docker-compose.yml` (raíz): servicio `db` = `postgres:16-alpine`, volumen persistente, healthcheck `pg_isready`; servicio `api` opcional para dev (build backend, env_file). Aplicando `docker-testcontainers`: fixture pytest `module`-scoped `PostgresContainer("postgres:16-alpine")` que expone URL vía variable de entorno al test de migraciones Alembic up/down (smoke: `upgrade head` + `downgrade -1` + `upgrade head` contra contenedor). NUNCA SQLite (regla 9). Reutilización local con `withReuse(true)` documentada; CI usa DinD/Ryuk estándar.

### D5 — CI GitHub Actions con jobs paralelos + gates mínimos

`.github/workflows/ci.yml`: `backend` (python + `ruff check` + `pytest -q` smoke) y `frontend` (`npm ci` + `tsc --noEmit` + `vitest run` + `vite build`) en paralelo, sin caché exótica en C-01. Falla rápido: cualquier job rojo bloquea merge. Sin E2E browser en este change (eso es C-14/QA con `webapp-testing`).

### D6 — Seeds/tests solo sintéticos, sin datos de salud

Tests usan `clinica_id` ficticio y pacientes `seed=true` evidentes (`Paciente Sintético N`). Sin DNI/emails reales (regla 14). Ningún test toca HC (regla 15/16 aplican desde C-09; se dejan como constraints citadas en tasks).

## Risks / Trade-offs

- [Risk] QR de WhatsApp puede romper cambios futuros de env si C-15 elige librería con otras vars → Mitigación: vars QR de C-01 son placeholders documentados como "sujetas a C-15", con prefijo `WHATSAPP_` estable.
- [Risk] Contenedor PG en CI lento la primera vez (pull imagen) → Mitigación: `docker pull postgres:16-alpine` como paso previo + imagen `alpine` liviana; tests PG son 1 fixture module-scoped, no por test.
- [Risk] TS 6 defaults (`types: []`, `module preserve`) rompen a quien espera tsconfig clásico → Mitigación: tsconfig comentado + `tsc --noEmit` en CI lo detecta día 1.
- Trade-off aceptado: dirs `domain/application` vacíos generan 3 `__init__.py` + READMEs "placeholder intencional" — ruido mínimo a cambio de no reestructurar en C-02.

## Migration Plan

Greenfield: no hay datos ni despliegue previo. Apply crea directorios/archivos nuevos + workflow CI; rollback = borrar paths creados (listados en tasks.md). Alembic `versions/` vacío: `upgrade head` es no-op verificado contra testcontainers. Sin feature flags (nada que apagar).

## Open Questions

- Q1 (→ C-15): ¿qué librería/cliente QR (sesión, reconexión, backup) se adopta? No cambia specs de este change: solo puede renombrar placeholders `WHATSAPP_*`.
- Q2 (→ piloto, SU-04/SU-06): ¿`RESERVA_PREBLOQUEO_MIN=15` es el valor operativo real? Default propuesto; cambiarlo es un valor, no un cambio de diseño.
