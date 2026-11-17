# Design — transiciones-estado-turno (C-05b)

## Context

Motivación: ver `proposal.md` §Why. Requisitos: ver `specs/appointments/spec.md`.

Estado actual observado en el código:

- `backend/app/domain/agenda/turnos.py`:
  - modelo `Turno` con `estado` (CHECK de 6 valores) y `ESTADOS_ACTIVOS = (reservado, confirmado, asistido)`;
  - dos exclusion constraints GiST con predicado `is_active AND estado IN ('reservado','confirmado','asistido')`, por lo que `cancelado`/`ausente` ya no ocupan el horario;
  - servicios `crear_turno` y `obtener_turno`.
- `backend/app/api/turnos.py`: `POST /api/turnos`, `GET /api/turnos/{id}` y la dependencia `get_ahora()` (reloj inyectable en tests).
- `backend/app/domain/agenda/servicio.py`: `CatalogoError` (`NoEncontrado` 404, `Conflicto` 409, `ReferenciaInvalida` 422), traducida a HTTP por el handler de `create_app()`, y `profesional_de_usuario(session, usuario_id)` (vínculo Usuario → Profesional de C-04).
- Migración 004: función `fn_rechazar_mutacion()`, usada por triggers append-only (UPDATE/DELETE por fila y TRUNCATE por sentencia).
- `AuditoriaHC` (C-08): auditoría **clínica**. Entidades limitadas a `paciente|ficha|adjunto`, consulta solo admin y diff con allowlist sin PHI.

Reglas que gobiernan el diseño (skill `dominio-agenda`): RN-TU-01, reglas duras 4 (extra='forbid'), 7 (TIMESTAMPTZ), 9 (testcontainers), 10 (clinica_id + índice + aislamiento).

## Goals / Non-Goals

**Goals:**
- Una sola fuente de verdad para las transiciones permitidas, testeable sin base de datos.
- Transición + historial atómicos, serializados por turno.
- Reutilizar errores, reloj, resolver de agenda y trigger existentes, sin dependencias nuevas.

**Non-Goals:**
- Eventos de dominio o bus para C-15/C-16. Cuando existan, se engancharán en el servicio de transición.
- Endpoint de lectura del historial.

## Decisions

### D1 — Tabla de transiciones (decisión de dominio con el usuario)

`TRANSICIONES: dict[str, frozenset[str]]` en `turnos.py`:

| Desde | Hacia |
|---|---|
| `reservado` | `confirmado`, `cancelado`, `asistido`, `ausente` |
| `confirmado` | `asistido`, `ausente`, `cancelado` |
| `asistido`, `ausente`, `cancelado`, `sobreturno` | — (terminales o fuera de alcance) |

- **Por qué `reservado → asistido | ausente`:** RN-TU-01 escribe la cadena `reservado → confirmado → …`, pero el Flujo 2 de `07` muestra que la confirmación depende del recordatorio por WhatsApp (C-15, pendiente). Exigir confirmar antes de marcar asistencia obligaría a dos pasos en mostrador por cada paciente que vino sin confirmar. Lo decidió el usuario el 2026-11-16 como interpretación de RN-TU-01.
- **`sobreturno` sin transiciones** en este change: hoy no se puede crear un sobreturno (C-05c). Se definirán junto con su alta.
- **Alternativa descartada:** máquina de estados con una librería (`transitions`, etc.). Es una dependencia nueva para 7 aristas, y un `dict` alcanza.

### D2 — RBAC: odontólogo solo asistencia/ausencia en su agenda (decisión con el usuario)

La matriz de `03` da al odontólogo "lectura + bloqueos propios" en agenda, mientras el Flujo 5 arranca con `confirmado → asistido` cuando el paciente está en el sillón. El usuario decidió ampliar la matriz solo para `asistido`/`ausente` en turnos de la agenda propia.

Implementación:

- La ruta exige `require_role("admin", "recepcionista", "odontologo")`.
- Si el usuario **no** es admin ni recepcionista, la ruta pasa al servicio `solo_agenda_de = profesional_de_usuario(session, auth.sub)` (None → 403, falla cerrado) y `destinos_permitidos = {asistido, ausente}`.
- El servicio, ya con el turno bloqueado, lanza `PermisoDenegado` (nuevo `CatalogoError`, `status_code = 403`) si el destino o el profesional no corresponden.

Orden de chequeo: 401 → 403 de rol → 422 de cuerpo → 404 (turno ajeno o inexistente) → 403 fino → 422 de transición → 422 de horario → 200. El 404 va antes del 403 fino para no revelar turnos de otra clínica.

- **Alternativa descartada:** reutilizar `require_own_agenda()`. Lee `profesional_id` del path/query y acá solo llega el id del turno: habría que cargar el turno dos veces, y fuera del lock.

