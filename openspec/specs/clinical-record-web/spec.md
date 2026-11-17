# clinical-record-web Specification

## Purpose
Gobierna las pestañas clínicas del paciente en el navegador (ficha de anamnesis versionada y adjuntos) y los estados transversales que protegen la historia clínica en pantalla: sin acceso clínico para recepción, consentimiento requerido y carga de datos en paralelo.

## Requirements

### Requirement: Pestañas del paciente enlazables

El frontend SHALL organizar `/pacientes/:id` en las pestañas Ficha, Odontograma, Evoluciones y Adjuntos, cada una con su propia URL (`/pacientes/:id/ficha`, `/odontograma`, `/evoluciones`, `/adjuntos`), navegables con teclado y con la pestaña activa indicada de forma accesible. `/pacientes/:id` SHALL abrir la pestaña Ficha.

#### Scenario: Navegar entre pestañas (happy path)

- **WHEN** el usuario elige la pestaña Odontograma
- **THEN** la URL pasa a `/pacientes/:id/odontograma`, la pestaña queda marcada como actual y "Atrás" del navegador vuelve a la pestaña anterior.

#### Scenario: Enlace directo a una pestaña (borde)

- **WHEN** se abre `/pacientes/7/evoluciones` directamente
- **THEN** se muestra el paciente 7 con la pestaña Evoluciones activa.

### Requirement: Carga clínica en paralelo

Al abrir el detalle, el frontend SHALL pedir en paralelo, nunca en secuencia, el paciente (`GET /api/pacientes/{id}`), la historia consolidada (`GET /api/pacientes/{id}/historia`) y los profesionales de la clínica (`GET /api/catalogo/profesionales`). Un fallo de una parte SHALL afectar solo a las secciones que dependen de ella.

#### Scenario: Requests en paralelo (happy path)

- **WHEN** se abre `/pacientes/7`
- **THEN** las tres requests salen antes de que termine cualquiera de ellas y la ficha, el odontograma y las evoluciones se muestran con una sola carga de la historia.

#### Scenario: La historia falla pero el paciente carga (borde)

- **WHEN** `GET /historia` responde `500` y `GET /pacientes/{id}` responde `200`
- **THEN** el encabezado y los datos administrativos se muestran, y las pestañas clínicas muestran un error con "Reintentar".

### Requirement: Sin acceso clínico para recepción

Cuando un endpoint clínico responde `403` por rol, el frontend SHALL mostrar en las pestañas Ficha (sección clínica), Odontograma, Evoluciones y Adjuntos el mensaje "Sin acceso clínico: tu rol no permite ver la historia clínica" sin datos clínicos ni error genérico, y SHALL mantener visibles los datos administrativos y de obra social (regla dura 16).

#### Scenario: Recepcionista abre el odontograma (error de negocio)

- **GIVEN** un usuario recepcionista
- **WHEN** abre `/pacientes/7/odontograma` y `/historia` responde `403`
- **THEN** ve el mensaje de sin acceso clínico, no ve el SVG del odontograma ni ninguna evolución, y el encabezado del paciente sigue visible.

#### Scenario: Recepcionista edita contacto (borde)

- **GIVEN** un usuario recepcionista en la pestaña Ficha
- **WHEN** edita el teléfono del paciente
- **THEN** puede guardarlo, aunque la sección de anamnesis muestre el mensaje de sin acceso clínico.

### Requirement: Acciones clínicas solo para odontólogo

El frontend SHALL mostrar los controles de escritura clínica (editar anamnesis, guardar odontograma, nueva evolución, corregir, subir adjunto) solo a usuarios con rol odontólogo; un admin sin ese rol SHALL ver la historia en modo lectura. Si igual llega un `403` a una escritura, SHALL mostrar el motivo devuelto por el servidor.

#### Scenario: Admin sin rol odontólogo (borde)

- **WHEN** un admin sin rol odontólogo abre la pestaña Evoluciones
- **THEN** ve la timeline pero no el formulario "Nueva evolución" ni botones "Corregir".

#### Scenario: Escritura rechazada por el servidor (error de negocio)

- **WHEN** un guardado clínico responde `403`
- **THEN** el frontend muestra el `detail` del servidor y conserva lo escrito.

### Requirement: Escritura clínica bloqueada sin consentimiento

Si el paciente tiene `consentimiento_datos = false`, el frontend SHALL deshabilitar los controles de escritura clínica con un aviso que explique que falta el consentimiento, y SHALL seguir mostrando los datos clínicos existentes. Un `403` de consentimiento devuelto por el servidor SHALL mostrar el mismo aviso.

