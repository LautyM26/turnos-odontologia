# Design — huecos-y-sobreturnos (C-05c)

## Context

Motivación: ver `proposal.md`. Requisitos: `specs/schedule-availability/spec.md` y `specs/appointments/spec.md`.

Estado observado:

- `turnos.py`: `ESTADOS_ACTIVOS`, `_PREDICADO_ACTIVO = "is_active AND estado IN ('reservado','confirmado','asistido')"` (lo usan las dos exclusion constraints GiST), `crear_turno` (pasado → referencias → bloqueos → pre-chequeo de solapamiento → INSERT) y la tabla `TRANSICIONES` de C-05b. El estado `sobreturno` existe en el CHECK pero no tiene alta ni transiciones.
- `bloqueos.py`: `bloqueos_solapados(...)` (bloqueos de clínica, profesional y sillón).
- `permissions.py`: `require_sobreturno()` (admin/recepcionista, mismos roles que el alta), `require_own_agenda` (lee `profesional_id` del query).
- `settings.py`: `Settings` con `extra="forbid"` y `.env.example` verificado por `test_env_example.py`.
- PostgreSQL 16: multirangos (`range_agg`, `multirange - multirange`, `unnest`), consultados con Context7 (`/websites/postgresql/16`, functions-range y functions-aggregate). Evidencia E6 en `docs/skills-mcp/evidencias/README.md`.

## Goals / Non-Goals

**Goals:** una definición de hueco = "un `POST /api/turnos` normal ahí respondería 201", calculada por la base en una consulta; sobreturno sin romper el ciclo de estados ni las constraints.

**Non-Goals:** horario de atención (C-05d); cache o materialización de huecos; límite de sobreturnos.

## Decisions

### D1 — Ventana pedida por la recepción + paso configurable (decisión con el usuario)

- La KB no define horario de atención. El cliente manda `desde`/`hasta`, por ejemplo "jueves 9–18".
- Los inicios candidatos son `desde + k·paso` mientras `inicio + duración <= hasta` e `inicio >= ahora`.
- `AGENDA_PASO_MIN` es un setting (default 15, rango 5–60), no una constante (SU-04).
- La ventana máxima es de 7 días: acota el costo y alcanza para la vista semana de C-07.
- **Alternativa descartada por el usuario:** modelar el horario de atención ya. Es una entidad nueva fuera de la KB y queda como C-05d, que bloquea C-06.

### D2 — Sobreturno como marca, no como estado (decisión con el usuario)

- Columnas `es_sobreturno BOOLEAN NOT NULL DEFAULT false` y `motivo_sobreturno TEXT NULL`.
- CHECK `es_sobreturno = (motivo_sobreturno IS NOT NULL)` y `length(motivo_sobreturno) <= 500`.
- El predicado de las exclusion constraints pasa a `is_active AND NOT es_sobreturno AND estado IN (...)`. La migración 007 hace `DROP` y re-`ADD` de las dos constraints con el predicado nuevo.
- El turno marcado sigue `TRANSICIONES` de C-05b sin cambios. Un sobreturno `asistido` no viola la constraint porque está excluido del predicado.
- El estado `sobreturno` queda en el CHECK (no se reescribe la 005) pero ningún código lo asigna. Antes de recrear las constraints, la 007 migra las filas que hubiera con `estado='sobreturno'` (no debería haber ninguna) a `estado='reservado', es_sobreturno=true, motivo='(migrado desde estado sobreturno)'`.
- **Por qué no el estado:** con el estado, el sobreturno no puede pasar por `confirmado`, y al pasar a `asistido` entraría al predicado activo y la base lo rechazaría (23P01) aunque fuera un sobreturno legítimo.
- La KB `04` (Turno) se actualiza al archivar: `estado` sin `sobreturno` + atributos `es_sobreturno`/`motivo_sobreturno`.

### D3 — El sobreturno respeta bloqueos (decisión con el usuario)

`crear_turno` con `sobreturno=True` hace pasado → referencias → **bloqueos (409)** → INSERT. Solo se saltea el pre-chequeo de solapamiento con turnos. RN-AG-03 sigue sin excepciones.

### D4 — Contrato de alta del sobreturno

