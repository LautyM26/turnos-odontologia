# Spec Delta — data-export

## Purpose

Garantiza que el consultorio pueda llevarse en cualquier momento, sin costo ni retención, una copia completa y portable de todos sus datos existentes en el sistema, aislada de las demás clínicas (RN-CU-04, US-014).

## ADDED Requirements

### Requirement: Exportación completa en ZIP de CSV

El sistema SHALL responder a `GET /api/admin/exportacion?formato=csv` con un archivo ZIP descargable que contenga un CSV por entidad existente del tenant (pacientes, fichas, adjuntos, odontogramas, evoluciones, consentimientos, firmas, turnos, historial de turnos, catálogo, usuarios y auditoría clínica), los archivos de los adjuntos y un `manifest.json`.

#### Scenario: Exportación de una clínica con datos

- **WHEN** un admin pide la exportación de una clínica con pacientes, ficha, odontograma, evoluciones, turnos y un consentimiento firmado
- **THEN** recibe `200` con `Content-Type: application/zip`, `Content-Disposition: attachment` y un ZIP con un CSV por entidad cuyas filas coinciden en cantidad con las de la base para esa clínica, más los archivos de adjuntos y el `manifest.json`.

#### Scenario: Clínica sin datos clínicos (borde)

- **WHEN** un admin exporta una clínica sin pacientes
- **THEN** recibe un ZIP válido donde cada CSV tiene solo la fila de encabezados y el manifest declara 0 filas para esas entidades.

#### Scenario: Formato PDF no soportado

- **WHEN** se pide `formato=pdf` o un formato desconocido
- **THEN** el sistema responde `422` indicando que el formato soportado es `csv` y no registra una exportación.

### Requirement: Manifest de la exportación

El ZIP SHALL incluir un `manifest.json` con la clínica, la fecha/hora de generación del servidor (ISO 8601 con zona), la versión de esquema, la cantidad de filas por entidad y la lista de entidades excluidas con su motivo (caja, cobros y facturas: aún no existen).

#### Scenario: Conteos y exclusiones declarados

- **WHEN** se abre el `manifest.json` de una exportación
- **THEN** declara la cantidad de filas de cada CSV y lista `caja` y `facturas` como excluidas porque todavía no existen en el sistema.

#### Scenario: Conteo coincide con el CSV

- **WHEN** se cuentan las filas de datos de `pacientes.csv`
- **THEN** coinciden con el conteo del manifest para `pacientes`.

#### Scenario: Fechas con zona (borde)

- **WHEN** se lee una columna de fecha/hora en cualquier CSV
- **THEN** está en ISO 8601 con desplazamiento horario (nunca hora local sin zona).

### Requirement: Exportación sin secretos y segura para planillas

El sistema SHALL excluir de la exportación los hashes de contraseña y cualquier credencial, y SHALL neutralizar celdas que empiecen con `=`, `+`, `-` o `@` para que una planilla no las ejecute como fórmula; los CSV SHALL ser UTF-8 con BOM.

#### Scenario: Usuarios sin hash

- **WHEN** se lee `usuarios.csv`
- **THEN** no existe ninguna columna de contraseña ni hash.

#### Scenario: Inyección de fórmulas neutralizada

- **WHEN** un paciente sintético tiene un nombre que empieza con `=`
- **THEN** la celda exportada empieza con un apóstrofo seguido del texto original.

#### Scenario: Acentos y comas (borde)

- **WHEN** un texto tiene tildes, `ñ`, comas, comillas y saltos de línea
- **THEN** el CSV lo conserva y una planilla lo abre en una sola celda, sin caracteres corruptos.

### Requirement: Exportación aislada por clínica y solo admin

El sistema SHALL exportar únicamente los datos de la clínica del admin autenticado y SHALL rechazar con `403` a cualquier otro rol.

#### Scenario: Nada de otra clínica

- **WHEN** existen las clínicas A y B con datos y un admin de A exporta
- **THEN** ningún CSV ni archivo del ZIP contiene ids, pacientes ni adjuntos de la clínica B (0 filas cruzadas).

#### Scenario: Odontólogo o recepcionista

- **WHEN** un odontólogo o un recepcionista pide la exportación
- **THEN** el sistema responde `403` y no genera ningún archivo.

#### Scenario: Adjunto con archivo faltante (borde)

- **WHEN** un adjunto tiene fila pero su archivo no está en el almacenamiento
- **THEN** la exportación se completa, el CSV conserva la fila y el manifest lista ese adjunto como archivo faltante.

### Requirement: Exportación auditada

El sistema SHALL registrar cada exportación exitosa en la auditoría administrativa con el admin, la fecha del servidor, el formato y los conteos por entidad, sin datos de pacientes.

#### Scenario: Exportación registrada

- **WHEN** un admin descarga una exportación
- **THEN** existe un evento `exportar` con su usuario como actor y los conteos del manifest.

#### Scenario: Exportación rechazada no se registra

- **WHEN** la exportación termina en `403` o `422`
- **THEN** no existe evento `exportar` para esa request.

#### Scenario: Dos exportaciones seguidas (borde)

- **WHEN** el mismo admin exporta dos veces
- **THEN** existen dos eventos `exportar` distintos y ambos ZIP son válidos (sin costo ni límite de cantidad).
