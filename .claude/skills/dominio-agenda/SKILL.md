---
name: dominio-agenda
description: Reglas vigentes de agenda y turnos (RN-AG + RN-TU) con trazabilidad a specs y tests. Usar al programar turnos, huecos, solapamientos, sillones, bloqueos, sobreturnos, estados del turno (reservado, confirmado, asistido, ausente, cancelado), cancelar o reprogramar, reserva online, lista de espera o la agenda del frontend (changes C-05, C-05b transiciones-estado-turno, C-06, C-07, C-16, C-17), y antes de /opsx:propose de cualquier change de agenda.
---

# dominio-agenda

> Generada con `crear-skill-de-dominio` el 2026-11-16 (matriz actualizada el mismo día tras archivar C-05b) a partir de `knowledge-base/05_reglas_de_negocio.md`, `knowledge-base/09_decisiones_y_supuestos.md` y `AGENTS.md`. Si cambia una RN o DD de esta área, regenerarla.

## 1. Propósito

Cubre el corazón operativo de la clínica: cuándo y dónde puede atenderse un paciente (profesional + sillón + prestación) sin choques, y el ciclo de vida del turno. La agenda por sillón con anti-solapamiento duro es el diferenciador del producto (DD-04).

## 2. Cuándo usarla

- Modelo `Turno`, servicio `crear_turno`, transiciones de estado, huecos, sobreturnos, reprogramación.
- Endpoints `/api/turnos`, `/api/agenda/huecos`, reserva pública (`/api/public/...`), UI `/agenda`.
- Changes del roadmap: C-05 `motor-turnos` (parcial: recorte `crear-turno-sin-solapamientos` archivado), C-05b `transiciones-estado-turno` (archivado 2026-11-16), C-06 `reserva-online-publica`, C-07 `agenda-frontend`, C-16 `lista-espera-relleno`, C-17 `chatbot-reprogramacion`.

## 3. Reglas vigentes

| Código | Regla (texto vigente) | DD que la condiciona |
|---|---|---|
| RN-AG-01 | El sillón es recurso de agenda junto a profesional y equipo; ningún turno activo puede solaparse en (sillón, rango) ni en (profesional, rango). Prevención dura. | DD-04 |
| RN-AG-02 | Cada prestación tiene duración propia; el turno hereda esa duración, no un slot fijo. | DD-04 |
| RN-AG-03 | Los bloqueos (almuerzo, admin, feriados) impiden reservas en su rango. | DD-04 |
| RN-AG-04 | El sobreturno solo lo crea un rol autorizado y queda marcado como tal, con motivo. | DD-04 |
| RN-AG-05 | La reserva online por enlace no exige registro ni cuenta; abierta a pacientes nuevos. | — |
| RN-AG-06 | La lista de espera ofrece el hueco automáticamente ante una cancelación, por prioridad; si se acepta, el turno se reasigna. (Inferencia de modelado, marcada S en la KB.) | — |
| RN-TU-01 | `openspec/specs/appointments/spec.md` · "Transición de estado explícita", "Transiciones no permitidas rechazadas", "Historial de transiciones auditado e inmutable", "Transiciones concurrentes sobre el mismo turno" (C-05b, archivado 2026-11-16) | `backend/tests/unit/test_turno_transiciones.py` · `test_aristas_permitidas`, `test_todo_lo_demas_rechazado`; `backend/tests/integration/test_turno_transiciones_api.py` · `test_recepcionista_confirma_un_turno_reservado`, `test_turno_cancelado_no_puede_confirmarse`, `test_transicion_registrada_en_el_historial`; `backend/tests/integration/test_turno_transicion_db.py` · `test_update_delete_truncate_rechazados`; `backend/tests/integration/test_turno_transiciones_concurrencia.py` · `test_transicion_espera_el_lock_y_se_evalua_contra_el_estado_confirmado` | cubierta |
| RN-TU-02 ⚠️ | El recordatorio sale por WhatsApp (sesión QR con número dedicado, texto base interno) con ventana de confirmación. Si la sesión cae, el turno queda sin confirmar y se escala por email/recordatorio manual. | DD-10 (reemplaza DD-02) |
| RN-TU-03 | Confirmar, cancelar y reprogramar por WhatsApp actualiza la agenda (bidireccional real). | DD-10 |
| RN-TU-04 | Todo ausente entra a recuperación (seguimiento con monto visible) y alimenta el score de riesgo del paciente. | — |

