# Verify — odontograma-evolucion (C-09)

Fecha: 2026-11-17. Resultado: **VERDE, listo para revisión humana y archivo** (governance CRÍTICO; no se archivó ni se hizo commit).

## Entorno

- Windows 11, Docker Desktop (Server 29.7.2); PostgreSQL `postgres:16-alpine` vía testcontainers (nunca SQLite).
- Python 3.13 (intérprete global, sin `.venv`), pytest, ruff.
- Decisiones DC-1…DC-9 de `design.md` aprobadas por el usuario el 2026-11-16 tal como estaban escritas (gate CRÍTICO cumplido; quedó anotado en el design).

## Comandos (desde la raíz del repo)

```
python -m pytest backend/tests -q
ruff check backend
python -m alembic -c backend/alembic.ini heads
python .claude/skills/crear-skill-de-dominio/scripts/verificar.py dominio-clinica RN-CL
```

## Resultados

- Baseline previo al change: **615 passed** (5 min 37 s).
- Con el change: **813 passed, 0 failed** (ver "Suite final"). Tests nuevos: **198** (el resto del aumento es el cambio de la corrida 2, ver abajo).
- Primera corrida con el change: `1 failed, 812 passed`. El único fallo fue `test_migracion_004.py::test_auditoria_checks_y_fk`, que usaba `entidad = 'evolucion'` como ejemplo de valor **inválido**. La 008 amplía el CHECK a propósito (spec delta `clinical-audit`), así que se cambió el ejemplo inválido por `'receta'` (una línea). Es el único test existente modificado en su semántica.
- `ruff check backend`: **All checks passed**.
- `alembic heads` (`python -m alembic -c backend/alembic.ini heads`): **un único head** `008_odontograma_evolucion` (`down_revision = 006_turno_transicion`).
- Migración, ciclo upgrade → downgrade → upgrade: lo ejecuta `test_migracion_008.py::test_downgrade_borra_conserva_funcion_restaura_checks_y_reupgrade` sobre un contenedor real (borra tablas y triggers, **conserva** `fn_rechazar_mutacion()`, restaura los CHECK angostos y el re-upgrade lo deja como estaba). `test_un_unico_head` verifica la cadena. Además `alembic upgrade head` corrió limpio sobre una base vacía en la prueba manual.
- `dominio-clinica`: `verificar.py dominio-clinica RN-CL` → `RESULTADO: OK`; las copias de `.github/` y `.opencode/` idénticas; `diff AGENTS.md CLAUDE.md` vacío.

| Archivo nuevo | Tests | Qué cubre |
|---|---|---|
| unit/test_fdi.py | 6 (parametrizados) | 32 + 20 + 52 piezas, bordes FDI válidos e inválidos, catálogos DC-3 |
| unit/test_clinica_schemas.py | 21 (parametrizados) | `OdontogramaIn` y `EvolucionIn` (extra=forbid, FDI, caras/estados, corrección) |
| unit/test_clinica_errores.py | 3 (parametrizados) | status de cada error + traducción por el handler de `create_app()` |
| integration/test_migracion_008.py | 5 | tablas, índices (GIN `jsonb_path_ops`, único parcial), triggers, TIMESTAMPTZ, CHECK ampliados, head único, downgrade/re-upgrade |
| integration/test_clinica_db.py | 14 | UPDATE/DELETE/TRUNCATE rechazados, autor/profesional nulos, FKs por tenant (23503), 23505, 23514, aislamiento |
| integration/test_odontograma_api.py | 21 | escenarios de `odontogram` + auditoría del odontograma |
| integration/test_odontograma_concurrencia.py | 1 | dos guardados simultáneos |
| integration/test_evoluciones_api.py | 24 | alta, sin autor, correcciones, 405, orden, paginación, auditoría |
| integration/test_evoluciones_concurrencia.py | 1 | dos correcciones simultáneas |
| integration/test_historia_api.py | 5 | historia consolidada y su único evento |
| integration/test_rbac_clinica.py | 8 | 7 rutas × roles, resolver de vínculo, fallo cerrado, 404 sin resolver |
| integration/test_clinica_aislamiento.py | 2 | aislamiento por servicio y por API |
| integration/test_auditoria_writer.py (extendido) | +14 | entidades/acciones/claves nuevas, texto clínico rechazado, CHECK de la DB |

