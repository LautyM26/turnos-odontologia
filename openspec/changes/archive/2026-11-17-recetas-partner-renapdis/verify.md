# Verify — recetas-partner-renapdis (C-19)

Fecha: 2026-11-17. Resultado: **VERDE** (governance ALTO). El pendiente humano de la task 1.2 quedó resuelto (ver "Cierre del bloqueo").

## Cierre del bloqueo (2026-11-17, orquestador)

- El usuario agregó a `backend/.env.example` las líneas `RECETAS_PARTNER=fake`, `ENTORNO=desarrollo` y `RECETAS_PARTNER_KEY=changeme-solo-placeholder` (sin valores reales).
- `python -m pytest backend/tests/test_env_example.py backend/tests/test_settings.py -q` → **25 passed** (incluye `test_backend_env_example_recetas_c19`, antes en rojo con `KeyError: 'RECETAS_PARTNER'`).
- Suite completa re-corrida por el orquestador tras el fix de `TRUNCATE … CASCADE`: **1183 passed, 1 failed** en 9 min 59 s; la única falla era `test_backend_env_example_recetas_c19`, que ahora pasa → **1184/1184 en verde**.
- `ruff check backend` → All checks passed. `python -m alembic -c backend/alembic.ini heads` → `010_recetas_externas (head)`.
- Grep de secretos (`APP_USR-`, `EAAB`, `whsec_`, `-----BEGIN`): solo los marcadores de los propios tests y los ejemplos con `…` de `knowledge-base/08`; ninguna credencial.

## Entorno

- Windows 11, Docker Desktop; PostgreSQL `postgres:16-alpine` vía testcontainers (nunca SQLite).
- Python 3.13 (intérprete global, sin `.venv`), pytest, ruff.
- Decisiones DT-1…DT-8 de `design.md` aprobadas por el usuario (aprobación delegada del 2026-11-16) y aplicadas tal como estaban escritas. Sin desvíos de diseño salvo los de la sección "Desvíos".

## Comandos (desde la raíz del repo)

```
python -m pytest backend/tests -q
ruff check backend
python -m alembic -c backend/alembic.ini heads
python .claude/skills/crear-skill-de-dominio/scripts/verificar.py dominio-cumplimiento RN-CU
```

## Resultados

- Baseline previo al change: **1057 passed** (8 min 53 s).
- Con el change: **1183 passed, 1 failed (la esperada de 1.2)** sobre 1184 tests (+127 nuevos); corrida completa de 10 min 23 s con 2 fallas (`test_env_example.py::test_backend_env_example_recetas_c19` y `test_clinica_db.py::test_truncate_rechazado[evolucion]`); la segunda se corrigió (ver "Desvíos") y `test_clinica_db.py` + `test_cumplimiento_db.py` se re-corrieron en verde (58 passed).
- `ruff check backend`: **All checks passed**.
- `alembic heads`: un único head, `010_recetas_externas` (`down_revision = 009_consentimientos_cumplimiento`).
- Migración: `test_migracion_010.py` cubre upgrade, downgrade a la 009 (conserva `fn_rechazar_mutacion()` y restaura el CHECK de `auditoria_hc`) y re-upgrade; `test_migracion_009.py` se aflojó (ya no fija el head, igual que C-18 hizo con la 008).
- `verificar.py dominio-cumplimiento RN-CU`: **RESULTADO: OK**; `diff AGENTS.md CLAUDE.md` vacío; las 3 copias de la skill son idénticas (RN-CU-03 pasa a `cubierta`).
- Grep de secretos (`APP_USR-`, `EAAB`, `whsec_`, `-----BEGIN`): sin coincidencias nuevas (solo las listas de marcadores de los tests de settings/env que ya existían).

## Bloqueo (task 1.2) y desvíos

