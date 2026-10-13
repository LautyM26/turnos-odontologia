# Design — crear-turno-sin-solapamientos

## Context

Ver `proposal.md` (Why) y `explore.md` (exploración completa con referencias a archivo:línea). Estado relevante del código (C-04 y C-08 archivados):

- Migraciones `001`…`004_pacientes_ficha` (head). `003` ya crea la extensión `btree_gist` (y no la elimina en downgrade). Helpers `_audit_columns()`, `_pk_identity()`, `_clinica_fk()` en `004` (patrón a copiar).
- `app/domain/agenda/models.py`: `Profesional` (`agenda_activa`, `UNIQUE (clinica_id, id)`), `SillonRecurso` (`UNIQUE (clinica_id, id)`), `Prestacion` (`duracion_min` 5..480, **sin** `UNIQUE (clinica_id, id)`), `ProfesionalSillon` (habilitación N–M con FKs compuestas + `AuditMixin`), `Bloqueo` (columna generada `rango tstzrange(inicio, fin, '[)')`). `Paciente` en `domain/pacientes/models.py` con `uq_paciente_clinica_id`.
- Contratos que C-04 dejó para este change: `calcular_fin(inicio, duracion_min)` (`domain/agenda/duracion.py`) y `bloqueos_solapados(session, clinica_id, inicio, fin, profesional_id, sillon_id)` (`domain/agenda/bloqueos.py`).
- Errores de dominio `CatalogoError` / `NoEncontrado` (404) / `Conflicto` (409) / `ReferenciaInvalida` (422) en `domain/agenda/servicio.py`, con handler global en `main.py`; `_commit()` ya traduce SQLSTATE `23505` → 409.
- RBAC: `require_role(*claves)` + `require_tenant_checked` (JWT autoritativo, header `X-Clinica-Id` solo cross-check).
- Tests: `tests/integration/conftest.py` levanta `postgres:16-alpine` por módulo y aplica Alembic a head; fixtures `auth_data` (clínicas A/B, usuarios por rol), `catalogo_data` (sillones S1..S3, profesionales P/Q, prestación de 30 min en A; datos de B), `make_test_client`, `bearer`, `alta_paciente`. `catalogo_data` **no** crea habilitaciones profesional↔sillón: hay que agregarlas en una fixture propia de este change.

Restricción de entorno: Docker Desktop no está instalado en la máquina de desarrollo (explore §5); sin él solo corren los tests unitarios.

## Goals / Non-Goals

**Goals:**
- Que la base de datos sea el árbitro final del anti-solapamiento entre turnos (no la aplicación), incluso con requests concurrentes.
- Reutilizar los contratos de C-04 sin modificarlos.
- Dejar el modelo `Turno` listo para que el resto de C-05 (transiciones, sobreturnos, huecos) se agregue **sin** volver a migrar las exclusion constraints.

**Non-Goals (de diseño, además de los Non-goals del proposal):**
- Sin `SELECT … FOR UPDATE`, advisory locks ni niveles de aislamiento `SERIALIZABLE`.
- Sin trigger que impida crear un bloqueo sobre turnos existentes ni turno sobre bloqueo creado concurrentemente (ver Riesgos).
- Sin columnas `sena_*`, `motivo_sobreturno`, `hold_expires_at`, `public_token` (las agregan C-05 completo / C-06 / C-11).
- Sin auditoría de transiciones (no hay transiciones); `created_at`/`updated_at` de `AuditMixin` alcanzan.

## Decisions

1. **Rango semiabierto como columna generada** (igual que `Bloqueo`): `rango tstzrange GENERATED ALWAYS AS (tstzrange(inicio, fin, '[)')) STORED`, `Computed` de solo lectura en el ORM.
   - `[10:00, 10:30)` y `[10:30, 11:00)` no se superponen con `&&` → cubre el escenario "Turno que empieza justo cuando termina otro". Y es el mismo tipo de rango que usa `bloqueos_solapados`, así que turno-contiguo-a-bloqueo también funciona.
   - Alternativa: exclusion sobre `tstzrange(inicio, fin)` como expresión en la constraint. Descartada: duplica la expresión en dos constraints y en consultas futuras (huecos), y rompe la simetría con `Bloqueo`.

