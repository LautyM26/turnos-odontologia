# Design — c-04-clinica-catalogo

## Context

Ver `proposal.md` (Why). Estado actual (C-03 archivado):

- Persistencia: `Base` con naming convention, `TenantMixin` (`clinica_id` FK RESTRICT) + `AuditMixin` (`is_active`, `created_at`, `updated_at`, `deleted_at` TIMESTAMPTZ), `BaseRepository` (scoped por `clinica_id`, activos por defecto, `delete` lógico), `UnitOfWork`.
- Migraciones: `001_core_models` (PK `BIGINT GENERATED ALWAYS AS IDENTITY` vía `_pk_identity()`, flags `is_active`/`es_seed`), `002_token_blacklist` (head actual).
- Auth/RBAC: `get_current_user` → `AuthContext(sub, tenant_id, roles, ...)`, `require_tenant_checked`, `require_role/require_admin` y `require_own_agenda` en `app/api/permissions.py`, este último con un resolver inyectable `set_resolver_agenda_propia(fn)` que hoy es `None` → falla cerrado.
- Seed: `seed_core` crea clínica piloto (CUIT `30123456781`, `es_seed=True`) + 4 roles + admin.
- Tests: `tests/integration/conftest.py` levanta `postgres:16-alpine` por módulo y aplica Alembic a head; `make_test_client(...)` monta la app real con sesión PG; `auth_data` crea usuarios por rol en clínicas A y B.
- `app/domain/README.md` reserva `domain/agenda/` para el motor de agenda (arquitectura `08`).

Trabajo en paralelo: C-08 (pacientes) usará la migración `004` con `down_revision = "003_clinica_catalogo"`.

## Goals / Non-Goals

**Goals:**
- Dejar el catálogo con integridad multi-tenant garantizada por la DB (no solo por la app).
- Dejar a C-05 dos contratos estables: `calcular_fin(inicio, duracion_min)` y la consulta de bloqueos solapados.
- Cerrar el hook de agenda propia de C-03 sin cambiar su firma.

**Non-Goals:**
- No modelo `Turno`, ni huecos, ni exclusion constraints (C-05).
- No UI (C-07/C-10).
- No horarios laborales/recurrencia de bloqueos (bloqueo semanal "todos los martes"): cada bloqueo es un rango concreto; recurrencia queda para F2 o C-05 si el piloto la exige.
- No validar que un bloqueo nuevo choque con turnos existentes (no hay turnos aún; C-05 decide la política).
- No "equipo" como tercer recurso simultáneo del turno: `equipo` es solo un tipo de `SillonRecurso` en MVP.

## Decisions

1. **Módulo `app/domain/agenda/`** (`models.py`, `schemas.py`, `duracion.py`, `bloqueos.py`, `servicio.py`), routers `app/api/admin_catalogo.py`, `app/api/catalogo.py`, `app/api/bloqueos_propios.py`, seed en `app/infrastructure/persistence/seed_catalogo.py`.
   - Sigue la estructura del `08` (`domain/agenda`). Alternativa `domain/catalogo/` descartada: C-05 vive en el mismo bounded context y reusa modelos sin imports cruzados.

2. **PK `BIGINT GENERATED ALWAYS AS IDENTITY`**, igual que 001 (`_pk_identity()`); en ORM `Identity(always=True)` para que el modelo coincida con la migración. Join `profesional_sillon` con PK compuesta `(profesional_id, sillon_id)` como `usuario_rol`.
   - UUID descartado: inconsistente con 001/002 y sin requisito de ids públicos (la reserva pública de C-06 usará tokens propios).

3. **Convenciones heredadas, no las del roadmap literal:** el flag de alta/baja es `is_active` (de `AuditMixin`, el "activo" del roadmap) y la marca de seed es `es_seed` (como `clinica.es_seed`, el "seed=true" del roadmap). `agenda_activa` del profesional es un flag de negocio distinto de `is_active` (profesional existente que temporalmente no recibe turnos).

