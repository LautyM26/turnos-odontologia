# Tasks — c-08-pacientes-ficha

> Strict TDD: cada task arranca con el test en ROJO en el archivo/capa indicados, luego GREEN mínimo, triangulación (≥ 2 casos) y refactor. Integración solo con `PostgresContainer("postgres:16-alpine")` + Alembic (fixtures de `backend/tests/integration/conftest.py`), nunca SQLite. Datos 100 % sintéticos (`es_seed=true`, DNIs `9xxxxxxx`, `@example.com`, `+54911555500xx`, archivos generados en memoria). Prerrequisito: C-04 aplicado (migración `003_clinica_catalogo` presente, incluido `uq_usuario_clinica_id`) y aprobación humana de los "Puntos para aprobación humana" de `design.md`.

## 1. Dependencias y settings

- [x] 1.1 Añadir `phonenumbers` y `python-multipart` a `backend/pyproject.toml`, y verificar que `python -c "import phonenumbers, multipart"` funciona en el entorno backend y `ruff check backend` queda limpio.
- [x] 1.2 RED en `backend/tests/test_settings.py` (unit): `adjuntos_storage_dir` default `./var/adjuntos` y `adjunto_max_bytes` default 10485760 con `ge=1`/`le=26214400` (valor 0 y 30 MiB → error); RED en `backend/tests/test_env_example.py` exigiendo `ADJUNTOS_STORAGE_DIR` y `ADJUNTO_MAX_BYTES`. Implementar en `app/infrastructure/settings.py` + placeholders en `backend/.env.example`, y verificar `pytest backend/tests/test_settings.py backend/tests/test_env_example.py -q` en verde.

## 2. Normalización pura (dominio, sin DB)

- [x] 2.1 RED en `backend/tests/unit/test_normalizacion_paciente.py` (unit): DNI `30.123.456`→`30123456`, `12AB`/`123456`/`123456789` → error; email `" Ana@Example.COM "`→`ana@example.com`. Implementar `app/domain/pacientes/normalizacion.py` y verificar los casos en verde.
- [x] 2.2 RED en el mismo archivo: teléfono `011 15 5555-0001`→`+5491155550001`, `+54 9 11 5555-0002` idempotente, `abc`/`123` → error; `nombre_busqueda("Pérez", "José María")`→`"perez jose maria"`. Implementar con `phonenumbers` (`is_possible_number`, E.164) y `unicodedata`, y verificar en verde.

## 3. Migración 004 (tablas, extensión, triggers)

- [x] 3.1 RED en `backend/tests/integration/test_migracion_004.py` (integración PG): tras `upgrade head` existen `paciente`, `ficha_version`, `adjunto`, `auditoria_hc`, la extensión `pg_trgm`, `UNIQUE (clinica_id, dni)`, `uq_paciente_clinica_id (clinica_id, id)`, las FKs compuestas `(clinica_id, paciente_id) → paciente(clinica_id, id)` y `(clinica_id, *_usuario_id) → usuario(clinica_id, id)` (insert de ficha/adjunto/evento con paciente o autor de otra clínica → error de FK), los índices `(clinica_id, …)` y GIN trigram del design §2/§6/§8/§9, y los CHECK (DNI, E.164, contacto obligatorio, `riesgo_ausencia` 0..100, consentimiento con fecha, `tipo`/`mime`/`accion`/`entidad`). Crear `backend/alembic/versions/004_pacientes_ficha.py` (`down_revision = "003_clinica_catalogo"`, sin recrear `uq_usuario_clinica_id`; columnas TIMESTAMPTZ, TEXT+CHECK, BIGINT identity) y verificar el test en verde.
- [x] 3.2 RED en el mismo archivo: `downgrade -1` elimina las 4 tablas, la función y los triggers (la extensión puede persistir; `uq_usuario_clinica_id` de la 003 sigue existiendo) y `upgrade head` vuelve a aplicar sin error. Implementar `downgrade()` y verificar el ciclo up/down/up en verde.
- [x] 3.3 RED en `backend/tests/integration/test_append_only_db.py` (integración PG): `UPDATE`, `DELETE` y `TRUNCATE` crudos sobre `auditoria_hc` y `ficha_version` con la conexión de la app fallan con error de DB y la fila persiste; `INSERT` funciona. Implementar `fn_rechazar_mutacion()` + triggers en la 004 y verificar en verde.

## 4. Modelos ORM y writer de auditoría

