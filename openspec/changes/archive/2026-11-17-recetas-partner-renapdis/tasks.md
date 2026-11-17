# Tasks — recetas-partner-renapdis (C-19)

> Governance ALTO: cubierto por la aprobación delegada del usuario (2026-11-16); decisiones en `design.md` §"Decisiones tomadas". Prerrequisitos: C-09 (`008`) y C-18 (`009`, registro de exportación) implementados en la rama.
> Strict TDD: en **cada** tarea, primero el test (RED, verlo fallar por la razón correcta), después el mínimo código (GREEN), después triangular y refactorizar con la suite en verde.
> Tests de integración solo con testcontainers `postgres:16-alpine` (regla dura 9). Solo datos sintéticos (regla dura 14). Ninguna llamada de red real y ningún secreto en el repo (regla 12).
> No tocar archivos de agenda (`profesional_de_usuario` solo se importa), `openspec/changes/huecos-y-sobreturnos/` ni `openspec/changes/archive/2026-11-17-odontograma-evolucion/`.

## 1. Configuración y puerto del partner (sin DB)

- [x] 1.1 RED: `backend/tests/test_settings.py` (casos nuevos): sin `RECETAS_PARTNER`/`RECETAS_PARTNER_KEY`/`ENTORNO` los settings cargan con `recetas_partner = ""`, `recetas_partner_key is None`, `entorno = "produccion"`; un `.env` temporal con `RECETAS_PARTNER_KEY=` vacía no falla y da `None`; con valor, `repr(settings)` no contiene el secreto; `ENTORNO=staging` → error de validación. GREEN: campos y validador en `backend/app/infrastructure/settings.py` (D2). Verificar con `pytest backend/tests/test_settings.py`.
- [x] 1.2 (desbloqueada 2026-11-17: el usuario agregó las 3 líneas a `backend/.env.example`; RED real `KeyError: 'RECETAS_PARTNER'` → GREEN, ver verify.md) RED: `backend/tests/test_env_example.py`: el ejemplo incluye `RECETAS_PARTNER=fake`, `ENTORNO=desarrollo` y `RECETAS_PARTNER_KEY` con placeholder; ningún `VITE_` relacionado con recetas en `frontend/.env.example`. GREEN: actualizar `backend/.env.example`. Verificar con pytest en verde.
- [x] 1.3 RED: `backend/tests/unit/test_recetas_partner.py`: `FakePartner.emitir` devuelve `FAKE-…` determinista por `clave_idempotencia` (misma clave → mismo id, distinta → distinto), `pdf_url` en `https://partner-simulado.invalid/…`, registra la solicitud recibida y propaga `PartnerNoDisponible`/`PartnerRechazo` cuando se le pide. GREEN: `backend/app/infrastructure/recetas/partner_client.py` y `fake.py` (D1). Verificar con pytest en verde.
- [x] 1.4 RED: en el mismo archivo, `obtener_partner(settings)`: vacío → `NoConfigurado` con mensaje que nombra `RECETAS_PARTNER`; `fake` + `desarrollo`/`test`/`demo` → `FakePartner`; `fake` + `produccion` → `NoConfigurado` "deshabilitado en producción" + warning (`caplog`); `farmalink` (desconocido) → `NoConfigurado` + warning; nunca levanta excepción. GREEN: `backend/app/infrastructure/recetas/factory.py`. Verificar con pytest en verde.
- [x] 1.5 RED: `backend/tests/unit/test_recetas_schemas.py`: `RecetaIn` acepta receta con 1 medicamento y orden con 1 estudio; rechaza 0 o 11 ítems, medicamentos en una orden, estudios en una receta, diagnóstico vacío o > 500, `clave_idempotencia` no UUID y los extras `id_externo`/`partner`/`pdf_url`/`simulada`/`autor_usuario_id`/`fecha`; `huella_solicitud` es estable ante el orden de claves y cambia si cambia un ítem. GREEN: `backend/app/domain/recetas/schemas.py` (`extra='forbid'`, unión discriminada por `tipo`) y la función de huella. Verificar con pytest en verde.
- [x] 1.6 RED: `backend/tests/unit/test_recetas_errores.py`: cada error de `backend/app/domain/recetas/errores.py` es `PacienteError` con su status (501/502/422/409/404), `PartnerCaido` serializa `reintentable: true` y la función `sanear_motivo` enmascara la credencial y trunca a 300 caracteres. GREEN: las clases y la función. Verificar con pytest en verde.

## 2. Persistencia: migración 010 e inmutabilidad

