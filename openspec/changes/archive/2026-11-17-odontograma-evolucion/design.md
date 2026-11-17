# Design — odontograma-evolucion (C-09)

## Context

Motivación: ver `proposal.md` §Why. Requisitos: ver `specs/odontogram`, `specs/clinical-evolutions` y los deltas de `clinical-record`, `clinical-audit` y `access-control`.

Estado actual observado en el código (C-08, archivado):

- `backend/alembic/versions/004_pacientes_ficha.py`:
  - tablas `paciente` (con `uq_paciente_clinica_id`), `ficha_version`, `adjunto` (`evolucion_id BIGINT NULL` **sin FK**) y `auditoria_hc`;
  - función `fn_rechazar_mutacion()` y triggers append-only por fila (UPDATE/DELETE) y por sentencia (TRUNCATE);
  - CHECKs de `auditoria_hc`: `entidad IN ('paciente','ficha','adjunto')` y `accion IN ('crear','actualizar','leer','descargar','consentimiento_*')`.
- `backend/app/domain/auditoria/writer.py`: `registrar_evento(...)` en la sesión del llamador, con validación de `accion`/`entidad` contra `ACCIONES`/`ENTIDADES` (`models.py`) y un diff con allowlist (`campos`, `version`, ids, `consentimiento_datos`).
- `backend/app/api/pacientes.py`:
  - dependencias `paciente_lectura` (`require_clinico()` + `require_vinculo_paciente`) y `paciente_escritura` (`require_clinico_escritura()` + vínculo + consentimiento → 403 antes del payload);
  - patrón de ficha versionada con `version_esperada` y `UNIQUE` → 409;
  - lecturas auditadas con commit propio.
- `backend/app/api/permissions.py`: el vínculo odontólogo–paciente sigue con la **regla interina** (`main.py` llama `set_resolver_vinculo_paciente(None)`).
- `backend/app/domain/agenda/servicio.py`: `profesional_de_usuario(session, usuario_id)` devuelve el profesional activo vinculado al login (C-04). Solo se **importa**: no es un archivo reservado de agenda y no se modifica.
- `PacienteError` (con `status_code`) ya tiene handler en `create_app()`.
- Convención de nombres de constraints (`backend/app/infrastructure/persistence/base.py`): `ck_%(table_name)s_%(constraint_name)s`.

Skill de dominio usada: **`dominio-clinica`** (generada el 2026-11-16 con `crear-skill-de-dominio`, verificada con `verificar.py` → `RESULTADO: OK`). Mapeo de reglas:

| Regla | Dónde la toma este change |
|---|---|
| RN-CL-01 | D3, D4 (autor = usuario + profesional vinculado; hora del servidor; sin profesional → 422) |
| RN-CL-02 | D1, D4, D5 (snapshots y evoluciones append-only, corrección encadenada, triggers, auditoría) |
| RN-CL-03 | D2 (FDI permanente 32 + temporal 20; mixta como unión; mixta fina y BOP en F2) |
| RN-CL-04 | Solo prepara: índice GIN para el recall de C-11/C-14 (D2). No implementa recall. |
| RN-CL-05 | No cambia: el vínculo adjunto ↔ evolución queda fuera (Non-goals) |

Reglas duras aplicadas: 4 (`extra='forbid'`), 7 (TIMESTAMPTZ del servidor), 9 (testcontainers), 10 (`clinica_id` + índice + aislamiento), 14 (datos sintéticos), 15 (HC append-only), 16 (consentimiento + RBAC clínico).

Compact rules del registry aplicadas:

- `postgresql-table-design`: BIGINT identity, TEXT + CHECK (no ENUM), TIMESTAMPTZ, FKs indexadas, JSONB con GIN.
- `postgresql-optimization`: GIN + operadores de contención, nunca `::text LIKE`; paginación keyset.
- `event-store-design`: correcciones como filas nuevas con `corrige_a_id`; `AuditoriaHC` sin endpoint de escritura.
- `auth-implementation-patterns`: AuthZ en servidor en cada ruta.
- `docker-testcontainers`: `postgres:16-alpine` y migración up/down.

## Goals / Non-Goals

**Goals:**

- Reutilizar los mecanismos de C-08 (trigger, writer de auditoría, dependencias RBAC, versionado optimista, handler de errores) sin inventar otros nuevos.
- Que la inmutabilidad la garantice la base (triggers + FKs compuestas), no solo la API.
- Validar el odontograma con funciones puras testeables sin DB (`fdi.py` + schemas).

