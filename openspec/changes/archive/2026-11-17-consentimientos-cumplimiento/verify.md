# Verify — consentimientos-cumplimiento (C-18)

Fecha: 2026-11-17. Resultado: **VERDE, listo para revisión humana y archivo** (governance ALTO; no se archivó ni se hizo commit).

## Entorno

- Windows 11, Docker Desktop; PostgreSQL `postgres:16-alpine` vía testcontainers (nunca SQLite).
- Python 3.13 (intérprete global, sin `.venv`), pytest, ruff; frontend con vitest, tsc estricto, Vite y biome.
- Decisiones DT-1…DT-10 de `design.md` aprobadas por el usuario (aprobación delegada del 2026-11-16) y aplicadas tal como estaban escritas.

## Comandos (desde la raíz del repo)

```
python -m pytest backend/tests -q
ruff check backend
python -m alembic -c backend/alembic.ini heads
python .claude/skills/crear-skill-de-dominio/scripts/verificar.py dominio-cumplimiento RN-CU
npm --prefix frontend test -- tests/legal.test.tsx tests/app-shell.test.tsx
npm --prefix frontend run build ; npm --prefix frontend run lint
```

## Resultados

- Baseline previo al change: **813 passed** (8 min 17 s).
- Con el change: **1057 passed, 0 failed** (ver "Suite final"). Tests nuevos del backend: **244** (corrida intermedia: 1057 passed, 11 min 2 s).
- `ruff check backend`: **All checks passed**.
- `alembic heads`: un único head, `009_consentimientos_cumplimiento` (`down_revision = 008_odontograma_evolucion`).
- Migración: `test_migracion_009.py` cubre upgrade, downgrade a la 008 (conserva `fn_rechazar_mutacion()` y restaura los CHECK de `auditoria_hc`) y re-upgrade.
- Frontend: `legal.test.tsx` + `app-shell.test.tsx` 34 passed; `tsc --noEmit` limpio; `npm run build` (tsc estricto + Vite) y `npm run lint` limpios.
- `verificar.py dominio-cumplimiento RN-CU`: **RESULTADO: OK** (5/5 RN en la matriz, 32 rutas citadas existentes); `diff AGENTS.md CLAUDE.md` vacío; las 3 copias de la skill son idénticas.

## Pruebas de mutación (task 8.3)

Cada mutación se aplicó, se corrió el subconjunto de tests y se restauró el archivo (verificado con `diff`).

| # | Mutación | Tests que fallan |
|---|---|---|
| a | `009`: no crear los triggers append-only de `consentimiento_firma` | `test_cumplimiento_db.py::test_update_delete_rechazados_y_fila_persiste[UPDATE consentimiento_firma…]`, `[DELETE FROM consentimiento_firma…]`, `::test_truncate_rechazado[TRUNCATE consentimiento_firma…]`, `test_migracion_009.py::test_upgrade_crea_tablas_indices_constraints_y_triggers`, `::test_downgrade_borra_conserva_funcion_restaura_checks_y_reupgrade` (5 failed) |
| b | Exportación: quitar el filtro `clinica_id` de las consultas | `test_exportacion_aislamiento.py::test_la_exportacion_de_a_no_contiene_nada_de_b`, `::test_la_exportacion_de_b_no_contiene_nada_de_a`, `test_exportacion_api.py::test_exportacion_200_zip_con_un_csv_por_entidad_y_conteos_de_la_db`, `::test_clinica_sin_pacientes_csv_solo_encabezados_y_conteos_cero` (4 failed) |
| c | Usuarios: quitar el chequeo de último admin | `test_admin_usuarios_api.py::test_quitar_el_ultimo_admin_a_si_mismo_409_sin_cambios`, `test_usuarios_concurrencia.py::test_dos_admins_que_se_quitan_el_rol_dejan_al_menos_uno` (2 failed) |
| d | Firma: quitar la comparación de `texto_hash` | `test_consentimientos_api.py::test_hash_distinto_409_y_sigue_pendiente` (1 failed) |

Incidente de proceso: al restaurar (c) se copió por error un backup con el mismo nombre de archivo que otro (`servicios.py`) y se pisó `usuarios/servicios.py`; se reescribió con el contenido original y la suite completa final lo confirma.

## Prueba manual contra la API real (uvicorn + PostgreSQL 16)

`postgres:16-alpine` en el puerto 55433, `alembic upgrade head`, seed sintético (clínica A con admin, odontólogo vinculado a un profesional, recepcionista y un paciente con consentimiento de datos; clínica B con su admin y su paciente), uvicorn en el puerto 8001. API y contenedor eliminados al terminar.