- [x] 4.1 RED en `backend/tests/unit/test_modelos_pacientes.py` (unit): `Paciente` y `Adjunto` componen `TenantMixin`+`AuditMixin`; `FichaVersion` y `AuditoriaHC` tienen `clinica_id` pero no `updated_at`/`deleted_at`; columnas temporales `DateTime(timezone=True)`. Implementar `app/domain/pacientes/models.py` y `app/domain/auditoria/models.py` alineados a la 004, y verificar en verde.
- [x] 4.2 RED en `backend/tests/integration/test_auditoria_writer.py` (integración PG): `registrar_evento(session, auth, accion, entidad, entidad_id, paciente_id, diff)` inserta con `created_at` del servidor; el writer no expone update/delete; si la transacción se revierte el evento no queda (atomicidad); `diff` con claves no permitidas (p. ej. `alergias_texto`, `telefono_valor`) → `ValueError`. Implementar `app/domain/auditoria/writer.py` (allowlist de claves de diff) y verificar en verde.

## 5. Pacientes: servicio y endpoints administrativos

- [x] 5.1 RED en `backend/tests/unit/test_schemas_pacientes.py` (unit): `PacienteCreate` rechaza campos extra (`riesgo_ausencia`, `clinica_id`) y alta sin email ni teléfono; normaliza DNI/email/teléfono vía validators; `PacienteUpdate` todo opcional y sin `riesgo_ausencia`. Implementar `app/domain/pacientes/schemas.py` (`_ForbidBase`) y verificar en verde.
- [x] 5.2 RED en `backend/tests/integration/test_pacientes_servicio.py` (integración PG): `crear_paciente` persiste con `nombre_busqueda`, audita `crear`, **no** cambia el conteo de `usuario`; DNI duplicado (con otro formato) → `PacienteDuplicado(paciente_id)`; mismo DNI en clínica B OK. Implementar `app/domain/pacientes/servicios.py` y verificar en verde.
- [x] 5.3 RED en `backend/tests/integration/test_pacientes_api.py` (integración PG + TestClient): `POST /api/pacientes` 201 / 409 con `paciente_id` / 422 extra; `GET/PATCH /api/pacientes/{id}` 200 con normalización + evento `actualizar` cuyo diff solo lista campos; paciente de otra clínica → 404; `DELETE` → 405; PATCH con `riesgo_ausencia` → 422. Implementar `app/api/pacientes.py` (con `require_tenant_checked`) y montarlo en `app/main.py`, y verificar en verde.
- [x] 5.4 RED en `test_pacientes_api.py`: PATCH `consentimiento_datos=true` setea fecha + usuario y audita `consentimiento_otorgado`; `false` audita `consentimiento_revocado` sin borrar nada. Implementar y verificar en verde.
- [x] 5.5 RED en `backend/tests/integration/test_pacientes_busqueda.py` (integración PG): `dni=30.123.456` encuentra `30123456`; `telefono` en formato local encuentra E.164; `q=perez` encuentra `Pérez`; `q` < 3 chars → 422; 45 pacientes con `limit=20` → 3 páginas encadenando `after_id = next_cursor` sin repetidos ni faltantes, `limit=0`/`201` → 422 y default 50 (contrato keyset de C-04, reutilizando `BaseRepository.page`); búsqueda de DNI de otra clínica → lista vacía; `EXPLAIN` de la búsqueda por DNI usa el índice `(clinica_id, dni)`. Implementar búsqueda keyset y verificar en verde.

## 6. RBAC clínico y vínculo odontólogo–paciente

- [x] 6.1 RED en `backend/tests/integration/test_rbac_pacientes.py` (integración PG): `/api/pacientes` con rol `paciente-enlace` → 403; recepcionista → 403 en ficha, historial, adjuntos (listado, contenido, POST); admin sin odontólogo → 403 en PUT ficha y POST adjunto; admin+odontólogo → permitido; odontólogo → 403 en `/auditoria`. Implementar `require_clinico_escritura()` y uso de `require_clinico()`/`require_admin()` en `app/api/permissions.py` y el router, y verificar en verde.
- [x] 6.2 RED en `test_rbac_pacientes.py`: con el resolver por defecto (regla interina) un odontólogo lee la ficha de un paciente de su clínica (y queda evento `leer`); con `set_resolver_vinculo_paciente(lambda *_: False)` → 403; resolver que lanza excepción → 403; paciente de otra clínica → 404 sin invocar el resolver; admin no pasa por el resolver. Implementar `VinculoPacienteResolver` + `set_resolver_vinculo_paciente` + dependencia `require_vinculo_paciente`, documentar en el docstring que C-05 lo reemplaza, y verificar en verde.

## 7. Ficha versionada