**Non-Goals (de diseño):**

- JSON Schema dentro de PostgreSQL (`pg_jsonschema` no viene en `postgres:16-alpine`). La DB valida solo el tipo raíz.
- Eventos de dominio para recall. Cuando exista C-11/C-14, consultarán el odontograma vigente con `@>`/`@?`.

## Decisions

### D1 — Odontograma como snapshots append-only (tabla `odontograma`)

Cada guardado inserta una **versión completa**. "Odontograma actual" = la versión de mayor número. Es el mismo patrón que `ficha_version` (C-08 D6).

Columnas:

- `id` BIGINT identity, `clinica_id`, `paciente_id`;
- `version` INT CHECK > 0;
- `denticion` TEXT CHECK IN (`permanente`, `temporal`, `mixta`);
- `piezas` JSONB NOT NULL DEFAULT `'{}'`, CHECK `jsonb_typeof(piezas) = 'object'`;
- `autor_usuario_id` BIGINT NOT NULL;
- `created_at` TIMESTAMPTZ DEFAULT `now()`.

Restricciones e índices:

- `UNIQUE (clinica_id, paciente_id, version)`. Resuelve la carrera (23505 → 409) y sirve de índice `(clinica_id, …)` para "vigente" e historial.
- GIN `piezas jsonb_path_ops` (`ix_odontograma_piezas_gin`, ver D8).
- FKs compuestas `(clinica_id, paciente_id) → paciente` y `(clinica_id, autor_usuario_id) → usuario`, `ON DELETE RESTRICT`.
- Triggers con `fn_rechazar_mutacion()`.
- Modelo con `TenantMixin` únicamente, sin `AuditMixin` (no hay update ni soft-delete).

Alternativas descartadas:

- *Fila mutable única + diff en auditoría*: obliga a guardar estados clínicos en `auditoria_hc` (rompe "diff sin PHI") o pierde historia.
- *Una fila por marca (pieza, cara, estado) como evento*: da trazabilidad fina, que la KB declara F2 ("versionado fino"). Multiplica filas y complica reconstruir el estado.

### D2 — Forma del JSONB y validación FDI

`piezas` es un objeto **disperso**, indexado por código FDI como string. Una pieza ausente del objeto significa "sin registro / sana".

```json
{
  "16": {"estado": {"codigo": "corona", "registro": "existente"},
         "caras": {"O": {"codigo": "caries", "registro": "a_realizar"}}},
  "26": {"estado": {"codigo": "extraida", "registro": "existente"}, "caras": {}}
}
```

- Un objeto (no un array) hace imposible duplicar una pieza y permite consultas de contención (`piezas @> '{"16": {"caras": {"O": {"codigo": "caries"}}}}'`) o JSONPath (`piezas @? '$.*.caras.* ? (@.codigo == "caries")'`) para el recall.
- `fdi.py` (puro):
  - `PERMANENTES` = {11–18, 21–28, 31–38, 41–48} (32 piezas);
  - `TEMPORALES` = {51–55, 61–65, 71–75, 81–85} (20 piezas);
  - `piezas_validas(denticion)`: `mixta` = unión de ambos sets;
  - `es_pieza_fdi(n)`: unión, usada por `evolucion.pieza_fdi`.
- Schemas Pydantic (`extra='forbid'` en todos los niveles):
  - `OdontogramaIn(version_esperada ≥ 0, denticion, piezas: dict[str, PiezaIn])`;
  - `PiezaIn(estado: MarcaIn | None, caras: dict[Literal["V","L","M","D","O"], MarcaIn])`;
  - `MarcaIn(codigo, registro: Literal["existente","a_realizar"] = "existente")`;
  - un `model_validator` rechaza:
    - claves que no estén en `piezas_validas(denticion)`;
    - un código de pieza en una cara, o uno de cara en la pieza;
    - una pieza `ausente`/`extraida` con caras;
    - más de 52 piezas.
- Catálogo MVP (constantes en `fdi.py`, ver DC-3):
  - **pieza**: `ausente`, `extraida`, `extraccion_indicada`, `corona`, `endodoncia`, `implante`;
  - **cara**: `caries`, `obturacion`, `sellador`, `fractura`.
- La DB solo garantiza `jsonb_typeof = 'object'`. La estructura la valida el dominio (ver Non-Goals) y la API es el único camino de escritura.