2. **Dos exclusion constraints GiST parciales** (requiere `btree_gist`, ya presente):
   ```sql
   EXCLUDE USING gist (clinica_id WITH =, profesional_id WITH =, rango WITH &&)
     WHERE (is_active AND estado IN ('reservado','confirmado','asistido'))   -- ex_turno_profesional_rango
   EXCLUDE USING gist (clinica_id WITH =, sillon_id WITH =, rango WITH &&)
     WHERE (is_active AND estado IN ('reservado','confirmado','asistido'))   -- ex_turno_sillon_rango
   ```
   - "Activos" = `reservado`, `confirmado`, `asistido`. `cancelado` y `ausente` liberan el hueco; `sobreturno` queda **fuera** del predicado a propósito, porque por definición (RN-AG-04) puede superponerse — así el C-05 completo agrega sobreturnos sin tocar estas constraints.
   - `clinica_id` va en la clave aunque los ids sean globales: refuerza el aislamiento (regla dura 10) y alinea el índice GiST con el prefijo de tenant que usarán las consultas de agenda.
   - Se crean con SQL crudo en Alembic (`op.execute`) y se declaran en el modelo con `ExcludeConstraint` para que metadata y migración coincidan.
   - Alternativa: validación solo en servicio (SELECT previo + INSERT). Descartada por regla dura 8 y porque no resiste concurrencia.

3. **Concurrencia: la DB arbitra, el servicio traduce.** El servicio hace un pre-chequeo amigable (consulta de solapamiento en la misma transacción) pero la garantía es el `INSERT` + `commit`: si falla con `IntegrityError` y `orig.sqlstate == '23P01'` (exclusion_violation) → `Conflicto("Horario no disponible")` → `409`. El nombre de la constraint (`orig.diag.constraint_name`) permite distinguir profesional vs sillón en el log/mensaje interno, pero la respuesta al cliente es la misma y no expone datos del turno en conflicto (paciente, ids).
   - Bajo `READ COMMITTED`, dos transacciones que insertan rangos superpuestos: la segunda espera el commit de la primera y luego falla con `23P01` → exactamente un `201` (escenario "Doble clic concurrente").
   - Alternativas: `SELECT FOR UPDATE` sobre profesional/sillón o advisory lock por (clinica, profesional). Descartadas: serializan escrituras sin agregar garantías sobre la exclusion constraint, y complican el código.
   - Se extiende el patrón de `_commit()` (que hoy solo mapea `23505`) con una función específica de turnos para no alterar el comportamiento del catálogo.

4. **Bloqueos chequeados en el servicio, misma transacción.** Los bloqueos viven en otra tabla y no pueden entrar en una exclusion constraint de `turno`. Antes del `INSERT`, el servicio llama a `bloqueos_solapados(session, clinica_id, inicio, fin, profesional_id, sillon_id)`; si devuelve algo → `409` "Horario no disponible". Se reutiliza tal cual (contrato C-04, sin cambios).
   - TOCTOU residual aceptado: un bloqueo creado entre el chequeo y el commit del turno no se detecta (ver Riesgos).

5. **Tabla `turno` (migración 005)** — columnas mínimas:

   | Columna | Tipo | Notas |
   |---|---|---|
   | `id` | `BIGINT GENERATED ALWAYS AS IDENTITY` | `_pk_identity()` |
   | `clinica_id` | `BIGINT NOT NULL` | `TenantMixin`, FK `clinica` RESTRICT |
   | `profesional_id`, `sillon_id`, `paciente_id`, `prestacion_id` | `BIGINT NOT NULL` | FKs **compuestas** `(clinica_id, x_id) → x(clinica_id, id)` RESTRICT |
   | `duracion_min` | `INTEGER NOT NULL` | snapshot de la prestación al reservar; `CHECK BETWEEN 5 AND 480` |
   | `inicio`, `fin` | `TIMESTAMPTZ NOT NULL` | regla dura 7; `CHECK (fin > inicio)` |
   | `rango` | `tstzrange` generada | decisión 1 |
   | `estado` | `TEXT NOT NULL DEFAULT 'reservado'` | `CHECK IN ('reservado','confirmado','asistido','ausente','cancelado','sobreturno')` (enum completo de KB04; TEXT+CHECK, no ENUM) |
   | `origen` | `TEXT NOT NULL DEFAULT 'mostrador'` | `CHECK IN ('enlace','mostrador','whatsapp','lista_espera')` |
   | `is_active`, `created_at`, `updated_at`, `deleted_at` | | `AuditMixin` / `_audit_columns()` |

   - Índices: `ix_turno_clinica_profesional_inicio (clinica_id, profesional_id, inicio)`, `ix_turno_clinica_sillon_inicio (clinica_id, sillon_id, inicio)`, `ix_turno_clinica_paciente_inicio (clinica_id, paciente_id, inicio)`, `ix_turno_clinica_estado (clinica_id, estado)` (KB04 con prefijo tenant; cubren además los FKs). Las exclusion constraints aportan los índices GiST de rango.
   - `duracion_min` como snapshot: si el admin cambia la duración de la prestación, los turnos ya reservados no cambian su `fin`.
   - **Aditivo en tabla existente:** `UNIQUE (clinica_id, id)` `uq_prestacion_clinica_id` en `prestacion` (hoy no existe) para habilitar la FK compuesta. No falla con datos existentes (`id` ya es único). Mismo patrón que C-04 aplicó a `usuario`.

