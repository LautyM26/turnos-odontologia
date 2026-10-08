# Design — c-08-pacientes-ficha

## Context

Ver `proposal.md` (Why) y las specs del change (`patients`, `clinical-record`, `clinical-audit`, delta `access-control`). Estado observado del código tras C-03:

- PKs `BIGINT GENERATED ALWAYS AS IDENTITY` (`_pk_identity()` en `001_core_models.py`); revisiones Alembic con id descriptivo (`001_core_models`, `002_token_blacklist`). `TenantMixin` (`clinica_id` FK RESTRICT) + `AuditMixin` (`is_active`, `created_at/updated_at/deleted_at` TIMESTAMPTZ) en `infrastructure/persistence/mixins.py`; naming convention en `base.py`.
- `BaseRepository` filtra por `clinica_id` y soft-delete; `delete()` es lógico.
- Auth: `get_current_user` → `AuthContext(sub, tenant_id, roles, …)`, `require_tenant_checked` (JWT autoritativo). `permissions.py` ya tiene `require_role`, `require_clinico()` (admin+odontólogo) y el patrón de **resolver inyectable con fallo cerrado** (`set_resolver_agenda_propia`).
- `Settings` es `extra="forbid"`; `tests/test_env_example.py` exige la lista de env en `backend/.env.example`.
- No hay `python-multipart` en `pyproject.toml` (FastAPI lo necesita para `UploadFile`).
- C-04 (en paralelo) crea la migración `003_clinica_catalogo` y el catálogo (Profesional, vínculo Usuario→Profesional). C-08 no crea tablas de catálogo; su migración `004` se encadena a `003_clinica_catalogo`. Convenciones de C-04 que C-08 adopta: `UNIQUE (clinica_id, id)` en tablas referenciadas + **FKs tenant compuestas** `(clinica_id, x_id)`; `uq_usuario_clinica_id` (UNIQUE `(clinica_id, id)` en `usuario`) ya lo crea la 003 y C-08 lo **reutiliza sin recrearlo**; `is_active`/`es_seed`; paginación keyset `limit` 1..200 (default 50) + `after_id` → `next_cursor` (ver `openspec/changes/c-04-clinica-catalogo/design.md` §11/§14).

## Goals / Non-Goals

**Goals:**
- Paciente + ficha + adjuntos + auditoría con garantías de inmutabilidad que no dependan solo del código de aplicación.
- Contratos que C-05/C-06/C-09/C-10 consumen sin rediseño: servicio de alta/búsqueda por DNI, resolver de vínculo, writer de auditoría, abstracción de storage.

**Non-Goals:**
- No endpoint público de reserva (C-06) ni turnos (C-05); `riesgo_ausencia` solo se lee.
- No evolución ni odontograma (C-09); no consentimiento firmado con constancia Ley 25.506 (C-18) — aquí solo el flag de consentimiento de datos.
- No validación de OS en línea (RN-OS-01 MVP), no DICOM/HEIC/WebP (RN-CL-05, F2), no antivirus, no cifrado a nivel aplicación, no proveedor cloud de storage.
- No exportación HC (RN-CU-04 → C-18) ni frontend (C-10).

## Decisions

1. **Modelo `paciente`** (`TenantMixin` + `AuditMixin`): `nombre`, `apellido` (TEXT NOT NULL, CHECK 1..100), `dni` (TEXT NOT NULL, CHECK `^[0-9]{7,8}$`), `email` (TEXT NULL, minúsculas, CHECK len ≤ 320), `telefono` (TEXT NULL, E.164, CHECK `^\+[0-9]{8,15}$`), CHECK `email IS NOT NULL OR telefono IS NOT NULL`, `obra_social_nombre`/`obra_social_plan`/`nro_afiliado` (TEXT NULL, CHECK len ≤ 120/120/50), `riesgo_ausencia SMALLINT NOT NULL DEFAULT 0 CHECK 0..100`, `consentimiento_datos BOOLEAN NOT NULL DEFAULT false`, `consentimiento_datos_at TIMESTAMPTZ NULL`, `consentimiento_datos_por BIGINT NULL FK usuario`, CHECK `NOT consentimiento_datos OR consentimiento_datos_at IS NOT NULL`, `nombre_busqueda TEXT NOT NULL`, `es_seed BOOLEAN NOT NULL DEFAULT false`.
   - Se separa `nombre`/`apellido` (KB dice "nombre"): búsqueda y orden por apellido son la práctica del mostrador AR. Supuesto documentado.
   - `obra_social` como texto (no FK `obra_social_id` del ERD): RN-OS-01 MVP; el catálogo de OS es etapa 2.
   - Estados como TEXT + CHECK, nunca ENUM (convención del proyecto).
