# Proposal: c-02-core-models-multitenancy

## Why

Sin modelos base multi-tenant no existe ningún dominio posterior: C-03 (auth/RBAC con `tenant_id`), C-04/C-08 (catálogos y pacientes scoped por clínica) y todo el SaaS dependen de `Clinica` como tenant raíz, `Usuario/Rol` como identidad y una garantía de aislamiento por query. C-01 dejó el scaffolding (FastAPI + Alembic + PG16) sin ninguna tabla de dominio; este change cierra GATE 1 y desbloquea el camino crítico.

## What Changes

- Modelos SQLAlchemy base en `backend/app/domain/` + `infrastructure/persistence/`:
  - `Clinica` (nombre, CUIT con validador AR, domicilio, datos fiscales ARCA, moneda ARS default, política de seña JSON/columnas).
  - `Usuario` (`clinica_id` FK NOT NULL, email normalizado único por tenant, password hash — sin autenticación aún, solo almacenamiento —, activo), `Rol` (4 filas seed: `admin`, `odontologo`, `recepcionista`, `paciente-enlace`), `UsuarioRol` (join N—M).
  - `TenantMixin` (`clinica_id` obligatorio) + `AuditMixin` (`is_active`, `created_at`, `updated_at`, `deleted_at` TIMESTAMPTZ); soft-delete por defecto (nunca DELETE físico en dominio).
- Aislamiento por tenant a nivel query: scoped session / dependencia FastAPI `require_tenant` (lee `X-Clinica-Id`, valida existencia; C-03 agregará JWT después — aquí solo header + existencia, documentado como decisión de seguridad temporal).
- `BaseRepository[T]` genérico + `UnitOfWork` (commit/rollback por request).
- Validador CUIT argentino (módulo 11, acepta `XX-XXXXXXXX-X` y dígitos; normaliza a 11 dígitos).
- Migración Alembic 001: tablas core + índices `(clinica_id, ...)`, `LOWER(email)` por tenant, parcial `WHERE is_active`.
- Seed mínimo idempotente (`seed=true`): 1 clínica piloto sintética, 4 roles, 1 usuario ADMIN (hash bcrypt, credencial solo por env en apply, nunca en repo).
- Tests (solo planificación aquí, ejecución en apply): aislamiento multi-tenant (query cruzada = 0 filas) con testcontainers `postgres:16-alpine` + Alembic up/down; CUIT inválido rechazado; seed re-ejecutable sin duplicados.
- NO incluye: JWT/login (C-03), catálogo profesional/sillón/prestación (C-04), pacientes (C-08), endpoints CRUD admin (solo modelos + repo + migración + seed).

## Capabilities

### New Capabilities

- `tenant-isolation`: garantía de aislamiento multi-tenant — todo dato tenant-scoped exige `clinica_id`, índice `(clinica_id, ...)` y queries scoped; `require_tenant` rechaza requests sin tenant válido; soft-delete excluye inactivos por defecto.
- `core-models`: entidades base `Clinica`, `Usuario`, `Rol`, `UsuarioRol` con constraints (CUIT válido, email único por tenant, moneda ARS), `BaseRepository`/`UnitOfWork`, migración 001 y seed mínimo idempotente.

### Modified Capabilities

- Ninguna. `platform-health` y `platform-config` no cambian (health sigue sin auth/tenant; settings sin secretos nuevos).

## Impact

- Código: nuevos `backend/app/domain/core/`, `backend/app/infrastructure/persistence/` (models, mixins, repository, uow, validators/cuit.py, seed), `backend/alembic/versions/001_core_models.py`; sin cambios en `frontend/` (el header `X-Clinica-Id` ya existe desde C-01) ni en specs main.
- APIs: ninguna ruta nueva salvo dependencia interna `require_tenant` (sin endpoint público; C-03 la conectará a JWT).
- Dependencias: requiere C-01 archivado (Alembic, compose PG16, settings). Bloquea C-03.
- Governance CRÍTICO: decisiones de seguridad (header vs JWT temporal, sin RLS en 001, hash bcrypt) documentadas en design.md para revisión humana antes del apply.