Estabilidad de concurrencia: ambos tests de concurrencia pasaron en 3 corridas (aislados, tras las mutaciones, y en la suite completa).

## Pruebas de mutación (task 7.3)

Cada mutación se aplicó sobre una copia de respaldo, se ejecutó el test y se restauró el archivo (`diff` contra el respaldo vacío).

| # | Mutación | Tests que fallaron |
|---|---|---|
| a | Quitar `raise AutorProfesionalRequerido` (dejar `pass`) en `registrar_evolucion` | `test_evoluciones_api.py::test_odontologo_sin_profesional_422_sin_fila`, `::test_sin_evento_de_escritura_tras_403_422` |
| b | Quitar en la 008 el trigger por fila de `evolucion` | `test_clinica_db.py::test_update_delete_rechazados_y_fila_persiste[UPDATE evolucion…]`, `[DELETE FROM evolucion…]`, `::test_texto_de_evolucion_intacto_tras_intento_de_update`; `test_migracion_008.py::test_upgrade_crea_tablas_indices_y_triggers`, `::test_downgrade_borra_conserva_funcion_restaura_checks_y_reupgrade` |
| c | Quitar el chequeo `original.autor_usuario_id != auth.sub` | `test_evoluciones_api.py::test_otro_odontologo_intenta_corregir_403` |
| d (extra) | No traducir 23505 → `VersionOdontogramaConflicto` en `guardar_odontograma` | `test_odontograma_concurrencia.py::test_dos_guardados_simultaneos_un_201_y_un_409` (revienta con `IntegrityError` en vez del 409) |

Las cuatro mutaciones hacen fallar al menos un test nombrado: no hizo falta agregar tests.

Hallazgo durante el apply: la primera versión del test "ninguna ruta expone PUT/PATCH/DELETE" recorría `app.routes` y pasaba **en vacío** (con esta versión de Starlette `create_app().routes` no expone los paths de los routers incluidos). Se reescribió sobre `app.openapi()["paths"]` (mismo patrón que el test de auditoría de C-08) y exige 4 rutas de odontograma/evoluciones y 7 operaciones en total, para que no pueda volver a pasar en vacío.

## Prueba manual contra la API real (uvicorn + PostgreSQL 16)

- Base temporal `postgres:16-alpine` en el puerto 55432 (el 5432 lo ocupa un PostgreSQL de Windows). `alembic upgrade head` (… → 006 → 008), `seed_core`, un odontólogo con profesional vinculado, un recepcionista y el admin sintético; `uvicorn app.main:app` en el puerto 8765 y pedidos HTTP con `httpx`. Paciente sintético (DNI `91234567`).