4. **Tablas (migración 003):**

   | Tabla | Columnas clave | Constraints / índices |
   |---|---|---|
   | `profesional` | `nombre`, `matricula`, `especialidad?`, `agenda_activa` (true), `tercerizado` (false), `usuario_id?`, `es_seed` | `CHECK length(nombre) 1..200`, `CHECK length(matricula) 1..50`; `UNIQUE (clinica_id, id)`; uq parcial `(clinica_id, lower(matricula)) WHERE is_active`; uq parcial `(clinica_id, usuario_id) WHERE usuario_id IS NOT NULL AND is_active`; FK compuesta `(clinica_id, usuario_id) → usuario(clinica_id, id)`; `ix (clinica_id, is_active)` |
   | `sillon_recurso` | `nombre`, `tipo`, `es_seed` | `CHECK tipo IN ('sillon','box','equipo')` (TEXT+CHECK, no ENUM); `UNIQUE (clinica_id, id)`; uq parcial `(clinica_id, lower(nombre)) WHERE is_active`; `ix (clinica_id, is_active)` |
   | `prestacion` | `nombre`, `duracion_min INTEGER`, `precio_referencia NUMERIC(12,2)`, `es_seed` | `CHECK duracion_min BETWEEN 5 AND 480`, `CHECK precio_referencia >= 0`; `ix (clinica_id, is_active)` |
   | `profesional_sillon` | `profesional_id`, `sillon_id`, `clinica_id` + audit | PK `(profesional_id, sillon_id)`; FKs compuestas `(clinica_id, profesional_id)` y `(clinica_id, sillon_id)`; `ix (clinica_id, sillon_id)` |
   | `bloqueo` | `profesional_id?`, `sillon_id?`, `inicio`, `fin` TIMESTAMPTZ, `motivo`, `rango` generada | ver decisión 6 |

   - Todas con `clinica_id` NOT NULL + `AuditMixin` (regla dura 10). Todo FK indexado (PG no lo hace solo).
   - **Integridad tenant por FK compuesta**: `UNIQUE (clinica_id, id)` en `profesional`, `sillon_recurso` y (nuevo, aditivo) `usuario`; las referencias usan `(clinica_id, x_id)`. Así un sillón de B no puede quedar habilitado para un profesional de A ni aunque el servicio falle. Alternativa (solo validación en app) descartada por regla dura 10 + skill postgres "tenant isolation CRITICAL". `MATCH SIMPLE` deja pasar las columnas opcionales nulas (`usuario_id`, `profesional_id`/`sillon_id` de bloqueo).
   - Unicidad **parcial `WHERE is_active`**: permite re-crear una matrícula/nombre después de una baja lógica. Nombre de prestación no es único (dos variantes con igual nombre y distinta duración son válidas en el piloto).

5. **Montos:** `NUMERIC(12,2)` en DB, `Decimal` en ORM (`Mapped[Decimal]`) y en Pydantic (`max_digits=12, decimal_places=2, ge=0`) → `422` si hay más decimales o es negativo. Pydantic v2 serializa `Decimal` como string JSON (`"15000.50"`), sin pérdida (regla dura 7). No se replica el `float` del type hint de `Clinica.sena_*` (deuda de C-02, fuera de alcance).

6. **Bloqueo como rango semiabierto con columna generada:**
   - Columnas `inicio`, `fin` TIMESTAMPTZ NOT NULL + `rango tstzrange GENERATED ALWAYS AS (tstzrange(inicio, fin, '[)')) STORED` (en ORM `Computed`, solo lectura).
   - `CHECK (fin > inicio)`, `CHECK (fin - inicio <= interval '31 days')`, `CHECK (NOT (profesional_id IS NOT NULL AND sillon_id IS NOT NULL))` (alcance único), `CHECK length(motivo) 1..200`.
   - Índices: GiST `(clinica_id, rango) WHERE is_active` (requiere `btree_gist` para el `bigint`), btree `(clinica_id, profesional_id)`, `(clinica_id, sillon_id)`, `(clinica_id, is_active)`.
   - Por qué columna generada y no solo `inicio/fin`: C-05 compara con `&&` contra `tstzrange` del turno usando el mismo índice GiST; semiabierto `[)` hace que bloqueos contiguos a un turno no se consideren superpuestos (spec "Rango contiguo no se superpone"). Alternativa `tstzrange` como única columna descartada: complica Pydantic/ORM y la API expone `inicio/fin` de todos modos.
   - Bloqueos superpuestos entre sí se permiten (inocuo; la consulta devuelve todos).

7. **Consulta de solapamiento (contrato para C-05)** en `domain/agenda/bloqueos.py`:
   `bloqueos_solapados(session, clinica_id, inicio, fin, profesional_id, sillon_id) -> list[Bloqueo]` con
   `WHERE clinica_id = :c AND is_active AND rango && tstzrange(:i, :f, '[)') AND ((profesional_id IS NULL AND sillon_id IS NULL) OR profesional_id = :p OR sillon_id = :s)`.
   C-05 la invoca dentro de la misma transacción que inserta el turno (el anti-solapamiento entre turnos es su exclusion constraint; el chequeo de bloqueos es de dominio, como dice el roadmap C-05).

8. **Tiempo y duración solo en servidor (regla dura 6):**
   - `calcular_fin(inicio: datetime, duracion_min: int) -> datetime` puro en `domain/agenda/duracion.py`: `ValueError` si `inicio` es naive o `duracion_min` fuera de 5..480; suma en tiempo absoluto (`timedelta`), por lo que cruces de medianoche y offsets funcionan sin tabla de zonas.
   - Schemas de entrada usan `AwareDatetime` de Pydantic → `422` ante fechas sin offset; se normalizan a UTC antes de persistir. Ningún schema acepta `fin` calculado ni `duracion` en payloads de turno (C-05 hereda los schemas de este patrón).