2. **Integridad tenant por FK compuesta (convención C-04)**: `paciente` declara `UNIQUE (clinica_id, id)` (`uq_paciente_clinica_id`); `ficha_version`, `adjunto` y `auditoria_hc` referencian `(clinica_id, paciente_id) → paciente(clinica_id, id)`; toda referencia a usuario (`consentimiento_datos_por`, `autor_usuario_id`, `subido_por`, `actor_usuario_id`) es `(clinica_id, x) → usuario(clinica_id, id)` apoyada en `uq_usuario_clinica_id` de la 003 (MATCH SIMPLE deja pasar las nulables). Así una ficha/adjunto/evento no puede apuntar a un paciente o autor de otra clínica aunque el servicio falle. Todas las FKs `ON DELETE RESTRICT`.
   **Índices** (regla 10, todos con `clinica_id` primero): `UNIQUE (clinica_id, dni)` (sin parcial: no hay borrado de pacientes; NOT NULL hace innecesario `NULLS NOT DISTINCT`), `(clinica_id, telefono)`, `(clinica_id, email)`, `uq_paciente_clinica_id (clinica_id, id)` (sirve también al listado keyset), GIN `nombre_busqueda gin_trgm_ops` para `LIKE '%q%'`. El GIN no lleva `clinica_id` (requeriría `btree_gin`); el filtro por tenant se aplica igual en el WHERE.
3. **Normalización en dominio puro** (`domain/pacientes/normalizacion.py`, unit-testeable sin DB): DNI → quitar `.`/espacios/guiones, validar 7–8 dígitos; email → `strip().lower()`; teléfono → `phonenumbers.parse(v, "AR")` + `is_possible_number` + `format E164` (convierte el `15` local al `9` móvil; `is_possible` y no `is_valid` para no rechazar numeraciones nuevas/sintéticas); `nombre_busqueda` → `unicodedata` NFKD sin marcas diacríticas + minúsculas de `"apellido nombre"`, calculado en app al escribir.
   - Alternativa `unaccent` en PG descartada: no es IMMUTABLE, exige wrapper para indexar y otra extensión; la columna derivada es más simple y testeable.
   - Alternativa normalizador de teléfono propio descartado: reglas AR (código de área variable, `15`/`9`) son frágiles; `phonenumbers` es estándar y C-15 (WhatsApp) necesita E.164 igual.
4. **Búsqueda**: `GET /api/pacientes?dni=&telefono=&q=&limit=&after_id=` — `dni`/`telefono` exactos sobre la forma normalizada (btree); `q` (≥ 3 chars, normalizado igual que `nombre_busqueda`) con `LIKE '%' || :q || '%'` acelerado por trigramas. Paginación keyset **alineada a C-04**: `WHERE id > :after_id ORDER BY id LIMIT :limit + 1`, `limit` 1..200 (default 50, `Query(ge=1, le=200)` → 422), respuesta `Pagina[T](items, next_cursor)` con `next_cursor` = id del último ítem si hay más. Se reutiliza `BaseRepository.page(...)` que agrega C-04. Orden por id (no alfabético): el resultado de `q` suele ser corto y el frontend (C-10) puede ordenar la página; alternativa keyset por `(nombre_busqueda, id)` descartada para no divergir del contrato de paginación del proyecto. Nunca OFFSET. Queries parametrizadas.
5. **`pg_trgm` en la migración** con `CREATE EXTENSION IF NOT EXISTS pg_trgm`: es contrib (incluida en la imagen oficial `postgres:16-alpine`) y *trusted* desde PG13 (el owner de la DB puede crearla sin superusuario). El downgrade **no** la elimina (puede ser usada por otras migraciones; `IF NOT EXISTS` hace el re-upgrade idempotente).
6. **Ficha como versiones append-only (`ficha_version`)** en lugar de una fila mutable 1—1 + diff en auditoría: columnas `id`, `clinica_id`, `paciente_id` FK, `version INT NOT NULL CHECK > 0`, `anamnesis`/`alergias`/`antecedentes` TEXT NULL (CHECK len ≤ 10000), `autor_usuario_id` FK NOT NULL, `created_at` TIMESTAMPTZ default now(); `UNIQUE (paciente_id, version)`; índice `(clinica_id, paciente_id, version DESC)`. Sin `AuditMixin` (no hay update/soft-delete). Ficha vigente = max(version).
   - Cumple "editable con traza" (US-007) y "ningún cambio borra historia" (RN-CL-02) sin poner texto clínico en la auditoría. Alternativa fila mutable + diff con valores en `auditoria_hc` descartada: duplica PHI en el log y la reconstrucción depende del diff.
   - PUT = reemplazo completo de los 3 campos + `version_esperada` (0 si no hay ficha). Servicio: lee la vigente, compara, inserta `version_esperada + 1`; el `UNIQUE (paciente_id, version)` resuelve la carrera (IntegrityError → 409). Sin `SELECT … FOR UPDATE` (el constraint basta).
