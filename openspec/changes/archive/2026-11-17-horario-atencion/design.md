# Design — horario-atencion (C-05d)

## Context

Motivación: ver `proposal.md`. Requisitos: `specs/business-hours`, `specs/schedule-availability`, `specs/appointments`.

Estado observado (después de C-05c):

- `huecos.py::_SQL_HUECOS`: CTEs `libre_prof` y `libre_sillon` (`MATERIALIZED`) calculadas como `tstzmultirange(ventana) - range_agg(ocupado)`; los candidatos valen si `cand.r <@ libre_prof` y `<@ libre_sillon`.
- `turnos.py::crear_turno`: pasado (422) → referencias (422) → bloqueos (409) → solapamiento (409, salvo sobreturno) → INSERT.
- `admin_catalogo.py`: `PUT /api/admin/profesionales/{id}/sillones` reemplaza un set en una transacción (`servicio.reemplazar_habilitacion`, 422 sin cambios parciales). Es el patrón a imitar.
- `catalogo.py`: lectura del catálogo para el staff (`/api/catalogo`, admin/recepcionista/odontólogo).
- `Clinica` (`core/models.py`) no tiene zona horaria.
- PostgreSQL 16, verificado con Context7 (`/websites/postgresql/16`, functions-datetime y functions-range):
  - `timestamp AT TIME ZONE zona → timestamptz`, interpretando el valor como hora local de la zona, con la regla vigente para esa fecha;
  - `anymultirange * anymultirange` es la intersección;
  - `anyrange <@ anymultirange` es la contención.

## Goals / Non-Goals

**Goals:**

- Una sola definición de "horario del profesional en un rango de instantes", calculada por la base, que comparten huecos y el alta.
- Mantener la propiedad de C-05c: todo hueco devuelto acepta un `POST /api/turnos` normal.

**Non-Goals:** excepciones por fecha, horario por sillón o por clínica, editar `zona_horaria` por API (ver proposal).

## Decisions

### D1 — Tabla `franja_horaria` con minutos desde la medianoche

- Columnas:
  - `id`, `clinica_id`;
  - `profesional_id` (FK compuesta `(clinica_id, profesional_id)` → `profesional`, `ON DELETE RESTRICT`);
  - `dia_semana SMALLINT` (1–7, ISO, igual que `extract(isodow)`);
  - `inicio_min SMALLINT` y `fin_min SMALLINT`, con CHECK `0 <= inicio_min < fin_min <= 1440`.
- Índice `(clinica_id, profesional_id, dia_semana)` (regla dura 10).
- **Por qué minutos y no `TIME`:** `24:00` (día completo) no entra en `datetime.time` de Python, y los minutos simplifican el CHECK. La API sigue hablando `HH:MM` (`"24:00"` permitido); el schema convierte.
- **Sin `AuditMixin` (sin baja lógica):** el horario es configuración que se reemplaza entera. Guardar franjas "dadas de baja" no aporta trazabilidad clínica ni contable, y complica cada consulta con `is_active`. El PUT borra e inserta.
- **Superposición dentro del día:** se valida en el schema (422), ordenando por `(dia, inicio)` y comparando cada franja con la anterior; la contigüidad (`fin == inicio` siguiente) es válida. No se agrega una exclusion constraint: todas las escrituras pasan por un PUT atómico que serializa (D3).

### D2 — Zona horaria en `clinica.zona_horaria`

- `TEXT NOT NULL DEFAULT 'America/Argentina/Buenos_Aires'`.
- No hay CHECK de validez porque un CHECK no puede consultar `pg_timezone_names`. Como no hay escritura por API, el valor solo viene de la migración o del seed; cuando C-14 lo haga editable, valida con `zoneinfo.ZoneInfo` en el schema.

### D3 — Reemplazo atómico serializado por profesional

`horario.reemplazar_horario(session, clinica_id, profesional_id, franjas)`:

1. `SELECT ... FOR UPDATE` del profesional activo del tenant (404 si no existe). El lock serializa dos PUT concurrentes sobre el mismo profesional; sin él, los dos borrarían las filas viejas, cada uno insertaría las suyas, y quedaría la unión superpuesta.
2. `DELETE` de sus franjas.
3. `INSERT` de las nuevas.
4. `commit`.

Si falla algún paso, rollback y queda el horario anterior.

### D4 — Multirango del horario en SQL, compartido por huecos y alta

Fragmento CTE único (`horario.SQL_HORARIO_CTE`), parametrizado por `:c`, `:p`, `:desde`, `:hasta`:

