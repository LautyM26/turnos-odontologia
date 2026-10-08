# Tasks: c-02-core-models-multitenancy

## 1. Base de persistencia y mixins

- [x] 1.1 Crear `infrastructure/persistence/base.py` (Base + naming convention FK) y mixins `TenantMixin`/`AuditMixin` con type hints + snake_case; verificar con `ruff check backend/app/infrastructure/persistence` limpio.
- [x] 1.2 Implementar `BaseRepository[T]` (filtro `clinica_id` + `is_active` por defecto, soft-delete) y `UnitOfWork` (commit/rollback por request); verificar con test unitario de filtro default (mock de sesión: `list()` sin `include_inactive` excluye inactivos).

## 2. Modelos core + CUIT

- [x] 2.1 Implementar `domain/core/cuit.py` (`normalizar_cuit`, `validar_cuit` módulo 11) + schemas Pydantic `ClinicaCreate/UsuarioCreate` con `extra="forbid"`; verificar con `pytest backend/tests/unit/test_cuit.py` (válido con guiones → normalizado, inválido → False, payload con campo extra → 422).
- [x] 2.2 Implementar modelos `Clinica`, `Rol`, `Usuario`, `UsuarioRol` (BIGINT IDENTITY, NUMERIC/TIMESTAMPTZ, TEXT+CHECK, `UNIQUE(cuit)`, `UNIQUE(clinica_id, LOWER(email))`, `UNIQUE(rol.clave)`); verificar con `ruff` + import smoke (`python -c "from app.domain.core.models import Clinica, Usuario, Rol, UsuarioRol"`).
- [x] 2.3 Agregar dependencia `require_tenant` (`X-Clinica-Id` → 422 sin header / 404 inexistente, con `TODO(C-03)`) + wiring de sesión scoped por request; verificar con test de dependencia (header ausente → 422, tenant inexistente → 404, existente → id inyectado).

## 3. Migración 001

- [x] 3.1 Escribir `alembic/versions/001_core_models.py` manual (tablas + índices D5 + checks D4) con `upgrade()`/`downgrade()` completos; verificar con `alembic upgrade head && alembic downgrade -1 && alembic upgrade head` en PG16 local sin errores.
- [x] 3.2 Verificar plan de índices con `EXPLAIN` (query por `clinica_id` + `is_active` usa index scan; `LOWER(email)` usa índice de expresión) y adjuntar salida al PR/apply log.

## 4. Seed mínimo

- [x] 4.1 Implementar `seed_core.py` (upsert por `cuit`/`clave`/`(clinica_id, lower(email))`, `seed=true`, ADMIN vía `SEED_ADMIN_PASSWORD` + bcrypt); verificar con doble ejecución sobre PG16 (conteos: 1 clínica, 4 roles, 1 admin, segunda corrida = no-op).
- [x] 4.2 Auditar que el seed usa solo datos sintéticos (grep de nombres/DNI reales = 0 coincidencias, clínica piloto ficticia) y que ningún secreto quedó en repo (grep `APP_USR-|EAAB|whsec_|BEGIN PRIVATE` = solo placeholders).

## 5. Tests de aislamiento (testcontainers, nunca SQLite)

- [x] 5.1 Test aislamiento multi-tenant con `PostgresContainer("postgres:16-alpine")` + Alembic up: crear A/B, escribir/leer con tenant A → 0 filas de B; verificar con `pytest backend/tests/integration/test_tenant_isolation.py -v` en verde.
- [x] 5.2 Test escritura sin `clinica_id` rechazada (integridad) + soft-delete (eliminado desaparece de listados pero persiste con `deleted_at`); verificar en el mismo run de integración.
- [x] 5.3 Gate final: `ruff check backend` + `pytest backend/tests/unit backend/tests/integration` + `alembic check` en verde antes de pedir review humana de seguridad (riesgos CRÍTICOS de design.md).

## Workflow follow-up

- Pedir revisión humana explícita de las decisiones D1/D2 (header temporal, sin RLS) antes del merge.
- Archivar con `/opsx:archive c-02-core-models-multitenancy` y marcar `[x]` C-02 en CHANGES.md.
- Desbloquea C-03 (auth/RBAC) como siguiente change.