### Reglas duras de AGENTS.md que aplican

- **6**: fin = inicio + duración de la prestación, solo en servidor; solapamiento validado en dominio.
- **7**: tiempo siempre `TIMESTAMPTZ`.
- **8**: anti-solapamiento con exclusion constraints GiST (`sillon_id`/`profesional_id`, `tstzrange`) + chequeo de bloqueos; doble clic concurrente → 409.
- **9**: tests de PG solo con testcontainers `postgres:16-alpine` + migraciones up/down.
- **10**: tabla con `clinica_id` + índice `(clinica_id, …)` + test de aislamiento.
- **13**: en el frontend, `Promise.all(huecos + turnos + bloqueos)` y 409 → mostrar alternativas.

### Supuestos abiertos (no son reglas cerradas)

- **SU-04**: recordatorio 24 h antes, pre-bloqueo ~15 min (`RESERVA_PREBLOQUEO_MIN`), timeout de oferta de lista de espera. Sin validar con el piloto: usar configuración, nunca constantes.
- **PA-06 / SU-07**: política de seña y reembolso al cancelar (afecta C-06 si la reserva exige seña). Ver `dominio-caja`.

## 4. Cómo aplicarlas

- Código existente: `backend/app/domain/agenda/turnos.py` (modelo `Turno`, `ESTADOS_ACTIVOS`, predicado de turno activo, `crear_turno`), `backend/app/domain/agenda/schemas.py`, `backend/app/api/turnos.py`, migración `backend/alembic/versions/005_turnos.py`.
- "Activo" = `reservado`, `confirmado`, `asistido`. `cancelado`/`ausente` liberan el hueco sin tocar las constraints. `sobreturno` está fuera de las exclusion constraints a propósito (RN-AG-04).
- Respuestas: solapamiento o bloqueo → `409` "Horario no disponible" sin datos del turno ajeno; referencia inválida/ajena → `422`; rol no autorizado → `403`; turno de otra clínica → `404`.
- Sobreturno: reutilizar `require_sobreturno()` de `backend/app/api/permissions.py` (admin/recepcionista).
- Transiciones (C-05b): `TRANSICIONES` + `transicionar_turno` en `backend/app/domain/agenda/turnos.py`; `POST /api/turnos/{id}/transicion`; historial append-only `turno_transicion`. No duplicar la tabla de transiciones: importar `puede_transicionar`.

## 5. Matriz de trazabilidad RN → spec → test

