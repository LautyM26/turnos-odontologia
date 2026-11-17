# Spec Delta — admin-audit

## Purpose

Deja una traza inmutable de las acciones administrativas que no pertenecen a un paciente (alta de usuarios, cambios de roles, exportaciones), para responder quién hizo qué y cuándo ante la Ley 25.326.

## ADDED Requirements

### Requirement: Eventos administrativos registrados

El sistema SHALL registrar un evento administrativo con clínica, actor, acción (`usuario_crear`, `usuario_roles`, `exportar`), id de la entidad afectada cuando exista, un diff mínimo sin datos de pacientes ni contraseñas, IP y fecha/hora del servidor, en la misma transacción que la operación.

#### Scenario: Alta de usuario auditada

- **WHEN** un admin crea un usuario
- **THEN** existe un evento `usuario_crear` con el admin como actor, el id del usuario creado y sus roles, sin email ni contraseña en el diff.

#### Scenario: Cambio de roles auditado

- **WHEN** un admin cambia los roles de un usuario
- **THEN** existe un evento `usuario_roles` con los roles anteriores y los nuevos.

#### Scenario: Falla al auditar revierte la operación (borde)

- **WHEN** el registro del evento falla durante un cambio de roles
- **THEN** el cambio de roles no queda aplicado.

### Requirement: Auditoría administrativa inmutable

El sistema SHALL rechazar a nivel base de datos todo UPDATE, DELETE o TRUNCATE sobre los eventos administrativos, y la API SHALL NOT exponer ningún endpoint para escribirlos o borrarlos.

#### Scenario: UPDATE rechazado

- **WHEN** una sentencia SQL intenta modificar un evento administrativo
- **THEN** la base rechaza la sentencia y el evento persiste sin cambios.

#### Scenario: TRUNCATE rechazado

- **WHEN** se intenta `TRUNCATE` de la tabla de eventos administrativos
- **THEN** la base rechaza la sentencia.

#### Scenario: Sin rutas de escritura (borde)

- **WHEN** se recorren las rutas de la API
- **THEN** ninguna permite crear, modificar o borrar eventos administrativos.

### Requirement: Eventos administrativos aislados por clínica

El sistema SHALL guardar cada evento con `clinica_id` e índice `(clinica_id, created_at)`, y el actor SHALL pertenecer a la misma clínica.

#### Scenario: Actor de otra clínica rechazado por la base

- **WHEN** se inserta un evento de la clínica A con un actor de la clínica B
- **THEN** la base rechaza la fila por la FK compuesta.

#### Scenario: Consulta cruzada

- **WHEN** se consultan eventos filtrando por la clínica A
- **THEN** no aparece ningún evento de la clínica B (0 filas cruzadas).

#### Scenario: Evento sin entidad (borde)

- **WHEN** se registra un evento `exportar`
- **THEN** se guarda con entidad nula y los conteos en el diff.