```
POST /api/pacientes/1/consentimientos -> 201 generar (extraccion)
POST /api/pacientes/1/consentimientos -> 422 tipo inválido
POST .../consentimientos/1/firmar -> 422 firma incompleta (acepta=false), reintentable
POST .../consentimientos/1/firmar -> 201 firma completa
  constancia: firmado_en=2026-11-17T07:15:53Z, ip=127.0.0.1, dispositivo="NavegadorSintetico/1.0",
  texto_hash=c3065454…d118, firmante, asistido_por_usuario_id=2; documento_bloqueado=true
POST .../consentimientos/1/firmar -> 409 segunda firma
PUT|PATCH|DELETE .../consentimientos/1 -> 405 (documento firmado no modificable)
GET .../consentimientos | GET /historia | GET /api/admin/exportacion | GET /api/admin/usuarios (recepción) -> 403 x4
GET .../consentimientos (admin) -> 200
GET /api/admin/usuarios (admin) -> 200
POST /api/admin/usuarios -> 201 ; mismo email en otra capitalización -> 409
PATCH /api/admin/usuarios/5/roles -> 200 (recepcionista -> odontólogo) ; admin de B sobre ese usuario -> 404
PATCH /api/admin/usuarios/4/roles (único admin de B se quita el rol) -> 409
GET /api/admin/exportacion?formato=csv (A) -> 200 application/zip, attachment; 18 entradas;
  conteos pacientes=1 consentimientos=1 firmas=1 usuarios=4; excluidas caja/facturas;
  no contiene datos de la clínica B
GET /api/admin/exportacion?formato=pdf -> 422
GET /api/admin/exportacion (B) -> 200, solo datos de B
```

Las páginas públicas `/cumplimiento` y `/privacidad` se verificaron con `legal.test.tsx` (render del árbol de rutas público, sin sesión) y `npm run build`; no se abrió un navegador.

## Desvíos respecto de tasks.md y del design

1. `rango` (columna generada `tstzrange` de `turno` y `bloqueo`) se agrega a la denylist de la exportación junto con `password_hash`: es derivada de `inicio`/`fin` y no tiene representación CSV portable. D5 solo nombraba `password_hash`.
2. Task 3.4 pedía recorrer `app.routes`; se usa `app.openapi()["paths"]` (en esta versión de Starlette `app.routes` no lista las rutas de routers incluidos; gotcha de C-09).
3. Task 4.3: la carrera de dos admins se prueba llamando al servicio con dos sesiones (no por HTTP): entre autenticar y mutar no hay ventana controlable por HTTP, y el segundo request recibiría 403 por haber perdido ya el rol.
4. Task 1.5: `FormatoNoSoportado` (D5) vive junto a los errores de consentimientos en `cumplimiento/errores.py`; los errores de usuarios en `usuarios/errores.py`.
5. `test_migracion_008.py::test_un_unico_head` dejó de fijar el head en la 008 (ahora verifica un único head y el encadenado); el head vigente lo fija `test_migracion_009.py`. `'receta'` como entidad inválida de auditoría pasó a `'entidad_inexistente'` en `test_migracion_004.py` y `test_auditoria_writer.py` (C-19 lo agregará).
6. `/privacidad` se registró en el bloque público existente de `frontend/src/router.tsx`, junto a `/cumplimiento` (C-10 ya no usa `App.tsx`).
7. Las specs delta aún no están en `openspec/specs/`: la matriz de `dominio-cumplimiento` cita `openspec/changes/consentimientos-cumplimiento/specs/…`; al archivar hay que regenerar esas rutas.

## Trazabilidad escenario → test

### informed-consents
| Escenario | Test |
|---|---|
| Consentimiento generado / hash verificable | `test_consentimientos_api.py::test_generar_201_pendiente_con_texto_hash_y_version_vigente`, `::test_detalle_con_constancia_y_hash_recalculable` |
| Tipo inexistente / campos de servidor | `::test_tipo_invalido_422_sin_crear`, `::test_campos_de_servidor_en_el_cuerpo_422`, `test_cumplimiento_schemas.py` |
| Textos distintos, hashes distintos / espacios y acentos | `::test_textos_distintos_dan_hashes_distintos`, `test_cumplimiento_hash.py::test_espacios_y_acentos_cuentan` |
| Firma completa / sin user-agent | `::test_firma_completa_201_con_constancia_y_documento_bloqueado`, `::test_firma_sin_user_agent_guarda_no_informado` |
| Hash mostrado no coincide | `::test_hash_distinto_409_y_sigue_pendiente` |
| Sin aceptación / DNI inválido / reintento | `::test_firma_incompleta_422_reintentable_sin_constancia_ni_evento`, `::test_sin_acepta_en_el_cuerpo_tambien_es_reintentable`, `::test_reintento_exitoso_deja_una_sola_constancia` |
| Segunda firma / PUT-PATCH-DELETE / mutación directa / concurrencia | `::test_segunda_firma_409_y_constancia_intacta`, `::test_metodos_de_edicion_405_y_documento_intacto`, `::test_ninguna_ruta_de_consentimientos_expone_put_patch_delete`, `test_cumplimiento_db.py::test_update_delete_rechazados_y_fila_persiste`, `test_consentimientos_concurrencia.py` |
| Listado / otro paciente / lista vacía | `::test_listado_mas_reciente_primero_con_estados`, `::test_cid_de_otro_paciente_404`, `::test_paciente_sin_consentimientos_lista_vacia` |
| RBAC: recepción, sin consentimiento de datos, admin solo lee | `test_rbac_consentimientos.py` |
| Aislamiento: otra clínica, consulta cruzada, cid ajeno | `test_rbac_consentimientos.py::test_paciente_de_otra_clinica_404`, `::test_firma_de_cid_de_otra_clinica_con_paciente_propio_404`, `test_cumplimiento_db.py::test_consulta_con_otra_clinica_devuelve_0_filas` |

