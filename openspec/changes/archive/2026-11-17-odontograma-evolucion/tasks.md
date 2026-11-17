# Tasks — odontograma-evolucion (C-09)

> Governance CRÍTICO: antes de la tarea 1.1, el usuario confirma `design.md` §"Decisiones a confirmar por el usuario" (DC-1…DC-9). Si cambia algún default, actualizar specs y tasks antes de codificar.
> Strict TDD: en **cada** tarea, primero el test (RED, verlo fallar por la razón correcta), después el mínimo código (GREEN), después triangular y refactorizar con la suite en verde.
> Tests de integración solo con testcontainers `postgres:16-alpine` (regla dura 9; Docker Desktop corriendo). Solo datos sintéticos (regla dura 14).
> No tocar `backend/app/domain/agenda/turnos.py`, `huecos.py`, `backend/app/api/turnos.py`, `backend/app/api/agenda.py` ni `openspec/changes/huecos-y-sobreturnos/`.

## 1. Dominio puro: FDI y schemas (sin DB)

- [x] 1.1 RED: `backend/tests/unit/test_fdi.py` con `PERMANENTES` (32), `TEMPORALES` (20), `piezas_validas("mixta")` (52), bordes válidos `11`, `18`, `48`, `51`, `85` e inválidos `10`, `19`, `49`, `56`, `86`, `90`, y `es_pieza_fdi`. GREEN: `backend/app/domain/clinica/fdi.py` (D2) con los catálogos de estados de pieza y de cara (DC-3). Verificar con `pytest backend/tests/unit/test_fdi.py`.
- [x] 1.2 RED: `backend/tests/unit/test_clinica_schemas.py` para `OdontogramaIn`. Debe aceptar piezas vacías y las marcas `existente`/`a_realizar`. Debe rechazar, sin excepción, una pieza temporal en dentición permanente, cara `X`, estado `blanqueamiento`, pieza `ausente`/`extraida` con caras, un código de cara usado en la pieza, un campo extra en cada nivel y más de 52 piezas. GREEN: `backend/app/domain/clinica/schemas.py` con `extra='forbid'` (regla dura 4). Verificar con pytest en verde.
- [x] 1.3 RED: en el mismo archivo, `EvolucionIn`:
  - texto en blanco → error, y el de más de 10 000 caracteres → error;
  - `pieza_fdi = 19` → error;
  - `autor_usuario_id`/`profesional_id`/`fecha_hora` → error (extra);
  - `corrige_a_id` sin `motivo_correccion` o viceversa → error;
  - el motivo de más de 500 caracteres → error.

  GREEN: el schema y los schemas de salida (`OdontogramaOut`, `EvolucionOut` con `corregida_por_id`, `HistoriaOut`). Verificar con pytest en verde.
- [x] 1.4 RED: `backend/tests/unit/test_clinica_errores.py` comprueba que cada error de `backend/app/domain/clinica/errores.py` (D6) es `PacienteError` con su `status_code` (422/409/403/404) y que el handler de `create_app()` lo traduce (ruta de prueba con `TestClient`). GREEN: las clases. Verificar con pytest en verde.

## 2. Persistencia: migración 008, modelos e inmutabilidad

- [x] 2.1 RED: `backend/tests/integration/test_migracion_008.py`. El upgrade crea:
  - `odontograma` y `evolucion`, con `created_at`/`fecha_hora` TIMESTAMPTZ (regla dura 7);
  - los índices `(clinica_id, paciente_id, …)`, el GIN `jsonb_path_ops`, `uq_evolucion_corrige_a` y los 4 triggers;
  - en `auditoria_hc`, los CHECKs ampliados, verificando el nombre real en `pg_constraint`.

  El downgrade borra todo eso, **conserva** `fn_rechazar_mutacion()` y restaura los CHECKs angostos, y el re-upgrade lo restaura. Hay un único head en `alembic heads`. GREEN: `backend/alembic/versions/008_odontograma_evolucion.py` (D7, `down_revision = "006_turno_transicion"`; re-apuntar a `007_sobreturno_huecos` si C-05c ya mergeó) y los modelos `Odontograma`/`Evolucion` en `backend/app/domain/clinica/models.py`. Verificar con pytest + `backend/tests/test_migrations_smoke.py` en verde.
