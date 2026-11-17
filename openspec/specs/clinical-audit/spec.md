# clinical-audit Specification

## Purpose

Gobierna la auditoría de historia clínica (AuditoriaHC): un registro inmutable de quién hizo qué, sobre qué entidad y cuándo, para cada escritura de datos del paciente y cada acceso a datos clínicos, consultable solo por administradores.

## Requirements

### Requirement: Toda escritura de datos del paciente queda auditada

El sistema SHALL registrar un evento de auditoría por cada alta o edición de paciente, cambio de consentimiento, nueva versión de ficha, alta de adjunto, nueva versión de odontograma, alta de evolución y corrección de evolución (acción `corregir`), con actor (usuario), acción, entidad, id de entidad, paciente, clínica y fecha/hora TIMESTAMPTZ asignada por el servidor.

#### Scenario: Alta de paciente auditada

- **WHEN** un recepcionista crea un paciente
- **THEN** existe un evento `crear` sobre la entidad `paciente` con el id del recepcionista como actor y la fecha/hora del servidor.

#### Scenario: Nueva versión de ficha auditada

- **WHEN** un odontólogo crea la versión 2 de una ficha
- **THEN** existe un evento `actualizar` sobre la entidad `ficha` que referencia la versión 2 y lista los campos cambiados.

#### Scenario: Nueva versión de odontograma auditada

- **WHEN** un odontólogo guarda la versión 2 de un odontograma cambiando las piezas `16` y `21`
- **THEN** existe un evento `actualizar` sobre la entidad `odontograma` con el id de la versión 2, el número de versión y los códigos `16` y `21` como campos cambiados, sin estados ni caras.

#### Scenario: Alta y corrección de evolución auditadas

- **WHEN** un odontólogo registra la evolución E1 y luego la corrige con E2
- **THEN** existen un evento `crear` sobre la entidad `evolucion` con id E1 y un evento `corregir` sobre la entidad `evolucion` con id E2 que referencia `corrige_a_id = E1`.

#### Scenario: Escritura clínica rechazada no deja evento (borde)

- **WHEN** un alta de evolución o un guardado de odontograma termina en `403`, `409` o `422`
- **THEN** no se registra ningún evento de escritura para esa operación.

### Requirement: Accesos clínicos auditados

El sistema SHALL registrar un evento de auditoría por cada lectura de ficha, de su historial, de odontograma (vigente o historial), de evoluciones (listado o una sola) y de la historia consolidada, y por cada descarga de contenido de adjunto, con el usuario que accedió.

#### Scenario: Lectura de ficha auditada

- **WHEN** un odontólogo hace `GET /api/pacientes/{id}/ficha`
- **THEN** existe un evento `leer` sobre la entidad `ficha` con su id como actor.

#### Scenario: Descarga auditada

- **WHEN** un admin descarga el contenido de un adjunto
- **THEN** existe un evento `descargar` sobre la entidad `adjunto`.

#### Scenario: Lectura de evoluciones y odontograma auditada

- **WHEN** un admin pide las evoluciones y el odontograma actual de un paciente
- **THEN** existen un evento `leer` sobre la entidad `evolucion` y otro sobre la entidad `odontograma`, ambos con el admin como actor.

#### Scenario: Lectura de la historia consolidada auditada

- **WHEN** un odontólogo pide `GET /api/pacientes/{id}/historia`
- **THEN** existe un evento `leer` sobre la entidad `paciente` cuyo diff lista `ficha`, `odontograma` y `evoluciones` como campos leídos.

### Requirement: Auditoría atómica con la operación

El sistema SHALL persistir el evento de auditoría en la misma transacción que la operación auditada: si el evento no puede registrarse, la operación SHALL fallar sin efectos.

#### Scenario: Falla al auditar

- **WHEN** la inserción del evento de auditoría falla durante una edición de ficha
- **THEN** la nueva versión de ficha no queda persistida y el cliente recibe un error.

### Requirement: Diff mínimo sin datos clínicos

El sistema SHALL guardar en el diff de cada evento solo nombres de campos cambiados (o códigos FDI de piezas cambiadas), números de versión, ids y valores booleanos de consentimiento; nunca el texto de anamnesis, alergias, antecedentes o evoluciones, ni estados o caras del odontograma, ni contenidos o nombres originales de archivos, ni valores de contacto.

#### Scenario: Diff de edición de ficha

- **WHEN** se audita una edición de alergias
- **THEN** el diff contiene `alergias` como campo cambiado y la versión, pero no el texto de las alergias.

#### Scenario: Diff de edición de contacto

- **WHEN** se audita un cambio de teléfono
- **THEN** el diff contiene `telefono` como campo cambiado pero no el número anterior ni el nuevo.

#### Scenario: Diff de evolución sin texto clínico

- **WHEN** se audita el alta o la corrección de una evolución
- **THEN** el diff contiene solo ids (`evolucion_id` y, si corresponde, `corrige_a_id`), sin el texto ni el motivo de corrección.

### Requirement: Auditoría inmutable a nivel base de datos

El sistema SHALL impedir modificar o borrar eventos de auditoría, versiones de ficha, versiones de odontograma y evoluciones incluso con acceso SQL directo de la aplicación: `UPDATE`, `DELETE` y `TRUNCATE` sobre esas tablas SHALL fallar con error de base de datos.

#### Scenario: UPDATE directo rechazado

- **WHEN** se ejecuta `UPDATE` sobre un evento de auditoría con la conexión de la aplicación
- **THEN** la base de datos rechaza la sentencia y el evento queda intacto.

#### Scenario: DELETE de versión de ficha rechazado

- **WHEN** se ejecuta `DELETE` sobre una versión de ficha
- **THEN** la base de datos rechaza la sentencia y la versión persiste.

#### Scenario: Mutación de evolución u odontograma rechazada

- **WHEN** se ejecuta `UPDATE`, `DELETE` o `TRUNCATE` sobre la tabla de evoluciones o la de odontogramas
- **THEN** la base de datos rechaza la sentencia y las filas persisten.

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

### Requirement: Consentimientos auditados en la auditoría clínica

El sistema SHALL registrar en la auditoría clínica, en la misma transacción, un evento `crear` al generar un consentimiento y un evento `firmar` al firmarlo (entidad `consentimiento`), y un evento `leer` por cada listado o detalle consultado, con diff limitado a ids y versión de texto, sin el texto ni los datos del firmante.

#### Scenario: Generación y firma auditadas

- **WHEN** un odontólogo genera el consentimiento C1 y luego lo firma
- **THEN** existen un evento `crear` y un evento `firmar` sobre la entidad `consentimiento` con id C1, su usuario como actor y la fecha del servidor.

#### Scenario: Lectura auditada

- **WHEN** un admin consulta el detalle de un consentimiento
- **THEN** existe un evento `leer` sobre la entidad `consentimiento` con ese id.

#### Scenario: Firma incompleta sin evento (borde)

- **WHEN** una firma termina en `422`, `409` o `403`
- **THEN** no existe evento `firmar` para esa request y el diff de los eventos existentes no contiene `firmante_nombre`, `firmante_dni` ni el texto.
