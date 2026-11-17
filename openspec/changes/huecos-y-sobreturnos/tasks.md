# Tasks — huecos-y-sobreturnos (C-05c)

> Governance CRÍTICO: antes de la tarea 1.1, el equipo aprueba `design.md` (D1–D6).
> TDD en cada grupo. Integración solo con testcontainers `postgres:16-alpine` (regla dura 9).

## 1. Sobreturno: modelo, migración y contrato

- [ ] 1.1 Migración `backend/alembic/versions/007_sobreturno_huecos.py` + columnas en el modelo `Turno` + predicado activo con `NOT es_sobreturno` (D2). Verificar con `backend/tests/integration/test_migracion_007.py`: columnas y CHECKs existen; las exclusion constraints incluyen `NOT es_sobreturno`; downgrade a 006 y re-upgrade OK.
- [ ] 1.2 Ajustar `backend/tests/integration/test_turnos_db_constraints.py::test_sobreturno_puede_superponerse_a_un_turno_activo` y el assert `"sobreturno" not in defs` de `test_migracion_005.py` al nuevo modelado (marca en lugar de estado), y agregar en `test_turnos_db_constraints.py` que un sobreturno marcado `asistido` superpuesto no viola 23P01 y que el CHECK de coherencia rechaza marca sin motivo (23514). Verificar que el archivo pase.
- [ ] 1.3 `TurnoCreate`/`TurnoOut` con `sobreturno`/`motivo_sobreturno`/`es_sobreturno` (D4). Verificar en `backend/tests/unit/test_turno_schemas.py`: motivo sin sobreturno → error; sobreturno sin motivo o en blanco → error; motivo > 500 → error; `sobreturno` no booleano → error.

## 2. Sobreturno en el alta

- [ ] 2.1 `crear_turno` con `sobreturno=True`: saltea el pre-chequeo de turnos pero chequea bloqueos (D3); la ruta aplica `require_sobreturno()` cuando corresponde. Verificar con `backend/tests/integration/test_sobreturnos_api.py`:
  - "Recepcionista da un sobreturno sobre un horario ocupado" → 201 con `es_sobreturno`;
  - "Sobreturno sin motivo" y "Motivo sin sobreturno" → 422 sin fila;
  - "Sobreturno sobre un feriado" → 409;
  - "Un sobreturno no ocupa el horario" → turno normal 201;
  - "Sobreturno superpuesto pasa a asistido" → 200 y 200;
  - odontólogo → 403.

## 3. Huecos

- [ ] 3.1 `AGENDA_PASO_MIN` en `backend/app/infrastructure/settings.py` (5–60, default 15) y en `backend/.env.example`. Verificar con `backend/tests/test_env_example.py` y `backend/tests/test_settings.py` en verde.
- [ ] 3.2 `buscar_huecos` en `backend/app/domain/agenda/huecos.py` (D5) + schemas `HuecoOut`. Verificar con `backend/tests/integration/test_huecos_servicio.py`:
  - "Día libre devuelve huecos cada paso";
  - "Turno del profesional ocupa el hueco" (incluye contiguo);
  - "Bloqueo de clínica";
  - "Un sillón ocupado deja el otro";
  - "Turno cancelado o sobreturno no restan";
  - "Ventana que empieza en el pasado";
  - propiedad: cada hueco devuelto, creado con `crear_turno`, da 201.
- [ ] 3.3 Router `GET /api/agenda/huecos` en `backend/app/api/agenda.py` + `include_router` en `main.py` (D6). Verificar con `backend/tests/integration/test_huecos_api.py`:
  - "Ventana mayor a 7 días" → 422;
  - "Prestación inactiva" → 422;
  - "Profesional de otra clínica" → 422;
  - `hasta <= desde` y fechas sin zona → 422;
  - "Odontólogo consulta su agenda" → 200; "Odontólogo consulta otra agenda" → 403; "Sin autenticación" → 401;
  - lista vacía → 200 `[]`.

## 4. Integración, documentación y trazabilidad

- [ ] 4.1 Suite completa `python -m pytest backend/tests -q` + `ruff check backend` en verde; `EXPLAIN ANALYZE` de la consulta de huecos con ventana de 7 días; prueba de mutación (quitar `NOT es_sobreturno` del predicado y verificar que algún test falla). Todo en `verify.md`.
- [ ] 4.2 Prueba manual con uvicorn + Swagger: consultar huecos, dar un sobreturno, verificar que el hueco sigue apareciendo y que ambos turnos pasan a asistido. Registrar en `verify.md`.
- [ ] 4.3 KB `04_modelo_de_datos.md` §Turno (marca `es_sobreturno`/`motivo_sobreturno`; estado `sobreturno` en desuso) y README (tests del change). Verificar con `diff AGENTS.md CLAUDE.md` vacío si se tocan.
- [ ] 4.4 Actualizar la matriz de `dominio-agenda` (RN-AG-04 → cubierta) y sincronizar las copias. Verificar con `verificar.py dominio-agenda RN-AG RN-TU` → OK.

## Workflow follow-up

- `/opsx:archive huecos-y-sobreturnos` tras la revisión humana y con `verify.md` completo.
- Marcar C-05c `[x]` y C-05 `[x]` en `CHANGES.md` (reprogramar queda en C-17).