9. **Schemas Pydantic** (todos con base `extra="forbid"`, regla dura 4): `{Profesional,Sillon,Prestacion,Bloqueo}{Create,Update,Out}` + `HabilitacionIn(sillon_ids: list[int])` + `Pagina[T](items, next_cursor)`. `Update` = todos los campos opcionales, aplicado con `model_dump(exclude_unset=True)`. Ningún payload acepta `clinica_id`, `id`, `es_seed`, `is_active` ni `rango`.

10. **Endpoints y RBAC:**

    | Ruta | Método(s) | Roles | Notas |
    |---|---|---|---|
    | `/api/admin/profesionales` | GET (lista), POST | admin | `?limit&after_id&incluir_inactivos` |
    | `/api/admin/profesionales/{id}` | GET, PATCH, DELETE | admin | detalle incluye `sillon_ids` |
    | `/api/admin/profesionales/{id}/sillones` | PUT | admin | reemplaza set, atómico |
    | `/api/admin/sillones[/{id}]` | GET, POST, PATCH, DELETE | admin | idem |
    | `/api/admin/prestaciones[/{id}]` | GET, POST, PATCH, DELETE | admin | idem |
    | `/api/admin/bloqueos[/{id}]` | GET, POST, PATCH, DELETE | admin | lista con `desde/hasta/profesional_id/sillon_id` |
    | `/api/catalogo/{profesionales,sillones,prestaciones}` | GET | admin, recepcionista, odontologo | solo activos, paginado |
    | `/api/profesionales/{profesional_id}/bloqueos` | GET, POST | admin, odontologo + `require_own_agenda` | POST fuerza `profesional_id` del path |
    | `/api/profesionales/{profesional_id}/bloqueos/{id}` | DELETE | admin, odontologo + `require_own_agenda` | `404` si el bloqueo no es de ese profesional |

    - Tenant siempre de `require_tenant_checked` (JWT autoritativo + cross-check header). Recepcionista queda fuera de bloqueos: la matriz `03` le da "CRUD turnos", no bloqueos; `require_own_agenda` la dejaría pasar, por eso se antepone `require_role("admin", "odontologo")`.
    - Errores: id ajeno/inexistente → `404`; referencia (sillón/profesional/usuario) ajena o inactiva → `422` (validada en servicio antes del INSERT); unicidad → `IntegrityError` capturado → `409`. DELETE → `204`. Ningún router nuevo entra en `PUBLIC_PREFIXES`.

11. **Paginación por keyset** (skill postgresql-optimization): `WHERE id > :after_id ORDER BY id LIMIT :limit + 1`; si vuelven `limit+1` filas, `next_cursor = id` de la fila `limit`. `limit` 1..200 (default 50) validado por `Query(ge=1, le=200)` → `422`. Se añade `BaseRepository.page(after_id, limit, include_inactive, *filtros)` (aditivo, no cambia métodos existentes). Offset descartado.

12. **Vínculo Usuario→Profesional:** columna `profesional.usuario_id` (nullable). Resolver `profesional_de_usuario(session, usuario_id) -> int | None` (profesional activo con ese `usuario_id`) registrado en `create_app()` vía `set_resolver_agenda_propia`. La firma del hook de C-03 no cambia; la FK compuesta garantiza que el profesional es de la misma clínica que el usuario. Se valida que el usuario exista, esté activo y sea del tenant (→ `422`) y que no tenga otro profesional activo (→ `409`). No se exige que el usuario tenga rol `odontologo` (un admin-dueño también atiende).

13. **Seed sintético (regla dura 14, PA-09 parcial):** `seed_catalogo(session) -> dict[str, int]` idempotente por clave natural, sobre la clínica piloto de `seed_core` (debe correr después):
    - Sillón `"Sillón 1 (seed)"` tipo `sillon`.
    - Profesional `"Profesional Ejemplo (seed)"`, matrícula `"SEED-0001"`, sin usuario vinculado, habilitado en el sillón seed.
    - Prestaciones: `"Consulta y diagnóstico (seed)"` 30 min / 20000.00; `"Limpieza y profilaxis (seed)"` 45 min / 30000.00; `"Obturación simple (seed)"` 60 min / 45000.00.
    - Todos `es_seed=True`. `borrar_seed_catalogo(session, clinica_id)` borra físicamente solo filas `es_seed` (y sus habilitaciones/bloqueos dependientes): es utilitario de infraestructura para retirar datos de ejemplo antes del go-live, no un camino de dominio (el dominio sigue siendo baja lógica). Valores de duración/precio **sintéticos**; el catálogo real del consultorio piloto los reemplaza (SU-06).

