# Proposal — odontograma-evolucion (C-09)

## Why

C-08 dejó la ficha de anamnesis versionada, los adjuntos y la auditoría `AuditoriaHC`, pero el odontólogo todavía no puede registrar **qué encontró en cada pieza** ni **qué hizo en la consulta**. Sin odontograma no hay base para presupuestar por pieza (C-11) ni para el recall (RN-CL-04), y sin evolución no hay historia clínica en el sentido de la Ley 26.529.

La skill `dominio-clinica` marca **RN-CL-01** (evolución con autor) y **RN-CL-03** (odontograma FDI) como **pendientes**, y **RN-CL-02** (HC append-only) como **parcial**: está cubierta para la ficha, pero no para evoluciones ni odontograma. C-09 es el único change de la FASE 3 sin dependencias abiertas (C-08 está archivado) y desbloquea C-10, C-11, C-18 y C-19.

## What Changes

- **Odontograma FDI versionado e inmutable**:
  - `POST /api/pacientes/{id}/odontograma` guarda una **versión completa nueva** (snapshot), con control optimista `version_esperada` (desfasada → `409`).
  - `GET /api/pacientes/{id}/odontograma/actual` devuelve la versión vigente (`version = 0` si no hay ninguna).
  - `GET /api/pacientes/{id}/odontograma` devuelve el historial de versiones.
  - Piezas válidas según la dentición: permanente (11–48, 32 piezas), temporal (51–85, 20 piezas) o mixta (ambos sets). Pieza, cara o estado inválidos → `422`.
- **Evolución append-only**:
  - `POST /api/pacientes/{id}/evoluciones`: el autor sale del usuario autenticado y de su profesional vinculado, y la fecha/hora la asigna el servidor. Odontólogo sin profesional vinculado → `422`. `autor`, `profesional_id` o `fecha_hora` en el cuerpo → `422`.
  - `GET /api/pacientes/{id}/evoluciones` (orden descendente, paginado por cursor) y `GET /api/pacientes/{id}/evoluciones/{evolucion_id}`.
  - **Sin PUT/PATCH/DELETE**: `405`. Corregir = `POST` con `corrige_a_id` + `motivo_correccion`, que crea una fila nueva y deja la original intacta.
- **Historia consolidada**: `GET /api/pacientes/{id}/historia` (ficha vigente + odontograma actual + primera página de evoluciones).
- **Auditoría**: toda escritura y lectura de odontograma/evolución queda en `AuditoriaHC`, en la misma transacción y sin texto clínico en el diff. Se amplían las entidades (`odontograma`, `evolucion`) y las acciones (`corregir`).
- **Inmutabilidad en la base**: triggers con `fn_rechazar_mutacion()` (de la migración 004) sobre `odontograma` y `evolucion`.
- **RBAC clínico**: lectura admin + odontólogo; escritura solo odontólogo, con vínculo y consentimiento; recepcionista → `403`; paciente de otra clínica → `404`.
- Migración `008_odontograma_evolucion`. Se toma el 008 porque el 007 está reservado para C-05c (`docs/CONTINUAR.md` §5).

Las decisiones de dominio que la KB no resuelve están en `design.md` §"Decisiones a confirmar por el usuario". Governance **CRÍTICO**: el apply requiere que el usuario las confirme.

## Non-goals

- UI del odontograma y de la timeline (C-10).
- Vincular adjuntos a evoluciones (`evolucion_id` sigue → `422`, spec `clinical-record`). Se habilita cuando C-10 lo necesite.
- Recall (RN-CL-04), presupuesto desde el odontograma (C-11), RNO de obras sociales (RN-OS-02).
- Dentición mixta fina (recambio, estadios de erupción), periodontograma/BOP y versionado fino por marca (F2, RN-CL-03).
- Vínculo odontólogo–paciente por turnos: se mantiene la regla interina de C-08 (el resolver por turnos toca agenda, que es de otro integrante).
- Firma electrónica de la evolución (C-18, Ley 25.506).

## Capabilities

### New Capabilities

- `odontogram`: odontograma FDI del paciente (permanente, temporal y mixta), versionado como snapshots inmutables, con validación de piezas, caras y estados y control de concurrencia.
- `clinical-evolutions`: evoluciones clínicas append-only, con autor profesional y hora del servidor, correcciones como filas nuevas encadenadas y consulta ordenada.

### Modified Capabilities

- `clinical-record`: se agrega la historia clínica consolidada (`GET /historia`).
- `clinical-audit`: la auditoría de escrituras y lecturas se extiende a odontograma y evolución (incluida la acción `corregir`), y la inmutabilidad a nivel base se extiende a las tablas nuevas.
- `access-control`: las reglas de lectura y escritura clínica cubren odontograma, evoluciones e historia.

## Impact

- Código nuevo:
  - `backend/app/domain/clinica/` (`fdi.py` puro, `models.py`, `schemas.py`, `servicios.py`);
  - `backend/app/api/historia_clinica.py` (router registrado en `create_app()`);
  - `backend/alembic/versions/008_odontograma_evolucion.py`.
- Código modificado (aditivo):
  - `backend/app/domain/auditoria/models.py` y `writer.py`: entidades, acciones y allowlist de diff;
  - `backend/app/main.py`: registro del router.
- Reutiliza:
  - `paciente_lectura` / `paciente_escritura` de `backend/app/api/pacientes.py`;
  - `require_vinculo_paciente`;
  - `profesional_de_usuario` de `backend/app/domain/agenda/servicio.py` (solo lectura, sin modificarlo);
  - `PacienteError` y su handler.
- **No toca** archivos de agenda (`turnos.py`, `huecos.py`, `api/turnos.py`, `api/agenda.py`) ni `openspec/changes/huecos-y-sobreturnos/`.
- DB: 2 tablas, índices `(clinica_id, paciente_id, …)`, GIN sobre `odontograma.piezas`, CHECKs de `auditoria_hc` ampliados. Sin dependencias nuevas.
- Verificación: Docker Desktop (testcontainers `postgres:16-alpine`).
