# Evidencias de uso — skill propia y MCP

Cada evidencia registra: pedido realizado, resultado obtenido y qué aportó al change. Todas las fechas son de 2026-11-16.

## E1 — Uso de `skill-creator` para crear la skill propia

- **Pedido** (Claude Code, sesión de Matheo): *"Crear una skill de proyecto llamada crear-skill-de-dominio para el repo Turnos Odontología: genera skills dominio-<área> desde knowledge-base/05 (RN), filtradas por DD vigentes de 09, reglas duras de AGENTS.md y trazabilidad RN → spec → test."* Se invocó la skill `anthropic-skills:skill-creator`.
- **Qué tomamos de skill-creator:**
  - la anatomía de una skill: frontmatter `name` + `description` y cuerpo con instrucciones;
  - la `description` "insistente", que dice qué hace y cuándo usarla, porque es lo único que el agente lee para decidir;
  - recursos agrupados: `templates/` y `scripts/`;
  - casos de prueba en el formato `evals/<caso>/{prompt.md, case.yaml, graders/}`;
  - la prueba de activación.
- **Qué adaptamos al dominio:** las 6 secciones de la propuesta (propósito, activación, entradas, procedimiento, resultado, criterios de revisión), el filtro por DD vigentes, las reglas duras, la trazabilidad por significado y el registro en los 3 índices del repo.
- **Resultado:**
  - `.claude/skills/crear-skill-de-dominio/SKILL.md`
  - `templates/dominio-template.md`
  - `scripts/verificar.py`
  - `evals/genera-dominio-agenda/`, `evals/genera-dominio-caja/` (solo en `.claude/`, son de desarrollo)

## E2 — Ejecución de `crear-skill-de-dominio` (genera `dominio-agenda` y `dominio-caja`)

- **Pedidos** (los mismos de los casos de prueba de E1):
  1. *"Creá la skill del dominio agenda para el repo, con las reglas RN-AG y RN-TU…"*
  2. *"necesito que armes la skill de caja antes de proponer C-12 (seña, cobros, mercado pago)"*
- **Resultado:**
  - `.claude/skills/dominio-agenda/SKILL.md`: 10 reglas, 3 cubiertas, 4 parciales, 3 pendientes.
  - `.claude/skills/dominio-caja/SKILL.md`: 3 reglas, 0 cubiertas, 1 parcial, 2 pendientes.
  - Copias idénticas en `.github/skills/` y `.opencode/skills/`.
- **Verificación de los criterios de revisión:** [verificacion-criterios.txt](verificacion-criterios.txt). Las dos skills dan `RESULTADO: OK`. La tercera corrida es un control negativo a propósito: pedir RN-AF sobre `dominio-caja` debe fallar, y falla, lo que demuestra que el script detecta filas faltantes.
- **Calificación de los casos de prueba de skill-creator** (`evals/*/graders/`):

| Caso | Aserción | Resultado | Evidencia |
|---|---|---|---|
| genera-dominio-agenda | 10 filas RN-AG-01..06 + RN-TU-01..04 | ✅ | verificar.py [1]: 6/6 y 4/4 |
| genera-dominio-agenda | RN-TU-02 reescrita según DD-10 y listada en Conflictos | ✅ | Sección 3 (⚠️) y "Conflictos detectados" |
| genera-dominio-agenda | RN-AG-01 cita appointments/spec.md y un test real | ✅ | Fila RN-AG-01 + verificar.py [3]: 20 rutas, 0 inexistentes |
| genera-dominio-agenda | Toda ruta citada existe | ✅ | verificar.py [3] |
| genera-dominio-agenda | Registrada en AGENTS.md, CLAUDE.md, registry; AGENTS = CLAUDE | ✅ | verificar.py [5] |
| genera-dominio-caja | 3 filas RN-CA | ✅ | verificar.py [1]: 3/3 |
| genera-dominio-caja | Sin trazabilidad inventada | ✅ | Única celda llena (RN-CA-03) verificada: `require_anulacion_caja` + `test_anulacion_caja_solo_admin` existen y comprueban el permiso |
| genera-dominio-caja | Description con caja, seña, cobro, Mercado Pago | ✅ | verificar.py [4] |
| genera-dominio-caja | Incluye regla dura 7 (NUMERIC) | ✅ | Sección 3 |

  Limitación: los casos se ejecutaron en esta sesión, que ya tenía el contexto. No hubo corridas aisladas con subagentes ni comparación contra una corrida sin skill (baseline). Las mismas carpetas `evals/` se pueden correr con `claude plugin eval .` desde `.claude/skills/crear-skill-de-dominio/` (son corridas reales, se facturan).
- **Aporte al change:** `dominio-agenda` muestra que RN-TU-01 está **parcial** (solo el estado inicial `reservado` y el CHECK de estados). Eso define el alcance de C-05b: transiciones explícitas y auditadas.