- [x] 7.1 RED en `backend/tests/integration/test_ficha_api.py` (integración PG): `GET /ficha` sin versiones → 200 `version=0`; `PUT` con `version_esperada=0` → versión 1 con autor; segundo PUT con `version_esperada=1` → versión 2 y la 1 intacta; PUT con `version_esperada` vieja → 409 sin nueva versión; paciente sin consentimiento → 403 sin versión; campos extra → 422. Implementar servicio + endpoints `GET/PUT /api/pacientes/{id}/ficha` y verificar en verde.
- [x] 7.2 RED en `test_ficha_api.py`: dos PUT concurrentes (dos sesiones/hilos) con la misma `version_esperada` → exactamente uno 200 y otro 409, una sola versión nueva (IntegrityError del `UNIQUE (paciente_id, version)` mapeado a 409). Implementar el mapeo y verificar en verde.
- [x] 7.3 RED en `test_ficha_api.py`: `GET /ficha/versiones` devuelve 3,2,1 con autor y fecha; cada PUT audita `actualizar`/`crear` con diff `{"campos": [...], "version": N}` sin texto clínico (assert de que el texto de alergias no aparece en el JSON del diff); cada GET de ficha/historial audita `leer`. Implementar y verificar en verde.

## 8. Adjuntos

- [x] 8.1 RED en `backend/tests/unit/test_archivos_firma.py` (unit): bytes con firma JPEG/PNG/PDF → (`foto`|`pdf`, MIME); GIF, ZIP/DOCX (`PK\x03\x04`), ejecutable `MZ`, DICOM y vacío → rechazo; content-type declarado distinto del detectado → rechazo. Implementar `app/domain/pacientes/archivos.py` y verificar en verde.
- [x] 8.2 RED en `backend/tests/unit/test_storage_local.py` (unit, `tmp_path`): `LocalDirStorage.guardar` escribe atómico bajo `root/{clinica}/{paciente}/{uuid}`, `abrir` devuelve el contenido, una clave que resuelva fuera del root (`../`) → error, `eliminar` borra; sin archivos temporales residuales tras error. Implementar `app/infrastructure/storage/adjuntos.py` (`AdjuntoStorage` Protocol + `LocalDirStorage`) y verificar en verde.
- [x] 8.3 RED en `backend/tests/integration/test_adjuntos_api.py` (integración PG + `tmp_path` como storage): `POST /adjuntos` JPEG válido → 201 con tipo/MIME/tamaño/sha256 y evento `crear` sin nombre de archivo en el diff; ejecutable renombrado `.pdf` → 415; GIF → 415; `max+1` bytes (con `Content-Length` falso menor) → 413 sin archivo ni fila; 0 bytes → 422; form field `evolucion_id` → 422; sin consentimiento → 403 sin archivo; nombre `../../etc/passwd.png` queda dentro del root. Implementar servicio + endpoint con lectura por chunks y compensación (borrar archivo si falla la DB), y verificar en verde.
- [x] 8.4 RED en `test_adjuntos_api.py`: `GET /adjuntos` lista metadatos del paciente (sin otros tenants); `GET /adjuntos/{id}/contenido` → 200 con bytes idénticos, `Content-Disposition: attachment`, `X-Content-Type-Options: nosniff`, `Cache-Control: no-store`, y evento `descargar`; adjunto de otra clínica → 404; falla simulada de DB en el POST deja el storage sin el archivo. Implementar y verificar en verde.

## 9. Consulta de auditoría

- [x] 9.1 RED en `backend/tests/integration/test_auditoria_api.py` (integración PG): admin `GET /api/pacientes/{id}/auditoria` devuelve eventos del paciente en orden descendente (`id DESC`, `after_id`/`next_cursor`, `limit` 1..200 default 50) y sin eventos de otra clínica; `POST/PUT/PATCH/DELETE` a esa ruta → 405 y el conteo de `auditoria_hc` no cambia; ningún router expone escritura sobre `auditoria_hc` (test que recorre `app.routes`). Implementar el endpoint y verificar en verde.

## 10. Integración y cierre

- [x] 10.1 Verificación E2E por tenant en `backend/tests/integration/test_e2e_pacientes.py` (`postgres:16-alpine`): login recepcionista → alta paciente (sin Usuario nuevo) → consentimiento → login odontólogo → PUT ficha v1/v2 → subir PDF → descargar → login admin → auditoría muestra la secuencia completa → JWT de clínica B no ve nada (404/lista vacía); y verificar `ruff check backend` + `pytest backend -q` en verde (incluidas las suites de C-01..C-04 sin regresiones).
- [x] 10.2 Verificar que no hay datos reales en el change (`git diff` sin DNIs fuera del rango sintético `9xxxxxxx`, sin emails fuera de `@example.com`, sin archivos binarios reales en tests) y que `openspec validate c-08-pacientes-ficha --strict` pasa.

## Workflow follow-up

- Revisión humana de "Puntos para aprobación humana" (design.md) antes de `/opsx:apply c-08-pacientes-ficha` (governance CRÍTICO); C-04 debe estar aplicado antes (`003_clinica_catalogo`).
- Tras implementar: `/opsx:archive c-08-pacientes-ficha` y marcar `[x] C-08` en CHANGES.md.
- Avisar a C-05 que debe inyectar el resolver de vínculo por turnos y escribir `riesgo_ausencia`; a C-09 que agregue la FK `adjunto.evolucion_id` y amplíe los CHECK de `auditoria_hc`.
