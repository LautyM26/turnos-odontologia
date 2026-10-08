# clinical-record Specification

## Purpose

Gobierna los datos clínicos base del paciente en el MVP: la ficha de anamnesis (anamnesis, alergias, antecedentes) versionada sin pérdida de historia y los adjuntos clínicos simples (fotos y PDFs), ambos protegidos por el consentimiento de datos.

## Requirements

### Requirement: Ficha de anamnesis versionada append-only

El sistema SHALL mantener una única ficha vigente por paciente compuesta por anamnesis, alergias y antecedentes, donde cada edición crea una nueva versión numerada con autor y fecha/hora; ninguna versión previa SHALL modificarse ni borrarse (RN-CL-02, Ley 26.529).

#### Scenario: Primera carga de ficha

- **WHEN** un odontólogo hace `PUT /api/pacientes/{id}/ficha` con `version_esperada=0` en un paciente con consentimiento
- **THEN** el sistema crea la versión 1 con el usuario autor y responde `200` con la ficha vigente.

#### Scenario: Edición conserva la versión anterior

- **WHEN** el odontólogo edita las alergias con `version_esperada=1`
- **THEN** el sistema crea la versión 2, `GET /ficha` devuelve la versión 2 y la versión 1 sigue disponible sin cambios en el historial.

#### Scenario: Paciente sin ficha

- **WHEN** se pide `GET /api/pacientes/{id}/ficha` de un paciente sin versiones
- **THEN** el sistema responde `200` con `version = 0` y campos vacíos.

### Requirement: Control de concurrencia de la ficha

El sistema SHALL rechazar con `409` una edición de ficha cuyo `version_esperada` no coincida con la versión vigente, incluso ante dos ediciones concurrentes sobre la misma versión, sin crear versiones duplicadas.

#### Scenario: Edición sobre versión vieja

- **WHEN** se hace PUT con `version_esperada=1` y la vigente ya es la 2
- **THEN** el sistema responde `409` y no crea versión nueva.

#### Scenario: Dos ediciones simultáneas

- **WHEN** dos requests PUT con `version_esperada=2` llegan en paralelo
- **THEN** exactamente una crea la versión 3 y la otra recibe `409`.

### Requirement: Historial de versiones de la ficha

El sistema SHALL exponer `GET /api/pacientes/{id}/ficha/versiones` con todas las versiones de la ficha en orden descendente, cada una con número, autor, fecha/hora y contenido.

#### Scenario: Consulta del historial

- **WHEN** un usuario con lectura clínica pide el historial de una ficha con 3 versiones
- **THEN** el sistema retorna las versiones 3, 2 y 1 con su autor y fecha.

### Requirement: Gate de consentimiento para datos de salud

El sistema SHALL rechazar con `403` toda carga de datos de salud (crear versión de ficha o subir adjunto) de un paciente con `consentimiento_datos = false` (Ley 25.326, RN-CU-01), sin persistir nada.

#### Scenario: Ficha sin consentimiento

- **WHEN** un odontólogo hace PUT de ficha de un paciente con `consentimiento_datos = false`
- **THEN** el sistema responde `403` indicando que falta el consentimiento y no crea versión.

#### Scenario: Adjunto sin consentimiento

- **WHEN** un odontólogo sube un adjunto a un paciente sin consentimiento
- **THEN** el sistema responde `403` y no almacena el archivo.

### Requirement: Adjuntos limitados a foto o PDF

El sistema SHALL aceptar adjuntos solo de tipo JPEG, PNG o PDF determinados por el contenido real del archivo (firma de bytes), no por la extensión ni por el content-type declarado; otro tipo, o un content-type declarado que no coincida con el contenido, SHALL responder `415` sin almacenar nada.

#### Scenario: Foto válida

- **WHEN** un odontólogo sube un JPEG a un paciente con consentimiento
- **THEN** el sistema responde `201` con metadatos (id, tipo `foto`, MIME, tamaño, hash SHA-256, autor, fecha).

#### Scenario: Ejecutable renombrado

- **WHEN** se sube un archivo ejecutable renombrado a `radiografia.pdf` con content-type `application/pdf`
- **THEN** el sistema responde `415` y no almacena el archivo.

#### Scenario: Tipo no permitido

- **WHEN** se sube un archivo DOCX, GIF o DICOM
- **THEN** el sistema responde `415`.

### Requirement: Límite de tamaño de adjuntos

El sistema SHALL rechazar con `413` todo adjunto que supere el tamaño máximo configurado, midiendo los bytes efectivamente recibidos y no solo el header declarado, sin dejar archivo ni registro parcial.

#### Scenario: Archivo excedido

- **WHEN** se sube un PDF de un byte más que el máximo configurado
- **THEN** el sistema responde `413` y no queda archivo en el storage ni fila de adjunto.

#### Scenario: Archivo vacío

- **WHEN** se sube un archivo de 0 bytes
- **THEN** el sistema responde `422`.

### Requirement: Listado y descarga segura de adjuntos

El sistema SHALL listar los metadatos de adjuntos del paciente y SHALL servir su contenido solo por endpoint autenticado, como descarga (`attachment`) con el MIME detectado y sin permitir interpretación de tipo por el navegador; las rutas de almacenamiento SHALL no derivarse del nombre de archivo provisto por el cliente.

#### Scenario: Descarga de adjunto propio

- **WHEN** un usuario con lectura clínica pide el contenido de un adjunto del paciente
- **THEN** el sistema responde `200` con el contenido, `Content-Disposition: attachment` y `X-Content-Type-Options: nosniff`.

#### Scenario: Nombre de archivo malicioso

- **WHEN** se sube un archivo llamado `../../etc/passwd.png` con contenido PNG válido
- **THEN** el sistema lo almacena bajo una clave generada por el servidor dentro del directorio de adjuntos y no escribe fuera de él.

#### Scenario: Adjunto de otra clínica

- **WHEN** se pide el contenido de un adjunto que pertenece a otra clínica
- **THEN** el sistema responde `404`.

### Requirement: Adjunto opcionalmente ligado a evolución

El sistema SHALL asociar cada adjunto a un paciente y SHALL reservar la asociación opcional a una evolución clínica, que no se acepta por API hasta que exista la entidad Evolución.

#### Scenario: Intento de vincular evolución antes de que exista

- **WHEN** se sube un adjunto enviando `evolucion_id`
- **THEN** el sistema responde `422`.