- [x] 2.2 RED: `backend/tests/integration/test_clinica_db.py`:
  - `UPDATE`/`DELETE`/`TRUNCATE` sobre `odontograma` y `evolucion` fallan y las filas persisten (escenarios "UPDATE directo rechazado" y "Mutación de evolución u odontograma rechazada");
  - INSERT con autor o profesional nulo → falla ("INSERT directo sin autor");
  - `profesional_id` de otra clínica → 23503;
  - `corrige_a_id` de otro paciente → 23503;
  - segunda corrección de la misma evolución → 23505;
  - `pieza_fdi = 19` → 23514;
  - `piezas` como array → 23514;
  - consulta del repositorio con otro `clinica_id` → 0 filas (regla dura 10).

  GREEN: ajustar los constraints si algo pasa de largo. Verificar con pytest en verde.
- [x] 2.3 RED: extender `backend/tests/integration/test_auditoria_writer.py` para que acepte `entidad` `odontograma`/`evolucion`, `accion` `corregir` y las claves `evolucion_id`, `corrige_a_id` y `odontograma_id`, y siga rechazando un texto clínico en el diff (`texto`, `motivo_correccion`, `piezas`). GREEN: `ACCIONES`/`ENTIDADES` en `backend/app/domain/auditoria/models.py` y la allowlist de `writer.py` (D5). Verificar con los tests de C-08 del writer sin regresión.

## 3. Servicio y API del odontograma

- [x] 3.1 RED: fixture `staff_c09` en `backend/tests/integration/conftest.py`: odontólogo O vinculado a un profesional, odontólogo P vinculado a otro, odontólogo sin profesional, admin, recepcionista, paciente con consentimiento, paciente sin consentimiento y paciente de la clínica B, todos sintéticos. Después `backend/tests/integration/test_odontograma_api.py`, un test por escenario de `specs/odontogram`:
  - felices: primer odontograma 201, nueva versión conserva la anterior, sin hallazgos, temporal `85`, límites `11/48/51/85`, marcas válidas por cara;
  - errores de negocio: versión vieja 409, pieza `55` en permanente 422, cara/estado desconocidos 422, pieza ausente con caras 422, campo extra 422, sin consentimiento 403 sin fila;
  - bordes: códigos fuera de rango 422, actual con `version = 0`, historial vacío, lectura tras revocar.

  GREEN: `backend/app/domain/clinica/servicios.py` (`guardar_odontograma`, `odontograma_vigente`, `listar_odontogramas`, con auditoría D5) y las rutas en `backend/app/api/historia_clinica.py` registradas en `backend/app/main.py`. Verificar con pytest en verde.
- [x] 3.2 RED: "Dos guardados simultáneos" en `backend/tests/integration/test_odontograma_concurrencia.py` (`ThreadPoolExecutor`, mismo patrón que `test_turnos_concurrencia.py`): exactamente un 201 y un 409, y una sola versión 3. GREEN: traducir 23505 → `VersionOdontogramaConflicto`. Verificar con pytest en verde.
- [x] 3.3 RED: auditoría del odontograma en `test_odontograma_api.py`:
  - evento `actualizar` con `odontograma_id`, `version` y `campos = ["16","21"]`, sin estados ni caras;
  - evento `leer` en actual e historial;
  - ningún evento de escritura tras 403/409/422;
  - "falla al auditar no deja versión" (monkeypatch del writer).

  GREEN: ajustar el servicio. Verificar con pytest en verde.

## 4. Servicio y API de evoluciones