- **`backend/.env.example` no se pudo editar**: las reglas de permisos del entorno deniegan su lectura y escritura. Quedó escrito el test (`test_env_example.py::test_backend_env_example_recetas_c19`) y **falla a propósito** hasta que alguien agregue estas 3 líneas (sin valores reales) a `backend/.env.example`: `RECETAS_PARTNER=fake`, `ENTORNO=desarrollo` y `RECETAS_PARTNER_KEY=changeme-solo-placeholder` (reemplazando la línea actual de `RECETAS_PARTNER_KEY` si existe). Por eso la suite completa tiene **exactamente 1 falla esperada** y la task 1.2 queda sin marcar.
- Los settings ya cargan sin esas variables (defaults seguros), así que el boot no depende de ese archivo.
- La firma de `EvolucionNoValidaParaReceta` usa `ajena: bool` (no `propia`): mensaje "evolución propia" cuando la evolución es de otro odontólogo. Sin impacto en la spec.
- **Test de C-09 ajustado**: `test_clinica_db.py::test_truncate_rechazado` ahora usa `TRUNCATE {tabla} CASCADE`. Con `receta_externa` referenciando `evolucion`, un `TRUNCATE evolucion` simple lo rechaza PostgreSQL por la FK ("cannot truncate a table referenced in a foreign key constraint") antes de llegar al trigger; con `CASCADE` el trigger append-only vuelve a ser el que rechaza. La inmutabilidad sigue probada y la mutación sigue rechazada.
- RED: los tests se escribieron antes que el código; los de integración no se ejecutaron en rojo (el módulo bajo prueba no existía, `ImportError`). La validación de que los tests discriminan está en las mutaciones de abajo y en el RED real de 1.2 (`KeyError: 'RECETAS_PARTNER'`).

## Pruebas de mutación (task 7.3)

Cada mutación se aplicó con un script (backups con nombre único por archivo), se corrió el subconjunto y se restauró el archivo (verificado: ninguna línea `if False` quedó en el código).

| # | Mutación | Tests que fallan |
|---|---|---|
| a | Factory: quitar la guarda `entorno == "produccion"` para `fake` | `test_recetas_partner.py::test_factory_fake_en_produccion_bloqueado_con_warning`, `test_recetas_api.py::test_fake_en_produccion_501` (2 failed) |
| b | Servicio: quitar el chequeo de evolución propia (`autor_usuario_id != auth.sub`) | `test_recetas_api.py::test_evolucion_de_otro_odontologo_422_evolucion_propia` (1 failed) |
| c | Servicio: quitar la búsqueda previa por `clave_idempotencia` | `test_recetas_api.py::test_misma_clave_y_contenido_200_misma_receta_una_emision`, `::test_misma_clave_otro_contenido_409_sin_emitir` (2 failed); el test de concurrencia sigue verde porque la carrera la cubre el UNIQUE (23505 → releer la ganadora) |
| d | Errores: quitar el enmascarado de la credencial en `sanear_motivo` | `test_recetas_errores.py::test_sanear_enmascara_credencial`, `test_recetas_api.py::test_partner_rechaza_422_con_credencial_enmascarada` (2 failed) |

## Prueba manual contra la API real (uvicorn + PostgreSQL 16)

`postgres:16-alpine` en el puerto 55434, `alembic upgrade head`, `seed_demo_clinica.py` (datos sintéticos), uvicorn en el puerto 8002. Contenedor y API eliminados al terminar. Fase 1: `ENTORNO=desarrollo RECETAS_PARTNER=fake`.

```
POST /api/pacientes/1/evoluciones -> 201 (evolución propia)
POST /api/pacientes/1/recetas -> 201 simulada=true, partner=fake, id_externo=FAKE-a605a475-…, pdf_url=https://partner-simulado.invalid/recetas/FAKE-….pdf
POST /api/pacientes/1/recetas (misma clave y contenido) -> 200, mismo id/id_externo
POST /api/pacientes/1/recetas (misma clave, otro diagnóstico) -> 409 "La clave de idempotencia ya se usó con otro contenido"
GET  /api/pacientes/1/recetas -> 200 (1 receta con enlace)
POST /api/pacientes/1/recetas (recepción) -> 403 "Rol insuficiente"
POST /api/pacientes/3/recetas (paciente sin consentimiento) -> 403 "Falta el consentimiento de datos del paciente"
POST /api/pacientes/1/recetas (evolución inexistente) -> 422 "La evolución no existe para este paciente"
POST /api/pacientes/1/recetas (evolución de otro paciente) -> 422 "La evolución no existe para este paciente"
PUT  /api/pacientes/1/recetas -> 405
```