- `TurnoCreate` agrega `sobreturno: bool = False` (`StrictBool`) y `motivo_sobreturno: str | None` (strip, ≤500).
- Un `model_validator` exige: motivo presente sii `sobreturno` (422 en ambos sentidos).
- Rol: `POST /api/turnos` ya exige admin/recepcionista, que son exactamente los roles de `require_sobreturno()`. Se usa explícitamente `require_sobreturno()` cuando `sobreturno=True`, para que si la matriz cambia el contrato siga en un solo lugar.

### D5 — Huecos en una sola consulta SQL con multirangos (evidencia Context7)

`backend/app/domain/agenda/huecos.py::buscar_huecos(session, clinica_id, profesional_id, prestacion, desde, hasta, ahora, paso_min)`:

1. Valida referencias reutilizando las reglas de `_validar_referencias` (profesional con agenda activa y prestación activa del tenant; 422).
2. Una consulta con CTEs:
   - `ocupado_prof = range_agg(rango)` de turnos activos no sobreturno del profesional ∪ bloqueos del profesional o de la clínica que se superponen con la ventana;
   - `libre_prof = tstzmultirange(ventana) - coalesce(ocupado_prof, '{}')`;
   - por cada sillón habilitado y activo: `libre_sillon = tstzmultirange(ventana) - range_agg(turnos activos no sobreturno del sillón ∪ bloqueos del sillón o de la clínica)`;
   - candidatos `generate_series(desde, hasta - duración, paso)` filtrados por `>= ahora`;
   - un candidato vale si `tstzrange(c, c+dur) <@ libre_prof` y existe un sillón con `<@ libre_sillon`.
   - Devuelve `(inicio, array_agg(sillon_id ORDER BY sillon_id))`.
3. La doc de PG16 confirma que la diferencia de *rangos* falla si el resultado es disjunto, y que con *multirangos* no falla. Por eso todo se castea a `tstzmultirange`.

**Alternativa descartada:** calcular en Python, trayendo turnos y bloqueos y recorriendo minuto a minuto. Son más líneas, más idas a la base y duplican la semántica de rangos semiabiertos que PostgreSQL ya resuelve igual que las constraints.

### D6 — Contrato HTTP de huecos

- `GET /api/agenda/huecos` (router nuevo `backend/app/api/agenda.py`).
- Query: `profesional_id`, `prestacion_id` (int), `desde`/`hasta` (`AwareDatetime`).
- Dependencias: `require_own_agenda` (admin/recep: todo; odontólogo: solo su `profesional_id`; 403/401), `require_tenant_checked`, `get_ahora` reutilizado de `api/turnos.py`.
- Respuesta: `[{"inicio", "fin", "sillon_ids": [..]}]`, ordenada por `inicio`. Lista vacía si no hay huecos (200, no 404).

## Risks / Trade-offs

- [Un turno normal puede reservarse encima de un sobreturno, porque el sobreturno "no ocupa"] → Es la semántica de la spec, y la agenda (C-07) los muestra marcados. Si el piloto quiere lo contrario, es un cambio de predicado.
- [Sin horario de atención, una ventana mal pedida, por ejemplo de día completo, devuelve huecos de madrugada] → Responsabilidad del cliente en C-05c. C-05d lo resuelve antes de exponer huecos al público (C-06).
- [Recrear las exclusion constraints bloquea la tabla `turno` durante la migración] → Tabla chica en MVP. Se documenta en la migración.
- [La consulta de huecos con muchos sillones y ventana de 7 días] → Máximo 672 candidatos × sillones habilitados, resuelto en la base con índices GiST existentes. Se mide con `EXPLAIN ANALYZE` en verify.

## Migration Plan

1. `007_sobreturno_huecos`: `ADD COLUMN`s, migración de filas `estado='sobreturno'`, CHECKs, `DROP CONSTRAINT` + `ADD CONSTRAINT ... EXCLUDE ... WHERE (is_active AND NOT es_sobreturno AND estado IN (...))`.
2. Downgrade: recrear las constraints con el predicado de la 005, convertir los sobreturnos marcados que sigan activos a `estado='sobreturno'` para no violar el predicado viejo, y borrar las columnas.
