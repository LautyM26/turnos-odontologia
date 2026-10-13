# Proposal — crear-turno-sin-solapamientos

## Why

**Por qué este change y no otro:** pertenece al MVP consolidado del Discovery (§09 "MVP consolidado": "Reglas de agenda: duración por prestación, bloqueos, sobreturnos por rol, anti-solapamiento" = **IMP**, "es el vacío más claro del mercado"); sus reglas de negocio son verificables de forma objetiva (RN-AG-01, RN-AG-02, RN-AG-03 → `201`/`409`/`422`); y es lo bastante chico para terminarlo: **una funcionalidad** (crear un turno), no el módulo de turnos completo.

Hoy el sistema tiene el catálogo operativo (C-04: profesionales, sillones, prestaciones, bloqueos, `calcular_fin`, `bloqueos_solapados`) y los pacientes (C-08), pero no existe el `Turno`: la recepción no puede reservar, y la garantía central del producto —ningún profesional ni sillón con dos turnos activos a la vez, ni reservas sobre un bloqueo— no está implementada. Este change es un **recorte de C-05 `motor-turnos`** (governance CRÍTICO) que entrega solo el alta de turno con anti-solapamiento duro, dejando el resto de C-05 para changes posteriores.

## What Changes

- Nueva entidad tenant-scoped `Turno` (`clinica_id`, profesional, sillón, paciente, prestación, `duracion_min` snapshot, `inicio`, `fin`, rango semiabierto `[inicio, fin)`, `estado` con nacimiento en `reservado`, `origen` = `mostrador`), con FKs compuestas por tenant e índices `(clinica_id, …)`.
- Anti-solapamiento **duro en la base de datos**: dos exclusion constraints GiST (por profesional y por sillón, dentro de la misma clínica) que solo consideran turnos activos (`reservado`, `confirmado`, `asistido`); los turnos cancelados/ausentes o dados de baja liberan el hueco.
- Chequeo de bloqueos (de profesional, de sillón o de clínica entera) en el servicio de dominio, en la misma transacción del alta, reutilizando `bloqueos_solapados` de C-04.
- Endpoint `POST /api/turnos` (roles `admin` y `recepcionista`; `odontologo` → `403`): el cliente envía `profesional_id`, `sillon_id`, `paciente_id`, `prestacion_id` e `inicio` con zona horaria; el servidor calcula `fin = inicio + duración de la prestación` (regla dura 6) y rechaza `fin`/`duracion_min`/campos extra con `422`. Tampoco se pueden crear turnos con `inicio` en el pasado (`422`; ajuste de la revisión humana, ver `design.md` D-A4).
- Endpoint `GET /api/turnos/{id}` de solo lectura para verificar el alta y el aislamiento (`404` ante id de otra clínica).
- Errores: solapamiento por profesional, por sillón o por bloqueo → `409` "Horario no disponible" (sin exponer datos del turno en conflicto); doble clic/concurrencia → gana la primera escritura, el resto recibe `409`; referencias inexistentes, ajenas, inactivas, profesional con agenda inactiva o profesional no habilitado en el sillón → `422`.
- Migración Alembic `005_turnos` (`down_revision = "004_pacientes_ficha"`) con upgrade/downgrade probados.

## Non-goals

Diferido al resto de C-05 (u otros changes del roadmap), explícitamente **fuera** de este change:

- Transiciones de la máquina de estados (`confirmar`, `asistido`, `ausente`, `cancelar`) y su auditoría (RN-TU-01): aquí el turno solo **nace** en `reservado`.
- Sobreturnos y `motivo_sobreturno` (RN-AG-04).
- Reprogramar turnos, endpoint de cancelación y listados/CRUD completo de `/api/turnos`.
- Endpoint de huecos `GET /api/agenda/huecos`.
- Score de riesgo de ausencia (RN-TU-04).
- Seña (`seña_exigida`, `seña_pagada`) y cobros (C-11/C-12).
- Reserva online pública por enlace (C-06, RN-AG-05), WhatsApp y lista de espera.
- UI de agenda (C-07/C-10).

## Capabilities

### New Capabilities

- `appointments`: alta de turno por el staff con duración calculada en servidor, prevención dura de solapamientos por profesional y por sillón, respeto de bloqueos, manejo de concurrencia, validación de referencias del tenant, RBAC y aislamiento multi-tenant.

### Modified Capabilities

(ninguna — `schedule-blocks` ya define la consulta "Consulta de bloqueos que impiden una reserva" que este change consume sin modificarla; `access-control` y `tenant-isolation` se cumplen sin cambiar sus requisitos.)

## Impact

- Código nuevo: `backend/app/domain/agenda/turnos.py` (modelo `Turno` + servicio `crear_turno`), schemas de turno en `backend/app/domain/agenda/schemas.py`, `backend/app/api/turnos.py`, `backend/alembic/versions/005_turnos.py`.
- Código modificado: `backend/app/main.py` (solo `include_router`), `backend/app/domain/agenda/__init__.py` (export del modelo para metadata), fixtures de tests (`catalogo_data` o fixture nueva para habilitaciones profesional↔sillón y pacientes sintéticos).
- APIs: 2 rutas nuevas bajo `/api/turnos` (ninguna pública).
- DB: tabla `turno` + 2 exclusion constraints GiST + 4 índices; usa la extensión `btree_gist` ya creada por `003`.
- Dependencias: ninguna nueva.
- Requiere Docker Desktop para la verificación (tests de integración con testcontainers `postgres:16-alpine`).
- Governance CRÍTICO (heredado de C-05): el apply requiere aprobación humana explícita del diseño antes de escribir código.