6. **Contrato HTTP.**
   - `POST /api/turnos` → `TurnoCreate {profesional_id, sillon_id, paciente_id, prestacion_id, inicio: AwareDatetime}` con `model_config = ConfigDict(extra="forbid")` (regla dura 4): `fin`, `duracion_min`, `estado`, `origen`, `clinica_id` en el cuerpo → `422`; `inicio` naive → `422`. `inicio` se normaliza a UTC.
   - `fin = calcular_fin(inicio, prestacion.duracion_min)` (regla dura 6). Respuesta `201` con `TurnoOut {id, profesional_id, sillon_id, paciente_id, prestacion_id, inicio, fin, duracion_min, estado, origen, created_at}`.
   - `GET /api/turnos/{id}` (admin, recepcionista, odontologo — lectura de agenda según matriz `03`) → `TurnoOut` o `404` si no existe, es de otra clínica o está dado de baja. No se agrega listado.
   - Ninguna ruta entra en `PUBLIC_PREFIXES`.

7. **Validación de referencias (todas scoped por el tenant del JWT)**, en el servicio antes del INSERT, todas → `422 ReferenciaInvalida` (patrón `crear_bloqueo` de C-04):
   - profesional existente, activo y con `agenda_activa = true`;
   - sillón existente y activo;
   - prestación existente y activa;
   - paciente existente y activo;
   - habilitación `ProfesionalSillon(profesional_id, sillon_id)` activa (ver "Decisiones abiertas" D-A1).
   - Las FKs compuestas son la red de seguridad si el servicio fallara (referencia de otra clínica → error de integridad, nunca un turno cruzado).

8. **RBAC y orden de evaluación.** `POST` con `require_role("admin", "recepcionista")` + `require_tenant_checked`. Orden: `401` (sin token) → `403` (rol) → `422` (cuerpo) → `422` (referencias) → `409` (bloqueo / solapamiento). El odontólogo recibe `403` incluso para su propia agenda (matriz `03`: "Lectura + bloqueos propios").

9. **Ubicación del código.** `app/domain/agenda/turnos.py` (modelo `Turno` + `crear_turno` + `obtener_turno` + error `TurnoNoDisponible(Conflicto)`), `TurnoCreate`/`TurnoOut` en `app/domain/agenda/schemas.py`, router `app/api/turnos.py` montado en `create_app()`. Los errores heredan de `CatalogoError` → reutilizan el handler existente (sin tocar `main.py` salvo el `include_router`).
   - Alternativa `domain/turnos/` separado: descartada; `08` ubica el motor anti-solapamiento en `domain/agenda/` y evita imports cruzados con el catálogo.

10. **Datos de pacientes.** Un turno es dato administrativo de agenda (recepción tiene CRUD de turnos en la matriz), no dato de salud: no se exige `consentimiento_datos = true` para reservar (regla dura 16 aplica a carga de datos clínicos). Todos los tests usan pacientes sintéticos creados con `alta_paciente` / `dni_sintetico()` (regla dura 14).

11. **Tests (strict TDD, nunca SQLite — regla dura 9).**
    - Unit: `tests/unit/test_turno_schemas.py` (extra forbid, naive → error, normalización UTC), `tests/unit/test_turno_errores.py` (mapeo `IntegrityError` con `sqlstate 23P01` → `TurnoNoDisponible`; otro sqlstate se propaga).
    - Integración PG16: `test_migracion_005.py` (up/down/up), `test_turnos_db_constraints.py` (exclusion por SQL directo, contiguos, cancelado/inactivo/sobreturno fuera del predicado, FKs compuestas, CHECKs), `test_turnos_api.py` (HTTP: happy path, 409, 422, bloqueos, RBAC, aislamiento), `test_turnos_concurrencia.py` (`ThreadPoolExecutor` + `threading.Barrier`, 5 requests; el override de `get_session` ya da sesión nueva por request).
    - Fixture nueva `turnos_data` (sobre `catalogo_data`): habilita P y Q en S1 y S2 (S3 sin habilitar para P), crea pacientes sintéticos en A y B y habilitación en B.