7. **Inmutabilidad a nivel DB**: función `fn_rechazar_mutacion()` (`RAISE EXCEPTION 'tabla append-only'`) + triggers `BEFORE UPDATE OR DELETE … FOR EACH ROW` y `BEFORE TRUNCATE … FOR EACH STATEMENT` sobre `auditoria_hc` y `ficha_version`. La app además usa un repositorio append-only sin `update`/`delete`.
   - Alternativa `REVOKE UPDATE, DELETE` descartada para MVP: la app conecta como owner (no hay rol DB separado aún) y el owner ignora REVOKE. Queda como hardening de infra (rol `app_rw` sin ownership) — ver Riesgos.
   - El trigger no protege contra el owner que haga `DROP TRIGGER`/`ALTER TABLE`; ese vector es de operación/migraciones, no del runtime de la app.
8. **`auditoria_hc`**: `id` identity, `clinica_id` FK, `paciente_id` FK NOT NULL, `actor_usuario_id` FK NULL + `actor_tipo TEXT NOT NULL CHECK IN ('usuario','sistema')` (CHECK `actor_tipo <> 'usuario' OR actor_usuario_id IS NOT NULL`; `sistema` reservado para C-06/C-05), `accion TEXT CHECK IN ('crear','actualizar','leer','descargar','consentimiento_otorgado','consentimiento_revocado')`, `entidad TEXT CHECK IN ('paciente','ficha','adjunto')`, `entidad_id BIGINT NOT NULL`, `diff JSONB NOT NULL DEFAULT '{}'`, `ip TEXT NULL`, `created_at TIMESTAMPTZ NOT NULL DEFAULT now()` (hora del servidor DB, no del cliente). Índices `(clinica_id, paciente_id, id DESC)` y `(clinica_id, created_at)`. Consulta paginada descendente: `WHERE id < :after_id ORDER BY id DESC LIMIT :limit + 1` (id identity es monótono con la inserción, equivale al orden cronológico), mismos `limit`/`next_cursor` que C-04. C-09 ampliará los CHECK de `entidad`/`accion` en su migración.
   - **Diff mínimo**: `{"campos": [...]}` + `version`/ids + booleanos de consentimiento. Nunca texto clínico, contacto, nombre de archivo original. Un test lo verifica (spec `clinical-audit`).
   - **Atomicidad**: el writer recibe la misma `Session` del request y hace `add` antes del `commit` del servicio; cualquier excepción revierte todo. Las lecturas clínicas auditadas hacen commit propio del evento (transacción de solo-insert).
   - Lecturas auditadas: `GET ficha`, `GET ficha/versiones`, `GET adjuntos/{id}/contenido`. El listado de metadatos de adjuntos y los GET administrativos de paciente no se auditan (volumen, no clínico).
