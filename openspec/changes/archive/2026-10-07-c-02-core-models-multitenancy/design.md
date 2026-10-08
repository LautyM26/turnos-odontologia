# Design: c-02-core-models-multitenancy

## Context

C-01 dejó: FastAPI app mínima (`GET /api/health`), `infrastructure/db.py` (engine/session factory placeholder sin modelos), `settings.py` (solo 3 vars cargadas de las 12 documentadas), Alembic inicializado sin revisiones, `compose` con PG16, frontend con header `X-Clinica-Id`. No existe ninguna tabla de dominio ni sesión scoped. Ver proposal.md (Why) para la motivación; ver `specs/tenant-isolation/spec.md` y `specs/core-models/spec.md` para el contrato de comportamiento.

Constraints duras aplicables: Pydantic `extra="forbid"`; montos NUMERIC ARS / tiempo TIMESTAMPTZ; toda tabla tenant-scoped con `clinica_id` + índice `(clinica_id, ...)` + test de aislamiento; tests PG solo con testcontainers `postgres:16-alpine`; snake_case + hints + ruff; solo datos sintéticos `seed=true`.

## Goals / Non-Goals

**Goals:**

- Esquema core mínimo que deja el SaaS arrancable y tenant-aislado: 4 tablas + mixins + repo/UoW + CUIT + migración 001 + seed.
- Aislamiento verificable por test (query cruzada = 0 filas) desde el día 1, sin esperar a C-03.
- Migración Alembic con `upgrade`/`downgrade` reales y seed idempotente apto para CI.

**Non-Goals:**

- Autenticación/autorización (C-03: JWT, `require_role`, blacklist). `require_tenant` aquí valida existencia, no identidad.
- RLS a nivel PostgreSQL (se difiere a hardening futuro — ver Riesgos).
- Endpoints CRUD admin, catálogo (C-04), pacientes (C-08), frontend.

## Decisions

### D1. Shared-schema con `clinica_id` discriminador (sin RLS en 001)

Toda tabla tenant-scoped vive en el schema `public` con `clinica_id BIGINT NOT NULL REFERENCES clinica(id)` y el aislamiento se aplica en la capa aplicación (scoped session + `require_tenant` + `BaseRepository` siempre filtrado). `clinica` misma es la única tabla no-scoped.

- Alternativas: (a) schema-por-tenant — rechazado: multiplica migraciones por clínica y complica seed/CI en MVP; (b) RLS desde el día 1 — rechazado para 001 por complejidad operativa (roles PG, `SET app.tenant`, políticas por tabla) sin auth real todavía; se re-evalúa como change de hardening con tests propios.
- Rationale: es el patrón SaaS mínimo que satisface DD-09/SU-01 con el tooling ya disponible (una DB, un Alembic, un compose).

### D2. `require_tenant` temporal basado en header (reemplazado en C-03)

Dependencia FastAPI que lee `X-Clinica-Id`, valida entero > 0, verifica existencia en `clinica` (404 si no), e inyecta el id en la sesión scoped. NO valida identidad: cualquier caller con el header pasa.

- Alternativa: esperar a JWT y salir sin tenant enforcement — rechazado: dejaría 001 sin ninguna barrera y todos los tests de aislamiento dependerían de C-03.
- Rationale: barrera mínima hoy, contrato claro de reemplazo: C-03 compara `tenant_id` del JWT contra el header y falla cerrado ante mismatch. La temporalidad queda marcada `TODO(C-03)` en código y en tasks.

### D3. PKs `BIGINT GENERATED ALWAYS AS IDENTITY`, sin UUID

Todas las PKs son `BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY`. Sin UUID (ningún id opaco/global lo requiere).

### D4. Tipos PG estrictos (regla dura 7)

- Dinero: `NUMERIC(12,2)` (`sena_monto_minimo`, futuros montos); moneda como `CHAR(3) DEFAULT 'ARS' CHECK (moneda = 'ARS')`.
- Tiempo: `TIMESTAMPTZ` (`created_at/updated_at/deleted_at` con `now()` como default — inicio de transacción, suficiente para auditoría MVP).
- Strings: `TEXT + CHECK(length(col) > 0 AND length(col) <= N)` en lugar de VARCHAR arbitrario.
- Estados/roles: `TEXT + CHECK IN (...)`, no ENUM (evita `ALTER TYPE` bloqueante al agregar valores).
- Email: `TEXT`, normalizado a minúsculas en aplicación + índice expresión `LOWER(email)`; las queries del repo usan la misma expresión.

### D5. Índices (supabase-postgres-best-practices)