### clinical-audit (delta)
`test_consentimientos_api.py::test_generar_audita_crear_sin_tipo_ni_texto`, `::test_firmar_audita_sin_datos_del_firmante`, `::test_cada_lectura_deja_un_evento_leer`, `::test_firma_incompleta_422_reintentable_sin_constancia_ni_evento` (sin evento), `::test_falla_al_auditar_la_firma_revierte_la_constancia`, `test_auditoria_writer.py` (casos C-18), `test_migracion_009.py::test_checks_de_auditoria_hc_ampliados_con_nombre_real`.

### user-administration
| Escenario | Test |
|---|---|
| Alta / email repetido / rol no asignable / campo no declarado | `test_admin_usuarios_api.py::test_alta_de_odontologo_201_sin_hash_y_con_login`, `::test_email_repetido_en_otra_capitalizacion_409`, `::test_roles_no_asignables_422`, `::test_campos_de_servidor_422`, `test_usuarios_schemas.py` |
| Listado propio / límite / un solo usuario | `::test_listado_solo_de_la_clinica_sin_hash_y_con_roles`, `::test_limite_fuera_de_rango_422`, `::test_clinica_con_un_solo_usuario_sin_cursor` |
| Cambio de rol efectivo / último admin / mismo conjunto | `::test_cambio_de_rol_es_efectivo_con_el_mismo_token`, `::test_quitar_el_ultimo_admin_a_si_mismo_409_sin_cambios`, `test_usuarios_concurrencia.py`, `::test_mismo_conjunto_200_sin_evento` |
| Solo admin / usuario de otra clínica / sin token | `test_rbac_admin_cumplimiento.py` |

### data-export
| Escenario | Test |
|---|---|
| Exportación con datos / clínica vacía / PDF | `test_exportacion_api.py::test_exportacion_200_zip_con_un_csv_por_entidad_y_conteos_de_la_db`, `::test_clinica_sin_pacientes_csv_solo_encabezados_y_conteos_cero`, `::test_formato_no_soportado_422_sin_evento` |
| Manifest: conteos, exclusiones, fechas con zona | `::test_manifest_con_clinica_fecha_con_zona_esquema_y_excluidas`, `::test_fechas_en_iso_con_desplazamiento_horario`, `test_exportacion_csv.py` |
| Sin secretos / fórmulas / acentos y comas | `::test_ningun_csv_tiene_columnas_de_secretos`, `::test_nombre_con_formula_sale_con_apostrofo_y_conserva_comas_y_comillas`, `test_exportacion_csv.py::test_csv_utf8_con_bom_conserva_caracteres_especiales` |
| Aislada por clínica / solo admin / adjunto faltante | `test_exportacion_aislamiento.py`, `test_rbac_admin_cumplimiento.py`, `test_exportacion_api.py::test_adjunto_sin_archivo_exportacion_completa_y_manifest_lo_lista` |
| Auditada / rechazada no se registra / dos exportaciones | `::test_exportacion_exitosa_deja_evento_con_conteos_sin_datos_de_pacientes`, `::test_403_no_registra_exportacion`, `::test_segunda_exportacion_tambien_es_valida_y_deja_otro_evento` |

### admin-audit
`test_auditoria_writer.py::test_registrar_evento_admin_guarda_con_allowlist`, `::test_evento_admin_descarta_email_password_y_tipos_invalidos`, `test_admin_usuarios_api.py::test_alta_audita_usuario_crear_sin_email`, `::test_cambio_audita_roles_anteriores_y_nuevos`, `::test_falla_del_writer_admin_revierte_el_cambio_de_roles`, `test_cumplimiento_db.py::test_update_delete_rechazados_y_fila_persiste[UPDATE auditoria_admin…]`, `::test_truncate_rechazado[TRUNCATE auditoria_admin…]`, `::test_evento_admin_con_actor_de_otra_clinica_23503`, `::test_evento_admin_sin_entidad_se_guarda`, `test_rbac_admin_cumplimiento.py::test_ninguna_ruta_escribe_o_borra_eventos_administrativos`.

