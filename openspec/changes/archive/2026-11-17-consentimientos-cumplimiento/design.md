# Design — consentimientos-cumplimiento (C-18)

## Context

Motivación: ver `proposal.md` §Why. Requisitos: ver `specs/informed-consents`, `specs/user-administration`, `specs/data-export`, `specs/admin-audit`, `specs/legal-pages` y el delta de `specs/clinical-audit`.

Estado actual observado en el código:

- `backend/alembic/versions/004_pacientes_ficha.py`: `fn_rechazar_mutacion()` + triggers append-only por fila (UPDATE/DELETE) y por sentencia (TRUNCATE). `auditoria_hc` exige `paciente_id NOT NULL` → no sirve para eventos sin paciente.
- `backend/alembic/versions/008_odontograma_evolucion.py` (C-09, archivado el 2026-11-17): `revision = "008_odontograma_evolucion"`, `down_revision = "006_turno_transicion"`. Amplía los CHECK de `auditoria_hc` a `entidad IN ('paciente','ficha','adjunto','odontograma','evolucion')` y agrega la acción `corregir`. Contrato fijo en `openspec/changes/archive/2026-11-17-odontograma-evolucion/` (no se edita).
- `backend/app/domain/auditoria/writer.py`: `registrar_evento(...)` con allowlist `_DIFF_PERMITIDO`; `models.py` con tuplas `ACCIONES`/`ENTIDADES`.
- `backend/app/api/pacientes.py`: dependencias `paciente_lectura` (admin + odontólogo + vínculo) y `paciente_escritura` (odontólogo + vínculo + `consentimiento_datos` → 403 antes del payload). C-09 ya las importa desde otro router; acá se hace lo mismo.
- C-03 **no expone ningún endpoint de usuarios**: solo `/api/auth/{login,refresh,logout,me}`. `UsuarioRol` tiene PK `(usuario_id, rol_id)` + `is_active`; `roles_of_user()` lee los roles **desde la DB en cada request** (`get_current_user`), así que un cambio de roles es efectivo sin reemitir tokens. Hash con `bcrypt` (`backend/app/domain/auth/passwords.py`); `UsuarioCreate` exige password 8..128.
- `backend/app/infrastructure/settings.py` usa `extra="forbid"`; este change no agrega variables de entorno.
- Frontend: `frontend/src/pages/CumplimientoPage.tsx` es un placeholder de C-01 y `App.tsx` ya declara `/cumplimiento`. No hay `/privacidad`. Tests con vitest + jsdom (`frontend/tests/`), sin `@testing-library` → se renderiza con `react-dom/server` (`renderToString`), sin dependencias nuevas. C-10 (en propuesta paralela) agrega un shell con login: debe dejar públicas estas dos rutas (`access-control` · "Rutas públicas declaradas" ya las declara).

Skill de dominio usada: **`dominio-cumplimiento`** (generada el 2026-11-16 con `crear-skill-de-dominio`, `verificar.py` → `RESULTADO: OK`). Mapeo de reglas:

| Regla | Dónde la toma este change |
|---|---|
| RN-CU-01 | D8 (privacidad pública con ubicación declarada); el gate `consentimiento_datos` de C-08 se reutiliza en D3 |
| RN-CU-02 | D1, D2, D3 (texto versionado, hash, constancia, bloqueo en DB) |
| RN-CU-03 | Solo se menciona en `/cumplimiento`; lo implementa C-19 |
| RN-CU-04 | D5, D6 (ZIP de CSV del tenant, sin costo, PDF diferido) |
| RN-CU-05 | D8 (página pública con aviso "a validar con asesoría legal") |

Reglas duras aplicadas: 4 (`extra='forbid'`), 7 (TIMESTAMPTZ del servidor), 9 (testcontainers), 10 (`clinica_id` + índice + aislamiento), 12 (sin secretos; la exportación excluye hashes), 14 (datos sintéticos, textos con marcadores), 15 (consentimiento firmado bloqueado), 16 (consentimiento de datos + RBAC clínico).

Compact rules del registry aplicadas: `event-store-design` (documento y constancia como filas append-only, auditoría sin endpoint de escritura), `auth-implementation-patterns` (AuthZ en servidor, `require_admin()` en cada ruta admin), `docker-testcontainers` (`postgres:16-alpine` + migración up/down), `postgresql-table-design` (BIGINT identity, TEXT + CHECK, TIMESTAMPTZ, FKs compuestas por tenant).