- `usuario`: `UNIQUE (clinica_id, LOWER(email))` vía índice único de expresión; compuesto `(clinica_id, is_active)` + parcial `WHERE is_active` para listados calientes; FK `clinica_id` indexada (PG no auto-indexa FKs).
- `usuario_rol`: PK compuesta `(usuario_id, rol_id)` + índice `(rol_id)`.
- `rol`: `UNIQUE (clave)` (clave estable `admin|odontologo|recepcionista|paciente-enlace`, independiente del nombre mostrable).
- `clinica`: `UNIQUE (cuit)` (11 dígitos normalizados) + parcial `WHERE is_active`.
- Cobertura `INCLUDE` solo donde el apply demuestre hot-path (no especular en planning).

### D6. Mixins + Repository + UnitOfWork

- `TenantMixin`: `clinica_id: Mapped[int]` NOT NULL + FK; `AuditMixin`: `is_active bool default True`, `created_at/updated_at TIMESTAMPTZ server_default now() + onupdate`, `deleted_at nullable`. `Base` central con naming convention para constraints FK (`fk_%(table_name)s_%(column_0_name)s`).
- `BaseRepository[T]`: `get/list/add` siempre con filtro `clinica_id` + `is_active` por defecto (flag `include_inactive` opt-in); `delete` = soft-delete. Ningún acceso directo a `Session` fuera del repo en dominio.
- `UnitOfWork`: contexto por request (`commit`/`rollback`); la sesión scoped se cierra al final del request.
- Ubicación: modelos de dominio en `backend/app/domain/core/`, persistencia (Base, mixins, repository, uow) en `backend/app/infrastructure/persistence/`, validador en `backend/app/domain/core/cuit.py`.

### D7. Validador CUIT (módulo 11)

Función pura `normalizar_cuit(str) -> str` (strip de guiones/espacios, exige 11 dígitos) + `validar_cuit(str) -> bool` (pesos `5 4 3 2 7 6 5 4 3 2`, `dv = 11 - sum % 11`, mapeo `11→0, 10→9`). Sin dependencia de AFIP/ARCA (offline). Reusado por schema Pydantic y constraint de dominio.

### D8. Seed idempotente por claves naturales

Script `backend/app/infrastructure/persistence/seed_core.py::seed_core(session)` con upserts por clave natural (`clinica.cuit`, `rol.clave`, `usuario.(clinica_id, lower(email))`), marcado `seed=true` en clínica piloto. Password ADMIN via env `SEED_ADMIN_PASSWORD` (fallback solo-dev documentado, nunca en repo); hash bcrypt (`passlib[bcrypt]`). Re-ejecución = no-op verificable por conteos.

## Risks / Trade-offs

- **[CRÍTICO] `require_tenant` por header sin auth permite cross-tenant manual (spoofing)** → Mitigación: sin JWT no hay frontera real; se documenta como temporal, se marca `TODO(C-03)`, no se expone PII clínica más allá de core, y C-03 es GATE 2 inmediato con cross-check JWT-vs-header. **Requiere revisión humana antes del apply.**
- **[CRÍTICO] Sin RLS, un bug en un repo futuro puede filtrar cross-tenant** → Mitigación: regla dura 10 (toda tabla con `clinica_id` + índice + test de aislamiento) + `BaseRepository` como único acceso + test de query cruzada en CI. RLS se propone como change de hardening post-C-05. **Requiere revisión humana.**
- **Bcrypt costea CPU en seed/login** → factor de costo estándar (12), solo 1 hash en seed; aceptable.
- **`UNIQUE (clinica_id, LOWER(email))` es índice de expresión: queries deben usar `LOWER(email)`** → el repo encapsula la expresión; test lo cubre.
- **Soft-delete eterniza filas** → `deleted_at` + índice parcial excluye inactivos de hot-paths; purga/GDPR es F2.
- **`now()` = inicio de transacción, no wall-clock** → aceptado para auditoría MVP; `clock_timestamp()` solo si el apply demuestra necesidad.

## Migration Plan

1. `alembic revision --autogenerate` NO — revisión manual `001_core_models.py` (tablas `clinica`, `rol`, `usuario`, `usuario_rol` + índices D5 + checks D4), con `upgrade()` y `downgrade()` completos (downgrade dropea en orden inverso FK).
2. Deploy: `alembic upgrade head` (base vacía → 001 limpio) + `seed_core` (idempotente, re-ejecutable en cada deploy).
3. Rollback: `alembic downgrade -1` (solo viable pre-datos reales; con datos de piloto requiere backup — documentado en tasks).
4. Verificación: tests de aislamiento + CUIT + seed con testcontainers `postgres:16-alpine` + Alembic up/down en CI (ejecución en apply, no en propose).

## Open Questions

- Ninguna bloqueante. Forma exacta de `politica_sena` en `clinica` (columnas `sena_porcentaje NUMERIC` + `sena_monto_minimo NUMERIC` + `sena_obligatoria_siempre bool` vs JSONB) se fija en apply sin cambiar specs (el contrato solo exige "política de seña" configurable por clínica).
- RLS como change de hardening dedicado (post-C-05) — propuesta para el roadmap, no para este change.
