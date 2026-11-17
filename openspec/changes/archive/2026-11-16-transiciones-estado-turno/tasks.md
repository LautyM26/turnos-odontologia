# Tasks — transiciones-estado-turno (C-05b)

> Governance CRÍTICO: antes de la tarea 1.1, el equipo aprueba `design.md` (D1–D6).
> TDD: en cada grupo, escribir el test, verlo fallar y recién entonces implementar.
> Tests de integración solo con testcontainers `postgres:16-alpine` (regla dura 9). Requiere Docker Desktop corriendo.

## 1. Tabla de transiciones y schema (dominio puro)

- [x] 1.1 Agregar `TRANSICIONES` y `puede_transicionar(desde, hacia)` en `backend/app/domain/agenda/turnos.py` (D1). Verificar con `backend/tests/unit/test_turno_transiciones.py`: las 7 aristas permitidas devuelven True; terminales → cualquiera, repetir estado, `→ reservado` y `→ sobreturno` devuelven False (escenarios "Turno cancelado no puede confirmarse" y "Asistido no vuelve a reservado").
- [x] 1.2 Agregar `PermisoDenegado(CatalogoError)` con `status_code = 403` en `backend/app/domain/agenda/servicio.py`. Verificar con un unit test de que el handler existente la traduce a 403 (`TestClient` con una ruta de prueba).
- [x] 1.3 Agregar `TurnoTransicionIn` en `backend/app/domain/agenda/schemas.py` (D6). Verificar en `test_turno_transiciones.py` que acepta los 4 destinos, rechaza `reservado`/`sobreturno`/campos extra (escenario "Campo extra en el cuerpo") y normaliza el `motivo` en blanco a None y el de más de 500 caracteres → error.

## 2. Persistencia del historial

- [x] 2.1 Modelo `TurnoTransicion` (D4) y migración `backend/alembic/versions/006_turno_transicion.py` (tabla, CHECKs, FKs compuestas, índice `(clinica_id, turno_id, id)`, triggers con `fn_rechazar_mutacion()`). Verificar con `backend/tests/integration/test_migracion_006.py`: upgrade crea tabla, índice y triggers; `created_at` es TIMESTAMPTZ; downgrade la elimina **sin** borrar `fn_rechazar_mutacion` y el re-upgrade la restaura.
- [x] 2.2 Verificar el escenario "Historial inmutable" en `backend/tests/integration/test_turno_transicion_db.py`: `UPDATE`, `DELETE` y `TRUNCATE` directos fallan; una FK a un turno de otra clínica falla (23503); una consulta del repositorio con otro `clinica_id` devuelve 0 filas (regla dura 10).

## 3. Servicio de transición

- [x] 3.1 Implementar `transicionar_turno(session, clinica_id, turno_id, destino, actor_id, motivo, ahora, solo_agenda_de=None, destinos_permitidos=None)` en `turnos.py`. Orden: lock `with_for_update` + `populate_existing` (D5) → 404 → `PermisoDenegado` → `puede_transicionar` (422) → ventana horaria (422, D3) → UPDATE de estado + INSERT de historial → commit. Verificar con los tests del grupo 4.
- [x] 3.2 Documentar en el docstring del servicio el orden de chequeo y la referencia a D5. Verificar con `ruff check backend` limpio.

## 4. Endpoint y escenarios de la spec

