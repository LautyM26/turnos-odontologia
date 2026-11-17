# patients-web Specification

## Purpose
Gobierna cómo el staff encuentra a un paciente y gestiona sus datos administrativos y su consentimiento de datos desde el navegador, como puerta de entrada a la historia clínica.

## Requirements

### Requirement: Listado de pacientes paginado

El frontend SHALL mostrar en `/pacientes` los pacientes de la clínica (nombre y apellido, DNI, teléfono, obra social) desde `GET /api/pacientes`, de a una página, con "Cargar más" mientras exista `next_cursor`. Cada fila SHALL enlazar a `/pacientes/:id`.

#### Scenario: Listado inicial (happy path)

- **GIVEN** una clínica con 3 pacientes sintéticos
- **WHEN** un usuario del staff abre `/pacientes`
- **THEN** ve los 3 pacientes y cada nombre lleva a su detalle.

#### Scenario: Más de una página (borde)

- **GIVEN** una respuesta con `next_cursor`
- **WHEN** el usuario elige "Cargar más"
- **THEN** el frontend pide la página siguiente con `after_id` y agrega los pacientes sin repetir ninguno.

#### Scenario: Clínica sin pacientes (borde)

- **WHEN** la respuesta trae una lista vacía y no hay búsqueda activa
- **THEN** el frontend muestra un estado vacío que explica que todavía no hay pacientes cargados.

#### Scenario: Error del servidor (error de negocio)

- **WHEN** `GET /api/pacientes` falla con `500` o por red
- **THEN** el frontend muestra un mensaje de error con un botón "Reintentar" y no un listado vacío.

### Requirement: Búsqueda de pacientes

El frontend SHALL ofrecer un único campo de búsqueda que envíe `dni` si el texto son solo dígitos y puntos (7 u 8 dígitos), `telefono` si empieza con `+` o tiene 10 o más dígitos, y `q` en otro caso, solo con 3 o más caracteres. La búsqueda SHALL dispararse al enviar el formulario o tras una pausa de escritura y SHALL reflejarse en la URL (`?buscar=`).

#### Scenario: Búsqueda por apellido (happy path)

- **WHEN** el usuario escribe `perez`
- **THEN** el frontend pide `GET /api/pacientes?q=perez` y muestra los resultados.

#### Scenario: Búsqueda por DNI con puntos

- **WHEN** el usuario escribe `30.123.456`
- **THEN** el frontend pide `GET /api/pacientes?dni=30.123.456`.

#### Scenario: Texto demasiado corto (borde)

- **WHEN** el usuario escribe `pe`
- **THEN** el frontend no envía la búsqueda e indica que hacen falta al menos 3 caracteres.

#### Scenario: Sin resultados (borde)

- **WHEN** la búsqueda devuelve una lista vacía
- **THEN** el frontend muestra "No hay pacientes que coincidan con «texto»" y una forma de limpiar la búsqueda.

### Requirement: Encabezado del paciente

El frontend SHALL mostrar en `/pacientes/:id` un encabezado con nombre y apellido, DNI, contacto, obra social y el estado del consentimiento de datos, cargado de `GET /api/pacientes/{id}`, visible para todo el staff y en todas las pestañas.

#### Scenario: Paciente con consentimiento (happy path)

- **WHEN** el usuario abre el detalle de un paciente con `consentimiento_datos = true`
- **THEN** el encabezado muestra sus datos y "Consentimiento de datos: otorgado" con la fecha.

#### Scenario: Paciente sin consentimiento (borde)

- **WHEN** el paciente tiene `consentimiento_datos = false`
- **THEN** el encabezado muestra un aviso visible "Sin consentimiento de datos: no se pueden cargar datos de salud".

#### Scenario: Paciente inexistente o de otra clínica (error de negocio)

- **WHEN** `GET /api/pacientes/{id}` responde `404`
- **THEN** el frontend muestra "Paciente no encontrado" con un enlace de vuelta a `/pacientes` y no muestra pestañas.

### Requirement: Edición de datos administrativos

El frontend SHALL permitir a todo el staff editar nombre, apellido, DNI, email, teléfono, obra social, plan y número de afiliado con `PATCH /api/pacientes/{id}`, enviando solo los campos modificados, y SHALL mostrar como solo lectura el riesgo de ausencia, la fecha de alta y quién/cuándo registró el consentimiento.

#### Scenario: Cambio de teléfono (happy path)

- **WHEN** un recepcionista cambia el teléfono y guarda
- **THEN** el frontend envía solo `telefono`, muestra el valor normalizado que devuelve el servidor y confirma "Datos guardados".

#### Scenario: Error de validación del servidor (error de negocio)

- **WHEN** el `PATCH` responde `422` o `409` (DNI duplicado)
- **THEN** el frontend muestra el mensaje junto al formulario, conserva lo escrito y no marca los datos como guardados.

#### Scenario: Campo obligatorio vacío (borde)

- **WHEN** el usuario borra el nombre o el DNI
- **THEN** el frontend indica el campo como obligatorio y no envía el `PATCH`.

#### Scenario: Riesgo de ausencia no editable (borde)

- **WHEN** se muestra el formulario de datos
- **THEN** el riesgo de ausencia aparece como texto de solo lectura y nunca se envía en el `PATCH`.

### Requirement: Registro del consentimiento de datos

El frontend SHALL permitir otorgar o revocar el consentimiento de datos con `PATCH consentimiento_datos`, pidiendo una confirmación explícita que explique el efecto (revocar bloquea nuevas cargas de datos de salud sin borrar las existentes), y SHALL actualizar el encabezado y las pestañas clínicas con la respuesta.

#### Scenario: Otorgar consentimiento (happy path)

- **GIVEN** un paciente sin consentimiento
- **WHEN** el usuario confirma "Registrar consentimiento"
- **THEN** el frontend envía `consentimiento_datos = true`, el aviso del encabezado desaparece y los formularios clínicos se habilitan.

#### Scenario: Cancelar la confirmación (borde)

- **WHEN** el usuario cancela el diálogo de confirmación
- **THEN** el frontend no envía nada y el estado no cambia.