```sql
horario AS MATERIALIZED (
  SELECT coalesce(range_agg(tstzrange(
           (d + make_interval(mins => f.inicio_min)) AT TIME ZONE cl.zona_horaria,
           (d + make_interval(mins => f.fin_min))    AT TIME ZONE cl.zona_horaria, '[)')),
         '{}'::tstzmultirange) AS m
  FROM clinica cl
  CROSS JOIN generate_series(
       (CAST(:desde AS timestamptz) AT TIME ZONE cl.zona_horaria)::date - 1,
       (CAST(:hasta AS timestamptz) AT TIME ZONE cl.zona_horaria)::date, interval '1 day') g(d0)
  CROSS JOIN LATERAL (SELECT g.d0::date AS d) dd
  JOIN franja_horaria f ON f.clinica_id = cl.id AND f.profesional_id = :p
                       AND f.dia_semana = extract(isodow FROM dd.d)
  WHERE cl.id = :c
)
```

- `range_agg` une las franjas contiguas, también las que cruzan de un día al siguiente (`24:00` de un día y `00:00` del otro), así que "turno que cruza dos franjas contiguas" sale gratis.
- Sin franjas, el resultado es `'{}'`, el multirango vacío. Así se falla cerrado sin un caso especial.
- Las fechas locales van de `desde − 1 día` a `hasta`, para cubrir ventanas que cruzan la medianoche local.
- **Huecos:** `libre_prof = (tstzmultirange(v.r) * horario.m) - ocupado`. El resto de `_SQL_HUECOS` no cambia.
- **Alta:** `horario.dentro_de_horario(session, c, p, inicio, fin) -> bool` ejecuta `SELECT tstzrange(:desde, :hasta, '[)') <@ horario.m` con el mismo CTE. En `crear_turno` va después de las referencias y antes de los bloqueos, solo si no es sobreturno, y responde `409` `TurnoNoDisponible` (decisión del usuario: mismo 409 genérico que un horario ocupado, sin revelar el motivo).
- **Alternativa descartada:** calcular las franjas en Python con `zoneinfo` y pasarlas a SQL. Duplica la semántica de rangos y obliga a un camino distinto para el alta y para huecos. Con un solo fragmento SQL, la propiedad "hueco ⇒ 201" queda garantizada por construcción.

### D5 — Contrato HTTP

- `PUT /api/admin/profesionales/{id}/horario` (router admin existente, `require_admin`).
  - Cuerpo: `{"franjas": [{"dia_semana": 1, "inicio": "09:00", "fin": "13:00"}, ...]}`, con `extra='forbid'` y máximo 70 franjas (10 por día), para acotar el payload.
  - Respuesta `200`: `{"profesional_id", "zona_horaria", "franjas": [...]}`, ordenadas.
- `GET /api/catalogo/profesionales/{id}/horario` (router de catálogo para staff): misma respuesta.
- Errores:
  - `422`: formato, rango, día o superposición;
  - `404`: profesional ajeno, inexistente o dado de baja;
  - `403`: rol;
  - `401`: sin token.

### D6 — Compatibilidad: fixtures y seed

- **Fixture `turnos_data`:** inserta `00:00–24:00` los 7 días para P, Q, R y el profesional de B. Así los tests de C-05/C-05b/C-05c conservan su significado sin reescribirlos.
- **Tests nuevos de horario:** usan un profesional propio con franjas acotadas.
- **Seed (`seed_catalogo`):** lunes a viernes `09:00–13:00` y `14:00–18:00` para el profesional seed. Es idempotente, igual que el resto del seed.

## Risks / Trade-offs

- [**BREAKING** en bases existentes: sin franjas, el profesional deja de aceptar turnos normales] → Es la decisión del usuario (falla cerrado). La migración no inventa horarios; el seed y la guía (`README`/`CONTINUAR`) indican cargarlos con el PUT. El sobreturno sigue disponible como escape operativo.
- [El 409 no dice "fuera de horario"] → Coherente con el 409 genérico de C-05. La UI (C-07) puede consultar el horario y mostrarlo; la API no filtra información de agenda ajena.
- [`zona_horaria` inválida en la base rompería las consultas] → Solo la escriben la migración y el seed; C-14 debe validarla antes de exponerla.
- [Costo de la CTE `horario` en ventanas de 7 días] → Son 9 fechas × franjas por día, materializado una vez. Se mide con `EXPLAIN ANALYZE` en verify.

## Migration Plan

1. `012_horario_atencion` (`down_revision = "011_sobreturno_huecos"`):
   - `ADD COLUMN clinica.zona_horaria`;
   - `CREATE TABLE franja_horaria` con FKs compuestas, CHECKs e índice.
2. Downgrade: `DROP TABLE franja_horaria` y `DROP COLUMN zona_horaria`. Se pierden los horarios cargados.