## Goals / Non-Goals

**Goals:**

- Que el bloqueo post-firma lo garantice la base (triggers + UNIQUE), no solo la API.
- Reutilizar `fn_rechazar_mutacion()`, `registrar_evento`, `paciente_lectura`/`paciente_escritura`, `require_admin()` y el handler de `PacienteError` sin crear mecanismos paralelos.
- Exportación construida solo con la stdlib (`csv`, `zipfile`, `tempfile`, `hashlib`).

**Non-Goals (de diseño):**

- Generar PDF (ni del consentimiento ni de la exportación).
- Jobs asíncronos de exportación: la exportación es síncrona en el MVP (ver Risks).
- Un CMS de textos legales: los textos viven versionados en código.

## Decisions

### D1 — Documento y constancia como dos tablas append-only

- `consentimiento`: `id`, `clinica_id`, `paciente_id`, `tipo` TEXT CHECK (catálogo D2), `texto` TEXT NOT NULL, `texto_version` TEXT NOT NULL, `texto_hash` CHAR(64) CHECK `texto_hash ~ '^[0-9a-f]{64}$'`, `autor_usuario_id`, `created_at` TIMESTAMPTZ DEFAULT `now()`.
  - `UNIQUE (clinica_id, paciente_id, id)` para la FK de la firma; FKs compuestas `(clinica_id, paciente_id) → paciente` y `(clinica_id, autor_usuario_id) → usuario`, `ON DELETE RESTRICT`.
  - Índice `(clinica_id, paciente_id, id DESC)` (listado) e índice `(clinica_id, paciente_id, tipo)` (el `(paciente_id, tipo)` de la ficha de `CHANGES.md`, con tenant al frente por regla 10).
- `consentimiento_firma`: `id`, `clinica_id`, `paciente_id`, `consentimiento_id`, `firmado_en` TIMESTAMPTZ DEFAULT `now()`, `ip` TEXT NOT NULL, `dispositivo` TEXT NOT NULL (user-agent truncado a 512), `texto_hash` CHAR(64), `firmante_nombre` TEXT CHECK 1..200, `firmante_dni` TEXT CHECK `~ '^[0-9]{7,8}$'`, `asistido_por_usuario_id`.
  - `UNIQUE (clinica_id, consentimiento_id)` → **una sola firma** por documento; la segunda (secuencial o concurrente) viola el índice → 409, sin `SELECT … FOR UPDATE`.
  - FK compuesta `(clinica_id, paciente_id, consentimiento_id) → consentimiento(clinica_id, paciente_id, id)`: la base impide firmar un documento de otro paciente u otra clínica.
- Ambas tablas con triggers `fn_rechazar_mutacion()` (fila UPDATE/DELETE + sentencia TRUNCATE). **Nunca hay UPDATE**: firmar = INSERT de la constancia. `estado` (`pendiente`/`firmado`) y `documento_bloqueado` se **derivan** en la lectura (`LEFT JOIN consentimiento_firma`), igual que `corregida_por_id` en C-09 D4.
- Alternativa descartada: una sola tabla con `documento_bloqueado` mutable + trigger condicional (`OLD.documento_bloqueado`). Exige un UPDATE legítimo antes del bloqueo y un trigger nuevo; con dos tablas se reutiliza la función de la 004 tal cual y el texto queda inmutable desde que se genera (lo que se firma es exactamente lo que se mostró).

### D2 — Textos versionados en código y hash

- `backend/app/domain/cumplimiento/textos.py`: diccionario inmutable `tipo → (version, texto)` con los tipos del catálogo cerrado `tratamiento_general`, `extraccion`, `endodoncia`, `implante`, `anestesia`. Cada texto empieza con el aviso "Texto base a validar con asesoría legal" y usa solo marcadores (`[A completar …]`).
- Cambiar un texto = subir su `version` (test que lo exige comparando hash conocido ↔ versión). Los documentos ya generados no cambian porque guardan su copia del texto.
- `hashing.py` puro: `sha256_hex(texto) = hashlib.sha256(texto.encode("utf-8")).hexdigest()`, sin normalizar (spec "Espacios y acentos cuentan").

### D3 — API de consentimientos y orden de respuestas

