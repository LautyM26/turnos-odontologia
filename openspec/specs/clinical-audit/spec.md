# clinical-audit Specification

## Purpose

Gobierna la auditoría de historia clínica (AuditoriaHC): un registro inmutable de quién hizo qué, sobre qué entidad y cuándo, para cada escritura de datos del paciente y cada acceso a datos clínicos, consultable solo por administradores.

## Requirements

### Requirement: Toda escritura de datos del paciente queda auditada

El sistema SHALL registrar un evento de auditoría por cada alta o edición de paciente, cambio de consentimiento, nueva versión de ficha y alta de adjunto, con actor (usuario), acción, entidad, id de entidad, paciente, clínica y fecha/hora TIMESTAMPTZ asignada por el servidor.

#### Scenario: Alta de paciente auditada

- **WHEN** un recepcionista crea un paciente
- **THEN** existe un evento `crear` sobre la entidad `paciente` con el id del recepcionista como actor y la fecha/hora del servidor.

#### Scenario: Nueva versión de ficha auditada

- **WHEN** un odontólogo crea la versión 2 de una ficha
- **THEN** existe un evento `actualizar` sobre la entidad `ficha` que referencia la versión 2 y lista los campos cambiados.

### Requirement: Accesos clínicos auditados

El sistema SHALL registrar un evento de auditoría por cada lectura de ficha, de su historial y por cada descarga de contenido de adjunto, con el usuario que accedió.

#### Scenario: Lectura de ficha auditada

- **WHEN** un odontólogo hace `GET /api/pacientes/{id}/ficha`
- **THEN** existe un evento `leer` sobre la entidad `ficha` con su id como actor.

#### Scenario: Descarga auditada

- **WHEN** un admin descarga el contenido de un adjunto
- **THEN** existe un evento `descargar` sobre la entidad `adjunto`.

### Requirement: Auditoría atómica con la operación

El sistema SHALL persistir el evento de auditoría en la misma transacción que la operación auditada: si el evento no puede registrarse, la operación SHALL fallar sin efectos.

#### Scenario: Falla al auditar

- **WHEN** la inserción del evento de auditoría falla durante una edición de ficha
- **THEN** la nueva versión de ficha no queda persistida y el cliente recibe un error.

### Requirement: Diff mínimo sin datos clínicos

El sistema SHALL guardar en el diff de cada evento solo nombres de campos cambiados, números de versión, ids y valores booleanos de consentimiento; nunca el texto de anamnesis, alergias o antecedentes, contenidos o nombres originales de archivos, ni valores de contacto.

#### Scenario: Diff de edición de ficha

- **WHEN** se audita una edición de alergias
- **THEN** el diff contiene `alergias` como campo cambiado y la versión, pero no el texto de las alergias.

#### Scenario: Diff de edición de contacto

- **WHEN** se audita un cambio de teléfono
- **THEN** el diff contiene `telefono` como campo cambiado pero no el número anterior ni el nuevo.

### Requirement: Auditoría inmutable a nivel base de datos

El sistema SHALL impedir modificar o borrar eventos de auditoría y versiones de ficha incluso con acceso SQL directo de la aplicación: `UPDATE`, `DELETE` y `TRUNCATE` sobre esas tablas SHALL fallar con error de base de datos.

#### Scenario: UPDATE directo rechazado

- **WHEN** se ejecuta `UPDATE` sobre un evento de auditoría con la conexión de la aplicación
- **THEN** la base de datos rechaza la sentencia y el evento queda intacto.

#### Scenario: DELETE de versión de ficha rechazado

- **WHEN** se ejecuta `DELETE` sobre una versión de ficha
- **THEN** la base de datos rechaza la sentencia y la versión persiste.

### Requirement: Sin endpoint de escritura de auditoría

El sistema SHALL no exponer ningún endpoint para crear, editar o borrar eventos de auditoría; los eventos SHALL generarse solo como efecto de las operaciones auditadas.

#### Scenario: Intento de escribir auditoría por API

- **WHEN** se envía `POST`, `PUT`, `PATCH` o `DELETE` a `/api/pacientes/{id}/auditoria`
- **THEN** el sistema responde `405` y no se crea ni altera ningún evento.

### Requirement: Consulta de auditoría solo admin

El sistema SHALL exponer `GET /api/pacientes/{id}/auditoria` solo al rol admin, con los eventos del paciente en la clínica del JWT en orden cronológico descendente y paginación por cursor; otros roles SHALL recibir `403`.

#### Scenario: Admin consulta auditoría

- **WHEN** un admin pide la auditoría de un paciente de su clínica
- **THEN** el sistema retorna los eventos del paciente sin eventos de otras clínicas.

#### Scenario: Odontólogo consulta auditoría

- **WHEN** un odontólogo sin rol admin pide la auditoría
- **THEN** el sistema responde `403`.