(La evolución de otro odontólogo → 422 "evolución propia" no se pudo probar a mano porque el seed solo trae un odontólogo; la cubre `test_evolucion_de_otro_odontologo_422_evolucion_propia`.)

Fase 2, reinicio con `ENTORNO=desarrollo RECETAS_PARTNER=` (vacío): el boot funciona (`/api/health` → 200); `POST …/recetas` → **501** "Configurá RECETAS_PARTNER para emitir recetas electrónicas"; `GET …/recetas` → 200 (las consultas no dependen del partner).

Fase 3, reinicio con `ENTORNO=produccion RECETAS_PARTNER=fake`: boot OK; `POST …/recetas` → **501** "El partner simulado está deshabilitado en producción"; `GET` → 200.

## Matriz escenario → test

| Requirement · escenario | Test |
|---|---|
| Config · Arranque sin credencial | `test_settings.py::test_settings_recetas_defaults_seguros`; `test_health.py::test_arranca_sin_credencial_de_recetas_ni_partner_valido[…]` |
| Config · Credencial vacía en el archivo de entorno | `test_settings.py::test_settings_recetas_key_vacia_en_dotenv_es_none` |
| Config · Credencial nunca expuesta | `test_settings.py::test_settings_recetas_key_con_valor_no_aparece_en_repr`; `test_recetas_api.py::test_partner_rechaza_422_con_credencial_enmascarada` |
| Config · Valor de partner desconocido | `test_recetas_partner.py::test_factory_desconocido_no_configurado_con_warning`; `test_health.py` (`valor-desconocido`) |
| Config · Ejemplo de entorno de desarrollo | `test_env_example.py::test_backend_env_example_recetas_c19` (**falla hasta editar `.env.example`**), `::test_frontend_env_example_sin_vars_de_recetas` |
| Emisión · Receta emitida con partner simulado | `test_recetas_api.py::test_receta_201_simulada_con_datos_del_servidor` |
| Emisión · Orden de estudio emitida | `test_recetas_api.py::test_orden_de_estudio_201` |
| Emisión · Ítems fuera de rango | `test_recetas_schemas.py::test_cantidad_de_items_fuera_de_rango`, `::test_borde_10_items_ok`; `test_recetas_api.py::test_cuerpo_invalido_422_sin_llamar_al_partner[…]` |
| Emisión · Datos de servidor en el cuerpo | `test_recetas_schemas.py::test_extras_de_servidor_rechazados`; `test_recetas_api.py::test_cuerpo_invalido_422_sin_llamar_al_partner[…]` |
| Datos desde servidor · Datos tomados de la base | `test_recetas_api.py::test_partner_recibe_datos_de_la_base_no_del_cuerpo` |
| Datos desde servidor · Odontólogo sin profesional | `test_recetas_api.py::test_odontologo_sin_profesional_422_sin_llamar_al_partner` |
| Datos desde servidor · Paciente sin obra social | `test_recetas_api.py::test_paciente_sin_obra_social_201_particular` |
| Evolución propia · de otro paciente | `test_recetas_api.py::test_evolucion_inexistente_o_de_otro_paciente_422`; `test_recetas_db.py::test_evolucion_de_otro_paciente_23503`, `::test_evolucion_de_otra_clinica_23503` |
| Evolución propia · de otro odontólogo | `test_recetas_api.py::test_evolucion_de_otro_odontologo_422_evolucion_propia` |
| Evolución propia · corregida | `test_recetas_api.py::test_evolucion_propia_corregida_201` |
| Partner no configurado · Sin partner | `test_recetas_api.py::test_sin_partner_501_nombra_variable_y_sin_filas`, `::test_501_viene_antes_que_el_422_del_cuerpo`; `test_recetas_partner.py::test_factory_vacio_no_configurado_nombra_variable` |
| Partner no configurado · Consultas sin partner | `test_recetas_api.py::test_get_sin_partner_200` |
| Partner no configurado · simulado en producción | `test_recetas_api.py::test_fake_en_produccion_501`; `test_recetas_partner.py::test_factory_fake_en_produccion_bloqueado_con_warning` |
| Errores del partner · caído | `test_recetas_api.py::test_partner_caido_502_reintentable_sin_fila_ni_evento` |
| Errores del partner · rechazo | `test_recetas_api.py::test_partner_rechaza_422_con_credencial_enmascarada` |
| Errores del partner · mensaje con secreto | `test_recetas_errores.py::test_sanear_*`; `test_recetas_api.py::test_partner_rechaza_422_con_credencial_enmascarada` (también `caplog`) |
| Idempotencia · Doble clic | `test_recetas_api.py::test_misma_clave_y_contenido_200_misma_receta_una_emision` |
| Idempotencia · otro contenido | `test_recetas_api.py::test_misma_clave_otro_contenido_409_sin_emitir` |
| Idempotencia · concurrentes | `test_recetas_concurrencia.py::test_dos_emisiones_simultaneas_misma_clave_una_fila` |
| Inmutable · Métodos de edición | `test_recetas_api.py::test_metodos_de_edicion_405`, `::test_openapi_sin_put_patch_delete_en_recetas` |
| Inmutable · Mutación directa / TRUNCATE | `test_recetas_db.py::test_update_delete_truncate_rechazados_y_fila_persiste[…]` |
| Consulta · Listado | `test_recetas_api.py::test_listado_mas_reciente_primero_con_enlaces_y_evento_leer`, `::test_listado_paginado_por_cursor` |
| Consulta · Receta de otro paciente | `test_recetas_api.py::test_detalle_y_rid_de_otro_paciente_404` |
| Consulta · Paciente sin recetas | `test_recetas_api.py::test_paciente_sin_recetas_lista_vacia` |
| RBAC · Recepción sin acceso | `test_rbac_recetas.py::test_recepcionista_403_en_las_3_rutas_sin_partner_ni_auditoria` |
| RBAC · Sin consentimiento de datos | `test_rbac_recetas.py::test_sin_consentimiento_403_antes_del_cuerpo_y_del_501` |
| RBAC · Admin solo lee | `test_rbac_recetas.py::test_admin_no_emite_403_pero_lee_200` |
| Auditoría · Emisión auditada / diff sin contenido | `test_recetas_api.py::test_evento_crear_sin_items_ni_diagnostico`; `test_auditoria_writer.py::test_acepta_receta_con_ids_y_partner`, `::test_diff_de_receta_descarta_items_diagnostico_e_id_externo` |
| Auditoría · Reintento no duplica | `test_recetas_api.py::test_misma_clave_y_contenido_200_misma_receta_una_emision` (1 evento) |
| Aislamiento · Paciente de otra clínica | `test_rbac_recetas.py::test_paciente_de_otra_clinica_404_sin_partner` |
| Aislamiento · Consulta cruzada en la base | `test_recetas_db.py::test_consulta_con_otra_clinica_devuelve_0_filas` |
| Exportación con recetas | `test_exportacion_api.py::test_recetas_csv_con_filas_de_la_clinica_y_items_json`; `test_exportacion_aislamiento.py::test_la_exportacion_de_a_no_contiene_nada_de_b` |

## Evidencia TDD

Ver el resumen del apply: tabla por task con test, capa, safety net (1057 passed), RED, GREEN, triangulación y refactor. Salvedad sobre RED indicada en "Bloqueo y desvíos".