- [x] 4.1 RED: `backend/tests/integration/test_evoluciones_api.py`:
  - alta 201 con autor, profesional y `fecha_hora` del servidor;
  - texto vacío 422; `pieza_fdi = 19` 422;
  - odontólogo sin profesional vinculado → 422 sin fila ("Evolución sin autor rechazada");
  - `autor_usuario_id`/`profesional_id`/`fecha_hora` en el cuerpo → 422;
  - sin consentimiento → 403;
  - lectura tras revocación → 200.

  GREEN: `registrar_evolucion` en `servicios.py` (autor vía `profesional_de_usuario`, D3) y las rutas `GET`/`POST /evoluciones` y `GET /evoluciones/{evolucion_id}`. Verificar con pytest en verde.
- [x] 4.2 RED: correcciones (D4) en `test_evoluciones_api.py`:
  - el autor corrige → 201, la original intacta y `corregida_por_id`;
  - corrección sin motivo o motivo sin corrección → 422;
  - otro odontólogo → 403;
  - `corrige_a_id` de otro paciente o de otra clínica → 422;
  - corregir una ya corregida → 409 nombrando la vigente;
  - corregir la corrección vigente → 201.

  Concurrencia en `backend/tests/integration/test_evoluciones_concurrencia.py`: dos correcciones simultáneas → un 201 y un 409. GREEN: el servicio. Verificar con pytest en verde.
- [x] 4.3 RED: sin edición ni borrado:
  - `PUT`/`PATCH`/`DELETE` a `/evoluciones/{id}` y a `/odontograma` → 405, con el conteo y el contenido sin cambios;
  - un test que recorre `app.routes` y comprueba que ninguna ruta de odontograma o evoluciones declara esos métodos (patrón de `test_ninguna_ruta_expone_escritura_de_auditoria`).

  GREEN: no debería requerir código. Si alguno pasa sin ruta GET, agregarla. Verificar con pytest en verde.
- [x] 4.4 RED: orden y paginación:
  - E1, E2, E3 (E3 corrige a E1) → E3, E2, E1 con `corregida_por_id`;
  - `limit = 2` + `next_cursor` sin repetidos;
  - `limit` 0 o 201 → 422;
  - `GET /pacientes/{A}/evoluciones/{id de B}` → 404.

  Auditoría: `crear`/`corregir` con `evolucion_id`/`corrige_a_id` y sin texto ni motivo en el diff; `leer` en el listado y en una sola. GREEN: el servicio. Verificar con pytest en verde.

## 5. Historia consolidada, RBAC y aislamiento

- [x] 5.1 RED: `backend/tests/integration/test_historia_api.py`:
  - historia completa (ficha v2 + odontograma v1 + 3 evoluciones ordenadas);
  - paciente sin datos (`version = 0` y lista vacía);
  - 51 evoluciones → 50 + `next_cursor` que continúa en `/evoluciones`;
  - paciente de otra clínica → 404;
  - **un solo** evento `leer` / `paciente` con `campos = ["ficha","odontograma","evoluciones"]`.

  GREEN: `historia_clinica` en `servicios.py` con consultas sin auditoría propia (D5) y la ruta. Verificar con pytest en verde.
- [x] 5.2 RED: `backend/tests/integration/test_rbac_clinica.py`:
  - recepcionista → 403 en las 7 rutas, sin evento de lectura;
  - paciente-enlace → 403;
  - admin sin rol odontólogo: lee 200, escribe 403;
  - dueño admin + odontólogo escribe 201;
  - resolver de vínculo que niega → 403 en odontograma, evoluciones e historia, y si lanza excepción → 403 (falla cerrado);
  - paciente de otra clínica → 404 sin invocar el resolver.

  GREEN: no debería requerir código nuevo (reutiliza `paciente_lectura`/`paciente_escritura`). Verificar con pytest en verde.
