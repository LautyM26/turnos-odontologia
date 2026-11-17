# Proposal — huecos-y-sobreturnos (C-05c)

## Why

La recepción no tiene forma de ver **dónde entra** un turno: tiene que probar horarios hasta que deja de recibir 409. Tampoco puede dar un **sobreturno**, algo habitual en el consultorio (urgencias, pacientes que se agregan al final de la jornada).

La skill `dominio-agenda` marca RN-AG-04 (sobreturno por rol con motivo) como **parcial**: existe el permiso `require_sobreturno()`, pero no hay forma de crear un sobreturno. El Flujo 1 de `07` arranca con "ve huecos reales (profesional + sillón + duración por prestación, con bloqueos aplicados)", y hoy no existe ningún endpoint que los devuelva.

Este change es el último recorte de C-05 (governance CRÍTICO), registrado como C-05c en `CHANGES.md`. Con C-05b y C-05c, C-05 queda completo; "reprogramar" pasa a C-17.

## What Changes

- **Huecos**: `GET /api/agenda/huecos?profesional_id&prestacion_id&desde&hasta`.
  - Devuelve los inicios, dentro de la ventana que pide la recepción y cada `AGENDA_PASO_MIN` minutos (default 15), en los que un turno normal de esa prestación **podría crearse**: profesional libre, al menos un sillón habilitado libre, sin bloqueos y no en el pasado.
  - Cada hueco lista los sillones libres.
  - La ventana debe ser válida y de 7 días como máximo (422).
  - Odontólogo: solo su agenda.
- **Sobreturno**: `POST /api/turnos` acepta `sobreturno: true` con `motivo_sobreturno` obligatorio (RN-AG-04).
  - Puede superponerse a otros turnos del profesional o del sillón, pero **respeta bloqueos** (409).
  - Mantiene el resto de las validaciones del alta.
- **Modelo**: marca `es_sobreturno` + `motivo_sobreturno` en `turno`. El sobreturno sigue el ciclo de estados normal de C-05b (confirmar, asistido, ausente, cancelar), y las exclusion constraints ignoran los turnos marcados.
- `TurnoOut` expone `es_sobreturno` y `motivo_sobreturno`.
- Migración `011_sobreturno_huecos` (`down_revision = "010_recetas_externas"`; renumerada en el apply, ver `design.md` §Migration Plan): columnas, CHECK de coherencia y exclusion constraints recreadas con `AND NOT es_sobreturno`.

### Decisiones de dominio tomadas con el usuario (2026-11-16)

Están justificadas en `design.md` (D1–D3):

1. La KB no define horario de atención. Los huecos se calculan dentro de la **ventana que pide la recepción**. El horario por profesional queda como change propio, C-05d, que bloquea C-06.
2. El sobreturno se modela como **marca** (`es_sobreturno`), no como estado. Así no pierde su ciclo de vida y, al pasar a `asistido`, no choca con las restricciones. El estado `sobreturno` de la 005 queda sin uso.
3. El sobreturno **respeta los bloqueos** (RN-AG-03): solo puede superponerse a otros turnos.

## Non-goals

- Horario de atención por profesional, sillón o clínica (C-05d).
- Reprogramar un turno (C-17) y reserva pública (C-06).
- Límite de sobreturnos por día o por profesional: la KB no lo define.
- UI de agenda (C-07).

## Capabilities

### New Capabilities

- `schedule-availability`: consulta de huecos libres reales de un profesional para una prestación dentro de una ventana, aplicando turnos, sobreturnos, bloqueos y habilitaciones profesional–sillón.

### Modified Capabilities

- `appointments`: se agrega el alta de sobreturno por rol con motivo y se modifica "Solo los turnos activos ocupan el horario" para excluir a los sobreturnos.

## Impact

- Código nuevo:
  - `backend/app/domain/agenda/huecos.py`: servicio `buscar_huecos` (una consulta con multirangos de PostgreSQL);
  - `backend/app/api/agenda.py`: router `/api/agenda`;
  - schemas `HuecosQuery`/`HuecoOut`;
  - `backend/alembic/versions/011_sobreturno_huecos.py`.
- Código modificado:
  - `turnos.py`: modelo, predicado activo y `crear_turno`;
  - `schemas.py`: `TurnoCreate` y `TurnoOut`;
  - `settings.py`: `AGENDA_PASO_MIN`;
  - `main.py`: `include_router`;
  - `.env.example`.
- Reutiliza: `bloqueos_solapados`, `calcular_fin`, `_validar_referencias`, `require_own_agenda`, `get_ahora`, la tabla de transiciones de C-05b.
- DB: 2 columnas, 1 CHECK y 2 exclusion constraints recreadas.
- Dependencias: ninguna nueva.
- Governance CRÍTICO: el apply requiere aprobación humana explícita del diseño.