### D3 — Ventana horaria con el reloj inyectable

`asistido`/`ausente` exigen `ahora >= turno.inicio`, con `ahora` de la dependencia existente `get_ahora()`, de modo que los tests usan reloj fijo. Lo decidió el usuario: evita ausencias anticipadas por error, que después alimentarán el score de RN-TU-04. Confirmar y cancelar no tienen ventana.

### D4 — Historial en tabla propia `turno_transicion`, no en `AuditoriaHC`

Columnas:

- `id` BIGINT identity
- `clinica_id`
- `turno_id`
- `desde` TEXT CHECK (estado válido)
- `hacia` TEXT CHECK (estado válido)
- `actor_usuario_id` BIGINT NOT NULL
- `motivo` TEXT NULL CHECK (`length <= 500`)
- `created_at` TIMESTAMPTZ DEFAULT `now()`

Restricciones e índices:

- FKs compuestas `(clinica_id, turno_id) → turno` y `(clinica_id, actor_usuario_id) → usuario`, ambas `ON DELETE RESTRICT`.
- Índice `(clinica_id, turno_id, id)`.
- Triggers `BEFORE UPDATE OR DELETE` (fila) y `BEFORE TRUNCATE` (sentencia) con `fn_rechazar_mutacion()`.
- Modelo con `TenantMixin` únicamente. Sin `AuditMixin`: un registro inmutable no tiene baja lógica ni `updated_at`.

Por qué no `AuditoriaHC`: es auditoría de historia clínica (Ley 26.529), con consulta solo admin, `paciente_id` obligatorio y CHECK de entidades. Meter ahí la operación de agenda obligaría a modificar la spec `clinical-audit` y mezclaría dos dominios. El historial de turnos además es dato operativo que C-16 (lista de espera) y RN-TU-04 (score) van a leer.

### D5 — Concurrencia con bloqueo de fila (evidencia Context7)

El servicio carga el turno con `select(Turno).where(id, clinica_id, is_active).with_for_update().execution_options(populate_existing=True)`:

- En PostgreSQL con READ COMMITTED, el segundo `SELECT … FOR UPDATE` espera al primero y relee la **versión confirmada** de la fila. Así la segunda transición se evalúa contra el estado nuevo: segunda cancelación → 422, sin doble historial.
- `populate_existing` evita usar una instancia vieja del identity map. Lo recomienda la doc de SQLAlchemy 2.0 consultada con Context7 (`/websites/sqlalchemy_en_20_orm`, "Use Query.with_for_update() with populate_existing()"; ver `docs/skills-mcp/evidencias/README.md` E4).

Alternativas descartadas:

- `nowait=True` / `skip_locked`: devolverían error u omitirían la fila ante cualquier contención, cuando la espera dura milisegundos.
- Columna `version` con optimistic locking: requiere migrar `turno` y reintentar en el cliente, y el lock pesimista alcanza para una fila.

### D6 — Contrato HTTP

- Cuerpo `TurnoTransicionIn(EntradaBase)`, con `extra='forbid'`:
  - `estado: Literal["confirmado","cancelado","asistido","ausente"]` (otro valor → 422 de validación);
  - `motivo: str | None` (`max_length=500`, strip; en blanco → None).
- Respuesta `TurnoOut` existente, sin campos nuevos.
- Mensajes 422 de negocio: "Transición no permitida: {desde} → {hacia}" y "No se puede marcar {hacia} antes del inicio del turno". No exponen datos de otros turnos.

## Risks / Trade-offs

- [El odontólogo marca ausente a un paciente que llegó tarde] → Admin y recepción ven el historial (por DB en este change). Corregir un estado terminal queda fuera de alcance. Si el piloto lo necesita, se resuelve con un change de "corrección" con traza, igual que la HC (corrección = nueva fila).
- [El lock de fila retiene la conexión durante la transición] → La transacción es corta (1 SELECT + 1 UPDATE + 1 INSERT).
- [El motivo podría contener datos sensibles escritos por el usuario] → Límite de 500 caracteres, nunca se loguea, y la documentación del endpoint aclara que es un motivo operativo y no clínico.
- [Ampliar la matriz RBAC de `03`] → Queda documentado acá y en `CHANGES.md`. Al archivar, actualizar `knowledge-base/03_actores_y_roles.md` (fila Odontólogo → Agenda).

## Migration Plan

1. `006_turno_transicion` (`down_revision = "005_turnos"`): crea la tabla, el índice y los triggers. No toca `turno`, así que no requiere backfill: los turnos existentes no tienen historial previo, lo cual es correcto.
2. Downgrade: borra triggers y tabla. **No** borra `fn_rechazar_mutacion()`, que pertenece a la 004.
3. Rollback de la aplicación: quitar la ruta. Los datos del historial quedan inertes.