| # | Pedido | Respuesta |
|---|---|---|
| 1 | recepción `POST /api/pacientes` + `PATCH` consentimiento | 201 / 200 |
| 2 | odontólogo `POST /odontograma` v1 (16 caries `a_realizar` en `O`) | 201, `version: 1`, autor = su usuario |
| 3 | `POST /odontograma` v2 (`version_esperada: 1`) | 201, `version: 2` |
| 4 | `POST /odontograma` con `version_esperada` vieja (1) | **409** |
| 5 | `POST /odontograma` pieza `55` en dentición permanente | **422** "Pieza 55 no válida para la dentición permanente" |
| 6 | `POST /odontograma` pieza FDI `19` | **422** |
| 7 | `GET /odontograma/actual` / `GET /odontograma` | 200 (`version: 2`) / 200 (2 versiones) |
| 8 | `POST /evoluciones` `{texto, pieza_fdi: 16}` | **201**, autor = usuario 2, `profesional_id: 1`, `fecha_hora` del servidor |
| 9 | recepción `POST /evoluciones` | **403** "Rol insuficiente" |
| 10 | `POST /evoluciones` con `autor_usuario_id` en el cuerpo | **422** `extra_forbidden` |
| 11 | corrección de la evolución 1 con motivo | **201**, `corrige_a_id: 1` (id 3) |
| 12 | segunda corrección de la evolución 1 | **409** "corregí la versión vigente (evolución 3)" |
| 13 | `PUT /evoluciones/1`, `DELETE /evoluciones/1`, `PUT /odontograma` | **405**, **405**, **405** |
| 14 | recepción `GET /historia` | **403** |
| 15 | odontólogo `GET /historia` | 200: `ficha.version=0`, `odontograma.version=2`, evoluciones `[3, 2, 1]` (más reciente primero) |
| 16 | admin `GET /auditoria` | 200: eventos `crear/paciente`, `consentimiento_otorgado`, `crear/odontograma {campos:["16","denticion"]}`, `actualizar/odontograma {campos:["16","21"], version:2}`, 2 `leer/odontograma`, 2 `crear/evolucion`, `corregir/evolucion {evolucion_id:3, corrige_a_id:1}`, 1 `leer/paciente {campos:["ficha","odontograma","evoluciones"]}`. Ningún diff contiene texto clínico, motivo, estados ni caras. |

Después de la prueba se detuvieron el servidor y el contenedor (`docker ps -a` ya no lo lista).

## Desvíos respecto de tasks.md y del design

- `OdontogramaOut` incluye `id` (el design no lo listaba): se necesita para que el cliente referencie la versión y para los tests de auditoría. Es aditivo.
- El primer guardado emite `crear` (con `campos` = códigos FDI presentes + `denticion`) y los siguientes `actualizar`, igual que la ficha de C-08; el spec solo exige `actualizar` para la versión 2.
- Las 7 rutas se documentan en los docstrings del router y se verifican con el test sobre `openapi()` (6.1). Que `/docs` los muestre sin campos de autor lo cubre `extra='forbid'` en `EvolucionIn`/`OdontogramaIn`.
- El único test previo cuyo contenido cambió es `test_migracion_004.py::test_auditoria_checks_y_fk` (ver arriba).
- Context7: no hubo consultas nuevas en el apply; la evidencia de `design.md` D8 se registró como **E7** en `docs/skills-mcp/evidencias/README.md` (6.4).
- La matriz de `dominio-clinica` cita las specs delta por su ruta actual en `openspec/changes/odontograma-evolucion/specs/`. **Al archivar hay que actualizar esas rutas a `openspec/specs/…`** (y volver a correr `verificar.py`).
- Pendiente fuera de este change: re-apuntar `down_revision` a `007_sobreturno_huecos` si C-05c mergea antes (D7), y avisar al equipo que la 008 está tomada (C-11 pasa a 009).

## Trazabilidad escenario → test

### odontogram

