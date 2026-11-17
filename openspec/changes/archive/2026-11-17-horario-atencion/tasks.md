# Tasks — horario-atencion (C-05d)

> Governance CRÍTICO: antes de la tarea 1.1, el usuario aprueba `design.md` (D1–D6).
> TDD en cada grupo. Integración solo con testcontainers `postgres:16-alpine` (regla dura 9).

## 1. Modelo, migración y contrato

- [x] 1.1 Migración `backend/alembic/versions/012_horario_atencion.py` (`down_revision = "011_sobreturno_huecos"`), modelo `FranjaHoraria` en `backend/app/domain/agenda/models.py` y `Clinica.zona_horaria` (D1, D2). Verificar con `backend/tests/integration/test_migracion_012.py`:
  - tabla, FKs compuestas, CHECKs e índice `(clinica_id, profesional_id, dia_semana)`;
  - columna con su default;
  - CHECK rechaza `inicio_min >= fin_min`, `fin_min > 1440` y `dia_semana` 0/8 (23514);
  - downgrade a 011 y re-upgrade;
  - único head.
- [x] 1.2 Test de aislamiento de `franja_horaria`: una consulta con el repositorio de otra clínica devuelve 0 filas (regla dura 10). Puede vivir en `test_migracion_012.py` o en `test_horario_api.py`.
- [x] 1.3 Schemas `FranjaIn`/`HorarioIn`/`HorarioOut` (D1, D5). Verificar en `backend/tests/unit/test_horario_schemas.py`:
  - `"09:00"` → 540 y `"24:00"` → 1440;
  - error con formato inválido (`"9:00"`, `"24:30"`, `"12:60"`), `inicio >= fin`, día 0/8, superposición en el mismo día, más de 70 franjas o campo extra;
  - franjas contiguas válidas y salida ordenada.

## 2. Administración y consulta del horario

- [x] 2.1 `reemplazar_horario` y `obtener_horario` en `backend/app/domain/agenda/horario.py` (D3), más las rutas `PUT /api/admin/profesionales/{id}/horario` y `GET /api/catalogo/profesionales/{id}/horario` (D5). Verificar con `backend/tests/integration/test_horario_api.py`:
  - "Horario partido de lunes a viernes" → 200 con 10 franjas;
  - "Franjas superpuestas en el mismo día" → 422 y horario previo intacto;
  - "Franja inválida" → 422;
  - "Día completo" → 200;
  - "Reemplazo total";
  - lista vacía deja sin horario;
  - "Recepción no edita horarios" → 403;
  - "Profesional de otra clínica" → 404;
  - "Recepcionista consulta el horario" → 200 con `zona_horaria`;
  - odontólogo consulta → 200;
  - sin token → 401.
- [x] 2.2 Concurrencia (D3): dos PUT simultáneos con horarios distintos sobre el mismo profesional dejan exactamente uno de los dos sets, nunca la unión. Verificar con `backend/tests/integration/test_horario_concurrencia.py`, con hilos y el lock real.

## 3. Horario en huecos y en el alta

- [x] 3.1 Fixture `turnos_data` con `00:00–24:00` los 7 días para P, Q, R y el profesional de B (D6). Verificar que `test_turnos_api.py`, `test_turnos_concurrencia.py`, `test_sobreturnos_api.py`, `test_huecos_servicio.py` y `test_huecos_api.py` siguen verdes sin otros cambios.
- [x] 3.2 Fragmento `SQL_HORARIO_CTE` + `dentro_de_horario` (D4) y su uso en `crear_turno`: normal fuera de horario → 409; sobreturno exceptuado. Verificar con `backend/tests/integration/test_horario_turnos.py`:
  - "Turno dentro del horario" → 201;
  - "Turno que termina fuera del horario" → 409 sin fila;
  - "Profesional sin horario" → 409;
  - "Sobreturno fuera del horario" → 201;
  - franjas contiguas aceptan un turno que las cruza;
  - turno a las 23:45 locales con franja hasta 24:00 y otra desde 00:00 del día siguiente → 201.
- [x] 3.3 Huecos ∩ horario en `_SQL_HUECOS` (D4). Verificar con `backend/tests/integration/test_horario_turnos.py` (sección huecos, mismo archivo que 3.2):
  - "Horario partido recorta los huecos";
  - "Turno que cruza dos franjas contiguas";
  - "Profesional sin horario" → `[]`;
  - "Franja local convertida a UTC" (primer inicio 12:00Z);
  - propiedad: con un horario partido, todo hueco devuelto acepta `crear_turno` normal.

## 4. Seed, integración, documentación y trazabilidad

- [x] 4.1 Seed: horario lunes a viernes `09:00–13:00` y `14:00–18:00` para el profesional seed, idempotente. Verificar con el test de seed existente ampliado (re-ejecutar = sin duplicados).
- [x] 4.2 Suite completa `python -m pytest backend/tests -q` + `ruff check backend` en verde. `EXPLAIN ANALYZE` de huecos con ventana de 7 días y horario partido. Prueba de mutación: quitar `* horario.m` en huecos o el chequeo en `crear_turno`, y verificar que algún test falla. Todo en `verify.md`.
- [x] 4.3 Prueba manual con uvicorn: cargar horario, consultar huecos, turno fuera de horario → 409, sobreturno → 201. Registrar en `verify.md`.
- [x] 4.4 KB `04_modelo_de_datos.md` (entidad FranjaHoraria y `Clinica.zona_horaria`), README (tests del change y "cargar horario antes de dar turnos") y `docs/CONTINUAR.md` (migración 012 tomada, la próxima es la 013). Verificar `diff AGENTS.md CLAUDE.md` vacío si se tocan.
- [x] 4.5 `dominio-agenda`: sección 4 (horario y falla cerrado), matriz (RN-AG-03 y la fila de C-05d) y copias sincronizadas. Verificar con `verificar.py dominio-agenda RN-AG RN-TU` → OK después del archive.

## Workflow follow-up

- `/opsx:archive horario-atencion` tras la revisión humana y con `verify.md` completo.
- Marcar C-05d `[x]` en `CHANGES.md`; C-06 queda desbloqueado.