9. **Adjuntos**: tabla `adjunto` (`TenantMixin` + `AuditMixin` para futuro soft-delete con traza), `paciente_id` FK NOT NULL, `evolucion_id BIGINT NULL` **sin FK** (C-09 la agrega), `tipo TEXT CHECK IN ('foto','pdf')`, `mime TEXT CHECK IN ('image/jpeg','image/png','application/pdf')`, `tamano_bytes BIGINT CHECK > 0`, `sha256 CHAR(64)`, `storage_key TEXT UNIQUE`, `nombre_original TEXT` (saneado: basename, sin controles, ≤ 255; solo display), `subido_por` FK usuario. Índice `(clinica_id, paciente_id, created_at DESC)`. Sin endpoint de borrado.
   - **Detección por magic bytes** (función pura): JPEG `FF D8 FF`, PNG `89 50 4E 47 0D 0A 1A 0A`, PDF `25 50 44 46 2D` (`%PDF-`). Content-type declarado ≠ detectado → 415. Sin `python-magic`/libmagic (dependencia nativa en Windows/alpine; 3 firmas no la justifican).
   - **Tamaño**: `ADJUNTO_MAX_BYTES` (default 10 MiB). Se lee el stream en chunks contando bytes y se aborta al exceder (→ 413) aunque `Content-Length` mienta; además se rechaza temprano si `Content-Length` ya excede. 0 bytes → 422.
   - **Storage**: `AdjuntoStorage` Protocol (`guardar(key, chunks) -> None`, `abrir(key) -> BinaryIO`, `eliminar(key)` solo para compensación). `LocalDirStorage(ADJUNTOS_STORAGE_DIR)`: clave `"{clinica_id}/{paciente_id}/{uuid4}"` generada en servidor (nunca el nombre del cliente), escritura a archivo temporal en el mismo dir + `os.replace` atómico, verificación de que la ruta resuelta queda dentro del root. Directorio fuera de cualquier static mount.
   - **Orden y compensación**: validar → escribir archivo → insertar fila + auditoría → commit; si la DB falla, `eliminar(key)` best-effort. Huérfanos residuales (crash entre pasos) → job de limpieza en F2 (documentado).
   - **Descarga**: `StreamingResponse` con MIME de la fila, `Content-Disposition: attachment; filename*=UTF-8''<saneado>`, `X-Content-Type-Options: nosniff`, `Cache-Control: no-store`.
10. **RBAC clínico** (extiende `permissions.py`, sin middleware global):
    - Datos administrativos: `require_role("admin","recepcionista","odontologo")`.
    - Lectura clínica: `require_clinico()` existente (admin, odontólogo). Escritura clínica: nuevo `require_clinico_escritura()` = `require_role("odontologo")` (matriz `03`: admin solo "Lectura (auditoría)" de HC; el dueño-odontólogo tiene ambos roles).
    - Auditoría: `require_admin()`.
    - **Vínculo odontólogo↔paciente**: `VinculoPacienteResolver = Callable[[Session, AuthContext, Paciente], bool]` inyectable con `set_resolver_vinculo_paciente()` (mismo patrón que `set_resolver_agenda_propia`). Se aplica solo cuando el usuario tiene rol odontólogo y **no** admin. Excepción en el resolver → 403 (fallo cerrado). **Regla interina (default)**: `True` para pacientes de la clínica del JWT (el paciente ya viene filtrado por tenant). C-05 inyecta "existe turno no cancelado entre el paciente y el profesional vinculado al usuario".
    - Orden de chequeo: auth (401) → rol (403) → paciente en tenant (404) → vínculo (403) → consentimiento (403, solo escrituras clínicas) → validación de payload/archivo.
    - Alternativas a la regla interina: (a) fallo cerrado hasta C-05 — bloquea C-10 y el uso del piloto; (b) tabla de asignación manual paciente↔profesional — trabajo que C-05 vuelve obsoleto. Se elige permisivo-dentro-del-tenant + lectura auditada porque el piloto (SU-02/PA-03) es el consultorio propio; **requiere aprobación** (ver abajo).