- [x] 5.3 RED: aislamiento en `backend/tests/integration/test_tenant_isolation.py` (o `test_clinica_db.py`): datos en la clínica B, y consultas de odontograma y evoluciones del servicio con el `clinica_id` de A → 0 filas. Por API, A no ve ni escribe en B (404) y no queda ningún evento. GREEN: ajustar los filtros si algo falla. Verificar con pytest en verde.

## 6. Documentación y trazabilidad

- [x] 6.1 Documentar las rutas en los docstrings del router (orden de chequeo, sin PUT/DELETE, autor desde el JWT) y agregar la sección "Tests de C-09" en `README.md`. Verificar que `/docs` muestra las 7 rutas con sus schemas (sin campos de autor en los cuerpos).
- [x] 6.2 Actualizar `knowledge-base/04_modelo_de_datos.md` (Odontograma: snapshot versionado y forma del JSONB; Evolucion: `corrige_a_id` y `motivo_correccion`) y, si el usuario cambió algún DC, `knowledge-base/03_actores_y_roles.md`. Verificar con `diff AGENTS.md CLAUDE.md` vacío si se tocan.
- [x] 6.3 Regenerar `dominio-clinica` con `crear-skill-de-dominio`: RN-CL-01, RN-CL-02 y RN-CL-03 → `cubierta` con las specs y los tests nuevos, y RN-CL-04 sigue pendiente. Verificar con `python .claude/skills/crear-skill-de-dominio/scripts/verificar.py dominio-clinica RN-CL` → `RESULTADO: OK` y las copias de `.github/` y `.opencode/` idénticas.
- [x] 6.4 Registrar la evidencia de MCP como **E7** en `docs/skills-mcp/evidencias/README.md` (las 2 consultas Context7 de `design.md` D8 y su impacto en la migración y el modelo) y el uso de `dominio-clinica`. Verificar que el archivo enlaza a este change.

## 7. Verificación integral (CRÍTICO)

- [x] 7.1 Suite completa `python -m pytest backend/tests -q` y `ruff check backend` en verde, sin regresiones en C-01…C-08, C-05 y C-05b. Confirmar `cd backend && alembic heads` → un único head. Guardar la salida en `openspec/changes/odontograma-evolucion/verify.md`.
- [x] 7.2 Prueba manual en Swagger (`/docs`) con datos sintéticos, registrando las respuestas en `verify.md`:
  - el odontólogo guarda el odontograma v1 y luego v2;
  - `version_esperada` vieja → 409;
  - registra una evolución y la corrige;
  - `PUT` a la evolución → 405;
  - el recepcionista pide la historia → 403;
  - el admin consulta `/auditoria` y ve los eventos sin texto clínico.
- [x] 7.3 Pruebas de mutación de las líneas clave, registradas en `verify.md` y revertidas después. Cada mutación tiene que hacer fallar al menos un test nombrado:
  - (a) quitar el `raise AutorProfesionalRequerido` cuando `profesional_de_usuario` devuelve `None` → falla el test de "Odontólogo sin profesional vinculado";
  - (b) quitar en la 008 el trigger por fila de `evolucion` → falla el test de UPDATE/DELETE de `test_clinica_db.py`;
  - (c) quitar el chequeo de autor en la corrección → falla "Otro odontólogo intenta corregir".

  Si una mutación no hace fallar ningún test, agregar el test que falta (lección de C-05b).
- [x] 7.4 Completar `verify.md` con la tabla escenario → test para todos los escenarios de las 5 specs delta y con la evidencia TDD (RED/GREEN/TRIANGULATE/REFACTOR por tarea). Verificar que no queda ningún escenario sin test.

## Workflow follow-up

- Revisión humana de `verify.md` (governance CRÍTICO) y `/opsx:archive odontograma-evolucion`.
- Marcar C-09 `[x]` en `CHANGES.md`. Avisar al equipo que la migración 008 está tomada (C-11 pasa a 009).
- Commits con conventional commits, sin co-autoría de IA (regla dura 3), en la rama `feat/clinica-c09`, solo cuando el usuario lo pida.