14. **Migración `003_clinica_catalogo`** (`revision = "003_clinica_catalogo"`, `down_revision = "002_token_blacklist"`):
    - up: `CREATE EXTENSION IF NOT EXISTS btree_gist` → `uq_usuario_clinica_id` en `usuario` → `profesional` → `sillon_recurso` → `prestacion` → `profesional_sillon` → `bloqueo` + índices.
    - down: orden inverso; drop de `uq_usuario_clinica_id`. **No** hace `DROP EXTENSION` (inocua, la necesita C-05 y otro objeto podría depender); `IF NOT EXISTS` mantiene up/down/up idempotente.

15. **Tests (strict TDD, nunca SQLite):**
    - Unit (sin DB): `tests/unit/test_agenda_duracion.py`, `tests/unit/test_agenda_schemas.py`, `tests/unit/test_repository_page.py` (construcción del statement).
    - Integración PG16 (`postgres:16-alpine` vía fixtures existentes): `test_migration_003.py`, `test_catalogo_db_constraints.py`, `test_admin_catalogo.py`, `test_admin_bloqueos.py`, `test_bloqueos_solapados.py`, `test_bloqueos_propios.py`, `test_catalogo_lectura.py`, `test_seed_catalogo.py`. Fixture nuevo `catalogo_data` (reusa `auth_data`) con profesionales/sillones en A y B y el vínculo del usuario `odonto@test.test`.

## Risks / Trade-offs

- [Riesgo] El resolver de agenda propia es estado global de módulo; `test_rbac.py` lo pone en `None` → Mitigación: `create_app()` lo registra en cada construcción y los tests de C-04 crean su propio client; se documenta que `set_resolver_agenda_propia(None)` en tests debe restaurar el real.
- [Riesgo] `btree_gist` no permitido en algún Postgres gestionado → Mitigación: está en la allowlist de los proveedores habituales (RDS, Cloud SQL, Supabase) y C-05 lo necesita igual; la migración falla en claro si no está.
- [Riesgo] `UNIQUE (clinica_id, id)` nuevo en `usuario` (tabla de 001) → Mitigación: aditivo, no falla con datos existentes (`id` ya es único); C-08 debe reutilizarlo y no recrearlo (nombre fijo `uq_usuario_clinica_id`).
- [Riesgo] Columna generada `rango` + `updated_at` vía ORM: un PATCH debe recargar la fila para devolver `rango` actualizado → Mitigación: `session.refresh(obj)` tras flush en el servicio; `rango` no se expone en la API (solo `inicio/fin`).
- [Riesgo] Bloqueo creado sobre turnos ya reservados (desde C-05) no los cancela → Mitigación: Non-Goal explícito; C-05 define si avisa/bloquea.
- [Trade-off] Alcance único por bloqueo (profesional XOR sillón XOR clínica) → un "profesional P en sillón S" requiere dos bloqueos; aceptado por semántica clara de la consulta.
- [Trade-off] Paginación por `id` y no por `inicio` en bloqueos → el admin filtra por ventana; orden cronológico queda para la vista de agenda (C-07).
- [Trade-off] Duración 5..480 min fijada por CHECK → cambiar el rango exige migración; aceptado (cubre de control rápido a cirugía larga).

## Migration Plan

- `alembic upgrade head` aplica 003 sobre 002; solo tablas nuevas + un UNIQUE aditivo en `usuario` → sin downtime ni migración de datos.
- Después: `seed_core` + `seed_catalogo` en entornos dev/piloto (nunca datos reales).
- Rollback: `alembic downgrade 002_token_blacklist` (drop de tablas del catálogo; se pierde el catálogo cargado) + redeploy anterior. Si C-08 ya aplicó 004, primero se baja 004.

## Supuestos / Preguntas abiertas

- **S1 (PA-09 parcial):** duraciones y precios del seed son sintéticos; el catálogo real del piloto se carga luego por API admin o reemplazando el seed (no cambia specs).
- **S2:** rango de duración 5..480 min y tope de bloqueo 31 días son supuestos razonables para un consultorio; ajustables por migración sin cambiar el diseño.
- **S3:** el odontólogo no gestiona bloqueos de sillón ni de clínica, y la recepcionista no gestiona bloqueos (lectura literal de la matriz `03`). Si el piloto pide que recepción cargue feriados, se agrega `recepcionista` a `/api/admin/bloqueos` sin cambiar el modelo.
- **S4:** el vínculo usuario→profesional no exige rol `odontologo` en el usuario.
- **Abierta:** ¿bloqueos recurrentes (almuerzo diario) en MVP? Hoy se cargan como rangos sueltos; si el piloto lo exige se agrega una regla de recurrencia que expanda a filas `bloqueo` (no cambia la consulta de solapamiento).