- [x] 2.1 RED: `backend/tests/integration/test_migracion_010.py`: el upgrade crea `receta_externa` con `emitida_en` TIMESTAMPTZ, la FK compuesta a `evolucion`, los UNIQUE de clave e id externo, el índice `(clinica_id, paciente_id, id DESC)`, los 2 triggers y el CHECK de `auditoria_hc` con `receta` (nombre real en `pg_constraint`); el downgrade a `009_consentimientos_cumplimiento` lo borra, conserva `fn_rechazar_mutacion()` y restaura el CHECK de la 009; re-upgrade OK; `alembic heads` → un único head. GREEN: `backend/alembic/versions/010_recetas_externas.py` (D3, D6) y `backend/app/domain/recetas/models.py`. Verificar con pytest + `backend/tests/test_migrations_smoke.py`.
- [x] 2.2 RED: `backend/tests/integration/test_recetas_db.py`: UPDATE/DELETE/TRUNCATE rechazados y la fila persiste; `evolucion_id` de otro paciente u otra clínica → 23503; clave repetida en la clínica → 23505; `items` no array → 23514; `pdf_url` sin https → 23514; consultas con otro `clinica_id` → 0 filas (regla 10). GREEN: ajustar constraints. Verificar con pytest en verde.
- [x] 2.3 RED: `backend/tests/integration/test_auditoria_writer.py` (casos nuevos): entidad `receta` aceptada; el diff admite `receta_id`/`evolucion_id`/`partner` y descarta `items`, `diagnostico` e `id_externo`. GREEN: ampliar `backend/app/domain/auditoria/models.py` y `writer.py` (D5). Verificar con pytest en verde.

## 3. Servicio y API de recetas

- [x] 3.1 RED: `backend/tests/integration/test_recetas_api.py` (emisión feliz, con override de `partner_recetas` → `FakePartner`): receta y orden → 201 con `FAKE-…`, `simulada=true`, `pdf_url`, `evolucion_id`, fecha del servidor; el `FakePartner` recibió DNI, obra social y matrícula de la base (no del cuerpo); paciente sin obra social → 201 particular; evento `crear` sin ítems ni diagnóstico. GREEN: `backend/app/domain/recetas/servicios.py` + `backend/app/api/recetas.py` registrado en `create_app()` (D4). Verificar con pytest en verde.
- [x] 3.2 RED: (negocio) odontólogo sin profesional → 422 sin llamar al partner; evolución inexistente o de otro paciente → 422; evolución de otro odontólogo → 422 "evolución propia"; evolución propia corregida → 201; ítems/extras inválidos → 422 sin llamar al partner. GREEN: validaciones del servicio. Verificar con pytest en verde.
- [x] 3.3 RED: (partner) sin override y `RECETAS_PARTNER` vacío → 501 con mensaje que nombra `RECETAS_PARTNER` y 0 filas; `fake` + `ENTORNO=produccion` → 501; `GET` de recetas sin partner → 200; `FakePartner` en modo `PartnerNoDisponible` → 502 `reintentable=true`, sin fila ni evento; en modo `PartnerRechazo` con la credencial sintética en el texto → 422 con `***` y sin la credencial en `caplog`. GREEN: dependencia `partner_recetas()` y mapeo de errores. Verificar con pytest en verde.
- [x] 3.4 RED: (idempotencia) misma clave y contenido → segunda respuesta 200 con el mismo `id`, una sola fila, un solo evento y una sola solicitud en el `FakePartner`; misma clave con otro contenido → 409 sin emitir. GREEN: búsqueda por clave + huella. Verificar con pytest en verde.
- [x] 3.5 RED: `backend/tests/integration/test_recetas_concurrencia.py`: dos emisiones simultáneas con la misma clave (dos hilos) → una sola fila y ambas respuestas con el mismo `id`. GREEN: manejo de 23505 releyendo la fila ganadora. Verificar con pytest en verde.
- [x] 3.6 RED: (lectura) listado más reciente primero con enlaces; detalle; `rid` de otro paciente → 404; paciente sin recetas → `[]`; evento `leer` por consulta; `PUT`/`PATCH`/`DELETE` → 405 y test sobre `app.routes` sin esos métodos en recetas. GREEN: endpoints GET con paginación keyset. Verificar con pytest en verde.
- [x] 3.7 RED: `backend/tests/integration/test_rbac_recetas.py`: recepcionista → 403 en las 3 rutas sin llamar al partner ni auditar; admin emite → 403 y lee → 200; sin `consentimiento_datos` → 403 antes del cuerpo y antes del 501 (con partner sin configurar sigue dando 403); paciente de otra clínica → 404 sin llamar al partner (reglas 10, 16). GREEN: dependencias en el orden de D4. Verificar con pytest en verde.