- Router `backend/app/api/consentimientos.py` (prefijo `/api/pacientes`, tag `consentimientos`):
  - `POST /{id}/consentimientos` y `POST /{id}/consentimientos/{cid}/firmar` usan `paciente_escritura` (solo odontólogo, vínculo, consentimiento de datos);
  - `GET /{id}/consentimientos` y `GET /{id}/consentimientos/{cid}` usan `paciente_lectura` (admin + odontólogo).
- Orden: 401 → 403 rol → 404 paciente ajeno → 403 vínculo → 403 consentimiento de datos → 422 cuerpo → 404 `cid` → 409 ya firmado / hash distinto → 201.
- `FirmaIn` (`extra='forbid'`): `acepta: bool | None`, `firmante_nombre: str | None`, `firmante_dni: str | None`, `texto_hash: str`. Los tres primeros son opcionales **a propósito** en el schema: la validación de completitud la hace el servicio y responde `FirmaIncompleta` (422, `{"detail": …, "reintentable": true, "faltantes": [...]}`) en vez del 422 genérico de Pydantic, así el cliente distingue "reintentá la firma" de "payload mal armado". `ip`, `fecha`, `dispositivo` en el cuerpo → 422 de Pydantic.
- IP = `request.client.host` (en despliegue, uvicorn con `--proxy-headers` y `--forwarded-allow-ips` del balanceador; no se lee `X-Forwarded-For` a mano). Dispositivo = header `User-Agent` o `no-informado`.
- Errores en `backend/app/domain/cumplimiento/errores.py` como subclases de `PacienteError` (handler existente): `TipoConsentimientoInvalido` 422, `ConsentimientoNoEncontrado` 404, `FirmaIncompleta` 422, `HashNoCoincide` 409, `ConsentimientoYaFirmado` 409.
- Sin PUT/PATCH/DELETE: test que recorre `app.routes` (patrón de C-08/C-09).

### D4 — Auditoría: `AuditoriaHC` para consentimientos, `auditoria_admin` para lo demás

- Consentimientos: `ENTIDADES += ("consentimiento",)`, `ACCIONES += ("firmar",)` (`crear`/`leer` ya existen). La 009 reemplaza los CHECK de `auditoria_hc` partiendo del conjunto que deja la 008. Allowlist: `consentimiento_id` (int), `texto_version` (str). Nunca `tipo`, texto ni firmante (el tipo revela el procedimiento).
- Tabla nueva `auditoria_admin`: `id`, `clinica_id`, `actor_usuario_id` NOT NULL, `accion` TEXT CHECK IN (`usuario_crear`,`usuario_roles`,`exportar`), `entidad_id` BIGINT NULL, `diff` JSONB, `ip`, `created_at`. FK `(clinica_id, actor_usuario_id) → usuario`, índice `(clinica_id, created_at)`, triggers `fn_rechazar_mutacion()`. Writer propio mínimo (`registrar_evento_admin`) con allowlist: `roles`, `roles_anteriores` (listas de claves), `formato`, `conteos` (dict str→int), `faltantes` (lista de ids). Sin email ni contraseña.
- Alternativa descartada: hacer `auditoria_hc.paciente_id` nullable. Cambia una spec archivada de C-08 y mezcla eventos clínicos con administrativos.

### D5 — Exportación: ZIP en archivo temporal y streaming