## E3 — Prueba de activación (¿el agente encuentra y usa las skills solo?)

- **Procedimiento:** 9 consultas reales con `claude -p` en la raíz del repo (`--permission-mode plan --max-turns 2`, sin acceso a escribir). Se registró qué skill invocó el modelo. Script: [activacion.py](activacion.py) · casos: [activacion-casos.json](activacion-casos.json) · resultado crudo: [activacion-resultado.json](activacion-resultado.json).
- **Resultado: 9/9 correctos.** Las 6 consultas que debían activar una skill la activaron, sin nombrarla. Las 3 de "casi coincidencia" (validador de CUIT, índice de pacientes, explicar `openspec-propose`) no activaron ninguna.
- **Observación:** en *"antes de hacer /opsx:propose de C-15 whatsapp necesito una skill con las reglas RN-WA…"* el modelo cargó `crear-skill-de-dominio` (correcto) y además `dominio-caja`, probablemente como ejemplo de skill ya generada. No es un error de la skill creadora, pero muestra que una skill de dominio puede cargarse fuera de su área. Ver `aplicacion.md` §Revisión crítica.
- **Problema de compatibilidad:** el script de skill-creator para esta prueba (`scripts/run_eval.py`) usa `select.select()` sobre un pipe, y eso no funciona en Windows (solo acepta sockets). Por eso se escribió `activacion.py`, que espera el fin de cada proceso en lugar de leer el stream.

## E4 — Herramienta real del MCP Context7 (preparación de C-05b)

- **Conexión:** después de agregar `.mcp.json` y reiniciar Claude Code, la sesión expone `mcp__context7__resolve-library-id` y `mcp__context7__query-docs`. Desde otra terminal, `claude mcp list` mostraba `context7: https://mcp.context7.com/mcp (HTTP) - ⏸ Pending approval`: la aprobación es por sesión interactiva. Ver troubleshooting en `README.md`.
- **Pedido 1, `resolve-library-id`:** `libraryName: "SQLAlchemy"`, `query: "Lock a row with SELECT ... FOR UPDATE (with_for_update) in SQLAlchemy 2.0 ORM to serialize concurrent state transitions"`.
  - **Resultado:** 5 bibliotecas. Se eligió `/websites/sqlalchemy_en_20_orm` (SQLAlchemy ORM 2.0, 6228 snippets, reputación High, benchmark 78.29) por coincidir con la versión 2.0 que usa el backend.
- **Pedido 2, `query-docs`:** `libraryId: "/websites/sqlalchemy_en_20_orm"`, `query: "select().with_for_update() to lock a single ORM row before updating its state, and session.get with with_for_update; behavior with PostgreSQL when another transaction holds the lock (nowait, skip_locked)"`, `language: "Python"`.
  - **Resultado (extracto):** firma `with_for_update(*, nowait=False, read=False, of=None, skip_locked=False, key_share=False)`; `Session.get(..., with_for_update=...)`; y el patrón "Use Query.with_for_update() with populate_existing()": *"Combining with populate_existing() forces all data read from the SELECT to be populated into the ORM objects returned, even if they are already in the identity map."* Fuente citada: https://docs.sqlalchemy.org/en/20/orm/queryguide/query.html
- **Aporte al change:** decisión **D5** de `openspec/changes/archive/2026-11-16-transiciones-estado-turno/design.md`.
  - Usar `with_for_update()` + `populate_existing` para serializar transiciones concurrentes.
  - Descartar `nowait`/`skip_locked`, que darían error u omitirían la fila ante cualquier contención.
  - Base del escenario borde "Dos cancelaciones simultáneas" de la spec y de la tarea 4.4.
- **Revisión del resultado:** la doc devuelta usa la API `Query` (1.x/legacy) en los ejemplos. El backend usa `select()` 2.0, así que se tradujo a `select(Turno)…with_for_update().execution_options(populate_existing=True)`. La firma de `with_for_update` es la misma en `GenerativeSelect` según el propio extracto ("identical to that of `GenerativeSelect.with_for_update()`").

## E5 — Uso de `dominio-agenda` en la preparación de C-05b

- **Pedido:** se invocó la skill `dominio-agenda` con *"Preparar C-05b transiciones-estado-turno (máquina de estados RN-TU-01)"*.
- **Resultado y aporte:**
  - La matriz marcaba RN-TU-01 como **parcial** (solo estado inicial + CHECK), lo que definió el alcance.
  - La sección 4 indicó qué reutilizar (`turnos.py`, `ESTADOS_ACTIVOS`, el predicado activo que ya libera el hueco) y los códigos HTTP del área.
  - Los supuestos abiertos (SU-04) llevaron a usar el reloj inyectable y no constantes.
