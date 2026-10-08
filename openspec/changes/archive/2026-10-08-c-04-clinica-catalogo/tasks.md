# Tasks — c-04-clinica-catalogo

> Strict TDD: cada task arranca en RED (test que falla nombrado abajo), luego GREEN mínimo, TRIANGULATE (≥2 casos por comportamiento) y REFACTOR con tests en verde. Integración PG solo con `postgres:16-alpine` vía fixtures de `backend/tests/integration/conftest.py` (nunca SQLite). Datos 100 % sintéticos. Safety net antes de tocar archivos existentes: `pytest backend/tests -q` en verde como baseline.

## 1. Migración 003 + modelos ORM

- [x] 1.1 RED `backend/tests/integration/test_migration_003.py` (integración): upgrade head crea `profesional`, `sillon_recurso`, `prestacion`, `profesional_sillon`, `bloqueo`, la extensión `btree_gist` y `uq_usuario_clinica_id`; `downgrade 002_token_blacklist` los elimina; re-upgrade OK. GREEN: crear `backend/alembic/versions/003_clinica_catalogo.py` (`revision="003_clinica_catalogo"`, `down_revision="002_token_blacklist"`, tablas/CHECKs/índices/FKs compuestas/columna generada `rango` según design §4, §6, §14), y verificar que el test pasa.
- [x] 1.2 RED `backend/tests/integration/test_catalogo_db_constraints.py` (integración, SQL directo): `tipo` fuera de `sillon|box|equipo`, `duracion_min` 0/481, `precio_referencia` negativo, `fin <= inicio`, bloqueo > 31 días y bloqueo con profesional+sillón → `IntegrityError`; FK compuesta rechaza habilitar sillón de B a profesional de A; matrícula repetida activa en A falla pero se permite tras baja lógica y en B; `rango` generado es `[inicio, fin)`. GREEN: ajustar migración si algo falta, y verificar que el test pasa.
- [x] 1.3 RED `backend/tests/integration/test_catalogo_isolation.py` (integración): `BaseRepository` de cada modelo nuevo con `clinica_id=A` devuelve 0 filas de B (lista y `get` por id ajeno → `None`). GREEN: `backend/app/domain/agenda/models.py` (`Profesional`, `SillonRecurso`, `Prestacion`, `ProfesionalSillon`, `Bloqueo` con `TenantMixin`+`AuditMixin`, `Identity(always=True)`, `Mapped[Decimal]`, `rango` como `Computed`, `__table_args__` espejo de 003) + `__init__.py`, y verificar que el test pasa y `ruff check backend` queda limpio.

## 2. Dominio puro y schemas

- [x] 2.1 RED `backend/tests/unit/test_agenda_duracion.py` (unit): `calcular_fin` con 30 y 60 min desde 10:00-03:00 → 10:30/11:00; cruce de medianoche 23:30 + 60 → 00:30 día siguiente; inicio naive → `ValueError`; duración 0/481 → `ValueError`. GREEN: `backend/app/domain/agenda/duracion.py`, y verificar que el test pasa.
- [x] 2.2 RED `backend/tests/unit/test_agenda_schemas.py` (unit): todos los `*Create/*Update` rechazan campos extra (incl. `clinica_id`, `es_seed`, `rango`); `tipo` inválido; `duracion_min` fuera de 5..480 o no entero; precio con 3 decimales o negativo; `15000.50` serializa como `"15000.50"`; `AwareDatetime` rechaza naive y normaliza a UTC; `BloqueoCreate` con profesional y sillón → error; `HabilitacionIn` sin duplicados. GREEN: `backend/app/domain/agenda/schemas.py` (base `extra="forbid"`, `Pagina[T]`), y verificar que el test pasa.
- [x] 2.3 RED `backend/tests/unit/test_repository_page.py` (unit, statement compilado) + caso en `test_catalogo_isolation.py` (integración): `BaseRepository.page(after_id, limit, ...)` ordena por id, aplica `id > after_id`, trae `limit+1` y devuelve `next_cursor`; 120 prestaciones con `limit=50` → 50/50/20 sin duplicados y cursor final `None`. GREEN: método aditivo en `backend/app/infrastructure/persistence/repository.py` sin cambiar los existentes, y verificar que los tests nuevos y `tests/unit/test_repository.py` pasan.

## 3. Endpoints admin de catálogo

- [x] 3.1 RED `backend/tests/integration/test_admin_catalogo.py` (integración HTTP, fixture `catalogo_data` sobre `auth_data`): sillones y prestaciones — admin `POST` → `201`; `GET` lista paginada y detalle; `PATCH` duración 30→40 reflejado; `DELETE` → `204` y fila persiste inactiva con `deleted_at`; `incluir_inactivos=true` la muestra; nombre de sillón duplicado → `409`; id de B → `404`; `clinica_id` en body → `422`; `limit=500` → `422`; recepcionista/odontólogo → `403`; sin token → `401`. GREEN: `backend/app/domain/agenda/servicio.py` (CRUD + mapeo `IntegrityError`→409) + `backend/app/api/admin_catalogo.py` (`require_admin()` + `require_tenant_checked`) montado en `create_app()`, y verificar que el test pasa.
- [x] 3.2 RED (mismo archivo) profesionales: alta con flags por defecto (`agenda_activa=true`, `tercerizado=false`); matrícula repetida activa en A → `409`, misma matrícula en B → `201`; vínculo `usuario_id` de B → `422`, usuario ya vinculado a otro profesional activo → `409`, usuario inactivo → `422`. GREEN: rutas `/api/admin/profesionales[/{id}]` + validación de vínculo en servicio, y verificar que el test pasa.
- [x] 3.3 RED (mismo archivo) habilitación: `PUT /api/admin/profesionales/{id}/sillones` reemplaza `[S3]` por `[S1,S2]` y el detalle expone `sillon_ids`; set con sillón de B o inactivo → `422` y habilitación previa intacta (atomicidad). GREEN: servicio de reemplazo en una transacción + ruta, y verificar que el test pasa.