| Escenario | Test |
|---|---|
| Primer odontograma | `test_odontograma_api::test_primer_odontograma_201` |
| Nueva versión conserva la anterior | `::test_nueva_version_conserva_la_anterior` |
| Sin hallazgos | `::test_sin_hallazgos_201` |
| Autor o fecha en el cuerpo | `::test_campo_extra_422`; `test_clinica_schemas::test_campos_extra_en_cada_nivel` |
| Guardado sobre versión vieja | `::test_version_vieja_409_sin_version_nueva` |
| Dos guardados simultáneos | `test_odontograma_concurrencia::test_dos_guardados_simultaneos_un_201_y_un_409` |
| Pieza temporal en temporal | `test_odontograma_api::test_temporal_85_201` |
| Pieza temporal en permanente | `::test_pieza_temporal_en_permanente_422` |
| Códigos fuera del rango | `::test_codigos_fuera_de_rango_422`; `test_fdi::test_bordes_invalidos` |
| Límites del rango | `::test_limites_mixta_201`; `test_fdi::test_bordes_validos` |
| Marcas válidas por cara | `::test_marcas_validas_por_cara_se_devuelven_tal_cual` |
| Cara o estado desconocidos | `::test_cara_o_estado_desconocido_o_ausente_con_caras_422` |
| Pieza ausente con caras | `::test_cara_o_estado_desconocido_o_ausente_con_caras_422`; `test_clinica_schemas::test_pieza_ausente_o_extraida_sin_caras` |
| Consulta del vigente | `::test_nueva_version_conserva_la_anterior` (actual = v2) |
| Paciente sin odontograma | `::test_actual_sin_odontograma_version_0` |
| Consulta del historial | `::test_historial_lo_lee_el_admin` |
| Historial vacío | `::test_historial_vacio_200_lista_vacia` |
| Intento de editar por API | `test_evoluciones_api::test_metodos_de_escritura_405_sin_cambios` |
| UPDATE directo rechazado | `test_clinica_db::test_update_delete_rechazados_y_fila_persiste`, `::test_truncate_rechazado` |
| Guardado sin consentimiento | `test_odontograma_api::test_sin_consentimiento_403_sin_fila_y_antes_de_validar` |
| Lectura tras revocar | `::test_lectura_tras_revocar_consentimiento` |
| Odontograma de otra clínica | `test_clinica_aislamiento::test_por_api_a_no_ve_ni_escribe_en_b_y_no_audita` |
| Consulta cruzada a nivel repositorio | `test_clinica_aislamiento::test_servicio_con_clinica_a_no_ve_filas_de_b`; `test_clinica_db::test_consulta_con_otra_clinica_devuelve_0_filas` |

### clinical-evolutions

| Escenario | Test |
|---|---|
| Odontólogo registra una evolución | `test_evoluciones_api::test_alta_201_con_autor_profesional_y_hora_del_servidor` |
| Texto vacío | `::test_texto_vacio_422` |
| Pieza FDI inexistente | `::test_pieza_fdi_19_422`; `test_clinica_db::test_pieza_fdi_invalida_23514` |
| Odontólogo sin profesional vinculado | `::test_odontologo_sin_profesional_422_sin_fila` |
| Autor declarado en el cuerpo | `::test_autor_o_fecha_en_el_cuerpo_422` |
| INSERT directo sin autor | `test_clinica_db::test_insert_sin_autor_o_profesional_falla` |
| PUT / DELETE sobre una evolución | `test_evoluciones_api::test_metodos_de_escritura_405_sin_cambios`, `::test_ninguna_ruta_de_odontograma_o_evoluciones_expone_put_patch_delete` |
| UPDATE o DELETE directo rechazado | `test_clinica_db::test_update_delete_rechazados_y_fila_persiste`, `::test_truncate_rechazado` |
| Autor corrige su evolución | `::test_autor_corrige_original_intacta_y_corregida_por` |
| Corrección sin motivo | `::test_correccion_sin_motivo_o_motivo_sin_correccion_422` |
| Corregir una ya corregida | `::test_corregir_ya_corregida_409_nombra_la_vigente_y_corregir_la_vigente_201` |
| Correcciones simultáneas | `test_evoluciones_concurrencia::test_dos_correcciones_simultaneas_un_201_y_un_409` |
| Otro odontólogo intenta corregir | `::test_otro_odontologo_intenta_corregir_403` |
| Corregir evolución de otro paciente / clínica | `::test_corregir_evolucion_de_otro_paciente_o_clinica_422`; `test_clinica_db::test_corrige_a_id_de_otro_paciente_23503` |
| Evoluciones ordenadas | `::test_orden_descendente_con_corregida_por_id` |
| Paginación sin repetidos | `::test_paginacion_sin_repetidos`, `::test_limit_fuera_de_rango_422` |
| Evolución de otro paciente por id | `::test_evolucion_de_otro_paciente_por_id_404` |
| Evolución sin consentimiento | `::test_sin_consentimiento_403_antes_de_validar` |
| Lectura tras revocación | `::test_lectura_tras_revocacion_200` |
| Evoluciones de otra clínica | `test_clinica_aislamiento::test_por_api_a_no_ve_ni_escribe_en_b_y_no_audita` |
| Consulta cruzada a nivel repositorio | `test_clinica_aislamiento::test_servicio_con_clinica_a_no_ve_filas_de_b` |
| Profesional de otra clínica a nivel base | `test_clinica_db::test_profesional_de_otra_clinica_23503` |