- **Reglas ambiguas detectadas** al contrastar RN-TU-01 con los flujos 2 y 5 y la matriz de `03`. Las resolvió el usuario y quedaron justificadas en `design.md` D1–D3:
  1. ¿`reservado → asistido | ausente` sin confirmar?
  2. ¿El odontólogo puede marcar asistencia?
  3. ¿Se puede marcar ausente antes de la hora?
- **Artefactos:** `openspec/changes/archive/2026-11-16-transiciones-estado-turno/{proposal,design,tasks}.md` + `specs/appointments/spec.md`. Son 8 requisitos y 18 escenarios: felices, de error de negocio y de borde. `openspec validate transiciones-estado-turno --strict` → *"Change 'transiciones-estado-turno' is valid"*.

## E6 — Context7 en la preparación de C-05c (huecos con multirangos de PostgreSQL)

- **Pedido 1, `resolve-library-id`:** `libraryName: "PostgreSQL"`, `query: "Compute free time slots: subtract booked tstzrange intervals from a window using multirange (range_agg, multirange difference operator) in PostgreSQL 16"`.
  - **Resultado:** `/websites/postgresql` (reputación High, benchmark 80.26, versiones 13–19). Se usó la versión `/websites/postgresql/16`, que coincide con `postgres:16-alpine`.
- **Pedido 2, `query-docs`:** `libraryId: "/websites/postgresql/16"`, `query: "range_agg aggregate returning multirange, multirange difference operator (-) and unnest(multirange) to list free sub-ranges of a tstzrange window"`.
  - **Resultado (extracto):** `range_agg(anyrange) → anymultirange` ("Computes the union of the non-null input values"); `anymultirange - anymultirange` ("`'{[5,20)}' - '{[10,15)}'` → `{[5,10), [15,20)}`"); `unnest(anymultirange) → setof anyrange`. Y la advertencia: *"The range union and difference operators will fail if the resulting range would need to contain two disjoint sub-ranges [...] you can avoid errors by first casting your ranges to multiranges."*
- **Aporte al change:** decisión **D5** de `openspec/changes/huecos-y-sobreturnos/design.md`. Los huecos se calculan en una sola consulta (`ventana - range_agg(ocupados)` por profesional y por sillón), casteando a `tstzmultirange` para no fallar con huecos disjuntos. Se descartó recorrer minuto a minuto en Python.

## E7 — Context7 y `dominio-clinica` en C-09 (odontograma JSONB y migración 008)

- **Pedido 1, `resolve-library-id` + `query-docs`:** `SQLAlchemy` → `/websites/sqlalchemy_en`; consulta: *"PostgreSQL JSONB type: mapped_column(JSONB), comparator contains (@>) and has_key operators, and mutation tracking with MutableDict"*.
  - **Resultado (extracto):** `JSONB` agrega `Comparator.contains()` (`@>`), `has_key()`, `path_exists()` (`@?`) y `path_match()` (`@@`). Además, *"like JSON, JSONB does not detect in-place changes when used with the ORM, unless the `sqlalchemy.ext.mutable` extension is used"*.
  - **Impacto en el modelo:** `Odontograma.piezas` es `JSONB` con `server_default '{}'::jsonb` y **sin** `MutableDict` (`backend/app/domain/clinica/models.py`). Que el ORM no detecte mutaciones in-place es coherente con la inmutabilidad: un `piezas` cargado y mutado por accidente nunca emite UPDATE (y el trigger lo rechazaría igual). Las consultas de recall futuras usarán `.contains()` / `.path_exists()`.
- **Pedido 2, `resolve-library-id` + `query-docs`:** `Alembic` → `/websites/alembic_sqlalchemy_en`; consulta: *"op.create_index with postgresql_using='gin' and postgresql_ops jsonb_path_ops on a JSONB column, and op.create_check_constraint"*.
  - **Resultado (extracto):** `create_index` acepta kwargs de dialecto `<dialect>_<arg>` y `create_check_constraint(name, table, condition)` acepta la condición como string.
  - **Impacto en la migración:** `backend/alembic/versions/008_odontograma_evolucion.py` crea `ix_odontograma_piezas_gin` con `postgresql_using="gin"` + `postgresql_ops={"piezas": "jsonb_path_ops"}` y amplía los CHECK de `auditoria_hc` con `drop_constraint(op.f(...))` + `create_check_constraint`. `test_migracion_008.py` verifica el índice (`USING gin (piezas jsonb_path_ops)`) y el nombre real de los CHECK en `pg_constraint`.
- **`dominio-clinica`:** leída antes del propose y del apply. Aporta las RN-CL-01/02/03, el patrón de reutilizar `fn_rechazar_mutacion()` y el orden 401 → 403 → 404 → 403 → 403 → 422 de las rutas clínicas. Al archivar se actualizó su matriz RN → spec → test (RN-CL-01, 02 y 03 pasan a `cubierta`).
- **Change:** `openspec/changes/archive/2026-11-17-odontograma-evolucion/` (`design.md` D8, `verify.md`).