### D3 — Evolución (tabla `evolucion`) con autor profesional

Columnas:

- `id`, `clinica_id`, `paciente_id`;
- `autor_usuario_id` BIGINT NOT NULL;
- `profesional_id` BIGINT NOT NULL;
- `fecha_hora` TIMESTAMPTZ NOT NULL DEFAULT `now()`;
- `texto` TEXT NOT NULL CHECK `length(btrim(texto)) BETWEEN 1 AND 10000`;
- `pieza_fdi` SMALLINT NULL, con CHECK aritmético FDI: `pieza_fdi IS NULL OR (pieza_fdi/10 BETWEEN 1 AND 4 AND pieza_fdi%10 BETWEEN 1 AND 8) OR (pieza_fdi/10 BETWEEN 5 AND 8 AND pieza_fdi%10 BETWEEN 1 AND 5)`;
- `corrige_a_id` BIGINT NULL;
- `motivo_correccion` TEXT NULL;
- CHECK `(corrige_a_id IS NULL) = (motivo_correccion IS NULL)`;
- CHECK `motivo_correccion IS NULL OR length(btrim(motivo_correccion)) BETWEEN 1 AND 500`;
- CHECK `corrige_a_id IS NULL OR corrige_a_id <> id`.

Restricciones e índices:

- `UNIQUE (clinica_id, paciente_id, id)` (`uq_evolucion_clinica_paciente_id`), que habilita la FK propia.
- FK `(clinica_id, paciente_id, corrige_a_id) → evolucion(clinica_id, paciente_id, id)`: la base impide corregir una evolución de otro paciente o de otra clínica. MATCH SIMPLE deja pasar `NULL`.
- FKs `(clinica_id, paciente_id) → paciente`, `(clinica_id, autor_usuario_id) → usuario` y `(clinica_id, profesional_id) → profesional` (usa `uq_profesional_clinica_id` de la 003).
- Índice `(clinica_id, paciente_id, id DESC)` para el listado.
- Índice único parcial `(clinica_id, corrige_a_id) WHERE corrige_a_id IS NOT NULL` (`uq_evolucion_corrige_a`): una sola corrección por evolución (DC-7).
- Triggers append-only.

Resolución del autor en el servicio:

- `profesional_id = profesional_de_usuario(session, auth.sub)`; `None` → `AutorProfesionalRequerido` (422, regla dura 15). La FK compuesta garantiza que el profesional es de la misma clínica.
- El cuerpo `EvolucionIn` (`extra='forbid'`) solo admite `texto`, `pieza_fdi`, `corrige_a_id` y `motivo_correccion`. `autor_usuario_id`, `profesional_id` o `fecha_hora` → 422.
- La hora es `now()` de la DB, nunca del cliente.

### D4 — Corrección encadenada (sin UPDATE)

`POST /evoluciones` con `corrige_a_id`. Orden en el servicio:

1. Cargar la evolución a corregir con `clinica_id` + `paciente_id`. Si no existe → `CorreccionInvalida` (422).
2. Si `autor_usuario_id ≠ auth.sub` → `CorreccionNoAutorizada` (403, DC-7).
3. INSERT + evento `corregir` + commit.
4. Si el INSERT viola `uq_evolucion_corrige_a` (23505) → `EvolucionYaCorregida` (409), que nombra la corrección vigente.

`corregida_por_id` no se guarda: se calcula en la lectura con un `LEFT JOIN evolucion c ON c.corrige_a_id = e.id`, de modo que la original nunca se actualiza. Sin `SELECT … FOR UPDATE`: el índice único resuelve la concurrencia, igual que la ficha en C-08 D6.

### D5 — Auditoría: ampliar `AuditoriaHC`, no crear otra tabla

- `ENTIDADES += ("odontograma", "evolucion")`, `ACCIONES += ("corregir",)`. En la migración: `drop_constraint` + `create_check_constraint` de `ck_auditoria_hc_entidad_valida` y `ck_auditoria_hc_accion_valida`. El test de migración verifica el nombre real en `pg_constraint`.
- Allowlist del writer: `evolucion_id`, `corrige_a_id`, `odontograma_id` (int).
  - Odontograma: `{"odontograma_id", "version", "campos": [códigos FDI cambiados + "denticion" si cambió]}`, sin estados ni caras (DC-8).
  - Evolución: `{"evolucion_id"}` o `{"evolucion_id", "corrige_a_id"}`. El texto y el motivo nunca van al diff.