### legal-pages
`frontend/tests/legal.test.tsx`: `/cumplimiento` (cuatro leyes, versión, aviso, enlace a `/privacidad`), `/privacidad` y `/privacidad/` (ubicación de los datos, aviso, marcadores), textos legales sin datos reales, sin llamadas a la API, `/privacidad` ruta pública.

## Evidencia TDD (RED → GREEN → TRIANGULATE → REFACTOR)

| Tarea | Test | Capa | Safety net | RED | GREEN | TRIANGULATE | REFACTOR |
|---|---|---|---|---|---|---|---|
| 1.1 | `unit/test_cumplimiento_hash.py` | Unit | n/a (nuevo) | ModuleNotFoundError | 4/4 | vectores, vacío, espacio/tilde | limpio |
| 1.2 | `unit/test_cumplimiento_textos.py` | Unit | n/a | ModuleNotFoundError; snapshot vacío falló | todos | 5 tipos | snapshot congelado |
| 1.3-1.4 | `unit/test_cumplimiento_schemas.py` | Unit | n/a | ModuleNotFoundError | todos | extras, hash, DNI x5, faltantes múltiples | limpio |
| 1.5 | `unit/test_cumplimiento_errores.py` | Unit | n/a | ModuleNotFoundError | todos | 6 errores + handler | limpio |
| 1.6 | `unit/test_exportacion_csv.py` | Unit | n/a | ModuleNotFoundError | todos | tipos, 6 peligrosos, 5 comunes, BOM | limpio |
| 1.7 | `unit/test_usuarios_schemas.py` | Unit | n/a | ModuleNotFoundError | todos | roles x5, password x3, extras x3 | limpio |
| 2.1 | `integration/test_migracion_009.py` | Integración PG16 | `test_migracion_008` verde | migración inexistente | todos | up / down / re-up | head de 008 desacoplado |
| 2.2 | `integration/test_cumplimiento_db.py` | Integración PG16 | n/a | tablas inexistentes | todos | 3 tablas x UPDATE/DELETE/TRUNCATE, 23505/23503/23514 | TRUNCATE de consentimiento junto con la firma |
| 2.3 | `integration/test_auditoria_writer.py` | Integración PG16 | previos verdes | ImportError `registrar_evento_admin` | todos | 3 acciones, diffs prohibidos | `receta` → `entidad_inexistente` |
| 3.1-3.2, 3.4 | `integration/test_consentimientos_api.py` | Integración PG16 | n/a | 404 de rutas | 39/39 | 6 firmas incompletas, 3 métodos 405, hash, UA | `faltantes_firma` en el servicio |
| 3.3 | `integration/test_consentimientos_concurrencia.py` | Integración PG16 | n/a | 404 de rutas | 1/1 | 201 + 409 | limpio |
| 3.5 | `integration/test_rbac_consentimientos.py` | Integración PG16 | n/a | 404 de rutas | todos | 4 rutas x rol | limpio |
| 4.1-4.2 | `integration/test_admin_usuarios_api.py` | Integración PG16 | n/a | 404 de rutas | todos | alta, listado, roles, writer roto | `monkeypatch.context()` |
| 4.3 | `integration/test_usuarios_concurrencia.py` | Integración PG16 | n/a | ImportError | 1/1 | 200 + 409 | HTTP → servicio con 2 sesiones |
| 4.4 | `integration/test_rbac_admin_cumplimiento.py` | Integración PG16 | n/a | 404 | todos | 3 roles x 4 rutas | `pytestmark` con `auth_data` |
| 5.1-5.2, 5.4 | `integration/test_exportacion_api.py` | Integración PG16 | n/a | 404 | todos | 17 entidades, bordes, auditoría | `rango` excluido |
| 5.3 | `integration/test_exportacion_aislamiento.py` | Integración PG16 | n/a | 404 | 2/2 | A↔B | limpio |
| 6.1-6.2 | `frontend/tests/legal.test.tsx` | Unit (vitest) | `app-shell.test.tsx` verde | módulo inexistente | todos | `/privacidad` con y sin barra | biome ordenó imports |

## Suite final

`python -m pytest backend/tests -q` → **1057 passed, 78 warnings in 648.39 s (0:10:48)** (813 del baseline + 244 nuevos), sin regresiones en C-01…C-09. `ruff check backend` limpio y un único head Alembic tras la corrida.
