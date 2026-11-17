# Proposal — consentimientos-cumplimiento (C-18)

## Why

El producto vende el cumplimiento legal como diferencial (US-014/015/016), pero hoy solo existe el flag `consentimiento_datos` del paciente (C-08) y una página `/cumplimiento` vacía (C-01). No hay consentimientos de tratamiento firmados con constancia (Ley 25.506), no hay política de privacidad pública (Ley 25.326), el administrador no puede gestionar usuarios ni roles desde la API y no hay forma de exportar los datos del consultorio "sin retención" (RN-CU-04).

La skill `dominio-cumplimiento` marca **RN-CU-02** y **RN-CU-04** como **pendientes** y **RN-CU-01** / **RN-CU-05** como **parciales**. C-09 (`odontograma-evolucion`) fija el contrato de la historia clínica que la exportación necesita, y C-03 dejó el RBAC que este change reutiliza.

## What Changes

- **Consentimientos con firma electrónica y constancia** (RN-CU-02, Flujo 8):
  - `POST /api/pacientes/{id}/consentimientos` genera un consentimiento de un tipo del catálogo cerrado, con el **texto exacto versionado** copiado en la fila y su hash SHA-256 calculado por el servidor. Queda `pendiente`.
  - `POST /api/pacientes/{id}/consentimientos/{cid}/firmar` registra la constancia (fecha del servidor, IP, user-agent, hash del texto, firmante) y **bloquea el documento**. Firma incompleta → `422` con `reintentable: true` y el documento sigue pendiente. Ya firmado → `409`.
  - `GET` de listado y detalle. **Sin PUT/PATCH/DELETE** (`405`); la base rechaza cualquier UPDATE/DELETE con `fn_rechazar_mutacion()` (migración 004).
  - Solo odontólogo escribe (recepción → `403`), con vínculo y `consentimiento_datos = true` (`403` si falta). Escrituras y lecturas auditadas en `AuditoriaHC`.
- **Administración de usuarios** (US-014): `GET`/`POST /api/admin/usuarios` y `PATCH /api/admin/usuarios/{id}/roles`, solo admin. C-03 no expone ningún endpoint de usuarios, así que no se duplica nada. La clínica nunca queda sin admin (`409`).
- **Exportación completa del tenant** (RN-CU-04): `GET /api/admin/exportacion?formato=csv` devuelve un **ZIP** con un CSV por entidad existente (pacientes, fichas, adjuntos + sus archivos, odontogramas, evoluciones, consentimientos y firmas, turnos y su historial, catálogo, usuarios sin hash de contraseña, auditoría HC) y un `manifest.json`. Solo datos de la clínica del admin. **Caja y facturas no existen todavía**: quedan fuera y el manifest lo declara. **PDF diferido**: `formato=pdf` → `422` con los formatos soportados.
- **Auditoría administrativa**: tabla append-only `auditoria_admin` para eventos sin paciente (alta de usuario, cambio de roles, exportación), con el mismo trigger de inmutabilidad.
- **Páginas públicas** `/cumplimiento` (ya existe, se completa) y `/privacidad` (nueva) en el frontend, con textos base versionados, ubicación de datos declarada y la marca visible **"a validar con asesoría legal"** (PA-04/SU-08).
- Migración `009_consentimientos_cumplimiento` (`down_revision = "008_odontograma_evolucion"`).

Las decisiones que la KB no resuelve están en `design.md` §"Decisiones tomadas (aprobación delegada del usuario, 2026-11-16)". Governance **ALTO**, cubierto por la aprobación del usuario del 2026-11-16.

## Non-goals

- Pantallas internas de consentimientos, usuarios o exportación (se usan por Swagger; la UI clínica es C-10).
- Firma remota del paciente por enlace o WhatsApp, firma digital con certificado y trazo manuscrito dibujado.
- PDF del consentimiento firmado y exportación en PDF (diferidos; ver design).
- Exportación de caja, cobros y facturas (C-12/C-13 la extienden cuando existan) y de recetas (C-19 la extiende).
- Baja/desactivación de usuarios, reseteo de contraseña e invitaciones por email.
- Revocación de un consentimiento firmado (se registra un consentimiento nuevo; la revocación formal queda para validar con asesoría).
- Textos legales definitivos (los entrega la asesoría legal; aquí son placeholders marcados).

## Capabilities

### New Capabilities

- `informed-consents`: consentimientos de tratamiento con texto versionado, firma electrónica con constancia (fecha, IP, dispositivo, hash) y bloqueo post-firma.
- `user-administration`: alta y listado de usuarios del tenant y asignación de roles por el administrador.
- `data-export`: exportación completa y aislada por tenant de los datos existentes en CSV dentro de un ZIP.
- `admin-audit`: registro inmutable de eventos administrativos sin paciente (usuarios, roles, exportación).
- `legal-pages`: páginas públicas de privacidad y cumplimiento con textos base versionados y aviso de validación legal.

### Modified Capabilities

- `clinical-audit`: se agrega la auditoría de consentimientos (crear, firmar, leer) en `AuditoriaHC` (requirement nuevo, sin modificar los existentes).

## Impact

- Código nuevo:
  - `backend/app/domain/cumplimiento/` (`textos.py` con plantillas versionadas, `hashing.py` puro, `models.py`, `schemas.py`, `servicios.py`, `exportacion.py`, `errores.py`);
  - `backend/app/domain/usuarios/` (`schemas.py`, `servicios.py`: administración de usuarios y roles);
  - routers `backend/app/api/consentimientos.py` y `backend/app/api/admin_cumplimiento.py`, registrados en `create_app()`;
  - `backend/alembic/versions/009_consentimientos_cumplimiento.py`;
  - `frontend/src/pages/PrivacidadPage.tsx`, `frontend/src/features/legal/textos.ts` y tests vitest.
- Código modificado (aditivo): `backend/app/domain/auditoria/models.py` y `writer.py` (entidad `consentimiento`, acción `firmar`, allowlist), `backend/app/main.py`, `frontend/src/pages/CumplimientoPage.tsx`, `frontend/src/App.tsx` (ruta `/privacidad`).
- Reutiliza: `paciente_lectura` / `paciente_escritura` (`backend/app/api/pacientes.py`), `require_admin()`, `fn_rechazar_mutacion()`, `bcrypt` de C-03, `PacienteError` y su handler.
- **No toca** archivos de agenda ni `openspec/changes/huecos-y-sobreturnos/` ni `openspec/changes/archive/2026-11-17-odontograma-evolucion/`.
- DB: tablas `consentimiento`, `consentimiento_firma`, `auditoria_admin`; CHECKs de `auditoria_hc` ampliados. Sin dependencias Python nuevas (`csv`, `zipfile`, `hashlib`, `tempfile` de la stdlib).
- Verificación: Docker Desktop (testcontainers `postgres:16-alpine`).