11. **Consentimiento**: `PATCH consentimiento_datos` lo pueden registrar admin/recepcionista/odontólogo (el consentimiento suele firmarse en papel en mostrador). `true` setea `_at = now()` y `_por = sub`; `false` (revocación) conserva HC y bloquea nuevas cargas clínicas (Ley 26.529 obliga a conservar la HC). Cada cambio → evento `consentimiento_otorgado`/`consentimiento_revocado`. Formalización con firma y constancia queda en C-18.
12. **Schemas** (`domain/pacientes/schemas.py`, base `_ForbidBase` como en `core/schemas.py`): `PacienteCreate`, `PacienteUpdate` (todos opcionales, sin `riesgo_ausencia`/`clinica_id`), `PacienteOut`, `PacientePage(items, next_cursor)`, `FichaPut(version_esperada ≥ 0, anamnesis, alergias, antecedentes)`, `FichaOut`, `AdjuntoOut`, `AuditoriaOut`. Validación de formato en validators que llaman a la normalización pura. Upload: `UploadFile` + `Form` con solo el archivo; cualquier otro form field (p. ej. `evolucion_id`) → 422.
13. **Errores**: 404 para recursos de otro tenant (no 403, evita enumeración); 409 DNI duplicado con `{"detail": ..., "paciente_id": N}`; 409 versión de ficha; 403 consentimiento con `detail` explícito; 413/415 adjuntos. Logs con ids, nunca PII/PHI (sin nombre, DNI, contacto ni contenido).
14. **Layout**: `domain/pacientes/{models,schemas,normalizacion,archivos,servicios}.py`, `domain/auditoria/{models,writer}.py`, `infrastructure/storage/adjuntos.py`, `api/pacientes.py` (router `/api/pacientes`, todas las rutas con `require_tenant_checked`). Settings: `adjuntos_storage_dir: Path` (default `./var/adjuntos`), `adjunto_max_bytes: int` (default 10485760, `ge=1`, `le=26214400`).
15. **Tests** (strict TDD, nunca SQLite): unit para normalización, magic bytes, storage local (`tmp_path`), schemas; integración con fixtures de `tests/integration/conftest.py` (`postgres:16-alpine` + Alembic head) para migración up/down/up, triggers, servicios y endpoints. Datos sintéticos: DNIs `9xxxxxxx`, emails `@example.com`, teléfonos `+54911555500xx`, nombres "Paciente Sintético N", `es_seed=true`; archivos de prueba generados en memoria (bytes mínimos con firma), nunca imágenes reales.

## Risks / Trade-offs

- [Riesgo] Regla interina de vínculo es permisiva dentro del tenant → un odontólogo tercerizado podría leer fichas de pacientes ajenos antes de C-05 → Mitigación: toda lectura clínica auditada y consultable por admin; resolver reemplazable en C-05; el piloto no tiene tercerizados (SU-02). Requiere aprobación.
- [Riesgo] La app conecta como owner: un bug con SQL crudo podría `DROP TRIGGER` → Mitigación: triggers + repositorio append-only + test que verifica que UPDATE/DELETE fallan; hardening con rol DB sin ownership como tarea de infra posterior.
- [Riesgo] Storage local no replica ni cifra → Mitigación: abstracción `AdjuntoStorage`; backup/cifrado del volumen es responsabilidad de despliegue; decisión de proveedor cloud pendiente (no bloquea el MVP local).
- [Riesgo] Huérfanos de archivo si el proceso cae entre escritura y commit → Mitigación: compensación best-effort + job de limpieza F2 (comparar `storage_key` vs disco).
- [Riesgo] PDF con contenido activo / polyglots → Mitigación: nunca se renderiza inline (attachment + nosniff + no-store); antivirus F2.
- [Riesgo] Crecimiento de `auditoria_hc` por lecturas → Mitigación: índices por tenant/paciente/fecha; particionado por fecha si hace falta (F2).
- [Trade-off] Ficha versionada duplica texto en cada versión → aceptado (volumen bajo, texto corto; legalmente preferible).
- [Trade-off] `nombre_busqueda` derivado en app puede desincronizarse si alguien escribe SQL directo → aceptado; solo el servicio escribe pacientes.
- [Trade-off] Sin HEIC (fotos de iPhone) → el usuario debe exportar a JPEG; soporte F2.

## Dependencias de validación legal (PA-04 abierta, supuesto Sprint 1 SU-08)

Los siguientes puntos se implementan sobre el supuesto SU-08 y deben revisarse con asesoría legal (leyes 26.529, 25.326, 25.506):

