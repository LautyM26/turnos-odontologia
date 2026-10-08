# Proposal — c-04-clinica-catalogo

## Why

El motor de turnos (C-05) y la agenda (C-07) no pueden existir sin el catálogo operativo de la clínica: quién atiende (profesional), dónde (sillón/box/equipo), qué se hace y cuánto dura (prestación, RN-AG-02) y cuándo no se puede reservar (bloqueos, RN-AG-03). Además C-03 dejó `require_own_agenda` fallando cerrado a la espera del vínculo `Usuario → Profesional`, que solo este change puede dar (DD-04, US-001/US-002).

## What Changes

- Nuevas entidades tenant-scoped (todas con `clinica_id` + índice `(clinica_id, is_active)` + aislamiento probado):
  - `Profesional` (nombre, matrícula única por clínica, especialidad, `agenda_activa`, `tercerizado`, vínculo opcional a `Usuario`, `es_seed`).
  - `SillonRecurso` (nombre, tipo `sillon|box|equipo`, `es_seed`).
  - `Prestacion` (nombre, `duracion_min` editable, `precio_referencia` NUMERIC ARS, `es_seed`).
  - `ProfesionalSillon` (habilitación N—M, misma clínica garantizada por FK compuesta).
  - `Bloqueo` (alcance único: profesional, sillón, o toda la clínica cuando ambos son nulos — p. ej. feriado; rango `[inicio, fin)` TIMESTAMPTZ; motivo).
- Endpoints admin (solo rol `admin`, paginados por cursor, scoped por tenant del JWT):
  - CRUD `/api/admin/profesionales`, `/api/admin/sillones`, `/api/admin/prestaciones`, `/api/admin/bloqueos` (POST/GET lista/GET detalle/PATCH/DELETE lógico).
  - `PUT /api/admin/profesionales/{id}/sillones` reemplaza el set de sillones habilitados.
- Endpoints de lectura para el staff (`admin`, `recepcionista`, `odontologo`): `GET /api/catalogo/profesionales|sillones|prestaciones` (solo activos) — lo que la agenda necesita para operar sin acceso a `/api/admin/*`.
- Bloqueos propios del odontólogo (matriz `03`: "Lectura + bloqueos propios"): `GET/POST /api/profesionales/{profesional_id}/bloqueos` y `DELETE /api/profesionales/{profesional_id}/bloqueos/{id}`, restringidos por `require_own_agenda`.
- Regla de servidor: duraciones y rangos se validan/normalizan solo en backend (datetimes sin zona → 422, `fin > inicio`, tope de duración); función de dominio `fin = inicio + duracion_prestacion` que C-05 consume (RN-AG-02, regla dura 6).
- Contrato de consulta "bloqueos que solapan un rango para (profesional, sillón)" incluyendo bloqueos de clínica, que C-05 usa para impedir huecos (RN-AG-03).
- Cierre del hook C-03: el resolver de agenda propia pasa a leer el vínculo real `Profesional.usuario_id`; un odontólogo sin profesional vinculado sigue recibiendo `403`.
- Migración Alembic `003_clinica_catalogo` (down_revision `002_token_blacklist`): tablas + índices + extensión `btree_gist` + índice GiST de rango de bloqueos; up/down probados.
- Seed sintético idempotente (`es_seed=true`, borrable): 1 sillón + 1 profesional + 3 prestaciones con duraciones sintéticas (PA-09 parcial: el catálogo real del piloto reemplaza estos valores).

## Capabilities

### New Capabilities

- `clinic-catalog`: catálogo operativo por clínica — profesionales (con vínculo a usuario y flag tercerizado), sillones/recursos, prestaciones con duración propia y precio de referencia ARS, habilitación profesional↔sillón, endpoints admin y de lectura, seed sintético.
- `schedule-blocks`: bloqueos de agenda por profesional, sillón o clínica entera — rango validado en servidor, alta/baja por admin o por el propio odontólogo, y consulta de solapamiento que impide reservas (RN-AG-03).

### Modified Capabilities

(ninguna — `access-control` ya exige "Tercerizado solo ve su agenda"; este change solo provee el dato del vínculo sin cambiar el requisito.)

## Impact

- Código nuevo: `backend/app/domain/agenda/` (modelos, schemas, cálculo de duración, consulta de bloqueos), `backend/app/api/admin_catalogo.py`, `backend/app/api/catalogo.py`, `backend/app/api/bloqueos_propios.py`, `backend/app/infrastructure/persistence/seed_catalogo.py`, `backend/alembic/versions/003_clinica_catalogo.py`.
- Código modificado: `backend/app/main.py` (routers + registro del resolver de agenda propia), `backend/app/api/permissions.py` (solo comentario/uso del resolver real; firma intacta).
- APIs: ~20 rutas nuevas bajo `/api/admin/*`, `/api/catalogo/*`, `/api/profesionales/{id}/bloqueos`. Todas exigen JWT (ninguna pública).
- DB: 5 tablas nuevas + `CREATE EXTENSION btree_gist` (contrib incluida en `postgres:16-alpine`); la migración 004 de C-08 (pacientes) se apila encima de 003.
- Dependencias: ninguna nueva de Python.
- Desbloquea C-05 (junto con C-08) y la parte de catálogo de C-07/C-10.
