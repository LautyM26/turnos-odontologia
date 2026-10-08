# Proposal — c-08-pacientes-ficha

## Why

Después de C-03 el sistema tiene identidad, tenant y RBAC, pero no tiene **pacientes**: el motor de turnos (C-05), la reserva pública (C-06), el odontograma/evolución (C-09) y todo lo comercial dependen de una entidad `Paciente` scoped por clínica. Además el producto maneja **datos de salud** (datos sensibles, Ley 25.326; HC, Ley 26.529): sin gate de consentimiento, sin RBAC clínico y sin una auditoría inmutable desde el primer dato clínico, todo lo que se construya encima nace incumpliendo. Este change (CRÍTICO, US-007 + US-017) pone esa base antes de que C-05 empiece a vincular turnos a pacientes.

## What Changes

- **Paciente** tenant-scoped: nombre, apellido, DNI (normalizado, único por clínica), email (minúsculas), teléfono/WhatsApp (normalizado a E.164 AR), obra social nombre + plan + nro_afiliado (sin validación en línea, RN-OS-01), `riesgo_ausencia` (score 0–100, default 0, solo lectura en este change; lo escribe C-05), `consentimiento_datos` (+ fecha y usuario que lo registró), `es_seed`. Crear un paciente **no** crea `Usuario` (reserva sin cuenta, RN-AG-05).
- Endpoints: `GET/POST /api/pacientes` (búsqueda exacta por `dni` / `telefono` normalizados y por nombre con trigramas `q`; paginación por cursor), `GET/PATCH /api/pacientes/{id}`. DNI duplicado en la clínica → `409` con el id existente.
- **Ficha (anamnesis)** 1—1 lógica con el paciente, persistida como **versiones append-only** (`ficha_version`): `GET/PUT /api/pacientes/{id}/ficha` (PUT crea versión N+1 con control optimista `version_esperada` → `409` ante conflicto) + `GET /api/pacientes/{id}/ficha/versiones`. Editable "con traza" (US-007) sin borrar historia (RN-CL-02).
- **Adjuntos** (foto JPEG/PNG o PDF): `POST /api/pacientes/{id}/adjuntos` (multipart; límite de tamaño configurable → `413`; MIME validado por **magic bytes** contra allowlist → `415`), `GET .../adjuntos` (metadatos) y `GET .../adjuntos/{adjunto_id}/contenido` (descarga como attachment). Storage detrás de una abstracción `AdjuntoStorage` con implementación de directorio local (proveedor cloud sin decidir). `evolucion_id` queda como columna nullable sin FK hasta C-09.
- **Gate de consentimiento** (Ley 25.326, RN-CU-01): cargar datos de salud (PUT ficha, POST adjunto) con `consentimiento_datos=false` → `403`. Los datos administrativos/contacto/OS sí se pueden cargar sin consentimiento (necesarios para reservar).
- **RBAC clínico**: datos administrativos del paciente → admin, recepcionista, odontólogo; ficha y adjuntos → lectura admin + odontólogo, escritura **solo odontólogo**; recepcionista → `403` en todo lo clínico. "Odontólogo solo sus pacientes" se resuelve con un resolver de vínculo inyectable (patrón C-03); **regla interina** hasta C-05: odontólogo accede a los pacientes de su clínica con toda lectura clínica auditada.
- **AuditoriaHC** inmutable: tabla `auditoria_hc` (actor, acción, entidad, entidad_id, paciente_id, diff mínimo sin valores clínicos, timestamp) escrita en la **misma transacción** que cada escritura (y cada lectura clínica). Sin endpoint de escritura; inmutabilidad a nivel DB con trigger que rechaza `UPDATE`/`DELETE`/`TRUNCATE` (también sobre `ficha_version`). Lectura solo admin: `GET /api/pacientes/{id}/auditoria`.
- Migración Alembic **004** (`down_revision` = revisión 003 de C-04): `CREATE EXTENSION IF NOT EXISTS pg_trgm`, tablas `paciente`, `ficha_version`, `adjunto`, `auditoria_hc`, función + triggers append-only, índices `(clinica_id, …)`.
- Settings nuevas (solo backend): `ADJUNTOS_STORAGE_DIR`, `ADJUNTO_MAX_BYTES`. Dependencias nuevas: `python-multipart` (uploads FastAPI), `phonenumbers` (normalización E.164).
- Tests (testcontainers `postgres:16-alpine` + Alembic up/down, datos 100 % sintéticos): reserva sin cuenta no crea Usuario, aislamiento por tenant (query cruzada = 0 filas / 404), adjunto no-imagen/PDF rechazado (incluido archivo renombrado), auditoría registra cada escritura y rechaza UPDATE/DELETE a nivel DB, gate de consentimiento, RBAC clínico.

## Capabilities

### New Capabilities

- `patients`: alta, edición, búsqueda y deduplicación de pacientes por clínica; normalización de DNI/email/teléfono; datos mínimos de obra social; flag de consentimiento de datos; independencia Paciente↔Usuario.
- `clinical-record`: ficha de anamnesis versionada append-only y adjuntos clínicos (validación de tipo/tamaño, storage abstracto, descarga segura), con gate de consentimiento.
- `clinical-audit`: registro inmutable de escrituras y lecturas clínicas (AuditoriaHC), atomicidad con la operación auditada, protección a nivel DB y consulta solo-admin.

### Modified Capabilities

- `access-control`: se agregan requisitos de RBAC clínico sobre pacientes — escritura clínica solo odontólogo, lectura clínica admin/odontólogo, recepción limitada a datos de contacto/OS, y vínculo odontólogo↔paciente resuelto por resolver inyectable con regla interina pre-C-05.

## Impact

- Código nuevo: `backend/app/domain/pacientes/` (modelos, schemas `extra='forbid'`, normalización, detección de tipo de archivo, servicios), `backend/app/domain/auditoria/` (writer append-only), `backend/app/infrastructure/storage/` (`AdjuntoStorage` + `LocalDirStorage`), `backend/app/api/pacientes.py`; extensión de `backend/app/api/permissions.py` (deps clínicas + resolver de vínculo); `main.py` monta el router; `settings.py` + `.env.example` + `tests/test_env_example.py` (2 env nuevas).
- Migración `backend/alembic/versions/004_pacientes_ficha.py` encadenada a la 003 de C-04 (se aplica después de C-04; no crea tablas de catálogo).
- APIs: 10 endpoints nuevos bajo `/api/pacientes/*`, todos con JWT + `require_tenant_checked`.
- Dependencias: `python-multipart`, `phonenumbers`; extensión PG `pg_trgm` (contrib, trusted desde PG13; incluida en `postgres:16-alpine`).
- Downstream: C-05 reemplaza el resolver de vínculo interino por "tiene turno con el profesional del usuario" y escribe `riesgo_ausencia`; C-06 reutiliza el servicio de alta/búsqueda por DNI; C-09 agrega FK `adjunto.evolucion_id` y reutiliza `auditoria_hc`; C-10 consume estos endpoints; C-18 formaliza el consentimiento firmado.
- Legal: varias decisiones dependen de PA-04 (validación legal abierta, supuesto Sprint 1 SU-08) — listadas en `design.md`.