## 4. Exportación con recetas

- [x] 4.1 RED: `backend/tests/integration/test_exportacion_aislamiento.py` y `test_exportacion_api.py` (casos nuevos): con recetas en las clínicas A y B, la exportación de A trae `recetas.csv` con sus filas (conteo igual al manifest) y ninguna de B. GREEN: sumar `recetas` a `ENTIDADES_EXPORTABLES` en `backend/app/domain/cumplimiento/exportacion.py` (D7). Verificar con pytest en verde.

## 5. Arranque sin credencial

- [x] 5.1 RED: `backend/tests/test_health.py` (casos nuevos): `create_app()` con un entorno sin `RECETAS_PARTNER`, sin `RECETAS_PARTNER_KEY` y con `RECETAS_PARTNER=valor-desconocido` arranca y `/api/health` responde 200. GREEN: confirmar que ni el router ni la factory leen el partner en el import. Verificar con pytest en verde.

## 6. Documentación y trazabilidad

- [x] 6.1 Docstrings del router (orden de chequeo, 501/502, idempotencia, simulado nunca en producción) y sección "Tests de C-19" + "Configurar el partner de recetas" en `README.md` (variables, valores permitidos, que `fake` es solo desarrollo/demo). Verificar que `/docs` muestra las 3 rutas sin campos de servidor en el cuerpo.
- [x] 6.2 Actualizar `knowledge-base/04_modelo_de_datos.md` (entidad `RecetaExterna`) y `knowledge-base/08_arquitectura_propuesta.md` (§Variables de entorno: `RECETAS_PARTNER`, `ENTORNO`) y regenerar `dominio-cumplimiento` (RN-CU-03 → cubierta). Verificar `python .claude/skills/crear-skill-de-dominio/scripts/verificar.py dominio-cumplimiento RN-CU` → `RESULTADO: OK` y `diff AGENTS.md CLAUDE.md` vacío.
- [x] 6.3 Registrar la evidencia de MCP en `docs/skills-mcp/evidencias/README.md` (las 2 consultas Context7 de `design.md` D8 y su impacto en settings y tests) y el uso de `dominio-cumplimiento`. Verificar que el archivo enlaza a este change.

## 7. Verificación integral

- [x] 7.1 (suite completa re-corrida por el orquestador: 1183 passed + la única falla de 1.2, que pasa tras desbloquearla; ruff limpio; head único `010_recetas_externas`; grep de secretos sin coincidencias nuevas) Suite completa `python -m pytest backend/tests -q` y `ruff check backend` en verde, sin regresiones en C-01…C-18. `cd backend && alembic heads` → un único head. Grep de secretos (`APP_USR-`, `EAAB`, `whsec_`, `-----BEGIN`) sin coincidencias nuevas. Guardar la salida en `openspec/changes/recetas-partner-renapdis/verify.md`.
- [x] 7.2 Prueba manual en Swagger (`/docs`) / HTTP con datos sintéticos, registrada en `verify.md`: con `RECETAS_PARTNER=fake` y `ENTORNO=desarrollo`, el odontólogo registra una evolución (C-09) y emite una receta (201 simulada) y la repite con la misma clave (200); recepcionista → 403; `PUT` → 405; reiniciar sin `RECETAS_PARTNER` → la app arranca y la emisión da 501 con el mensaje de configuración; con `ENTORNO=produccion` y `fake` → 501.
- [x] 7.3 Pruebas de mutación de las líneas clave, registradas en `verify.md` y revertidas: (a) quitar la guarda de producción en la factory → falla el test de `fake` + `produccion`; (b) quitar el chequeo de evolución propia → falla el test de "evolución de otro odontólogo"; (c) quitar la búsqueda por `clave_idempotencia` → falla el test de doble clic; (d) quitar el saneo del motivo → falla el test de credencial enmascarada. Si una mutación no rompe ningún test, agregar el test que falta.
- [x] 7.4 Completar `verify.md` con la tabla escenario → test para todos los escenarios de las 2 specs delta y la evidencia TDD (RED/GREEN/TRIANGULATE/REFACTOR por tarea). Verificar que no queda ningún escenario sin test.

## Workflow follow-up

- Revisión humana de `verify.md` (governance ALTO) y `/opsx:archive recetas-partner-renapdis` (después de archivar C-18).
- Marcar C-19 `[x]` en `CHANGES.md` y avisar que la migración 010 está tomada.
- Change posterior: adapter real del partner elegido en PA-08 (contrato HTTP, timeout, credencial en vault).
- Commits con conventional commits, sin co-autoría de IA (regla dura 3), solo cuando el usuario lo pida.