- Escrituras: el evento va en la misma transacción. Una falla al auditar revierte la escritura.
- Lecturas: commit propio, como C-08.
  - `GET /odontograma/actual` y `/odontograma` → `leer` / `odontograma`;
  - `GET /evoluciones` → `leer` / `evolucion` con `entidad_id = paciente.id`;
  - `GET /evoluciones/{id}` → `leer` / `evolucion` con el id;
  - `GET /historia` → **un solo** evento `leer` / `paciente` con `{"campos": ["ficha","odontograma","evoluciones"]}`. Usa consultas sin auditoría propia (`ficha_vigente_fila` y equivalentes) para no duplicar eventos.

### D6 — API y RBAC

- Router nuevo `backend/app/api/historia_clinica.py` (prefijo `/api/pacientes`, tag `historia-clinica`), registrado en `create_app()`.
- Reutiliza `paciente_lectura` / `paciente_escritura` importados de `backend/app/api/pacientes.py`, sin moverlos (no se reescribe C-08). Orden de respuestas: 401 → 403 de rol → 404 paciente ajeno → 403 de vínculo → 403 de consentimiento (solo escrituras) → 422 de cuerpo → 422/403/409 de negocio → 201/200.
- Rutas:
  - `GET`/`POST /{id}/odontograma`;
  - `GET /{id}/odontograma/actual`;
  - `GET`/`POST /{id}/evoluciones`;
  - `GET /{id}/evoluciones/{evolucion_id}`;
  - `GET /{id}/historia`.
- No se declaran PUT/PATCH/DELETE. Como la ruta existe con otros métodos, Starlette responde `405`. Un test recorre `app.routes` y verifica que ninguna ruta de odontograma o evoluciones expone esos métodos (mismo patrón que `test_ninguna_ruta_expone_escritura_de_auditoria`).
- Paginación de evoluciones: keyset `WHERE id < :after_id ORDER BY id DESC LIMIT :limit + 1`, `Pagina[T]`, `limit` 1..200. El `id` identity es monótono con la inserción y `fecha_hora` es del servidor, así que el orden por id coincide con el orden de registro.
- Errores: subclases de `PacienteError` en `backend/app/domain/clinica/errores.py`, que el handler existente traduce:
  - `AutorProfesionalRequerido` 422, `VersionOdontogramaConflicto` 409, `EvolucionYaCorregida` 409;
  - `CorreccionNoAutorizada` 403, `CorreccionInvalida` 422, `EvolucionNoEncontrada` 404.

### D7 — Migración `008_odontograma_evolucion`

- `revision = "008_odontograma_evolucion"`, `down_revision = "006_turno_transicion"`.
- **Si C-05c (`007_sobreturno_huecos`) mergea antes, re-apuntar `down_revision = "007_sobreturno_huecos"`** antes de mergear, y verificar con `cd backend && alembic heads`, que debe mostrar un único head (`docs/CONTINUAR.md` §5). Las migraciones no se tocan entre sí (tablas distintas), así que el re-apunte es solo de cadena.
- Upgrade: `odontograma` → `evolucion` (+ unique, FKs, índices, GIN) → triggers → CHECKs ampliados de `auditoria_hc`.
- Downgrade:
  - restaura los CHECKs angostos, borra triggers y tablas;
  - **no** borra `fn_rechazar_mutacion()`, que es de la 004;
  - si ya hay eventos `odontograma`/`evolucion`/`corregir` en `auditoria_hc`, restaurar el CHECK angosto falla y esas filas no se pueden borrar (trigger). Es intencional: en producción no se hace downgrade, se hace roll-forward (documentado en el docstring, como la 004).
- Nota de roadmap: `CHANGES.md` asignaba "Migración 007" a C-09 y "Migración 008" a C-11. Con este change, C-11 pasa a 009 (anotado en su ficha).

### D8 — Evidencia de Context7 (MCP) y qué se adoptó

Consultas hechas el 2026-11-16, sin secretos, datos de pacientes ni código privado:

1. `resolve-library-id("SQLAlchemy")` → `/websites/sqlalchemy_en` (el id `/websites/sqlalchemy_en_20` no existe). Luego `query-docs`: "PostgreSQL JSONB type: mapped_column(JSONB), comparator contains (@>) and has_key operators, and mutation tracking with MutableDict".
   - Respuesta: `JSONB` agrega `Comparator.contains()` (`@>`), `has_key()` (`?`), `path_exists()` (`@?`) y `path_match()` (`@@`). Además, "like JSON, JSONB does not detect in-place changes when used with the ORM, unless the `sqlalchemy.ext.mutable` extension is used".
   - **Adoptado:**
     - (a) `piezas: Mapped[dict[str, Any]] = mapped_column(JSONB, server_default=text("'{}'::jsonb"))`, igual que `AuditoriaHC.diff`;
     - (b) **no** usar `MutableDict`. Que el ORM no detecte mutaciones in-place es coherente con la inmutabilidad: cada guardado construye una fila nueva y una mutación accidental de un `piezas` cargado nunca emite UPDATE (y el trigger lo rechazaría igual);
     - (c) las consultas futuras de recall/presupuesto usarán `Odontograma.piezas.contains({...})` / `path_exists(...)`, que el GIN `jsonb_path_ops` acelera.
2. `resolve-library-id("Alembic")` → `/websites/alembic_sqlalchemy_en`. Luego `query-docs`: "op.create_index with postgresql_using='gin' and postgresql_ops jsonb_path_ops on a JSONB column, and op.create_check_constraint".
   - Respuesta: `create_index` acepta kwargs de dialecto con la forma `<dialect>_<arg>`, y `create_check_constraint(name, table, condition)` acepta la condición como string.
   - **Adoptado:**
     - `op.create_index("ix_odontograma_piezas_gin", "odontograma", ["piezas"], postgresql_using="gin", postgresql_ops={"piezas": "jsonb_path_ops"})`;
     - ampliar los CHECKs de `auditoria_hc` con `op.drop_constraint(op.f("ck_auditoria_hc_entidad_valida"), "auditoria_hc", type_="check")` + `op.create_check_constraint("entidad_valida", "auditoria_hc", "entidad IN (...)")`. `op.f()` evita que la naming convention vuelva a prefijar un nombre que ya está completo.
     - Triggers con `op.execute`, como en la 004/006.

En el apply, registrar esta evidencia como E7 en `docs/skills-mcp/evidencias/README.md` (task 6.4).

## Decisiones a confirmar por el usuario

Governance CRÍTICO: el apply no arranca hasta que el usuario confirme o cambie estos defaults. Si cambia alguno, se actualizan spec y tasks antes de codificar.

> **CONFIRMADO por el usuario el 2026-11-16: DC-1 … DC-9 aprobadas tal como están escritas (defaults elegidos), sin cambios.**