## E8 — Context7 y `dominio-cumplimiento` en C-18 (exportación ZIP y descarga)

- **Pedido 1, `resolve-library-id` + `query-docs`:** `FastAPI` → `/websites/fastapi_tiangolo`; consulta: *"StreamingResponse with a file-like object or generator yielding chunks, media_type application/zip and Content-Disposition attachment header; sync generator runs in threadpool"*.
  - **Resultado (extracto):** `StreamingResponse(content, status_code, headers, media_type, background)`; si `content` no es un async iterable se usa `iterate_in_threadpool(content)`. Para file-like objects bloqueantes, declarar la operación con `def` para que corra en el threadpool.
  - **Impacto en el código:** `GET /api/admin/exportacion` es un endpoint `def` (`backend/app/api/admin_cumplimiento.py`); el generador de chunks es **sincrónico** y cierra el archivo temporal en su `finally`; `Content-Disposition: attachment` explícito.
- **Pedido 2, `resolve-library-id` + `query-docs`:** `Python` → `/python/cpython`; consulta: *"zipfile.ZipFile open(name, mode='w') to write an entry incrementally, behavior when the underlying file object is not seekable, and ZIP_DEFLATED"*.
  - **Resultado (extracto):** `ZipFile` detecta si el archivo es seekable; si no, escribe con descriptores de datos. `open(name, "w")` devuelve un handle escribible y mientras está abierto no se puede escribir otra entrada. `ZIP_DEFLATED` requiere `zlib`.
  - **Impacto en el código:** `backend/app/domain/cumplimiento/exportador.py` arma el ZIP en un `SpooledTemporaryFile` (seekable, ZIP estándar compatible con cualquier descompresor) con `ZIP_DEFLATED` y escribe un CSV por vez con `zf.open(..., "w")`.
- **`dominio-cumplimiento`:** leída antes del propose y del apply. Aporta RN-CU-01/02/04/05, las reglas duras 4, 7, 10, 14, 15 y 16 aplicadas a consentimientos, el patrón de documento + constancia append-only y el orden 401 → 403 → 404 → 403 → 403 → 422 de las rutas. Al terminar se actualizó su matriz RN → spec → test.
- **Change:** `openspec/changes/archive/2026-11-17-consentimientos-cumplimiento/` (`design.md` D9, `verify.md`).

## E9 — Context7 y `dominio-cumplimiento` en C-19 (partner de recetas, settings y overrides)

- **Pedido 1, `resolve-library-id` + `query-docs`:** `pydantic-settings` → `/pydantic/pydantic-settings`; consulta: *"BaseSettings field of type SecretStr | None with default None loaded from environment variable, get_secret_value, and how extra='forbid' treats unknown keys in the dotenv file"*.
  - **Resultado (extracto):** con `extra='forbid'`, las entradas del dotenv sin campo declarado (incluso asignaciones vacías) levantan `extra_forbidden`; las variables del proceso desconocidas se ignoran. `env_ignore_empty=True` ignora valores vacíos en todos los campos.
  - **Impacto en el código:** `backend/app/infrastructure/settings.py` declara `recetas_partner`, `recetas_partner_key` (`SecretStr | None`, enmascarada en `repr`) y `entorno` (default `produccion`); un validador local convierte `RECETAS_PARTNER_KEY=` vacía en `None` en lugar de `env_ignore_empty` global. Tests en `backend/tests/test_settings.py` (dotenv temporal con la clave vacía).
- **Pedido 2, `query-docs`:** `FastAPI` → `/websites/fastapi_tiangolo`; consulta: *"Testing dependencies with app.dependency_overrides to replace an external service client dependency in tests, and resetting overrides"*.
  - **Resultado (extracto):** `app.dependency_overrides[original] = override` reemplaza la dependencia donde se use; se resetea con `app.dependency_overrides = {}`.
  - **Impacto en el código:** el partner se inyecta con `partner_recetas()` (`backend/app/api/recetas.py`); los tests la reemplazan por un `FakePartner` (helper `con_partner` en `backend/tests/integration/conftest.py`) y el camino real de la factory se prueba con variables de entorno.
- **`dominio-cumplimiento`:** leída antes del propose y del apply. Aporta RN-CU-03 y RN-CU-01, las reglas duras 4, 7, 9, 10, 12, 14, 15, 16 y 17, el patrón de tabla append-only con auditoría en `auditoria_hc` y el puerto + adapter `fake`. Al terminar se actualizó su matriz (RN-CU-03 pasa a `cubierta`).
- **Change:** `openspec/changes/archive/2026-11-17-recetas-partner-renapdis/` (`design.md` D8, `verify.md`).

