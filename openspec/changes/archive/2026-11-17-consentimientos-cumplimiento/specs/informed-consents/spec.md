# Spec Delta — informed-consents

## Purpose

Permite al odontólogo generar consentimientos de tratamiento con un texto versionado e inmutable y registrar la firma electrónica del paciente con una constancia verificable (fecha, IP, dispositivo, hash), dejando el documento bloqueado (RN-CU-02, Ley 25.506).

## ADDED Requirements

### Requirement: Generación de consentimiento con texto versionado

El sistema SHALL crear un consentimiento `pendiente` para un paciente a partir de un tipo del catálogo cerrado, copiando en el documento el texto exacto de la versión vigente de ese tipo, su número de versión y su hash SHA-256 calculado por el servidor, con autor y fecha/hora del servidor.

#### Scenario: Consentimiento generado

- **WHEN** un odontólogo hace `POST /api/pacientes/{id}/consentimientos` con `tipo = "extraccion"` para un paciente con `consentimiento_datos = true`
- **THEN** el sistema responde `201` con estado `pendiente`, `documento_bloqueado = false`, el texto de la versión vigente del tipo, su `texto_version`, su `texto_hash` SHA-256 en hexadecimal y la fecha del servidor.

#### Scenario: Tipo inexistente

- **WHEN** el cuerpo trae un `tipo` fuera del catálogo
- **THEN** el sistema responde `422` y no crea el consentimiento.

#### Scenario: Campos de servidor en el cuerpo (borde)

- **WHEN** el cuerpo trae `texto`, `texto_hash`, `fecha` o `autor_usuario_id`
- **THEN** el sistema responde `422` por campo no declarado y no crea nada.

### Requirement: Hash del texto exacto

El sistema SHALL calcular el hash como SHA-256 de los bytes UTF-8 del texto exacto guardado en el documento, de modo que cualquiera pueda recalcularlo a partir del texto devuelto por la API y obtener el mismo valor.

#### Scenario: Hash verificable

- **WHEN** se recalcula SHA-256 sobre el `texto` devuelto por `GET /api/pacientes/{id}/consentimientos/{cid}`
- **THEN** el resultado coincide con `texto_hash` del documento y con el hash de la constancia de firma.

#### Scenario: Textos distintos, hashes distintos

- **WHEN** se generan consentimientos de dos tipos con textos distintos
- **THEN** sus `texto_hash` son distintos.

#### Scenario: Espacios y acentos cuentan (borde)

- **WHEN** dos textos difieren solo en un espacio final o en una tilde
- **THEN** sus hashes son distintos (no se normaliza el texto antes de hashear).

### Requirement: Firma electrónica con constancia

El sistema SHALL registrar la firma de un consentimiento pendiente con una constancia que incluya fecha/hora del servidor (TIMESTAMPTZ), IP del cliente, dispositivo (user-agent), hash del texto firmado, nombre y DNI del firmante y el usuario que asistió la firma; la firma SHALL dejar el documento bloqueado.

#### Scenario: Firma completa

- **WHEN** un odontólogo hace `POST /api/pacientes/{id}/consentimientos/{cid}/firmar` con `acepta = true`, `firmante_nombre`, `firmante_dni` y el `texto_hash` mostrado
- **THEN** el sistema responde `201` con la constancia (fecha del servidor, IP, user-agent, hash, firmante) y el documento queda `firmado` con `documento_bloqueado = true`.

#### Scenario: Hash mostrado no coincide

- **WHEN** el `texto_hash` enviado no coincide con el hash del documento
- **THEN** el sistema responde `409` indicando que el texto mostrado no es el del documento y el documento sigue `pendiente`.

#### Scenario: Sin user-agent (borde)

- **WHEN** la firma llega sin header `User-Agent`
- **THEN** la constancia guarda el dispositivo como `no-informado` y la firma se registra igual.

### Requirement: Firma incompleta reintentable

El sistema SHALL rechazar con `422` y `reintentable = true` una firma sin aceptación expresa o sin datos del firmante, sin registrar constancia y dejando el documento `pendiente` para reintentar (Flujo 8).

#### Scenario: Sin aceptación

- **WHEN** la firma llega con `acepta = false` o sin `acepta`
- **THEN** el sistema responde `422` con `reintentable = true` y el documento sigue `pendiente` y sin constancia.