- [x] 4.1 Ruta `POST /api/turnos/{turno_id}/transicion` en `backend/app/api/turnos.py` (roles admin/recepcionista/odontólogo; para el odontólogo, `profesional_de_usuario` + destinos `{asistido, ausente}`, D2; `ahora` desde `get_ahora`). Verificar con `/docs` (Swagger) mostrando la ruta y el schema.
- [x] 4.2 Extender la fixture `turnos_data` (o crear `turnos_transicion_data`) en `backend/tests/integration/conftest.py` con un odontólogo vinculado a un profesional, turnos sintéticos en cada estado y reloj fijo vía `dependency_overrides[get_ahora]`. Solo datos sintéticos (regla dura 14). *Aplicado: no hizo falta tocar `conftest.py`; `turnos_data` ya trae a `odonto@test.test` vinculado a P y a Q sin usuario. Los turnos en cada estado y el reloj fijo se crean con helpers locales del módulo de tests.*
- [x] 4.3 `backend/tests/integration/test_turno_transiciones_api.py`, un test por escenario:
  - feliz: "Recepcionista confirma un turno reservado" → 200 y `estado = confirmado`; "Turno confirmado pasa a asistido"; "Turno reservado sin confirmar pasa a ausente";
  - error de negocio: "Turno cancelado no puede confirmarse" → 422 y estado sin cambio; "Asistido no vuelve a reservado"; "Campo extra en el cuerpo";
  - borde: "Ausente antes de la hora" → 422; "Asistido exactamente a la hora de inicio" → 200 (reloj = `inicio`);
  - "Transición registrada en el historial" (1 fila con desde, hacia, actor, motivo y fecha del servidor) y "Transición rechazada no deja historial" (conteo sin cambio tras 403 y 422);
  - "Reservar el hueco de un turno cancelado" → `POST /api/turnos` mismo profesional, sillón e inicio → 201;
  - RBAC: "Odontólogo marca asistido en su agenda" → 200; "Odontólogo intenta confirmar" → 403; "Odontólogo sobre la agenda de otro profesional" → 403; "Sin autenticación" → 401;
  - "Turno de otra clínica" → 404 y el turno ajeno no cambia.
- [x] 4.4 `backend/tests/integration/test_turno_transiciones_concurrencia.py`: escenario "Dos cancelaciones simultáneas" con `ThreadPoolExecutor` (mismo patrón que `test_turnos_concurrencia.py`) → exactamente un 200 y un 422, estado `cancelado`, 1 fila de historial. *Aplicado + hallazgo: una prueba de mutación (quitar `with_for_update()`) mostró que el test por HTTP seguía pasando, porque no discrimina: los pedidos casi nunca se solapan. Se agregó `test_transicion_espera_el_lock_y_se_evalua_contra_el_estado_confirmado`, que es determinista (una sesión retiene el lock y la transición concurrente debe esperar y recibir 422). Con la mutación, ese test falla.*

## 5. Integración, documentación y trazabilidad

- [x] 5.1 Correr la suite completa: `python -m pytest backend/tests -q` y `ruff check backend` en verde, sin regresiones en los tests de C-01…C-08 y `crear-turno-sin-solapamientos`. Guardar la salida en `openspec/changes/transiciones-estado-turno/verify.md`.
- [x] 5.2 Prueba manual en Swagger con datos sintéticos: crear un turno, confirmarlo, intentar `→ reservado` (422), cancelarlo y volver a reservar el hueco (201). Registrar las respuestas en `verify.md`.
- [x] 5.3 Actualizar `README.md` (sección de tests de este change) y `knowledge-base/03_actores_y_roles.md` (fila Odontólogo → Agenda: "+ marcar asistido/ausente en turnos propios", D2). Verificar con `diff AGENTS.md CLAUDE.md` vacío si se tocan.
- [x] 5.4 Regenerar `dominio-agenda` con `crear-skill-de-dominio`: fila RN-TU-01 → `cubierta` con la spec y los tests nuevos. Verificar con `python .claude/skills/crear-skill-de-dominio/scripts/verificar.py dominio-agenda RN-AG RN-TU` → OK y las copias en `.github/` y `.opencode/` idénticas.

## Workflow follow-up

- `/opsx:archive transiciones-estado-turno` después de la revisión humana (governance CRÍTICO) y con `verify.md` completo.
- Marcar C-05b `[x]` en `CHANGES.md`. C-05 sigue `[~]` hasta archivar C-05c (huecos y sobreturnos).