1. Que la anamnesis/ficha sea parte de la HC y por lo tanto deba ser append-only (versionado sin borrado).
2. Que un flag `consentimiento_datos` + fecha + usuario que lo registró sea suficiente como base para cargar datos de salud hasta C-18 (consentimiento firmado con constancia).
3. Que los datos administrativos/contacto/OS puedan cargarse **sin** consentimiento (necesario para reservar).
4. Efecto de la revocación: conservar la HC existente (Ley 26.529, plazo de conservación) y solo bloquear nuevas cargas.
5. Que la recepción pueda registrar el consentimiento en nombre del paciente.
6. Que auditar lecturas clínicas (y no solo escrituras) sea adecuado y el contenido mínimo del log (sin PHI) sea suficiente como trazabilidad.
7. Ubicación de datos declarada (RN-CU-01): el storage local/cloud de adjuntos y la DB deben declararse en la política de privacidad (C-18).
8. Ausencia de endpoint de borrado de pacientes/adjuntos frente al derecho de supresión de Ley 25.326 (que cede ante la obligación de conservar HC).

## Puntos para aprobación humana

Antes de `/opsx:apply` (governance CRÍTICO) el humano debe aprobar:

1. **Regla interina RBAC clínico**: odontólogo accede a todos los pacientes de su clínica (lecturas auditadas) hasta que C-05 inyecte el vínculo por turnos; alternativa: fallo cerrado hasta C-05.
2. **Escritura clínica solo rol odontólogo**: admin sin rol odontólogo solo lee ficha/adjuntos (matriz `03`); el dueño-odontólogo necesita ambos roles.
3. **Enforcement de consentimiento**: `403` en PUT ficha / POST adjunto sin `consentimiento_datos`; datos administrativos/OS permitidos sin consentimiento; cualquier rol de staff puede registrar/revocar el consentimiento; revocar no borra HC.
4. **Mecanismo de inmutabilidad**: triggers PG que rechazan UPDATE/DELETE/TRUNCATE en `auditoria_hc` y `ficha_version` + repositorio append-only; `REVOKE` con rol DB dedicado diferido a hardening de infra.
5. **Ficha versionada** (cada PUT = nueva versión, control optimista `version_esperada`) en vez de fila mutable con diff.
6. **Auditoría de lecturas clínicas** (ficha, historial, descarga de adjunto) además de escrituras, con diff sin PHI.
7. **Adjuntos**: solo JPEG/PNG/PDF por magic bytes, máx 10 MiB configurable (`ADJUNTO_MAX_BYTES`), storage en directorio local (`ADJUNTOS_STORAGE_DIR`) tras abstracción, sin cifrado de aplicación ni antivirus en MVP, sin borrado por API.
8. **Supuestos legales** de la sección anterior (PA-04/SU-08) aceptados para Sprint 1.
9. **Nuevas dependencias**: `phonenumbers`, `python-multipart`; extensión `pg_trgm`.

## Migration Plan

- `backend/alembic/versions/004_pacientes_ficha.py`: `revision = "004_pacientes_ficha"`, `down_revision = "003_clinica_catalogo"` (confirmado por el orquestador con la propuesta de C-04). Up: extensión `pg_trgm` → `paciente` (+ `uq_paciente_clinica_id`) → `ficha_version` → `adjunto` → `auditoria_hc` → función + triggers. Down: triggers → función → tablas en orden inverso (la extensión se conserva; **no** toca `uq_usuario_clinica_id`, que pertenece a la 003).
- Si C-04 aún no está aplicado al momento de `apply`, bloquear (no reencadenar a 002): la cadena lineal 001→002→003→004 es contrato con C-04/C-05 (005).
- Tablas nuevas, sin datos previos: despliegue sin downtime. Crear `ADJUNTOS_STORAGE_DIR` con permisos restringidos al usuario del proceso.
- Rollback: `alembic downgrade -1` borra tablas de pacientes (y la HC). En producción con datos reales **no** se hace downgrade: se hace roll-forward. Documentado en el docstring de la migración.

## Open Questions

- Límite exacto de tamaño (10 MiB) a confirmar con el piloto según tamaño de fotos intraorales/PDF de estudios (constante env; no cambia specs).
- ¿Proveedor cloud de storage (S3-compatible, GCS) y región? (Nueva implementación de `AdjuntoStorage`; no cambia specs.)
- ¿Retención/particionado de `auditoria_hc`? (Operativo, F2.)