| # | Pregunta | Opciones | Default elegido | Por qué |
|---|---|---|---|---|
| DC-1 | ¿El odontograma se guarda como snapshot por guardado o como un estado actual único y mutable? ¿Es append-only? | (a) snapshot completo por guardado, append-only; (b) fila única mutable + auditoría; (c) una fila por marca (eventos) | **(a)** | RN-CL-02 ("ningún cambio borra historia"), regla dura 15 y mismo patrón que `ficha_version`. (c) es el "versionado fino" que la KB pone en F2. |
| DC-2 | ¿Qué forma tiene el JSONB de piezas/caras/estados? | (a) objeto disperso por código FDI → `{estado, caras{V,L,M,D,O}}`; (b) array de marcas `{pieza, cara, estado}`; (c) tablas normalizadas | **(a)** | Sin piezas duplicadas, consultas `@>`/`@?` con GIN para el recall (RN-CL-04) y pedido explícito de JSONB en CHANGES/registry. |
| DC-3 | ¿Qué estados se permiten en el MVP? | Catálogo cerrado propuesto vs. catálogo configurable por clínica | **Cerrado**. Pieza: `ausente`, `extraida`, `extraccion_indicada`, `corona`, `endodoncia`, `implante`. Cara (`V`,`L`,`M`,`D`,`O`; `O` = oclusal/incisal): `caries`, `obturacion`, `sellador`, `fractura`. Cada marca con `registro` = `existente` \| `a_realizar` (convención rojo/azul) | La KB no define estados. Lo mínimo para presupuestar (C-11 toma lo `a_realizar`). Ampliarlo después es aditivo (no rompe snapshots viejos). |
| DC-4 | ¿Qué significa "mixta" en el MVP si RN-CL-03 la pone como posterior? | (a) `mixta` = unión de los sets permanente y temporal en un mismo odontograma; (b) solo `permanente`/`temporal` | **(a)** | `04_modelo_de_datos` y la ficha C-09 listan "mixta". Lo posterior es la mixta **fina** (recambio, erupción). Conflicto anotado en `dominio-clinica`. |
| DC-5 | ¿El odontólogo escribe evoluciones de cualquier paciente o solo de los que tienen turnos con él? | (a) regla interina de C-08: cualquier paciente de su clínica, lecturas auditadas; (b) solo con turno no cancelado con su profesional | **(a)** | Es la regla vigente aprobada en C-08. (b) requiere un resolver sobre `turno`, en archivos de agenda de otro integrante. Queda enchufable vía `set_resolver_vinculo_paciente`. |
| DC-6 | ¿Quién es el "autor" de la evolución? | (a) usuario autenticado + su profesional activo vinculado (sin profesional → 422); (b) solo el usuario | **(a)** | KB: `Evolucion.profesional_id (autor)`; regla dura 15: "sin autor profesional → 422". |
| DC-7 | ¿Quién puede corregir una evolución y cuántas veces? | (a) solo su autor, con motivo obligatorio, una corrección por evolución (se corrige la vigente: cadena lineal); (b) cualquier odontólogo vinculado; (c) varias correcciones sobre la misma original | **(a)** | Autoría individual de la HC (Ley 26.529). Una cadena lineal evita "dos versiones vigentes" y resuelve la concurrencia con un índice único. Otro profesional agrega una evolución nueva. |
| DC-8 | ¿El diff de auditoría del odontograma puede incluir los códigos FDI de las piezas cambiadas? | (a) sí, solo códigos (sin estados ni caras); (b) solo versión e id | **(a)** | US-008 pide "marca por pieza con trazabilidad". El código de pieza no es texto clínico, pero amplía la definición de "diff mínimo" de C-08: confirmarlo. |
| DC-9 | ¿Se habilita ya el vínculo adjunto ↔ evolución (`adjunto.evolucion_id`)? | (a) no, sigue `422` hasta C-10; (b) sí, con FK compuesta en la 008 | **(a)** | Lo necesita la UI (C-10). Hoy cambiaría una spec vigente (`clinical-record`) sin consumidor. |

Supuesto legal (PA-04 / SU-08, abierto): append-only + auditoría de escrituras y lecturas, sin firma electrónica (C-18), se considera suficiente para el MVP, a validar con asesoría (igual que C-08).

## Risks / Trade-offs

- [Un odontograma completo por guardado duplica datos] → Son unas pocas decenas de piezas por versión (KB). El volumen por paciente es bajo. Si molesta, la compactación es un change de F2.
- [La estructura del JSONB se valida solo en la app] → La API es el único camino de escritura. Hay CHECK de tipo raíz y tests unitarios exhaustivos de `fdi.py` y del schema. `pg_jsonschema` queda como hardening.
- [El odontólogo escribe algo en una evolución equivocada] → No se borra: se corrige con motivo y queda traza visible (`corregida_por_id`), que es exactamente lo que pide la ley.
- [Downgrade bloqueado si hay auditoría C-09] → Intencional (D7). En producción, roll-forward.
- [Choque de numeración/heads con C-05c] → D7: re-apuntar `down_revision` y verificar `alembic heads` antes de mergear (task 2.1 y 7.1).
- [El texto de la evolución puede contener datos sensibles] → Nunca se loguea ni va al diff de auditoría. Solo se devuelve a roles clínicos con vínculo.
- [Importar `paciente_lectura`/`paciente_escritura` desde otro router acopla módulos] → Es explícito y evita reescribir C-08. Si un tercer router los necesita, se mueven a `permissions.py` en un refactor aparte.

## Migration Plan

1. `008_odontograma_evolucion` (`down_revision = "006_turno_transicion"`, o `"007_sobreturno_huecos"` si C-05c mergeó antes). Tablas nuevas: no hay backfill ni downtime.
2. Antes de mergear: `cd backend && alembic heads` → un único head.
3. Rollback de la aplicación: quitar el router. Las tablas quedan inertes e inmutables.
4. Rollback de esquema: solo en entornos sin datos C-09 (D7).

## Open Questions

- Límite de 10 000 caracteres por evolución: igual que la anamnesis. Se ajusta con el piloto sin cambiar specs.
- Si la UI (C-10) necesitará un endpoint de "diff entre dos versiones" del odontograma: se decide en C-10 y no cambia este backend.