- `GET /api/admin/exportacion?formato=csv` (`require_admin()`), endpoint **`def` sincrónico** (corre en threadpool, Context7 #1).
- `formato` se valida contra `{"csv"}` en el servicio → `FormatoNoSoportado` 422 con `{"formatos": ["csv"]}`. PDF diferido (DT-3).
- Construcción **antes** de responder, dentro de la request: `tempfile.SpooledTemporaryFile(max_size=16 MiB)` (seekable → `zipfile` escribe cabeceras normales, Context7 #2), `ZipFile(tmp, "w", ZIP_DEFLATED)`. Cada CSV se escribe con `zf.open(nombre, "w")` envuelto en `io.TextIOWrapper(encoding="utf-8-sig", newline="")` + `csv.writer`, iterando la consulta con `yield_per` para no cargar la tabla en memoria. Adjuntos: `zf.open("adjuntos/<id><ext>", "w")` copiando por chunks desde el storage; archivo faltante → se lista en `manifest.faltantes`.
- Después: `registrar_evento_admin("exportar", …)` + commit; `tmp.seek(0)` y `StreamingResponse` con un generador sincrónico que lee chunks de 64 KiB y cierra el temporal en `finally`; headers `Content-Type: application/zip`, `Content-Disposition: attachment; filename="exportacion-clinica-<id>-<YYYYMMDDTHHMMSSZ>.zip"`. Como el ZIP se arma antes de devolver, un error produce un 500 limpio y no un ZIP truncado ni un evento `exportar` huérfano.
- Entidades y columnas: un registro `ENTIDADES_EXPORTABLES` (nombre de CSV → modelo + filtro por `clinica_id`) con **todas las columnas del modelo menos una denylist** (`password_hash`). Así columnas nuevas (p. ej. las de C-05c en `turno`) se exportan solas. Orden por `id`. Entidades: `pacientes`, `fichas`, `adjuntos`, `odontogramas`, `evoluciones`, `consentimientos`, `consentimiento_firmas`, `turnos`, `turno_transiciones`, `profesionales`, `sillones` (`sillon_recurso`), `prestaciones`, `profesional_sillones`, `bloqueos`, `usuarios`, `usuario_roles`, `auditoria_hc`. Si una tabla no tuviera `clinica_id` propio, se filtra por join con su padre del tenant (test de aislamiento lo cubre).
- Serialización: `datetime` → `isoformat()` (con zona, columnas TIMESTAMPTZ), `Decimal` → `str`, JSONB → `json.dumps(ensure_ascii=False, sort_keys=True)`, `None` → vacío. Celdas de texto que empiezan con `=`,`+`,`-`,`@`, tab o CR → prefijo `'` (OWASP CSV injection). Las numéricas no se tocan (un monto negativo no es texto).
- `manifest.json`: `clinica_id`, `generado_en`, `version_esquema` (= revisión Alembic actual), `formato`, `conteos`, `faltantes`, `excluidas: [{"entidad": "caja", "motivo": "no existe aún (C-12)"}, {"entidad": "facturas", "motivo": "no existe aún (C-13)"}]`. C-12/C-13/C-19 suman sus entidades al registro y se quitan de `excluidas`.
- Aislamiento: cada consulta filtra `clinica_id == auth.tenant_id`; un test arma dos clínicas y verifica que ningún id de B aparece en ningún CSV ni nombre de archivo.

### D6 — Administración de usuarios

- `backend/app/domain/usuarios/schemas.py`: `UsuarioAdminIn` (`email: EmailStr`, `nombre` 1..200, `password` 8..128, `roles: list[Literal["admin","odontologo","recepcionista"]]` con `min_length=1`, sin duplicados) y `RolesIn`; ambos `extra='forbid'`. `paciente-enlace` no es asignable (no es personal).
- `servicios.py`: alta con `bcrypt.hashpw` (misma librería que C-03), email normalizado con `normalize_email`; violación del índice único `lower(email)` por clínica → `UsuarioDuplicado` 409.
- Cambio de roles: `SELECT … FOR UPDATE` sobre las filas `usuario_rol` **de los admins activos de la clínica** antes de calcular "¿queda algún admin?", para que dos admins que se quitan el rol a la vez no dejen la clínica sin admin; si quedaría 0 → `UltimoAdmin` 409. Roles quitados → `is_active = false`; roles nuevos → INSERT o reactivación (`usuario_rol` no es append-only). Sin cambios → 200 sin evento.
- Router `backend/app/api/admin_cumplimiento.py` (prefijo `/api/admin`, tag `admin-cumplimiento`) con usuarios y exportación; listado paginado keyset (`limit` 1..200, `Pagina[T]` importado de `backend/app/domain/agenda/schemas.py`, solo import: no se modifica ese archivo).

### D7 — Migración `009_consentimientos_cumplimiento`

- `revision = "009_consentimientos_cumplimiento"`, `down_revision = "008_odontograma_evolucion"`.
- **Si C-05c (`007_sobreturno_huecos`) mergea**, la cadena se resuelve en la 008 (C-09 D7 re-apunta su `down_revision`); la 009 no cambia. Antes de mergear, `cd backend && alembic heads` debe mostrar **un único head**.
- Upgrade: `consentimiento` → `consentimiento_firma` → `auditoria_admin` → triggers → CHECKs de `auditoria_hc` ampliados (`op.drop_constraint(op.f("ck_auditoria_hc_entidad_valida"), …)` + `create_check_constraint`, mismo patrón que la 008).
- Downgrade: restaura los CHECK de la 008, borra triggers y tablas; **no** borra `fn_rechazar_mutacion()`. Si ya hay eventos `consentimiento`/`firmar`, restaurar el CHECK falla a propósito (roll-forward en producción, documentado en el docstring).

### D8 — Páginas legales estáticas en el frontend

- `frontend/src/features/legal/textos.ts`: objetos tipados `{ version, fecha, secciones: { titulo, parrafos }[] }` para privacidad y cumplimiento, con el aviso y marcadores `[A completar: responsable / CUIT / contacto]`. Ubicación declarada: "Servidores en la nube del proveedor [A completar: proveedor y región], contratado por la plataforma; los datos de cada clínica están aislados" (DD-09).
- `CumplimientoPage.tsx` se completa y `PrivacidadPage.tsx` es nueva; `App.tsx` suma `<Route path="/privacidad">` (react-router 7 ya iguala la barra final). Sin fetch: la página no depende de la API.
- Tests vitest en `frontend/tests/legal.test.tsx` con `renderToString` + `MemoryRouter`.

### D9 — Evidencia de Context7 (MCP) y qué se adoptó

Consultas hechas el 2026-11-16, sin secretos, datos de pacientes ni código privado:

1. `resolve-library-id("FastAPI")` → `/websites/fastapi_tiangolo`. `query-docs`: "StreamingResponse with a file-like object or generator yielding chunks, media_type application/zip and Content-Disposition attachment header; sync generator runs in threadpool".
   - Respuesta: `StreamingResponse(content, status_code, headers, media_type, background)`; si `content` no es async iterable usa `iterate_in_threadpool(content)`. Para file-like objects que bloquean, declarar la operación con `def` para que corra en threadpool.
   - **Adoptado:** endpoint `def`; generador **sincrónico** de chunks sobre el temporal (sin `async`), headers explícitos `Content-Disposition`; cierre del temporal en el `finally` del generador.
2. `resolve-library-id("Python")` → `/python/cpython`. `query-docs`: "zipfile.ZipFile open(name, mode='w') to write an entry incrementally, behavior when the underlying file object is not seekable, and ZIP_DEFLATED".
   - Respuesta: `ZipFile` detecta si el archivo es seekable (`tell`/`seek`); si no, lo envuelve y escribe con descriptores de datos. `open(name, "w")` devuelve un handle escribible y mientras está abierto no se puede escribir otra entrada. `ZIP_DEFLATED` requiere `zlib`.
   - **Adoptado:** `SpooledTemporaryFile` (seekable → ZIP estándar, compatible con cualquier descompresor) en lugar de escribir directo al socket; un CSV a la vez con `zf.open(..., "w")` y `ZIP_DEFLATED`.

En el apply, registrar esta evidencia en `docs/skills-mcp/evidencias/README.md` (task 7.3).

## Decisiones tomadas (aprobación delegada del usuario, 2026-11-16)

El usuario aprobó de antemano proponer, implementar y archivar C-18 (governance ALTO). Ante cada ambigüedad se eligió la opción más coherente con la KB y las reglas duras:

| # | Pregunta | Opciones | Elegida | Por qué |
|---|---|---|---|---|
| DT-1 | ¿Cómo se bloquea el documento firmado? | (a) documento + constancia en dos tablas append-only, estado derivado; (b) una tabla con flag `documento_bloqueado` mutable y trigger condicional | **(a)** | Reutiliza `fn_rechazar_mutacion()` sin cambios, el texto es inmutable desde que se genera y la doble firma la resuelve un UNIQUE (regla 15). |
| DT-2 | ¿Qué firma se implementa y quién la asiste? | (a) firma electrónica simple presencial: aceptación + nombre + DNI del firmante, asistida por el odontólogo logueado; (b) firma remota por enlace al paciente; (c) firma digital con certificado | **(a)** | Flujo 8 (odontólogo → paciente). (b) necesita token público y canal (C-06/C-15); (c) excede el MVP. Ley 25.506 a validar (PA-04). |
| DT-3 | ¿PDF en la exportación y del consentimiento? | (a) CSV/ZIP ahora, PDF diferido; (b) PDF ahora | **(a)** | El objetivo de RN-CU-04 es "salir sin retención": CSV es portable y completo; PDF agrega una dependencia de render sin datos nuevos. `formato=pdf` → 422 claro. |
| DT-4 | ¿Qué entidades exporta? | (a) todas las que existen hoy (incl. catálogo, usuarios sin hash, auditoría HC) + archivos de adjuntos; (b) solo pacientes/HC/turnos | **(a)** | "Respaldo completo" (US-014). Caja/facturas no existen: se declaran excluidas en el manifest. |
| DT-5 | ¿Dónde se auditan eventos sin paciente? | (a) tabla `auditoria_admin` append-only; (b) `auditoria_hc.paciente_id` nullable | **(a)** | No cambia el contrato archivado de C-08 y separa auditoría clínica de administrativa. |
| DT-6 | ¿Qué endpoints de usuarios? | (a) listar, crear, reemplazar roles; (b) además baja y reseteo de contraseña | **(a)** | Es lo que lista `CHANGES.md` y C-03 no provee nada; baja/reseteo afectan sesiones y van a un change propio. |
| DT-7 | ¿Textos legales en DB o en código? | (a) frontend estático versionado + plantillas de consentimiento en código backend; (b) tabla de textos legales con endpoint público | **(a)** | Sin CMS ni endpoint nuevo; las páginas funcionan sin API. El documento firmado guarda su propia copia del texto, así la versión del código no afecta lo ya firmado. |
| DT-8 | ¿Firmar un consentimiento cambia `consentimiento_datos`? | (a) no, son independientes; (b) un tipo `datos_personales` lo activa | **(a)** | El flag de C-08 ya tiene su endpoint auditado; acoplarlos cambiaría la spec `patients`. |
| DT-9 | ¿Quién genera consentimientos? | (a) solo odontólogo (escritura clínica, matriz `03`); (b) también recepción | **(a)** | Matriz RBAC: "consentimientos" están en el panel del odontólogo; recepción sin acceso clínico (regla 16). |
| DT-10 | ¿Ubicación de datos en la política? | (a) texto genérico con marcador de proveedor/región; (b) nombrar un proveedor | **(a)** | El proveedor cloud no está decidido en la KB (DD-09 solo dice "nube"); inventarlo sería un dato falso. |

## Risks / Trade-offs

- [Exportación síncrona de una clínica grande tarda o pesa mucho] → `yield_per` + temporal en disco a partir de 16 MiB; adjuntos ≤ 10 MiB c/u. Si un piloto la vuelve lenta, se pasa a job asíncrono con enlace (change aparte) sin cambiar el formato.
- [La firma presencial no prueba identidad fuerte] → Es firma electrónica simple con constancia; el texto legal lo dice y PA-04 queda abierto para validar con asesoría.
- [IP detrás de un proxy] → Configuración de uvicorn `--proxy-headers` en el despliegue (D3); en tests se usa la IP del `TestClient`.
- [C-09 todavía no mergeó la 008] → La 009 depende de su revisión; si C-09 cambia su id, se ajusta solo el `down_revision`. El apply de C-18 arranca después de C-09.
- [Dos changes amplían los CHECK de `auditoria_hc`] → La 009 parte del conjunto exacto de la 008 y el test de migración verifica el CHECK final en `pg_constraint`.
- [Columnas nuevas de otros changes aparecen en la exportación automáticamente] → Es deseado; la denylist explícita evita filtrar secretos (test que falla si una columna se llama `*password*`, `*secret*`, `*token*`).

## Migration Plan

1. `009_consentimientos_cumplimiento` sobre `008_odontograma_evolucion`. Tablas nuevas; sin backfill ni downtime.
2. Antes de mergear: `cd backend && alembic heads` → un único head (también si C-05c ya mergeó su 007).
3. Rollback de la aplicación: quitar los routers; las tablas quedan inertes e inmutables.
4. Rollback de esquema: solo en entornos sin consentimientos firmados ni eventos nuevos (D7).

## Open Questions

- Lista final de tipos de consentimiento y sus textos: los aporta la asesoría/piloto; agregar un tipo es aditivo (CHECK + texto) y no cambia specs.
- Plazo de conservación a declarar en `/privacidad` (Ley 26.529 fija 10 años para HC): queda como marcador hasta validación legal.