#### Scenario: Reintento exitoso

- **WHEN** después de una firma incompleta se envía la firma completa
- **THEN** el sistema responde `201` y existe exactamente una constancia.

#### Scenario: DNI del firmante inválido (borde)

- **WHEN** `firmante_dni` no tiene entre 7 y 8 dígitos o `firmante_nombre` está vacío
- **THEN** el sistema responde `422` con `reintentable = true` sin constancia.

### Requirement: Documento firmado bloqueado

El sistema SHALL impedir toda modificación o borrado de un consentimiento y de su constancia: la API no expone PUT/PATCH/DELETE y la base rechaza UPDATE, DELETE y TRUNCATE sobre ambas tablas; un documento firmado no puede volver a firmarse.

#### Scenario: Segunda firma rechazada

- **WHEN** se firma un consentimiento ya firmado
- **THEN** el sistema responde `409` y la constancia original no cambia.

#### Scenario: Métodos de edición no expuestos

- **WHEN** se hace `PUT`, `PATCH` o `DELETE` sobre `/api/pacientes/{id}/consentimientos/{cid}`
- **THEN** el sistema responde `405` y el documento no cambia.

#### Scenario: Mutación directa en la base (borde)

- **WHEN** una sentencia SQL intenta `UPDATE` o `DELETE` sobre un consentimiento o una constancia
- **THEN** la base rechaza la sentencia y la fila persiste sin cambios.

#### Scenario: Firmas concurrentes (borde)

- **WHEN** dos firmas completas del mismo consentimiento llegan a la vez
- **THEN** una responde `201`, la otra `409` y existe una sola constancia.

### Requirement: Consulta de consentimientos

El sistema SHALL listar los consentimientos de un paciente (más recientes primero) y devolver el detalle de uno con su texto, estado, `documento_bloqueado` y la constancia si está firmado, solo para la clínica del usuario.

#### Scenario: Listado con estados

- **WHEN** un admin pide `GET /api/pacientes/{id}/consentimientos` de un paciente con uno firmado y uno pendiente
- **THEN** recibe ambos con su estado y `documento_bloqueado` correctos.

#### Scenario: Consentimiento de otro paciente

- **WHEN** se pide un `cid` que pertenece a otro paciente de la misma clínica
- **THEN** el sistema responde `404`.

#### Scenario: Paciente sin consentimientos (borde)

- **WHEN** se lista un paciente sin consentimientos
- **THEN** el sistema responde `200` con una lista vacía.

### Requirement: RBAC y consentimiento de datos en consentimientos

El sistema SHALL permitir generar y firmar solo al odontólogo vinculado al paciente con `consentimiento_datos = true`, y leer solo a admin y odontólogo; recepcionista SHALL recibir `403` en todas las rutas de consentimientos.

#### Scenario: Recepción sin acceso

- **WHEN** un recepcionista llama a cualquier ruta de `/api/pacientes/{id}/consentimientos`
- **THEN** el sistema responde `403` y no crea ni audita nada.

#### Scenario: Paciente sin consentimiento de datos

- **WHEN** un odontólogo genera o firma un consentimiento de un paciente con `consentimiento_datos = false`
- **THEN** el sistema responde `403` antes de validar el cuerpo y no persiste nada.

#### Scenario: Admin solo lee (borde)

- **WHEN** un admin intenta generar o firmar un consentimiento
- **THEN** el sistema responde `403`.

### Requirement: Consentimientos aislados por clínica

El sistema SHALL guardar cada consentimiento y constancia con `clinica_id` e índice por `(clinica_id, …)`, y ninguna consulta SHALL devolver documentos de otra clínica.

#### Scenario: Paciente de otra clínica

- **WHEN** un odontólogo de la clínica A pide los consentimientos de un paciente de la clínica B
- **THEN** el sistema responde `404`.

#### Scenario: Consulta cruzada en la base

- **WHEN** se consultan consentimientos y constancias filtrando por la clínica A con ids de la clínica B
- **THEN** el resultado tiene 0 filas.

#### Scenario: Firma con id de otra clínica (borde)

- **WHEN** un odontólogo de la clínica A firma un `cid` de la clínica B usando un paciente propio
- **THEN** el sistema responde `404` y no crea constancia.