## 4. Bloqueos

- [x] 4.1 RED `backend/tests/integration/test_bloqueos_solapados.py` (integración, sin HTTP): `bloqueos_solapados` devuelve bloqueo del profesional que se superpone, bloqueo de clínica para cualquier par, nada para bloqueo de otro sillón, nada para bloqueo de otra clínica, nada para bloqueo inactivo y nada para rango contiguo `[12,13)` vs `[13,13:30)`. GREEN: `backend/app/domain/agenda/bloqueos.py` (consulta `rango && tstzrange(:i,:f,'[)')` según design §7), y verificar que el test pasa.
- [x] 4.2 RED `backend/tests/integration/test_admin_bloqueos.py` (integración HTTP): admin crea bloqueo de clínica/profesional/sillón → `201`; profesional+sillón → `422`; profesional de B → `422`; `fin <= inicio`, naive y 40 días → `422`; lista con `desde/hasta` devuelve solo los que se superponen con la ventana; `PATCH` de rango revalida; `DELETE` → `204` y `bloqueos_solapados` deja de devolverlo; id de B → `404`; recepcionista → `403`. GREEN: rutas `/api/admin/bloqueos[/{id}]` en `admin_catalogo.py` + servicio, y verificar que el test pasa.
- [x] 4.3 RED `backend/tests/integration/test_agenda_propia.py` (integración): con el resolver real, `odonto@test.test` vinculado a P accede a `/api/probe/agenda/P` (router de prueba) y recibe `403` en Q; usuario odontólogo sin vínculo → `403`; profesional dado de baja deja de resolver. GREEN: `profesional_de_usuario(session, usuario_id)` en `backend/app/domain/agenda/servicio.py` registrado vía `set_resolver_agenda_propia` dentro de `create_app()` (firma de C-03 intacta; actualizar comentario de `permissions.py`), y verificar que este test y `tests/integration/test_rbac.py` pasan.
- [x] 4.4 RED `backend/tests/integration/test_bloqueos_propios.py` (integración HTTP): odontólogo vinculado a P lista/crea/borra en `/api/profesionales/P/bloqueos` (`201`, bloqueo asociado a P aunque no envíe `profesional_id`; `sillon_id` en body → `422`); en `/Q/bloqueos` → `403`; borrar bloqueo que no es de P vía `/P/bloqueos/{id}` → `404`; recepcionista → `403`; admin opera sobre cualquier P de su clínica y P de otra clínica → `404`. GREEN: `backend/app/api/bloqueos_propios.py` (`require_role("admin","odontologo")` + `require_own_agenda`) montado en `create_app()`, y verificar que el test pasa.

## 5. Lectura del catálogo para el staff

- [x] 5.1 RED `backend/tests/integration/test_catalogo_lectura.py` (integración HTTP): admin, recepcionista y odontólogo listan `/api/catalogo/{profesionales,sillones,prestaciones}` solo activos de su clínica (0 de B, inactivos excluidos, prestaciones con `duracion_min`); JWT solo `paciente-enlace` → `403`; sin token → `401`. GREEN: `backend/app/api/catalogo.py` montado en `create_app()`, y verificar que el test pasa.

## 6. Seed sintético

- [x] 6.1 RED `backend/tests/integration/test_seed_catalogo.py` (integración): tras `seed_core`, `seed_catalogo` ejecutado dos veces deja exactamente 1 sillón, 1 profesional (habilitado en el sillón) y 3 prestaciones `es_seed=True` en la clínica piloto con duraciones 30/45/60; `borrar_seed_catalogo` elimina solo filas seed y conserva una prestación creada por el admin. GREEN: `backend/app/infrastructure/persistence/seed_catalogo.py` (valores sintéticos de design §13, docstring con supuesto PA-09/SU-06), y verificar que el test pasa.

## 7. Integración y cierre

- [x] 7.1 Verificar regresión completa: `ruff check backend` limpio (line-length 100), `pytest backend/tests -q` en verde (incluye `test_migrations_smoke.py` base↔head con 003) y ninguna ruta nueva aparece en `PUBLIC_PREFIXES`.
- [x] 7.2 Documentar en `backend/README.md` (sección corta) los endpoints de catálogo/bloqueos con su rol, el orden `seed_core` → `seed_catalogo`, y que C-08 apila `004` sobre `003_clinica_catalogo` reutilizando `uq_usuario_clinica_id`; actualizar `backend/app/domain/README.md` (agenda vive en `domain/agenda/`), y verificar `openspec validate c-04-clinica-catalogo --strict` en verde.

## Workflow follow-up

- Revisión humana (governance MEDIO) de decisiones expuestas en design: alcance único por bloqueo, recepción sin bloqueos, rangos 5..480 min / 31 días, seed sintético.
- `/opsx:archive c-04-clinica-catalogo` y marcar `[x] C-04` en CHANGES.md.
- C-05 consume `calcular_fin` y `bloqueos_solapados`; reemplazar el seed por el catálogo real del piloto (PA-09).
