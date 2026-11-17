# Proposal — recetas-partner-renapdis (C-19)

## Why

Desde el 1/1/2025 la receta (y las órdenes de estudios) solo es válida si se emite por una plataforma registrada en ReNaPDiS (Res. 1959/2024 y 2214/2025). Sin eso, el odontólogo sale del sistema para prescribir y la historia clínica queda incompleta. DD-06 decidió cubrirlo **temprano vía partner registrado** y dejar la receta propia para F2; la regla dura 17 prohíbe cualquier otra vía.

La skill `dominio-cumplimiento` marca **RN-CU-03** como **pendiente**. El partner todavía no está elegido (PA-08/SU-08), así que este change construye el **puerto** y todo lo que lo rodea (modelo, API, RBAC, auditoría, configuración) con un adapter **simulado** para tests y demo, y un camino "no configurado" que responde `501` sin romper nada más. C-09 aporta la evolución a la que cada receta queda vinculada.

## What Changes

- **Puerto de partner de recetas** con adapters intercambiables: `fake` (simulado, para tests/desarrollo/demo) y "no configurado". El adapter real (Farmalink, Innovamed u otro) es un change posterior cuando se resuelva PA-08.
- **Emisión**: `POST /api/pacientes/{id}/recetas` emite una receta o una orden de estudio vinculada a una **evolución propia** del odontólogo (C-09), con los datos del paciente y del profesional (matrícula) tomados del servidor. Guarda el id externo, el partner y el enlace al PDF del partner. Reintento con la misma `clave_idempotencia` → devuelve la misma receta sin volver a emitir.
- **Consulta**: `GET /api/pacientes/{id}/recetas` (lista con enlaces al PDF) y `GET /api/pacientes/{id}/recetas/{rid}`. Funcionan aunque no haya partner configurado.
- **Sin partner configurado** → `501` con un mensaje claro de configuración; el resto del sistema sigue funcionando y el **boot nunca falla** por falta de `RECETAS_PARTNER_KEY`.
- **Partner simulado nunca en producción**: con `ENTORNO=produccion` el adapter `fake` se ignora (`501`). Las recetas simuladas quedan marcadas `simulada = true`, con id `FAKE-…` y un enlace no navegable.
- **Errores del partner**: caído o timeout → `502` reintentable sin guardar nada; rechazo de validación del partner → `422` con su motivo.
- **Inmutabilidad**: la receta emitida es un documento legal append-only (`fn_rechazar_mutacion()`); sin PUT/PATCH/DELETE (`405`). Anular en el partner queda fuera.
- **RBAC y consentimiento**: solo odontólogo emite (recepción → `403`, admin solo lee); `consentimiento_datos = true` obligatorio (`403`). Emisión y lecturas auditadas en `AuditoriaHC`.
- **Exportación**: las recetas se suman a la exportación del tenant de C-18.
- **Configuración**: `RECETAS_PARTNER`, `RECETAS_PARTNER_KEY` (opcional, secreta) y `ENTORNO` declaradas en settings (que usa `extra="forbid"`), con defaults seguros.
- Migración `010_recetas_externas` (`down_revision = "009_consentimientos_cumplimiento"`).

Las decisiones que la KB no resuelve están en `design.md` §"Decisiones tomadas (aprobación delegada del usuario, 2026-11-16)". Governance **ALTO**, cubierto por la aprobación del usuario del 2026-11-16.

## Non-goals

- Integración real con un partner (contrato HTTP, homologación, credenciales): depende de PA-08.
- Receta propia registrada en ReNaPDiS (F2, US-F2-02).
- Anulación, renovación o consulta de estado de una receta en el partner.
- Firma digital del profesional en nuestro sistema (la firma la hace el partner con el profesional registrado en su plataforma).
- Pantalla de recetas (la UI clínica es C-10; acá se usa Swagger).
- Validación de cobertura de obra social (etapa 2, DD-03).

## Capabilities

### New Capabilities

- `prescriptions`: emisión de recetas y órdenes de estudio vía partner registrado en ReNaPDiS, vinculadas a una evolución, inmutables, con RBAC clínico, auditoría, idempotencia, manejo de errores del partner y aislamiento por tenant.

### Modified Capabilities

- `platform-config`: se agrega la configuración del partner de recetas (adapter elegido por entorno, credencial opcional y secreta, simulado prohibido en producción, boot sin credencial).

## Impact

- Código nuevo:
  - `backend/app/infrastructure/recetas/` (`partner_client.py` con el puerto y los tipos, `fake.py`, `factory.py` que elige el adapter desde settings);
  - `backend/app/domain/recetas/` (`models.py`, `schemas.py`, `servicios.py`, `errores.py`);
  - `backend/app/api/recetas.py` (router registrado en `create_app()`);
  - `backend/alembic/versions/010_recetas_externas.py`.
- Código modificado (aditivo):
  - `backend/app/infrastructure/settings.py` (3 campos nuevos), `backend/.env.example` (placeholders `RECETAS_PARTNER=fake`, `ENTORNO=desarrollo`) y `backend/tests/test_env_example.py`;
  - `backend/app/domain/auditoria/models.py` / `writer.py` (entidad `receta`, allowlist);
  - registro de entidades exportables de C-18 (`backend/app/domain/cumplimiento/exportacion.py`): suma `recetas`;
  - `backend/app/main.py`.
- Reutiliza: `paciente_lectura` / `paciente_escritura`, `profesional_de_usuario` (solo import), `fn_rechazar_mutacion()`, `PacienteError`, `uq_evolucion_clinica_paciente_id` de la 008.
- **No toca** archivos de agenda, `openspec/changes/huecos-y-sobreturnos/` ni `openspec/changes/archive/2026-11-17-odontograma-evolucion/`.
- Sin dependencias nuevas (no hay llamada HTTP real todavía). Ningún secreto en el repo (regla 12).
- Depende de C-09 (evolución) y C-18 (migración 009 y registro de exportación).