### clinical-record (historia consolidada)

| Escenario | Test |
|---|---|
| Historia completa | `test_historia_api::test_historia_completa` |
| Paciente sin datos clínicos | `::test_paciente_sin_datos_clinicos` |
| Historia de otra clínica | `::test_paciente_de_otra_clinica_404` |
| Más de una página | `::test_51_evoluciones_50_mas_cursor_que_continua` |

### clinical-audit

| Escenario | Test |
|---|---|
| Alta de paciente / ficha auditadas (vigentes de C-08) | `test_pacientes_api`, `test_ficha_api` (sin regresión) |
| Nueva versión de odontograma auditada | `test_odontograma_api::test_evento_actualizar_con_codigos_fdi_sin_estados_ni_caras`, `::test_evento_crear_en_la_primera_version_lista_las_piezas` |
| Alta y corrección de evolución auditadas | `test_evoluciones_api::test_auditoria_de_alta_sin_texto`, `::test_auditoria_de_correccion_sin_texto_ni_motivo` |
| Escritura rechazada no deja evento | `test_odontograma_api::test_sin_evento_de_escritura_tras_403_409_422`; `test_evoluciones_api::test_sin_evento_de_escritura_tras_403_422` |
| Falla al auditar no deja la escritura | `test_odontograma_api::test_falla_al_auditar_no_deja_version`; `test_evoluciones_api::test_falla_al_auditar_no_deja_evolucion` |
| Lectura de evoluciones y odontograma auditada | `test_odontograma_api::test_evento_leer_en_actual_e_historial`; `test_evoluciones_api::test_auditoria_de_lecturas_listado_y_una` |
| Lectura de la historia consolidada auditada | `test_historia_api::test_un_solo_evento_leer_paciente_con_los_tres_campos` |
| Diff de evolución sin texto clínico | `test_auditoria_writer::test_sigue_rechazando_texto_clinico_y_tipos_invalidos_en_c09`, `::test_acepta_entidades_acciones_y_claves_de_c09` |
| Mutación de evolución u odontograma rechazada | `test_clinica_db::test_update_delete_rechazados_y_fila_persiste`, `::test_truncate_rechazado` |

### access-control

| Escenario | Test |
|---|---|
| Recepcionista en odontograma, evoluciones o historia | `test_rbac_clinica::test_recepcionista_403_en_las_7_rutas_sin_evento` |
| Paciente-enlace en endpoints clínicos | `::test_paciente_enlace_403_en_las_7_rutas` |
| Admin lee | `::test_admin_sin_rol_odontologo_lee_200_y_escribe_403` |
| Recepcionista registra una evolución / guarda odontograma | `::test_recepcionista_403_en_las_7_rutas_sin_evento` |
| Admin sin rol odontólogo guarda odontograma o evolución | `::test_admin_sin_rol_odontologo_lee_200_y_escribe_403` |
| Dueño admin + odontólogo | `::test_dueno_admin_y_odontologo_escribe_201` |
| Regla de vínculo niega acceso / falla cerrado | `::test_resolver_que_niega_403_en_odontograma_evoluciones_e_historia`, `::test_resolver_que_lanza_excepcion_falla_cerrado_403` |
| Paciente de otra clínica sin evaluar el vínculo | `::test_paciente_de_otra_clinica_404_sin_invocar_el_resolver` |
| Regla interina dentro de la clínica | `test_odontograma_api` / `test_evoluciones_api` (odontólogo sin turnos opera sobre pacientes de su clínica) |