#### Scenario: Paciente sin consentimiento (error de negocio)

- **GIVEN** un odontólogo y un paciente sin consentimiento con evoluciones previas
- **WHEN** abre la pestaña Evoluciones
- **THEN** ve las evoluciones existentes y el formulario de alta deshabilitado con el aviso de consentimiento faltante.

#### Scenario: Consentimiento revocado mientras se edita (borde)

- **WHEN** el servidor responde `403` "Falta el consentimiento de datos del paciente" a un guardado
- **THEN** el frontend muestra el aviso de consentimiento, conserva lo escrito y deshabilita el guardado.

### Requirement: Ficha de anamnesis versionada

La pestaña Ficha SHALL mostrar anamnesis, alergias y antecedentes de la versión vigente con su número, autor y fecha, y SHALL permitir al odontólogo editarlos con `PUT /api/pacientes/{id}/ficha` enviando `version_esperada` igual a la versión que cargó. Guardar SHALL crear una versión nueva; la UI SHALL no ofrecer borrar versiones.

#### Scenario: Primera carga de ficha (happy path)

- **GIVEN** un paciente con ficha en versión 0
- **WHEN** el odontólogo completa las alergias y guarda
- **THEN** el frontend envía `version_esperada = 0` y muestra "Versión 1" con su autor y la fecha.

#### Scenario: Ficha vacía (borde)

- **WHEN** la ficha está en versión 0 y el usuario no puede editarla
- **THEN** el frontend muestra "Sin anamnesis registrada" en lugar de campos vacíos.

#### Scenario: Otro usuario guardó antes (error de negocio)

- **WHEN** el `PUT` responde `409`
- **THEN** el frontend muestra "La ficha cambió mientras la editabas" con la opción "Recargar versión vigente", conserva lo escrito hasta que el usuario elija recargar y no crea versión.

### Requirement: Historial de versiones de la ficha

La pestaña Ficha SHALL ofrecer "Ver versiones anteriores", que cargue `GET /api/pacientes/{id}/ficha/versiones` y las muestre de la más reciente a la más antigua, con número, autor, fecha y contenido, en solo lectura.

#### Scenario: Consulta del historial (happy path)

- **GIVEN** una ficha con 3 versiones
- **WHEN** el usuario abre "Ver versiones anteriores"
- **THEN** ve las versiones 3, 2 y 1 con autor y fecha, sin controles de edición.

### Requirement: Listado y descarga de adjuntos

La pestaña Adjuntos SHALL listar los adjuntos del paciente con tipo (foto o PDF), tamaño legible, autor y fecha, y SHALL descargarlos con la sesión autenticada desde `GET /adjuntos/{id}/contenido`, sin exponer el token en la URL.

#### Scenario: Paciente con adjuntos (happy path)

- **WHEN** el paciente tiene una foto y un PDF
- **THEN** la pestaña lista ambos con su tipo, tamaño en KB/MB, autor y fecha, y cada uno tiene "Descargar".

#### Scenario: Paciente sin adjuntos (borde)

- **WHEN** la lista está vacía
- **THEN** la pestaña muestra un estado vacío que indica qué tipos de archivo se aceptan.

### Requirement: Subida de adjuntos con validación

El frontend SHALL subir un archivo por vez con `POST /adjuntos` como `multipart` con el único campo `file`, SHALL rechazar antes de enviar un tipo distinto de JPEG, PNG o PDF o un tamaño mayor a 10 MB, y SHALL traducir `413`, `415` y `422` del servidor a mensajes claros.

#### Scenario: Subida válida (happy path)

- **WHEN** el odontólogo elige un PDF sintético de 200 KB
- **THEN** el frontend muestra "Subiendo…" con el botón deshabilitado, el adjunto aparece primero en la lista y se confirma "Adjunto subido".

#### Scenario: Tipo de archivo inválido (error de negocio)

- **WHEN** el usuario elige un archivo `.docx`
- **THEN** el frontend muestra "Solo se aceptan fotos JPG/PNG o PDF" y no envía la request.

#### Scenario: El servidor rechaza el contenido (borde)

- **WHEN** el servidor responde `415` a un archivo con extensión `.pdf` cuyo contenido no es PDF
- **THEN** el frontend muestra "El contenido del archivo no es una foto ni un PDF válido" y la lista no cambia.

#### Scenario: Archivo demasiado grande (borde)

- **WHEN** el servidor responde `413`
- **THEN** el frontend muestra "El archivo supera el tamaño máximo permitido" y la lista no cambia.
