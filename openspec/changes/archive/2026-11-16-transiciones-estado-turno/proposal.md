# Proposal — transiciones-estado-turno (C-05b)

## Why

Hoy el turno solo **nace** en `reservado` (recorte archivado `crear-turno-sin-solapamientos`). La recepción no puede confirmarlo, cancelarlo ni marcar si el paciente vino o faltó. Sin eso, un turno cancelado sigue ocupando el hueco y no hay registro de asistencia.

La skill `dominio-agenda` marca **RN-TU-01** ("estados reservado → confirmado → asistido | ausente | cancelado; transiciones explícitas y auditadas") como **parcial**: existen el estado inicial y el CHECK de estados, pero faltan las transiciones y su auditoría.

Este change es el **resto "máquina de estados" de C-05** (governance CRÍTICO), registrado como C-05b en `CHANGES.md`. Es chico y verificable de forma objetiva (200/403/404/422), y desbloquea C-15 (confirmar/cancelar por WhatsApp), C-16 (lista de espera ante cancelación) y C-07 (agenda UI).

## What Changes

- Endpoint `POST /api/turnos/{id}/transicion` con cuerpo `{ "estado": <destino>, "motivo"?: <texto> }` que aplica una **tabla de transiciones explícita**:
  - `reservado → confirmado | cancelado | asistido | ausente`
  - `confirmado → asistido | ausente | cancelado`
  - `asistido`, `ausente` y `cancelado` son **terminales**.
  - Cualquier otra transición, o un destino fuera de esa lista (`reservado`, `sobreturno`), → `422`.
- `asistido` y `ausente` solo pueden marcarse **desde la hora de inicio** del turno (antes → `422`).
- **RBAC**: admin y recepcionista hacen cualquier transición. El odontólogo solo marca `asistido`/`ausente` en turnos de **su propia agenda** (otra transición, u otro profesional → `403`). Turno de otra clínica → `404`.
- **Historial auditado e inmutable** `turno_transicion` (estado anterior, estado nuevo, usuario, motivo opcional, fecha/hora del servidor): una fila por transición, en la misma transacción. La base rechaza UPDATE/DELETE.
- **Concurrencia**: dos transiciones simultáneas sobre el mismo turno se serializan. Gana la primera y la otra se re-evalúa contra el estado nuevo.
- `cancelado`/`ausente` **liberan el hueco**: ya lo garantiza el predicado de turno activo de las exclusion constraints de la migración 005. Este change lo vuelve verificable por API.
- Migración Alembic `006_turno_transicion` (`down_revision = "005_turnos"`) con upgrade/downgrade probados.

### Decisiones de dominio tomadas con el usuario (2026-11-16)

RN-TU-01 y la KB no las resuelven. Están justificadas en `design.md` (D1–D3):

1. `reservado` puede pasar directo a `asistido`/`ausente`. Sin WhatsApp (C-15) nadie confirma, y el paciente igual viene o falta.
2. El odontólogo puede marcar `asistido`/`ausente` solo en su agenda (Flujo 5 arranca con `confirmado → asistido` en el sillón). Amplía la matriz de `03`, que le daba solo "lectura + bloqueos propios".
3. `asistido`/`ausente` solo desde el inicio del turno, para no registrar ausencias por error (alimentarán el score de RN-TU-04).

## Non-goals

- Reprogramar, sobreturnos (RN-AG-04) y huecos (`GET /api/agenda/huecos`): van a C-05c.
- Score de riesgo y seguimiento de ausentes (RN-TU-04): la KB no define la fórmula. Este change deja el historial que lo alimentará.
- Confirmación/cancelación por WhatsApp (C-15), oferta a lista de espera (C-16), seña (C-12), UI (C-07).
- Endpoint de lectura del historial: la verificación se hace con tests contra la base. Se agrega cuando una pantalla lo necesite.
- Reabrir un turno terminal (por ejemplo `cancelado → reservado`): exigiría revalidar solapamientos y no está en la KB.

## Capabilities

### New Capabilities

(ninguna)

### Modified Capabilities

- `appointments`: se agregan los requisitos de transición de estado, historial auditado, permisos por rol para transiciones, ventana horaria de asistencia/ausencia y concurrencia sobre un mismo turno. Los requisitos existentes de alta y anti-solapamiento no cambian.

## Impact

- Código nuevo:
  - en `backend/app/domain/agenda/turnos.py`, la tabla de transiciones, el servicio `transicionar_turno` y el modelo `TurnoTransicion`;
  - el schema `TurnoTransicionIn` en `backend/app/domain/agenda/schemas.py`;
  - la ruta en `backend/app/api/turnos.py`;
  - `backend/alembic/versions/006_turno_transicion.py`.
- Reutiliza: `obtener_turno`, `BaseRepository`, el resolver de agenda propia de `backend/app/api/permissions.py` y la función de trigger `fn_rechazar_mutacion()` de la migración 004.
- APIs: 1 ruta nueva, no pública.
- DB: tabla `turno_transicion` + índice `(clinica_id, turno_id)` + FKs compuestas por tenant + triggers append-only.
- Dependencias: ninguna nueva.
- Verificación: Docker Desktop (testcontainers `postgres:16-alpine`).
- Governance CRÍTICO: el apply requiere aprobación humana explícita del diseño.
