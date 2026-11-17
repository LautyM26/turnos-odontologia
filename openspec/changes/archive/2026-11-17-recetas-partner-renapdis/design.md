# Design — recetas-partner-renapdis (C-19)

## Context

Motivación: ver `proposal.md` §Why. Requisitos: ver `specs/prescriptions` y el delta de `specs/platform-config`.

Estado actual observado en el código:

- `backend/app/infrastructure/settings.py`: `Settings(BaseSettings)` con `extra="forbid"` y `env_file=".env"`. **No declara** `RECETAS_PARTNER_KEY`, aunque `backend/.env.example` y `backend/tests/test_env_example.py` ya la listan. Context7 (#1) confirma que con `extra="forbid"` toda clave desconocida **del archivo dotenv** (incluso vacía, `RECETAS_PARTNER_KEY=`) produce `extra_forbidden`, mientras que las variables del proceso desconocidas se ignoran. Declarar los campos es obligatorio para que un `.env` copiado del ejemplo no tumbe el boot.
- C-09 (`openspec/changes/archive/2026-11-17-odontograma-evolucion/`, en implementación): tabla `evolucion` con `autor_usuario_id`, `profesional_id`, `UNIQUE (clinica_id, paciente_id, id)` (`uq_evolucion_clinica_paciente_id`) y corrección por fila nueva. Errores en `backend/app/domain/clinica/errores.py` (`AutorProfesionalRequerido` 422).
- C-18 (`openspec/changes/archive/2026-11-17-consentimientos-cumplimiento/`, archivado): migración `009_consentimientos_cumplimiento`, CHECK de `auditoria_hc` con `consentimiento`/`firmar`, registro `ENTIDADES_EXPORTABLES` y `manifest.excluidas` en `backend/app/domain/cumplimiento/exportacion.py`.
- `backend/app/domain/agenda/servicio.py`: `profesional_de_usuario(session, usuario_id)`; `Profesional.matricula` (C-04). Solo se importan.
- `Paciente`: `nombre`, `apellido`, `dni`, `obra_social_nombre`, `obra_social_plan`, `nro_afiliado`, `consentimiento_datos`.
- `httpx` ya es dependencia de desarrollo (tests); no hay cliente HTTP de producción todavía.

Skill de dominio usada: **`dominio-cumplimiento`** (generada el 2026-11-16, `verificar.py` → `RESULTADO: OK`). Mapeo:

| Regla | Dónde la toma este change |
|---|---|
| RN-CU-03 | D1–D5 (solo vía partner, 501 sin partner, simulado nunca en producción) |
| RN-CU-01 | D4 (gate `consentimiento_datos` reutilizado) |
| RN-CU-04 | D7 (recetas en la exportación de C-18) |
| RN-CU-02, RN-CU-05 | No aplica (C-18) |

Reglas duras aplicadas: 4, 7, 9, 10, 12 (credencial solo env backend, `SecretStr`, enmascarada), 14 (recetas de demo con datos sintéticos y marcadas simuladas), 15 (documento inmutable), 16, 17 (receta solo vía partner ReNaPDiS).

Compact rules del registry aplicadas: `context7-mcp` (docs vigentes de pydantic-settings y FastAPI), `auth-implementation-patterns` (AuthZ en servidor; secreto solo en env/vault; 501 sin partner), `event-store-design` (receta append-only), `docker-testcontainers`.

## Goals / Non-Goals

**Goals:**

- Que el dominio no conozca a ningún partner concreto: cambiar de partner = agregar un adapter + un valor de `RECETAS_PARTNER`.
- Que todo el flujo (RBAC, validación, idempotencia, auditoría, exportación, errores del partner) quede probado con el adapter simulado, sin red.
- Que ningún error de configuración de recetas impida arrancar la app.

**Non-Goals (de diseño):**

- Definir el contrato HTTP de un partner real (se hace con su documentación cuando se resuelva PA-08).
- Reintentos automáticos o colas: el reintento lo decide el usuario ante un `502`.

## Decisions

### D1 — Puerto y adapters (`backend/app/infrastructure/recetas/`)

- `partner_client.py`: `PartnerRecetas` (`Protocol`) con `nombre: str`, `simulado: bool` y `emitir(solicitud: SolicitudPartner) -> EmisionPartner`. `SolicitudPartner` (dataclass inmutable) lleva `tipo`, `clave_idempotencia`, paciente (nombre, apellido, DNI, obra social/plan/afiliado), profesional (nombre, matrícula), diagnóstico e ítems. `EmisionPartner`: `id_externo`, `pdf_url`. Errores tipados: `PartnerNoDisponible` (timeout/5xx/conexión) y `PartnerRechazo(motivo)`.
- `fake.py`: `FakePartner` determinista. `id_externo = "FAKE-" + uuid5(clave_idempotencia)` (misma clave → mismo id, como haría un partner con idempotencia), `pdf_url = "https://partner-simulado.invalid/recetas/<id>.pdf"` (TLD `.invalid` reservado por RFC 2606: nunca resuelve). Hooks para tests: `fallar_con(PartnerNoDisponible | PartnerRechazo)` y registro de solicitudes recibidas (para afirmar "una sola emisión" y "datos tomados de la base").
- `factory.py`: `obtener_partner(settings) -> PartnerRecetas | NoConfigurado`:
  - `RECETAS_PARTNER` vacío/ausente → `NoConfigurado("Configurá RECETAS_PARTNER …")`;
  - `fake` con `ENTORNO = produccion` → `NoConfigurado("El partner simulado está deshabilitado en producción")` + log `WARNING`;
  - `fake` en otro entorno → `FakePartner` (singleton por proceso);
  - valor desconocido → `NoConfigurado` + log `WARNING` (nunca excepción en el boot).
  - Un partner real futuro que requiera credencial y no la tenga → `NoConfigurado("Falta RECETAS_PARTNER_KEY")`.
- Dependencia FastAPI `partner_recetas()` en `backend/app/api/recetas.py` que llama a la factory y, si es `NoConfigurado`, levanta `PartnerNoConfigurado` (501). Los tests la reemplazan con `app.dependency_overrides` (Context7 #2).
- Alternativa descartada: implementar ya un adapter HTTP genérico. Sin la documentación del partner sería un contrato inventado que habría que reescribir.

### D2 — Settings

Campos nuevos en `Settings`:

- `recetas_partner: str = ""` (normalizado a minúsculas y sin espacios);
- `recetas_partner_key: SecretStr | None = None` con validador `mode="before"` que convierte `""` en `None` (Context7 #1: una clave vacía en el dotenv es un valor, no una ausencia). `SecretStr` se enmascara en `repr`/logs; solo el adapter real llamará `get_secret_value()`;
- `entorno: Literal["desarrollo", "test", "demo", "produccion"] = "produccion"`: default **seguro** (si producción olvida definirlo, el simulado igual queda bloqueado).

`backend/.env.example` suma `RECETAS_PARTNER=fake` y `ENTORNO=desarrollo` (placeholders de desarrollo/demo), y `test_env_example.py` los exige. No se agrega ninguna variable `VITE_`.

### D3 — Tabla `receta_externa` (migración 010)

- Columnas: `id`, `clinica_id`, `paciente_id`, `evolucion_id` NOT NULL, `tipo` TEXT CHECK IN (`receta`,`orden_estudio`), `partner` TEXT NOT NULL, `simulada` BOOLEAN NOT NULL, `id_externo` TEXT NOT NULL, `pdf_url` TEXT NOT NULL (CHECK `pdf_url ~ '^https://'`), `diagnostico` TEXT CHECK 1..500, `items` JSONB NOT NULL CHECK `jsonb_typeof(items) = 'array'`, `clave_idempotencia` UUID NOT NULL, `huella_solicitud` CHAR(64) (SHA-256 del contenido canónico, para el 409 de "misma clave con otro contenido"), `autor_usuario_id`, `profesional_id`, `emitida_en` TIMESTAMPTZ DEFAULT `now()`.
- Restricciones:
  - FK `(clinica_id, paciente_id, evolucion_id) → evolucion(clinica_id, paciente_id, id)` (usa `uq_evolucion_clinica_paciente_id` de la 008): la base impide vincular una evolución de otro paciente u otra clínica;
  - FKs `(clinica_id, paciente_id) → paciente`, `(clinica_id, autor_usuario_id) → usuario`, `(clinica_id, profesional_id) → profesional`;
  - `UNIQUE (clinica_id, clave_idempotencia)` y `UNIQUE (clinica_id, partner, id_externo)`;
  - índice `(clinica_id, paciente_id, id DESC)`.
- Triggers `fn_rechazar_mutacion()` (fila + TRUNCATE). No hay estado mutable: una anulación futura será otra fila/tabla.
- `pdf_path` de `CHANGES.md` → se guarda el **enlace** del partner (`pdf_url`), no el binario (DT-4).

### D4 — Servicio y orden de respuestas

`POST /api/pacientes/{id}/recetas` (router `backend/app/api/recetas.py`, tag `recetas`):

1. 401 → 403 rol (solo odontólogo) → 404 paciente ajeno → 403 vínculo → 403 `consentimiento_datos` (todo vía `paciente_escritura`).
2. `partner_recetas()` → 501 si no está configurado. Va **después** del gate clínico y **antes** del cuerpo: FastAPI resuelve las dependencias antes de validar el body, así que el usuario no completa una receta que no se puede emitir.
3. 422 de cuerpo (`RecetaIn`, `extra='forbid'`: `tipo`, `evolucion_id`, `diagnostico`, `items` 1..10 con forma según `tipo` vía unión discriminada, `clave_idempotencia: UUID`).
4. Idempotencia: buscar `(clinica_id, clave_idempotencia)`; si existe y la `huella_solicitud` coincide → 200 con la existente; si no coincide → `ClaveIdempotenciaReutilizada` 409.
5. Negocio: `profesional_de_usuario` → `None` → `AutorProfesionalRequerido` (422, reutilizado de C-09); evolución inexistente/de otro paciente → `EvolucionNoValidaParaReceta` 422; `autor_usuario_id ≠ auth.sub` → mismo error con mensaje "evolución propia".
6. Llamada al partner **fuera de cualquier transacción abierta con locks** (se hace después de los SELECT y antes del INSERT): `PartnerNoDisponible` → 502 `{"reintentable": true}`; `PartnerRechazo` → 422 con el motivo saneado (se reemplaza cualquier ocurrencia de la credencial por `***` y se trunca a 300 caracteres).
7. INSERT + evento `crear` (entidad `receta`) + commit → 201. Si el INSERT viola el UNIQUE de la clave (carrera entre dos requests con la misma clave) → rollback, releer la fila ganadora y devolver 200 con ella (el partner deduplica por la misma clave; el `FakePartner` devuelve el mismo `id_externo`).

`GET /{id}/recetas` y `GET /{id}/recetas/{rid}` usan `paciente_lectura` (admin + odontólogo), **no** dependen del partner, paginación keyset y evento `leer`. Sin PUT/PATCH/DELETE (test sobre `app.routes`).

Errores en `backend/app/domain/recetas/errores.py` como subclases de `PacienteError`: `PartnerNoConfigurado` 501, `PartnerCaido` 502, `PartnerRechazoError` 422, `EvolucionNoValidaParaReceta` 422, `ClaveIdempotenciaReutilizada` 409, `RecetaNoEncontrada` 404.

### D5 — Auditoría

`ENTIDADES += ("receta",)` (la acción `crear`/`leer` ya existe). La 010 reemplaza los CHECK de `auditoria_hc` partiendo del conjunto de la 009. Allowlist del writer: `receta_id` (int), `evolucion_id` (ya existe en C-09), `partner` (str). Nunca ítems, diagnóstico ni `id_externo`.

### D6 — Migración `010_recetas_externas`

- `revision = "010_recetas_externas"`, `down_revision = "009_consentimientos_cumplimiento"`.
- Si C-05c (`007_sobreturno_huecos`) mergea, se re-encadena en la 008 (C-09 D7); la 010 no cambia. Antes de mergear, `cd backend && alembic heads` → **un único head**.
- Downgrade: restaura los CHECK de la 009, borra triggers y tabla; no borra `fn_rechazar_mutacion()`. Con eventos `receta` ya registrados, restaurar el CHECK falla a propósito (roll-forward, documentado en el docstring).

### D7 — Recetas en la exportación de C-18

Se agrega `recetas` al registro `ENTIDADES_EXPORTABLES` (todas las columnas de `receta_externa` filtradas por `clinica_id`; `items` como JSON). No hay columnas secretas en la tabla. El test de aislamiento de C-18 se extiende con recetas en ambas clínicas.

### D8 — Evidencia de Context7 (MCP) y qué se adoptó

Consultas hechas el 2026-11-16, sin secretos, datos de pacientes ni código privado:

1. `resolve-library-id("pydantic-settings")` → `/pydantic/pydantic-settings`. `query-docs`: "BaseSettings field of type SecretStr | None with default None loaded from environment variable, get_secret_value, and how extra='forbid' treats unknown keys in the dotenv file".
   - Respuesta: con `extra='forbid'`, las entradas del dotenv que no coinciden con un campo (incluso asignaciones vacías como `OTHER_TOOL_KEY=`) levantan `extra_forbidden`; las variables de entorno del proceso que no coinciden se ignoran. `env_ignore_empty=True` ignora valores vacíos para todos los campos. Los defaults de `BaseSettings` se validan (`validate_default=True`).
   - **Adoptado:** declarar `recetas_partner`, `recetas_partner_key` y `entorno` en `Settings` (si no, un `.env` copiado del ejemplo falla); validador local `"" → None` para la credencial en lugar de `env_ignore_empty=True` global (no cambiar el comportamiento de los demás campos); `entorno` con default `produccion`, que se valida igual.
2. `query-docs` sobre `/websites/fastapi_tiangolo`: "Testing dependencies with app.dependency_overrides to replace an external service client dependency in tests, and resetting overrides".
   - Respuesta: `app.dependency_overrides[original] = override` reemplaza la dependencia donde se use (ruta, decorador o router); se resetea con `app.dependency_overrides = {}`.
   - **Adoptado:** el partner se inyecta con la dependencia `partner_recetas()`; los tests la reemplazan por un `FakePartner` configurado (o por una que levanta `PartnerNoConfigurado`) y limpian los overrides en el teardown del fixture. El camino real de la factory se prueba aparte con settings construidos a mano.

En el apply, registrar esta evidencia en `docs/skills-mcp/evidencias/README.md` (task 6.3).

## Decisiones tomadas (aprobación delegada del usuario, 2026-11-16)

El usuario aprobó de antemano proponer, implementar y archivar C-19 (governance ALTO):

| # | Pregunta | Opciones | Elegida | Por qué |
|---|---|---|---|---|
| DT-1 | ¿Desarrollo/demo usan el partner simulado? | (a) sí, con `RECETAS_PARTNER=fake` en `.env.example`, bloqueado en producción; (b) no, siempre 501 hasta tener partner | **(a)** | Permite demostrar y probar el flujo completo sin red ni secretos. Las recetas simuladas quedan marcadas (`simulada`, `FAKE-`, URL `.invalid`), así no pueden confundirse con recetas válidas. |
| DT-2 | ¿Cómo se sabe que es producción? | (a) nueva variable `ENTORNO` con default `produccion`; (b) inferirlo de `APP_BASE_URL`; (c) sin guarda | **(a)** | Explícito y fail-safe: si falta, se asume producción y el simulado queda bloqueado. (b) es frágil (una demo en https quedaría bloqueada). |
| DT-3 | ¿Qué pasa con un valor inválido de `RECETAS_PARTNER`? | (a) 501 + warning, boot OK; (b) el boot falla | **(a)** | El constraint de C-19: la configuración de recetas no puede tumbar el sistema. |
| DT-4 | ¿Se guarda el PDF del partner? | (a) solo el enlace `pdf_url`; (b) descargar y guardar el binario | **(a)** | El partner es la fuente legal y el PDF incluye su verificación; guardar copias suma almacenamiento sensible sin valor legal adicional. Reevaluar con el partner real. |
| DT-5 | ¿A qué evolución se vincula? | (a) evolución existente del paciente escrita por el mismo odontólogo; (b) cualquier evolución del paciente; (c) opcional | **(a)** | `CHANGES.md` exige `evolucion_id`; la prescripción es un acto del profesional que atiende y queda trazable a su propia nota (Ley 26.529). Corregidas se aceptan: la cadena es visible. |
| DT-6 | ¿Cómo evitar recetas duplicadas por doble clic o reintento? | (a) `clave_idempotencia` obligatoria + huella del contenido; (b) sin idempotencia | **(a)** | Una receta duplicada en el partner es un problema legal y de dispensa; el `502` reintentable lo hace imprescindible. |
| DT-7 | ¿Quién emite y quién lee? | (a) emite solo odontólogo; leen admin y odontólogo; recepción 403; (b) admin también emite | **(a)** | Matriz RBAC (`03`): escritura clínica solo odontólogo; regla 16. |
| DT-8 | ¿Ítems y forma de la receta? | (a) 1..10 medicamentos por nombre genérico (Ley 25.649) / 1..10 estudios, validados localmente y el partner valida el resto; (b) catálogo de medicamentos | **(a)** | No hay vademécum en el sistema ni en la KB; el límite 10 es técnico, no legal (el partner aplica el suyo y su rechazo vuelve como 422). |

## Risks / Trade-offs

- [El contrato real del partner no encaja con el puerto] → El puerto es mínimo (emitir → id + enlace) y los datos enviados son los que cualquier receta requiere; ajustar `SolicitudPartner` es aditivo.
- [Alguien configura `fake` en producción] → Default `ENTORNO=produccion` + guarda en la factory + marcas visibles en cada receta simulada + test del caso.
- [Partner emite pero nuestra transacción falla después] → El partner deduplica por `clave_idempotencia`; el reintento del usuario con la misma clave recupera el mismo `id_externo` y lo guarda. Se loguea el `id_externo` (sin datos clínicos) cuando el INSERT falla.
- [La llamada al partner bloquea un worker] → Endpoint sincrónico en threadpool; el adapter real tendrá timeout corto (configurable en ese change).
- [C-09 y C-18 aún no mergearon] → La 010 depende de la 009 y de `uq_evolucion_clinica_paciente_id`; el apply de C-19 arranca después de C-18.

## Migration Plan

1. `010_recetas_externas` sobre `009_consentimientos_cumplimiento`. Tabla nueva; sin backfill.
2. Antes de mergear: `cd backend && alembic heads` → un único head.
3. Despliegue: en producción no definir `RECETAS_PARTNER` hasta tener partner (la emisión responde 501); `ENTORNO=produccion` explícito.
4. Rollback de la aplicación: quitar el router; la tabla queda inerte e inmutable. Rollback de esquema solo sin recetas emitidas (D6).

## Open Questions

- Timeout y política de reintentos del adapter real: se fijan con la documentación del partner (no cambia specs: el 502 reintentable ya está especificado).
- Alcance de órdenes de estudios por partner (PA-08): si el partner elegido no las soporta, su adapter responde `PartnerRechazo` (422) para ese tipo.