No queda ningún escenario de las 5 specs sin test.

## Evidencia TDD (RED → GREEN → TRIANGULATE → REFACTOR)

| Tarea | Test | Capa | Safety net | RED | GREEN | TRIANGULATE | REFACTOR |
|---|---|---|---|---|---|---|---|
| 1.1 | `unit/test_fdi.py` | Unit | baseline 615/615 (archivos nuevos) | `ImportError` (módulo inexistente) | 6 tests | bordes ×5 válidos, ×9 inválidos, 3 dentíciones | ruff format |
| 1.2 | `unit/test_clinica_schemas.py` | Unit | idem | `ImportError` | 21 tests | permanente/temporal/mixta, 4 niveles de campo extra, 52+1 piezas | ruff format |
| 1.3 | `unit/test_clinica_schemas.py` | Unit | idem | `ImportError` | incluido | texto 0/10 000/10 001, motivo 500/501, 6 piezas inválidas | ruff format |
| 1.4 | `unit/test_clinica_errores.py` | Unit | idem | `ImportError` | 3 tests (×6 errores) | status y handler real | ruff format |
| 2.1 | `integration/test_migracion_008.py` | Integración PG | suite 615/615 | 6 fallos (sin migración) | 5 tests | upgrade, downgrade, re-upgrade, head único | docstring de la 008 |
| 2.2 | `integration/test_clinica_db.py` | Integración PG | idem | (tabla inexistente) | 14 tests | 4 mutaciones, 6 piezas FDI inválidas, 5 válidas, 3 CHECK | ruff format |
| 2.3 | `integration/test_auditoria_writer.py` | Integración PG | writer C-08 intacto | 7 fallos | +14 tests | 6 combinaciones válidas, 6 diffs inválidos, CHECK en DB | docstring del writer |
| 3.1–3.3 | `integration/test_odontograma_api.py`, `test_odontograma_concurrencia.py` | Integración API | idem | falla por `servicios` inexistente | 22 tests | felices, errores, bordes, auditoría | `id` en `OdontogramaOut` |
| 4.1–4.4 | `integration/test_evoluciones_api.py`, `test_evoluciones_concurrencia.py` | Integración API | idem | idem | 25 tests | alta, sin autor, correcciones, 405, paginación | test de rutas reescrito (ver hallazgo) |
| 5.1 | `integration/test_historia_api.py` | Integración API | idem | idem | 5 tests | completa, vacía, 51 evoluciones, otra clínica | — |
| 5.2 | `integration/test_rbac_clinica.py` | Integración API | idem | idem | 8 tests | 7 rutas × 4 roles, resolver niega/lanza/404 | ruff format |
| 5.3 | `integration/test_clinica_aislamiento.py` | Integración API | idem | idem | 2 tests | servicio y 8 rutas por API | `count` antes/después |

Nota de honestidad TDD: los tests de las tareas 3 a 5 se escribieron todos antes del código de servicio/router, pero se ejecutaron por primera vez juntos con la migración y los modelos ya presentes; el RED de esas tareas es el fallo por módulo inexistente de la tarea 2 (verificado en la corrida de 2.1/2.3) y no una corrida por tarea.

## Suite final

Ver la línea de resultado al pie, añadida tras la corrida completa final.

**Suite completa final: `813 passed, 0 failed` en 7 min 11 s (baseline 615). `ruff check backend`: All checks passed. Un único head de Alembic.**