| Regla | Spec (archivo · requirement) | Test (archivo · función) | Estado |
|---|---|---|---|
| RN-AG-01 | `openspec/specs/appointments/spec.md` · "Sin solapamiento de turnos por profesional", "Sin solapamiento de turnos por sillón", "Concurrencia sobre el mismo hueco", "Garantía de no solapamiento en la capa de persistencia" | `backend/tests/integration/test_turnos_db_constraints.py` · `test_superpuesto_por_profesional_en_otro_sillon_23P01`, `test_superpuesto_por_sillon_con_otro_profesional_23P01`; `backend/tests/integration/test_turnos_concurrencia.py` · `test_cinco_pedidos_identicos_un_201_y_cuatro_409`; `backend/tests/integration/test_turnos_api.py` · `test_profesional_ocupado_en_otro_sillon_409`, `test_sillon_ocupado_por_otro_profesional_409` | cubierta |
| RN-AG-02 | `openspec/specs/clinic-catalog/spec.md` · "Prestación con duración propia", "Fin de turno calculado solo en servidor"; `openspec/specs/appointments/spec.md` · "Alta de turno con duración calculada en servidor" | `backend/tests/unit/test_agenda_duracion.py` · `test_suma_duracion_conservando_offset`; `backend/tests/integration/test_turnos_api.py` · `test_recepcionista_crea_turno_201_con_fin_calculado_y_get`, `test_fin_o_duracion_en_body_422_sin_fila` | cubierta |
| RN-AG-03 | `openspec/specs/appointments/spec.md` · "Los bloqueos impiden reservas"; `openspec/specs/schedule-blocks/spec.md` · "Consulta de bloqueos que impiden una reserva" | `backend/tests/integration/test_turnos_api.py` · `test_bloqueo_del_profesional_409_y_contiguo_201`, `test_bloqueo_del_sillon_409`, `test_bloqueo_de_clinica_409_para_cualquier_recurso`; `backend/tests/integration/test_bloqueos_solapados.py` · `test_devuelve_bloqueo_del_profesional_que_se_superpone` | cubierta |
| RN-AG-04 | `openspec/specs/access-control/spec.md` · "Sobreturnos y anulaciones chequeados por rol" (solo el permiso) | `backend/tests/integration/test_rbac.py` · `test_sobreturno_sin_rol_403`; `backend/tests/integration/test_turnos_db_constraints.py` · `test_sobreturno_puede_superponerse_a_un_turno_activo` | parcial: falta crear sobreturno con motivo (endpoint) |
| RN-AG-05 | `openspec/specs/patients/spec.md` · "Paciente no requiere cuenta de usuario" | `backend/tests/integration/test_pacientes_servicio.py` · `test_crear_paciente_persiste_audita_y_no_crea_usuario` | parcial: falta el enlace público de reserva (C-06) |
| RN-AG-06 | — | — | pendiente (C-16) |
| RN-TU-01 | `openspec/specs/appointments/spec.md` · "Alta de turno con duración calculada en servidor" (solo el estado inicial `reservado`) | `backend/tests/integration/test_turnos_db_constraints.py` · `test_checks_rechazan_valores_invalidos_23514`, `test_turno_no_activo_no_ocupa_el_horario` | parcial: faltan transiciones y auditoría (C-05b) |
| RN-TU-02 | — | — | pendiente (C-15) |
| RN-TU-03 | — | — | pendiente (C-15/C-17) |
| RN-TU-04 | `openspec/specs/patients/spec.md` · "Riesgo de ausencia de solo lectura" (solo el campo) | `backend/tests/integration/test_pacientes_api.py` · `test_patch_riesgo_ausencia_422` | parcial: falta que el ausente alimente el score y el seguimiento |

Resumen: 10 reglas · 4 cubiertas · 3 parciales · 3 pendientes. Ningún test cita el código RN: la trazabilidad se hizo por significado (requirement → escenario → test).

### Conflictos detectados

- **RN-TU-02** en `knowledge-base/05_reglas_de_negocio.md` decía que el recordatorio salía por la vía oficial de Meta con plantilla aprobada, lo que contradice DD-10 (QR con número dedicado, sin plantillas Meta). Esta skill usa el texto coherente con DD-10. **Corregido en la KB el 2026-11-16.**
- **DD-08** (trade-offs, `knowledge-base/09_decisiones_y_supuestos.md`) listaba la vía oficial de WhatsApp entre las integraciones no negociables. No es una regla de agenda, pero confundía a quien leyera DD-08 sin DD-10. **Anotado en la KB el 2026-11-16.**

## 6. Criterios de revisión

Antes de dar por terminado un change de esta área:

- [ ] Cada regla de la sección 3 que el change toca tiene escenario en la spec del change.
- [ ] Cada escenario nuevo tiene un test y la fila correspondiente de la matriz se actualizó (regenerar esta skill).
- [ ] Ninguna implementación contradice una DD vigente (WhatsApp = QR, DD-10).
- [ ] Se respetaron las reglas duras 6, 7, 8, 9, 10 y 13.
- [ ] Solo datos sintéticos en tests, seeds y ejemplos (regla dura 14).