## Risks / Trade-offs

- [Riesgo] **TOCTOU bloqueo↔turno**: un bloqueo creado entre el chequeo del servicio y el commit del turno no se detecta → Mitigación: ventana de milisegundos, los bloqueos son operaciones de admin poco frecuentes; documentado. Un trigger o lock compartido sería sobreingeniería para el MVP; el C-05 completo puede revisarlo si el piloto lo reporta.
- [Riesgo] **Docker no instalado** → los tests de integración (exclusion constraints, concurrencia, aislamiento) no pueden correr localmente → Mitigación: instalar Docker Desktop (WSL2) antes del apply; la task final de verificación lo exige y sin él la evidencia queda pendiente, no se da por verde.
- [Riesgo] Mensaje de `23P01` mal mapeado a `500` si se agrega otra exclusion constraint en el futuro → Mitigación: el mapeo es por SQLSTATE (no por nombre); el nombre solo se usa para el log.
- [Riesgo] `UNIQUE (clinica_id, id)` nuevo en `prestacion` → aditivo y sin conflicto con datos existentes; el downgrade de 005 lo elimina.
- [Trade-off] Contención en la misma franja: bajo `READ COMMITTED` la segunda transacción espera el commit de la primera antes de fallar; aceptable (la escritura es corta).
- [Trade-off] Respuesta `409` única para "profesional ocupado", "sillón ocupado" y "bloqueo": el cliente no sabe cuál fue la causa exacta. Aceptado por privacidad y simplicidad; el endpoint de huecos (resto de C-05) es quien ofrece alternativas.
- [Trade-off] Snapshot de `duracion_min`: cambios de duración en la prestación no reajustan turnos existentes (comportamiento deseado; reprogramar recalcula — fuera de alcance).

## Migration Plan

- `alembic upgrade head` aplica `005_turnos` sobre `004_pacientes_ficha`: `CREATE EXTENSION IF NOT EXISTS btree_gist` (idempotente) → `uq_prestacion_clinica_id` → tabla `turno` + CHECKs + FKs compuestas + índices → exclusion constraints. Solo objetos nuevos + un UNIQUE aditivo: sin downtime ni migración de datos.
- Rollback: `alembic downgrade 004_pacientes_ficha` → drop de `turno` (con sus constraints) y de `uq_prestacion_clinica_id`; **no** `DROP EXTENSION` (la usa `bloqueo`). Se pierden los turnos cargados.

## Decisiones abiertas (para revisión humana — governance CRÍTICO)

> **Revisión humana 2026-10-13 (Matheo Bazán):** D-A1, D-A2 y D-A3 **aprobadas** tal como están. D-A4 **ajustada** (Ajustar): se prohíben los turnos en el pasado → `422`. Ver D-A4.

- **D-A1 — Habilitación profesional↔sillón obligatoria.** El diseño exige que el profesional esté habilitado en el sillón (`ProfesionalSillon` activa) → `422` si no. Es coherente con el modelo de C-04 y con la idea de "sillón como recurso", pero ni RN-AG-01..03 ni KB07 lo dicen textualmente. **El equipo puede recortarlo** (quitar el chequeo, el escenario "Profesional no habilitado en el sillón" y su test) sin afectar el resto del diseño.
- **D-A2 — Estados que ocupan el horario:** `reservado`, `confirmado`, `asistido`. `ausente` libera el hueco (el horario ya pasó; no tiene efecto práctico en altas futuras, pero evita bloquear correcciones). Confirmar con el piloto.
- **D-A3 — `GET /api/turnos/{id}` incluido** solo para verificar alta y aislamiento. Si el equipo quiere el recorte mínimo absoluto, el aislamiento se prueba por repositorio/SQL y el GET se difiere al CRUD completo de C-05.
- **D-A4 — Turnos en el pasado: PROHIBIDOS (ajustado en revisión humana).** ~~Propuesta original: no se rechazan.~~ El servicio `crear_turno` compara `inicio` contra el reloj del servidor en UTC: si `inicio < ahora` → `422` "No se pueden crear turnos en el pasado", sin persistir. `inicio == ahora` se acepta. El instante `ahora` se inyecta en el servicio (parámetro con default `datetime.now(UTC)`) para que los tests sean deterministas. No se agrega `CHECK` en la base de datos: `now()` no es inmutable y un `CHECK` así rompería filas históricas y correcciones futuras; la regla vive en el dominio. Las inserciones SQL directas de los tests de constraints usan fechas futuras (`2031-03-10`) y no se ven afectadas.
